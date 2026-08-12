# -*- coding: utf-8 -*-
from odoo import fields, models


class RgbContractPaymentCondition(models.Model):
    _name = 'rgb.contract.payment.condition'
    _description = 'Contract Payment Condition'
    _order = 'sequence, id'

    contract_id = fields.Many2one(
        'rgb.contract',
        string='Contract',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Description', required=True)
    percentage = fields.Float(string='Percentage (%)', digits=(16, 4))
    currency_id = fields.Many2one('res.currency', string='Currency')
    amount_currency = fields.Monetary(
        string='Amount (Currency)',
        currency_field='currency_id',
    )
    amount_lyd = fields.Monetary(
        string='Amount (LYD)',
        currency_field='lyd_currency_id',
    )
    lyd_currency_id = fields.Many2one(
        'res.currency',
        related='contract_id.lyd_currency_id',
        store=True,
    )
    payment_method = fields.Selection(
        selection=[
            ('cash', 'Cash / Wire'),
            ('lc', 'Letter of Credit'),
            ('bank_guarantee', 'Bank Guarantee'),
            ('monthly_invoice', 'Monthly Progress Invoice'),
            ('advance', 'Advance Payment'),
            ('other', 'Other'),
        ],
        string='Payment Method',
    )
    notes = fields.Text()
