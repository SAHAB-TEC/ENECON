# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class RgbAccountMoveCurrencySplit(models.Model):
    _name = 'rgb.account.move.currency.split'
    _description = 'Invoice Payment Currency Split'
    _order = 'sequence, id'

    move_id = fields.Many2one(
        'account.move',
        string='Invoice',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
    )
    exchange_rate = fields.Float(
        string='Exchange Rate',
        digits=(16, 6),
        default=1.0,
        help='Manual rate from the contract: LYD per 1 unit of this currency.',
    )
    percentage = fields.Float(
        string='Percentage (%)',
        digits=(16, 4),
        required=True,
    )
    amount = fields.Monetary(
        string='Amount',
        currency_field='currency_id',
        compute='_compute_amount',
    )

    @api.depends(
        'percentage',
        'currency_id',
        'exchange_rate',
        'move_id.amount_total',
        'move_id.currency_id',
        'move_id.invoice_date',
        'move_id.date',
        'move_id.company_id',
        'move_id.contract_manual_exchange_rate',
    )
    def _compute_amount(self):
        lyd = self.env.ref('base.LYD', raise_if_not_found=False)
        for line in self:
            line.amount = 0.0
            move = line.move_id
            if not move or not move.amount_total or not move.currency_id or not line.currency_id:
                continue

            # Convert invoice total to LYD using manual rates, then to split currency.
            total_lyd = move._get_amount_total_lyd_manual()
            share_lyd = total_lyd * (line.percentage or 0.0) / 100.0

            if lyd and line.currency_id == lyd:
                line.amount = share_lyd
            elif line.exchange_rate:
                line.amount = share_lyd / line.exchange_rate
            else:
                conv_date = move.invoice_date or move.date or fields.Date.context_today(line)
                converted_total = move.currency_id._convert(
                    move.amount_total,
                    line.currency_id,
                    move.company_id,
                    conv_date,
                )
                line.amount = converted_total * (line.percentage or 0.0) / 100.0

    @api.constrains('currency_id', 'move_id')
    def _check_unique_currency(self):
        for line in self:
            if not line.move_id or not line.currency_id:
                continue
            duplicate = self.search([
                ('move_id', '=', line.move_id.id),
                ('currency_id', '=', line.currency_id.id),
                ('id', '!=', line.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'Currency %(currency)s is already used in the payment split for this invoice.',
                    currency=line.currency_id.display_name,
                ))

    @api.constrains('exchange_rate')
    def _check_exchange_rate(self):
        for line in self.filtered(lambda l: l.exchange_rate is not False):
            if line.exchange_rate <= 0:
                raise ValidationError(_('Exchange rate must be greater than zero.'))
