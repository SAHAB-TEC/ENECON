# -*- coding: utf-8 -*-
from odoo import fields, models


class RgbRiskImpact(models.Model):
    _name = 'rgb.risk.impact'
    _description = 'Risk Impact Assessment'
    _order = 'sequence, name, id'

    name = fields.Char(string='Impact', required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text(string='Description')
