# -*- coding: utf-8 -*-
from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    default_location_id = fields.Many2one(
        domain="['|', ('allowed_user_ids', '=', False), ('allowed_user_ids', 'in', uid)]",
    )
