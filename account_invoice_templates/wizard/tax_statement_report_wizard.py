# -*- coding: utf-8 -*-
import base64
import io
from collections import OrderedDict

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_round
from odoo.tools.misc import format_date, xlsxwriter

TAX_RATE_1 = 0.01
TAX_RATE_005 = 0.00005  # 0.005% of the 1% tax amount (not of base LYD)


class AitTaxStatementReportWizard(models.TransientModel):
    _name = 'ait.tax.statement.report.wizard'
    _description = 'Tax Statement Excel Report'

    date_from = fields.Date(string='From', required=True)
    date_to = fields.Date(string='To', required=True)
    partner_id = fields.Many2one('res.partner', string='Customer')
    ait_rig = fields.Char(string='Rig')
    invoice_ids = fields.Many2many(
        'account.move',
        'ait_tax_statement_wizard_move_rel',
        'wizard_id',
        'move_id',
        string='Selected Invoices',
    )
    xlsx_file = fields.Binary(string='Report File', readonly=True)
    xlsx_filename = fields.Char(string='Filename', readonly=True)

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        today = fields.Date.context_today(self)
        vals.setdefault('date_from', today.replace(day=1))
        vals.setdefault('date_to', today)
        return vals

    def _get_invoices(self):
        self.ensure_one()
        if self.invoice_ids:
            moves = self.invoice_ids.filtered(
                lambda m: m.move_type in ('out_invoice', 'in_invoice') and m.state == 'posted'
            )
            if not moves:
                raise UserError(_(
                    'No posted invoices/bills found among the selected records.'
                ))
            return moves.sorted(
                key=lambda m: (
                    m.ait_rig or '',
                    m.invoice_date or fields.Date.today(),
                    m.name or '',
                    m.id,
                )
            )

        domain = [
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', self.date_from),
            ('invoice_date', '<=', self.date_to),
        ]
        if self.partner_id:
            domain.append(('partner_id', '=', self.partner_id.id))
        if self.ait_rig:
            domain.append(('ait_rig', 'ilike', self.ait_rig))
        return self.env['account.move'].search(
            domain, order='ait_rig, invoice_date, name, id',
        )

    @api.model
    def action_export_from_selection(self):
        """Direct Excel download for invoices selected in the list Action menu."""
        active_ids = self.env.context.get('active_ids') or []
        moves = self.env['account.move'].browse(active_ids).filtered(
            lambda m: m.move_type in ('out_invoice', 'in_invoice') and m.state == 'posted'
        )
        if not moves:
            raise UserError(_(
                'Please select at least one posted customer invoice or vendor bill.'
            ))
        dates = moves.filtered('invoice_date').mapped('invoice_date')
        today = fields.Date.context_today(self)
        wizard = self.create({
            'invoice_ids': [(6, 0, moves.ids)],
            'date_from': min(dates) if dates else today,
            'date_to': max(dates) if dates else today,
        })
        return wizard.action_export_xlsx()

    def _conversion_date(self, move):
        return move.invoice_date or move.date or fields.Date.context_today(self)

    def _get_invoice_amount_in_currency(self, move, currency):
        """Full invoice total converted to ``currency`` (ignores payment splits)."""
        total = move.amount_total or 0.0
        if not currency or not move.currency_id:
            return 0.0
        if move.currency_id == currency:
            return total
        return move.currency_id._convert(
            total,
            currency,
            move.company_id,
            self._conversion_date(move),
        )

    def _group_invoices_by_rig(self, moves):
        groups = OrderedDict()
        for move in moves:
            rig = move.ait_rig or _('No Rig')
            groups.setdefault(rig, self.env['account.move'])
            groups[rig] |= move
        return groups

    def _compute_table_rate(self, moves, usd_currency, lyd_currency):
        """Official company rate: LYD per 1 USD (not split-portion ratio)."""
        if not usd_currency or not lyd_currency:
            return 0.0
        rate_date = self.date_to or fields.Date.context_today(self)
        if moves:
            dates = moves.filtered('invoice_date').mapped('invoice_date')
            if dates:
                rate_date = max(dates)
        return usd_currency._convert(
            1.0, lyd_currency, self.env.company, rate_date,
        )

    def _prepare_rig_rows(self, moves, table_rate, lyd_currency):
        usd_currency = self.env.ref('base.USD', raise_if_not_found=False)
        rows = []
        for move in moves:
            if usd_currency:
                usd_amount = float_round(
                    self._get_invoice_amount_in_currency(move, usd_currency),
                    precision_digits=3,
                )
                currency_symbol = usd_currency.symbol or usd_currency.name
            else:
                usd_amount = float_round(move.amount_total or 0.0, precision_digits=3)
                currency_symbol = move.currency_id.symbol or move.currency_id.name or ''

            if lyd_currency:
                lyd_amount = float_round(
                    self._get_invoice_amount_in_currency(move, lyd_currency),
                    precision_digits=3,
                )
            elif table_rate:
                lyd_amount = float_round(usd_amount * table_rate, precision_digits=3)
            else:
                lyd_amount = 0.0

            tax_1 = float_round(lyd_amount * TAX_RATE_1, precision_digits=3)
            tax_005 = float_round(tax_1 * TAX_RATE_005, precision_digits=3)
            tax_total = float_round(tax_1 + tax_005, precision_digits=3)

            rows.append({
                'name': move.name or '',
                'currency_symbol': currency_symbol,
                'foreign_amount': usd_amount,
                'usd_amount': usd_amount,
                'lyd_amount': lyd_amount,
                'tax_1': tax_1,
                'tax_005': tax_005,
                'tax_total': tax_total,
            })
        return rows

    def _build_formats(self, workbook):
        font_name = 'Calibri'
        color_header = '#D9B38C'
        color_rig = '#D9B38C'
        color_total = '#B8CCE4'
        color_tax_total = '#B8CCE4'
        border = {'border': 1, 'border_color': '#000000'}
        thick_border = {
            'top': 2, 'bottom': 2, 'left': 1, 'right': 1,
            'top_color': '#000000', 'bottom_color': '#000000',
            'left_color': '#000000', 'right_color': '#000000',
        }

        return {
            'letter_right': workbook.add_format({
                'font_size': 10, 'font_name': font_name, 'align': 'right', 'valign': 'vcenter',
            }),
            'letter_center': workbook.add_format({
                'bold': True, 'font_size': 11, 'font_name': font_name,
                'align': 'center', 'valign': 'vcenter',
            }),
            'table_title': workbook.add_format({
                'bold': True, 'font_size': 10, 'font_name': font_name,
                'align': 'center', 'valign': 'vcenter',
                'bg_color': color_header, **border,
            }),
            'header': workbook.add_format({
                'bold': True, 'font_size': 9, 'font_name': font_name,
                'align': 'center', 'valign': 'vcenter', 'text_wrap': True,
                'bg_color': color_header, **thick_border,
            }),
            'rig': workbook.add_format({
                'bold': True, 'font_size': 10, 'font_name': font_name,
                'align': 'center', 'valign': 'vcenter', 'text_wrap': True,
                'bg_color': color_rig, **border,
            }),
            'text': workbook.add_format({
                'font_size': 10, 'font_name': font_name,
                'align': 'center', 'valign': 'vcenter', **border,
            }),
            'money': workbook.add_format({
                'font_size': 10, 'font_name': font_name,
                'align': 'right', 'valign': 'vcenter',
                'num_format': '#,##0.000', **border,
            }),
            'money_lyd': workbook.add_format({
                'font_size': 10, 'font_name': font_name,
                'align': 'right', 'valign': 'vcenter',
                'num_format': '#,##0.000', **border,
            }),
            'tax_total': workbook.add_format({
                'font_size': 10, 'font_name': font_name,
                'align': 'right', 'valign': 'vcenter',
                'num_format': '#,##0.000', 'bg_color': '#FFFFFF', **border,
            }),
            'total_label': workbook.add_format({
                'bold': True, 'font_size': 10, 'font_name': font_name,
                'align': 'right', 'valign': 'vcenter',
                'bg_color': color_total, **border,
            }),
            'total_money': workbook.add_format({
                'bold': True, 'font_size': 10, 'font_name': font_name,
                'align': 'right', 'valign': 'vcenter',
                'num_format': '#,##0.000', 'bg_color': color_total, **border,
            }),
            'total_lyd': workbook.add_format({
                'bold': True, 'font_size': 10, 'font_name': font_name,
                'align': 'right', 'valign': 'vcenter',
                'num_format': '#,##0.000', 'bg_color': color_total, **border,
            }),
            'total_tax': workbook.add_format({
                'bold': True, 'font_size': 10, 'font_name': font_name,
                'align': 'right', 'valign': 'vcenter',
                'num_format': '#,##0.000', 'bg_color': color_tax_total, **border,
            }),
            'footer': workbook.add_format({
                'font_size': 10, 'font_name': font_name, 'align': 'right', 'valign': 'vcenter',
            }),
        }

    def _period_label(self):
        lang = self.env.user.lang or 'en_US'
        period_from = format_date(self.env, self.date_from, date_format='MMMM yyyy', lang_code=lang)
        period_to = format_date(self.env, self.date_to, date_format='MMMM yyyy', lang_code=lang)
        if period_from == period_to:
            return period_from
        return '%s - %s' % (period_from, period_to)

    def _write_rig_table(self, sheet, row, rig_name, moves, formats, lyd_currency):
        usd_currency = self.env.ref('base.USD', raise_if_not_found=False)
        table_rate = self._compute_table_rate(moves, usd_currency, lyd_currency)
        rows = self._prepare_rig_rows(moves, table_rate, lyd_currency)
        last_col = 7

        period_label = self._period_label()
        title = _('Tax statement for invoices - %(period)s', period=period_label)
        sheet.merge_range(row, 0, row, last_col, title, formats['table_title'])
        sheet.set_row(row, 20)
        row += 1

        rate_header = '%s\n%s' % (
            float_round(table_rate, precision_digits=8),
            _('Invoice Amount in L.D.'),
        )
        headers = [
            _('Rig'),
            _('Invoice No.'),
            '$',
            _('Amount in USD'),
            rate_header,
            '1%',
            '0.005%',
            _('Total'),
        ]
        for col, header in enumerate(headers):
            sheet.write(row, col, header, formats['header'])
        sheet.set_row(row, 42)
        header_row = row
        row += 1

        data_start = row
        totals = {
            'foreign': 0.0, 'usd': 0.0, 'lyd': 0.0,
            'tax_1': 0.0, 'tax_005': 0.0, 'tax_total': 0.0,
        }
        for line in rows:
            sheet.set_row(row, 18)
            sheet.write(row, 1, line['name'], formats['text'])
            sheet.write(row, 2, line['currency_symbol'], formats['text'])
            sheet.write(row, 3, line['foreign_amount'], formats['money'])
            sheet.write(row, 4, line['lyd_amount'], formats['money_lyd'])
            sheet.write(row, 5, line['tax_1'], formats['money_lyd'])
            sheet.write(row, 6, line['tax_005'], formats['money_lyd'])
            sheet.write(row, 7, line['tax_total'], formats['tax_total'])

            totals['foreign'] += line['foreign_amount']
            totals['usd'] += line['usd_amount']
            totals['lyd'] += line['lyd_amount']
            totals['tax_1'] += line['tax_1']
            totals['tax_005'] += line['tax_005']
            totals['tax_total'] += line['tax_total']
            row += 1

        data_end = row - 1
        if data_end >= data_start:
            if data_end > data_start:
                sheet.merge_range(data_start, 0, data_end, 0, rig_name, formats['rig'])
            else:
                sheet.write(data_start, 0, rig_name, formats['rig'])

        sheet.set_row(row, 18)
        sheet.write(row, 0, '', formats['total_label'])
        sheet.write(row, 1, _('Total'), formats['total_label'])
        sheet.write(row, 2, '', formats['total_label'])
        sheet.write(row, 3, totals['foreign'], formats['total_money'])
        sheet.write(row, 4, totals['lyd'], formats['total_lyd'])
        sheet.write(row, 5, totals['tax_1'], formats['total_lyd'])
        sheet.write(row, 6, totals['tax_005'], formats['total_lyd'])
        sheet.write(row, 7, float_round(totals['tax_total'], precision_digits=3), formats['total_tax'])

        return row + 2, header_row

    def _build_xlsx(self, rig_groups, lyd_currency):
        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        sheet = workbook.add_worksheet(_('Tax Statement'))
        sheet.hide_gridlines(2)
        sheet.set_landscape()
        sheet.set_paper(9)
        sheet.fit_to_pages(1, 0)

        formats = self._build_formats(workbook)
        last_col = 7
        row = 0

        report_date = format_date(
            self.env, fields.Date.context_today(self),
            date_format='dd/MMMM/yyyy', lang_code=self.env.user.lang or 'ar_001',
        )
        sheet.merge_range(row, 0, row, last_col, _('Brothers / Benghazi Tax Department'), formats['letter_right'])
        row += 1
        sheet.merge_range(row, 0, row, last_col, self.env.company.name, formats['letter_center'])
        row += 1
        sheet.merge_range(row, 0, row, last_col, report_date, formats['letter_right'])
        row += 1
        sheet.merge_range(
            row, 0, row, last_col,
            _('We kindly ask you to certify these invoices.'),
            formats['letter_right'],
        )
        row += 2

        if self.partner_id:
            sheet.merge_range(row, 0, row, last_col, self.partner_id.display_name, formats['letter_center'])
            row += 1

        filter_parts = [
            _('Period: %(date_from)s to %(date_to)s', date_from=self.date_from, date_to=self.date_to),
        ]
        if self.ait_rig:
            filter_parts.append(_('Rig: %s', self.ait_rig))
        sheet.merge_range(row, 0, row, last_col, ' | '.join(filter_parts), formats['letter_right'])
        row += 2

        if not rig_groups:
            sheet.merge_range(row, 0, row, last_col, _('No invoices found.'), formats['letter_center'])
        else:
            for rig_name, moves in rig_groups.items():
                row, _header_row = self._write_rig_table(
                    sheet, row, rig_name, moves, formats, lyd_currency,
                )

        footer_row = row + 1
        sheet.merge_range(
            footer_row, 0, footer_row, last_col,
            _('We thank you for your kind cooperation with us.'),
            formats['footer'],
        )
        sheet.merge_range(
            footer_row + 1, 0, footer_row + 1, last_col,
            '%s - %s' % (self.env.company.name, _('Financial Department')),
            formats['footer'],
        )

        sheet.set_column(0, 0, 14)
        sheet.set_column(1, 1, 22)
        sheet.set_column(2, 2, 6)
        sheet.set_column(3, 3, 18)
        sheet.set_column(4, 4, 22)
        sheet.set_column(5, 7, 14)

        workbook.close()
        return buffer.getvalue()

    def action_export_xlsx(self):
        self.ensure_one()
        if not self.invoice_ids:
            if self.date_from > self.date_to:
                raise UserError(_('The start date must be before or equal to the end date.'))

        lyd_currency = self.env.ref('base.LYD', raise_if_not_found=False)
        moves = self._get_invoices()
        rig_groups = self._group_invoices_by_rig(moves)

        content = self._build_xlsx(rig_groups, lyd_currency)
        filename = 'tax_statement_%s_%s.xlsx' % (self.date_from, self.date_to)
        self.write({
            'xlsx_file': base64.b64encode(content),
            'xlsx_filename': filename,
        })

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/?model=%s&id=%s&field=xlsx_file&filename_field=xlsx_filename&download=true' % (
                self._name, self.id,
            ),
            'target': 'self',
        }
