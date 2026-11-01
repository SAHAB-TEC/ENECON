# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.tools.float_utils import float_round


class AccountMove(models.Model):
    _inherit = "account.move"

    # ── Shared PDF blocks (USD / LYD share on Waha & Gulf layouts) ──
    dollar_percentage = fields.Float(
        string="USD %",
        help="Percentage share used on custom invoice PDFs.",
    )
    libya_dinar_percentage = fields.Float(
        string="LYD %",
        help="Percentage share used on custom invoice PDFs.",
    )
    usd_amount = fields.Monetary(
        string="USD Amount",
        compute="_compute_ait_currency_shares",
        currency_field="currency_id",
    )
    lyd_amount = fields.Monetary(
        string="LYD Amount",
        compute="_compute_ait_currency_shares",
        currency_field="currency_id",
    )

    # ── Extra header block on PDF (Akakos / shared layout) ──
    ait_well = fields.Char(string="Well")
    ait_service_to = fields.Char(string="Service To")
    ait_rig = fields.Char(string="Rig")
    ait_field = fields.Char(string="Field")
    ait_work_date = fields.Date(string="Work Date")
    ait_invoice_type = fields.Char(string="Invoice Type")

    # ── Gulf Transport layout totals ──
    ait_transport_subtotal = fields.Monetary(
        string="Transport subtotal",
        compute="_compute_ait_transport_amounts",
        currency_field="currency_id",
    )
    ait_transport_desert_charge = fields.Monetary(
        string="Desert charge 15%",
        compute="_compute_ait_transport_amounts",
        currency_field="currency_id",
    )
    ait_transport_grand_total = fields.Monetary(
        string="Transport grand total",
        compute="_compute_ait_transport_amounts",
        currency_field="currency_id",
    )

    @api.depends("invoice_line_ids.price_total", "invoice_line_ids.display_type", "currency_id")
    def _compute_ait_transport_amounts(self):
        for move in self:
            currency = move.currency_id or move.company_id.currency_id
            rounding = currency.rounding or 0.01
            lines = move.invoice_line_ids.filtered(lambda line: line.display_type == "product")
            subtotal = sum(lines.mapped("price_total"))
            desert = float_round(subtotal * 0.15, precision_rounding=rounding)
            total = float_round(subtotal + desert, precision_rounding=rounding)
            move.ait_transport_subtotal = subtotal
            move.ait_transport_desert_charge = desert
            move.ait_transport_grand_total = total

    @api.depends("amount_total", "dollar_percentage", "libya_dinar_percentage", "currency_id", "date")
    def _compute_ait_currency_shares(self):
        lyd_currency = self.env.ref("base.LYD", raise_if_not_found=False)
        usd_currency = self.env.ref("base.USD", raise_if_not_found=False)
        for move in self:
            move.usd_amount = 0.0
            move.lyd_amount = 0.0
            if not move.amount_total:
                continue
            currency = move.currency_id or move.company_id.currency_id
            if usd_currency and move.dollar_percentage:
                total_usd = currency._convert(
                    move.amount_total,
                    usd_currency,
                    move.company_id,
                    move.date,
                )
                move.usd_amount = total_usd * move.dollar_percentage / 100.0
            if lyd_currency and move.libya_dinar_percentage:
                total_lyd = currency._convert(
                    move.amount_total,
                    lyd_currency,
                    move.company_id,
                    move.date,
                )
                move.lyd_amount = total_lyd * move.libya_dinar_percentage / 100.0

    def _apply_contract_invoice_template_fields(self):
        for move in self:
            contract = move.contract_id
            if not contract:
                continue
            if contract.contract_business_type_id and not move.ait_invoice_type:
                move.ait_invoice_type = contract.contract_business_type_id.name
            if contract.date_start and not move.ait_work_date:
                move.ait_work_date = contract.date_start

    def ait_get_currency_splits_for_report(self, lyd_filter=None):
        """Return payment currency split lines filtered for PDF templates."""
        self.ensure_one()
        splits = self.currency_split_ids
        lyd = self.env.ref("base.LYD", raise_if_not_found=False)
        if not lyd_filter or not lyd:
            return splits
        if lyd_filter == "exclude":
            return splits.filtered(lambda s: s.currency_id != lyd)
        if lyd_filter == "only":
            return splits.filtered(lambda s: s.currency_id == lyd)
        return splits

    def ait_show_legacy_usd_on_report(self, lyd_filter=None):
        if self.currency_split_ids:
            return False
        if lyd_filter == "only":
            return False
        return bool(self.dollar_percentage or self.usd_amount)

    def ait_show_legacy_lyd_on_report(self, lyd_filter=None):
        if self.currency_split_ids:
            return False
        if lyd_filter == "exclude":
            return False
        return bool(self.libya_dinar_percentage or self.lyd_amount)


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    ait_transport_service_date = fields.Date(string="Transport line date")
    ait_transport_payload_type = fields.Char(string="Payload type")
    ait_transport_weight = fields.Float(string="Weight")
    ait_transport_dt_no = fields.Char(
        string="D.T No.",
        help="Delivery ticket number (printed on Gulf Transport layout).",
    )
