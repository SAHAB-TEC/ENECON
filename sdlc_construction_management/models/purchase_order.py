# -*- coding: utf-8 -*-
from odoo import fields, models


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    construction_project_id = fields.Many2one(
        'construction.project',
        string='Construction Project',
        index=True,
        copy=False,
        tracking=True,
    )
