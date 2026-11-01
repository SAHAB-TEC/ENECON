# -*- coding: utf-8 -*-
import base64
import io

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_round
from odoo.tools.misc import xlsxwriter


class AitInvoiceSummaryReportWizard(models.TransientModel):
    _name = 'ait.invoice.summary.report.wizard'
    _description = 'Invoice Summary Excel Report'

    date_from = fields.Date(string='From', required=True)
    date_to = fields.Date(string='To', required=True)
    partner_id = fields.Many2one('res.partner', string='Customer')
    ait_rig = fields.Char(string='Rig')
    invoice_ids = fields.Many2many(
        'account.move',
        'ait_invoice_summary_wizard_move_rel',
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
                key=lambda m: (m.invoice_date or fields.Date.today(), m.name or '', m.id)
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
        return self.env['account.move'].search(domain, order='invoice_date, name, id')

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

    def _collect_extra_currencies(self, moves, lyd_currency):
        """Invoice currencies other than LYD (base), for report columns."""
        currencies = self.env['res.currency']
        for move in moves:
            if not move.currency_id:
                continue
            if lyd_currency and move.currency_id == lyd_currency:
                continue
            currencies |= move.currency_id
        return currencies.sorted(key=lambda c: c.name)

    def _currency_header(self, currency):
        labels = {
            'USD': 'قيمة الفاتورة بالدولار\nAmount in USD',
            'EUR': 'قيمة الفاتورة باليورو\nAmount in EUR',
        }
        if currency.name in labels:
            return labels[currency.name]
        return _('قيمة الفاتورة\nAmount in %(currency)s', currency=currency.name)

    def _build_xlsx(self, moves, extra_currencies, lyd_currency):
        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        sheet = workbook.add_worksheet(_('Invoice Summary'))
        sheet.hide_gridlines(2)
        sheet.set_landscape()
        sheet.set_paper(9)  # A4
        sheet.fit_to_pages(1, 0)

        font_name = 'Calibri'
        color_header = '#D9B38C'      # tan/beige header row
        color_serial = '#CFE2F3'      # light blue serial column
        color_total = '#B8CCE4'       # gray-blue total row
        color_rate = '#C00000'        # red exchange rate

        border = {'border': 1, 'border_color': '#000000'}
        thick_border = {
            'top': 2, 'bottom': 2, 'left': 1, 'right': 1,
            'top_color': '#000000', 'bottom_color': '#000000',
            'left_color': '#000000', 'right_color': '#000000',
        }

        title_fmt = workbook.add_format({
            'bold': True, 'font_size': 11, 'font_name': font_name,
            'align': 'center', 'valign': 'vcenter', 'font_color': '#000000',
        })
        subtitle_fmt = workbook.add_format({
            'bold': True, 'font_size': 11, 'font_name': font_name,
            'align': 'center', 'valign': 'vcenter', 'font_color': '#000000',
        })
        filter_fmt = workbook.add_format({
            'font_size': 10, 'font_name': font_name,
            'align': 'center', 'valign': 'vcenter', 'font_color': '#000000',
        })
        header_fmt = workbook.add_format({
            'bold': True, 'font_size': 10, 'font_name': font_name,
            'align': 'center', 'valign': 'vcenter', 'text_wrap': True,
            'bg_color': color_header, 'font_color': '#000000',
            **thick_border,
        })
        seq_fmt = workbook.add_format({
            'font_size': 10, 'font_name': font_name,
            'align': 'center', 'valign': 'vcenter',
            'bg_color': color_serial, **border,
        })
        invoice_fmt = workbook.add_format({
            'font_size': 10, 'font_name': font_name,
            'align': 'center', 'valign': 'vcenter',
            'bg_color': '#FFFFFF', **border,
        })
        money_fmt = workbook.add_format({
            'font_size': 10, 'font_name': font_name,
            'align': 'right', 'valign': 'vcenter',
            'num_format': '#,##0.000', 'bg_color': '#FFFFFF', **border,
        })
        total_empty_fmt = workbook.add_format({
            'bg_color': color_total, **border,
        })
        total_label_fmt = workbook.add_format({
            'bold': True, 'font_size': 10, 'font_name': font_name,
            'align': 'right', 'valign': 'vcenter',
            'bg_color': color_total, **border,
        })
        total_money_fmt = workbook.add_format({
            'bold': True, 'font_size': 10, 'font_name': font_name,
            'align': 'right', 'valign': 'vcenter',
            'num_format': '#,##0.000', 'bg_color': color_total, **border,
        })
        rate_label_fmt = workbook.add_format({
            'bold': True, 'font_size': 10, 'font_name': font_name,
            'align': 'center', 'valign': 'vcenter',
            'bg_color': '#FFFFFF', **border,
        })
        rate_value_fmt = workbook.add_format({
            'bold': True, 'font_size': 10, 'font_name': font_name,
            'align': 'center', 'valign': 'vcenter',
            'num_format': '0.0000', 'font_color': color_rate,
            'border': 2, 'border_color': color_rate,
        })
        footer_fmt = workbook.add_format({
            'font_size': 10, 'font_name': font_name,
            'align': 'right', 'valign': 'vcenter',
        })

        headers = [
            'تسلسل\nSerial No.',
            'رقم الفاتورة\nInvoice No.',
            'قيمة الفاتورة بالدينار الليبي\nAmount in L.D.',
        ]
        headers.extend(self._currency_header(currency) for currency in extra_currencies)

        last_col = max(len(headers) - 1, 3)
        sheet.merge_range(0, 0, 0, last_col,
                          'مرفق لكم كشف بأرقام الفواتير التي تخص الشركة المذكورة أعلاه',
                          title_fmt)
        sheet.set_row(0, 22)

        partner_name = self.partner_id.display_name if self.partner_id else _('All Customers')
        sheet.merge_range(1, 0, 1, last_col, partner_name, subtitle_fmt)
        sheet.set_row(1, 20)

        filter_parts = [
            _('Period: %(date_from)s to %(date_to)s', date_from=self.date_from, date_to=self.date_to),
        ]
        if self.ait_rig:
            filter_parts.append(_('Rig: %s', self.ait_rig))
        sheet.merge_range(2, 0, 2, last_col, ' | '.join(filter_parts), filter_fmt)
        sheet.set_row(2, 18)

        row = 4
        for col, header in enumerate(headers):
            sheet.write(row, col, header, header_fmt)
        sheet.set_row(row, 48)

        totals = {'lyd': 0.0}
        totals.update({currency.id: 0.0 for currency in extra_currencies})

        usd_currency = self.env.ref('base.USD', raise_if_not_found=False)
        seq = 0
        for move in moves:
            seq += 1
            lyd_amount = self._get_invoice_amount_in_currency(move, lyd_currency) if lyd_currency else 0.0
            totals['lyd'] += lyd_amount

            row += 1
            sheet.set_row(row, 18)
            sheet.write(row, 0, seq, seq_fmt)
            sheet.write(row, 1, move.name or '', invoice_fmt)
            sheet.write(row, 2, lyd_amount, money_fmt)

            for col_offset, currency in enumerate(extra_currencies, start=3):
                amount = self._get_invoice_amount_in_currency(move, currency)
                totals[currency.id] += amount
                sheet.write(row, col_offset, amount, money_fmt)

        row += 1
        sheet.set_row(row, 18)
        sheet.write(row, 0, '', total_empty_fmt)
        sheet.write(row, 1, _('Total'), total_label_fmt)
        sheet.write(row, 2, totals['lyd'], total_money_fmt)
        for col_offset, currency in enumerate(extra_currencies, start=3):
            sheet.write(row, col_offset, totals[currency.id], total_money_fmt)

        if usd_currency and usd_currency in extra_currencies and lyd_currency:
            rate_date = self.date_to or fields.Date.context_today(self)
            # Official company rate (LYD per 1 USD), not LYD-split / USD-split.
            exchange_rate = usd_currency._convert(
                1.0, lyd_currency, self.env.company, rate_date,
            )
            rate_row = row + 2
            sheet.set_row(rate_row, 30)
            sheet.write(rate_row, 0, 'سعر الصرف\nExchange Rate', rate_label_fmt)
            sheet.write(rate_row, 1, float_round(exchange_rate, precision_digits=4), rate_value_fmt)

        footer_row = row + 4
        sheet.merge_range(footer_row, 0, footer_row, last_col,
                          'نشكركم علي حسن تعاونكم معنا', footer_fmt)
        sheet.merge_range(
            footer_row + 1, 0, footer_row + 1, last_col,
            '%s - %s' % (self.env.company.name, _('Financial Department')),
            footer_fmt,
        )

        sheet.set_column(0, 0, 16)
        sheet.set_column(1, 1, 26)
        sheet.set_column(2, last_col, 34)

        workbook.close()
        return buffer.getvalue()

    def action_export_xlsx(self):
        self.ensure_one()
        if not self.invoice_ids:
            if self.date_from > self.date_to:
                raise UserError(_('The start date must be before or equal to the end date.'))

        lyd_currency = self.env.ref('base.LYD', raise_if_not_found=False)
        moves = self._get_invoices()
        extra_currencies = self._collect_extra_currencies(moves, lyd_currency)

        content = self._build_xlsx(moves, extra_currencies, lyd_currency)
        filename = 'invoice_summary_%s_%s.xlsx' % (self.date_from, self.date_to)
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
