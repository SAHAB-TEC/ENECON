# -*- coding: utf-8 -*-
import base64
import io

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import format_date, xlsxwriter


class AitPayableInvoicesReportWizard(models.TransientModel):
    _name = 'ait.payable.invoices.report.wizard'
    _description = 'Invoices Ready for Payment Report'

    date_from = fields.Date(string='From', required=True)
    date_to = fields.Date(string='To', required=True)
    partner_id = fields.Many2one('res.partner', string='Partner')
    invoice_ids = fields.Many2many(
        'account.move',
        'ait_payable_invoices_wizard_move_rel',
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
            ('move_type', 'in', ('out_invoice', 'in_invoice')),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ('not_paid', 'partial', 'in_payment')),
            ('amount_residual', '>', 0),
            ('invoice_date', '>=', self.date_from),
            ('invoice_date', '<=', self.date_to),
        ]
        if self.partner_id:
            domain.append(('partner_id', '=', self.partner_id.id))
        return self.env['account.move'].search(domain, order='invoice_date, name, id')

    @api.model
    def _get_moves_from_selection(self):
        active_ids = self.env.context.get('active_ids') or []
        moves = self.env['account.move'].browse(active_ids).filtered(
            lambda m: m.move_type in ('out_invoice', 'in_invoice') and m.state == 'posted'
        )
        if not moves:
            raise UserError(_(
                'Please select at least one posted customer invoice or vendor bill.'
            ))
        return moves

    @api.model
    def action_export_from_selection(self):
        """Direct Excel download for invoices selected in the list Action menu."""
        moves = self._get_moves_from_selection()
        dates = moves.filtered('invoice_date').mapped('invoice_date')
        today = fields.Date.context_today(self)
        wizard = self.create({
            'invoice_ids': [(6, 0, moves.ids)],
            'date_from': min(dates) if dates else today,
            'date_to': max(dates) if dates else today,
        })
        return wizard.action_export_xlsx()

    @api.model
    def action_print_pdf_from_selection(self):
        """Print PDF for invoices selected in the list Action / Print menu."""
        moves = self._get_moves_from_selection()
        return self.env.ref(
            'account_invoice_templates.action_report_payable_invoices'
        ).report_action(moves)

    def action_print_pdf(self):
        self.ensure_one()
        moves = self._get_invoices()
        if not moves:
            raise UserError(_('No invoices found for the selected criteria.'))
        return self.env.ref(
            'account_invoice_templates.action_report_payable_invoices'
        ).report_action(moves)

    def _build_xlsx(self, moves):
        buffer = io.BytesIO()
        workbook = xlsxwriter.Workbook(buffer, {'in_memory': True})
        sheet = workbook.add_worksheet(_('Ready for Payment'))
        sheet.hide_gridlines(2)
        sheet.set_landscape()
        sheet.set_paper(9)
        sheet.fit_to_pages(1, 0)

        font_name = 'Calibri'
        color_header = '#D9B38C'
        color_total = '#B8CCE4'
        border = {'border': 1, 'border_color': '#000000'}

        title_fmt = workbook.add_format({
            'bold': True, 'font_size': 14, 'font_name': font_name,
            'align': 'center', 'valign': 'vcenter',
        })
        subtitle_fmt = workbook.add_format({
            'font_size': 10, 'font_name': font_name,
            'align': 'center', 'valign': 'vcenter',
        })
        header_fmt = workbook.add_format({
            'bold': True, 'font_size': 10, 'font_name': font_name,
            'align': 'center', 'valign': 'vcenter', 'text_wrap': True,
            'bg_color': color_header, **border,
        })
        text_fmt = workbook.add_format({
            'font_size': 10, 'font_name': font_name,
            'align': 'center', 'valign': 'vcenter', **border,
        })
        money_fmt = workbook.add_format({
            'font_size': 10, 'font_name': font_name,
            'align': 'right', 'valign': 'vcenter',
            'num_format': '#,##0.000', **border,
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
        total_empty_fmt = workbook.add_format({
            'bg_color': color_total, **border,
        })
        footer_fmt = workbook.add_format({
            'font_size': 10, 'font_name': font_name,
            'align': 'right', 'valign': 'vcenter',
        })

        last_col = 5
        sheet.merge_range(0, 0, 0, last_col, _('فواتير جاهزة للدفع\nInvoices Ready for Payment'), title_fmt)
        sheet.set_row(0, 32)

        partner_name = self.partner_id.display_name if self.partner_id else _('All Partners')
        sheet.merge_range(1, 0, 1, last_col, partner_name, subtitle_fmt)
        sheet.merge_range(
            2, 0, 2, last_col,
            _('Period: %(date_from)s to %(date_to)s', date_from=self.date_from, date_to=self.date_to),
            subtitle_fmt,
        )

        headers = [
            _('تسلسل\nSerial'),
            _('اسم الفاتورة\nInvoice'),
            _('التاريخ\nDate'),
            _('الشريك\nPartner'),
            _('العملة\nCurrency'),
            _('المبلغ المطلوب\nAmount Due'),
        ]
        row = 4
        for col, header in enumerate(headers):
            sheet.write(row, col, header, header_fmt)
        sheet.set_row(row, 36)

        totals_by_currency = {}
        seq = 0
        lang = self.env.user.lang or 'en_US'
        for move in moves:
            seq += 1
            row += 1
            amount_due = move.amount_residual or 0.0
            currency = move.currency_id
            currency_key = currency.id if currency else 0
            totals_by_currency[currency_key] = totals_by_currency.get(currency_key, 0.0) + amount_due

            sheet.set_row(row, 18)
            sheet.write(row, 0, seq, text_fmt)
            sheet.write(row, 1, move.name or '', text_fmt)
            sheet.write(
                row, 2,
                format_date(self.env, move.invoice_date or move.date, lang_code=lang) if (move.invoice_date or move.date) else '',
                text_fmt,
            )
            sheet.write(row, 3, move.partner_id.display_name or '', text_fmt)
            sheet.write(row, 4, currency.name if currency else '', text_fmt)
            sheet.write(row, 5, amount_due, money_fmt)

        row += 1
        sheet.set_row(row, 18)
        if len(totals_by_currency) == 1:
            sheet.write(row, 0, '', total_empty_fmt)
            sheet.write(row, 1, '', total_empty_fmt)
            sheet.write(row, 2, '', total_empty_fmt)
            sheet.write(row, 3, _('Total'), total_label_fmt)
            currency_id = next(iter(totals_by_currency))
            currency = self.env['res.currency'].browse(currency_id) if currency_id else False
            sheet.write(row, 4, currency.name if currency else '', total_label_fmt)
            sheet.write(row, 5, totals_by_currency[currency_id], total_money_fmt)
        else:
            sheet.merge_range(row, 0, row, 5, _('Total (by currency below)'), total_label_fmt)
            for currency_id, total in sorted(totals_by_currency.items()):
                row += 1
                currency = self.env['res.currency'].browse(currency_id) if currency_id else False
                sheet.write(row, 0, '', total_empty_fmt)
                sheet.write(row, 1, '', total_empty_fmt)
                sheet.write(row, 2, '', total_empty_fmt)
                sheet.write(row, 3, _('Total'), total_label_fmt)
                sheet.write(row, 4, currency.name if currency else '', total_label_fmt)
                sheet.write(row, 5, total, total_money_fmt)

        footer_row = row + 2
        sheet.merge_range(
            footer_row, 0, footer_row, last_col,
            _('نشكركم علي حسن تعاونكم معنا'),
            footer_fmt,
        )
        sheet.merge_range(
            footer_row + 1, 0, footer_row + 1, last_col,
            '%s - %s' % (self.env.company.name, _('Financial Department')),
            footer_fmt,
        )

        sheet.set_column(0, 0, 10)
        sheet.set_column(1, 1, 24)
        sheet.set_column(2, 2, 14)
        sheet.set_column(3, 3, 32)
        sheet.set_column(4, 4, 12)
        sheet.set_column(5, 5, 18)

        workbook.close()
        return buffer.getvalue()

    def action_export_xlsx(self):
        self.ensure_one()
        if not self.invoice_ids:
            if self.date_from > self.date_to:
                raise UserError(_('The start date must be before or equal to the end date.'))

        moves = self._get_invoices()
        if not moves:
            raise UserError(_('No invoices found for the selected criteria.'))

        content = self._build_xlsx(moves)
        filename = 'invoices_ready_for_payment_%s_%s.xlsx' % (self.date_from, self.date_to)
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
