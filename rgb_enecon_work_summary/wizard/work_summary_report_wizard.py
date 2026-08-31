from dateutil.relativedelta import relativedelta

from odoo import fields, models, _
from odoo.exceptions import ValidationError


class EneconWorkSummaryReportWizard(models.TransientModel):
    _name = 'rgb.enecon.work.summary.report.wizard'
    _description = 'ENECON Work Summary Report Wizard'

    def _default_date_from(self):
        today = fields.Date.context_today(self)
        return today.replace(day=1)

    def _default_date_to(self):
        today = fields.Date.context_today(self)
        return today.replace(day=1) + relativedelta(months=1, days=-1)

    project_id = fields.Many2one(
        'construction.project', string='Project', required=True, ondelete='cascade',
    )
    date_from = fields.Date(string='Date From', required=True, default=_default_date_from)
    date_to = fields.Date(string='Date To', required=True, default=_default_date_to)
    approved_only = fields.Boolean(
        string='Approved Entries Only', default=True,
        help='Recommended for the official summary report.',
    )

    def action_print_report(self):
        self.ensure_one()
        if self.date_from > self.date_to:
            raise ValidationError(_('Date From must be before or equal to Date To.'))
        return self.env.ref(
            'rgb_enecon_work_summary.action_report_rgb_enecon_work_summary'
        ).report_action(self)
