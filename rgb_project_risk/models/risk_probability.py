# -*- coding: utf-8 -*-
from odoo import fields, models


class RgbRiskProbability(models.Model):
    _name = 'rgb.risk.probability'
    _description = 'Risk Probability Assessment'
    _order = 'sequence, name, id'

    name = fields.Char(string='Probability', required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text(string='Description')
