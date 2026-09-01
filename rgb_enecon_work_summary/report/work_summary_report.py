from collections import defaultdict
from datetime import timedelta

from odoo import models


class EneconWorkSummaryReport(models.AbstractModel):
    _name = 'report.rgb_enecon_work_summary.work_summary_document'
    _description = 'ENECON Work Summary Report'

    def _get_report_values(self, docids, data=None):
        wizard = self.env[
            'rgb.enecon.work.summary.report.wizard'
        ].browse(docids).ensure_one()

        domain = [
            ('project_id', '=', wizard.project_id.id),
            ('date', '>=', wizard.date_from),
            ('date', '<=', wizard.date_to),
        ]
        if wizard.approved_only:
            domain.append(('state', '=', 'approved'))

        entries = self.env['rgb.enecon.work.summary.entry'].search(
            domain, order='date asc, id asc',
        )

        dates = []
        current = wizard.date_from
        while current <= wizard.date_to:
            dates.append(current)
            current += timedelta(days=1)

        material_keys = sorted(
            {
                (line.product_id.id, line.uom_id.id)
                for entry in entries for line in entry.material_line_ids
            },
            key=lambda key: (
                self.env['product.product'].browse(key[0]).display_name or '',
                self.env['uom.uom'].browse(key[1]).name or '',
            ),
        )
        material_columns = [
            {
                'key': key,
                'name': self.env['product.product'].browse(key[0]).display_name,
                'uom': self.env['uom.uom'].browse(key[1]).name,
            }
            for key in material_keys
        ]

        job_ids = sorted(
            {line.job_id.id for entry in entries for line in entry.workforce_line_ids},
            key=lambda rec_id: self.env['hr.job'].browse(rec_id).name or '',
        )
        workforce_columns = [
            {'key': rec_id, 'name': self.env['hr.job'].browse(rec_id).name}
            for rec_id in job_ids
        ]

        transport_ids = sorted(
            {
                line.transport_type_id.id
                for entry in entries for line in entry.transport_line_ids
            },
            key=lambda rec_id: (
                self.env['rgb.enecon.transport.type'].browse(rec_id).name or ''
            ),
        )
        transport_columns = [
            {
                'key': rec_id,
                'name': self.env['rgb.enecon.transport.type'].browse(rec_id).name,
            }
            for rec_id in transport_ids
        ]

        material_values = defaultdict(float)
        workforce_values = defaultdict(int)
        transport_values = defaultdict(int)
        notes_by_date = defaultdict(lambda: {'before': [], 'after': []})

        for entry in entries:
            for line in entry.material_line_ids:
                material_values[
                    (entry.date, line.product_id.id, line.uom_id.id)
                ] += line.quantity
            for line in entry.workforce_line_ids:
                workforce_values[(entry.date, line.job_id.id)] += line.count
            for line in entry.transport_line_ids:
                transport_values[
                    (entry.date, line.transport_type_id.id)
                ] += line.quantity
            if entry.notes_before_transport:
                notes_by_date[entry.date]['before'].append(entry.notes_before_transport)
            if entry.notes_after_transport:
                notes_by_date[entry.date]['after'].append(entry.notes_after_transport)

        material_rows = []
        workforce_rows = []
        transport_rows = []
        for report_date in dates:
            material_rows.append({
                'date': report_date,
                'values': [
                    material_values[(report_date, key[0], key[1])]
                    for key in material_keys
                ],
            })
            workforce_row_values = [
                workforce_values[(report_date, rec_id)] for rec_id in job_ids
            ]
            workforce_rows.append({
                'date': report_date,
                'values': workforce_row_values,
                'total': sum(workforce_row_values),
            })
            transport_rows.append({
                'date': report_date,
                'values': [
                    transport_values[(report_date, rec_id)] for rec_id in transport_ids
                ],
            })

        material_totals = [
            sum(
                material_values[(report_date, key[0], key[1])]
                for report_date in dates
            )
            for key in material_keys
        ]
        workforce_totals = [
            sum(workforce_values[(report_date, rec_id)] for report_date in dates)
            for rec_id in job_ids
        ]
        transport_totals = [
            sum(transport_values[(report_date, rec_id)] for report_date in dates)
            for rec_id in transport_ids
        ]

        notes = [
            {
                'date': report_date,
                'before': '\n'.join(notes_by_date[report_date]['before']),
                'after': '\n'.join(notes_by_date[report_date]['after']),
            }
            for report_date in dates
            if notes_by_date[report_date]['before']
            or notes_by_date[report_date]['after']
        ]

        return {
            'doc_ids': wizard.ids,
            'doc_model': wizard._name,
            'docs': wizard,
            'project': wizard.project_id,
            'entries': entries,
            'material_columns': material_columns,
            'material_rows': material_rows,
            'material_totals': material_totals,
            'workforce_columns': workforce_columns,
            'workforce_rows': workforce_rows,
            'workforce_totals': workforce_totals,
            'workforce_grand_total': sum(workforce_totals),
            'transport_columns': transport_columns,
            'transport_rows': transport_rows,
            'transport_totals': transport_totals,
            'notes_before': [note for note in notes if note['before']],
            'notes_after': [note for note in notes if note['after']],
            'notes': notes,
        }
