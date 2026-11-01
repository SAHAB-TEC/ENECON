# -*- coding: utf-8 -*-
from collections import OrderedDict

from odoo import api, models


class ReportPayableInvoices(models.AbstractModel):
    _name = 'report.account_invoice_templates.report_payable_invoices'
    _description = 'Invoices Ready for Payment PDF Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['account.move'].browse(docids)
        moves = docs.filtered(
            lambda m: m.move_type in ('out_invoice', 'in_invoice') and m.state == 'posted'
        ).sorted(key=lambda m: (m.invoice_date or m.date or '', m.name or '', m.id))

        totals_map = OrderedDict()
        for move in moves:
            currency = move.currency_id
            key = currency.id if currency else 0
            if key not in totals_map:
                totals_map[key] = {
                    'currency': currency,
                    'amount': 0.0,
                }
            totals_map[key]['amount'] += move.amount_residual or 0.0

        return {
            'doc_ids': docids,
            'doc_model': 'account.move',
            'docs': docs,
            'moves': moves,
            'totals': list(totals_map.values()),
            'company': self.env.company,
        }
