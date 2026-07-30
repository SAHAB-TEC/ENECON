# -*- coding: utf-8 -*-
from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    default_location_id = fields.Many2one(
        domain="['|', ('allowed_user_ids', '=', False), ('allowed_user_ids', 'in', uid)]",
    )
