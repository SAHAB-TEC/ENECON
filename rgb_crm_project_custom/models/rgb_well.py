# -*- coding: utf-8 -*-
from odoo import fields, models


class RgbWell(models.Model):
    _name = 'rgb.well'
    _description = 'Well'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(translate=True)
    active = fields.Boolean(default=True)
    partner_id = fields.Many2one('res.partner', string='Partner')
