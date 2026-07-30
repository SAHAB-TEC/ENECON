# -*- coding: utf-8 -*-
from odoo import fields, models


class StockLocation(models.Model):
    _inherit = "stock.location"

    allowed_user_ids = fields.Many2many(
        "res.users",
        "stock_location_allowed_user_rel",
        "location_id",
        "user_id",
        string="Allowed Users",
        domain=[("share", "=", False)],
        help="Users who can select this location on material requisitions. "
             "Leave empty to allow all users.",
    )
    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Analytic Account",
        help="Analytic account applied to stock valuation / transfer journal entries "
             "when this location is used as source or destination.",
        company_dependent=False,
        check_company=True,
    )
