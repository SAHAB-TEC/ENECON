# -*- coding: utf-8 -*-
from odoo import fields, models


class RgbContractBusinessType(models.Model):
    _name = 'rgb.contract.business.type'
    _description = 'Contract Business Type'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    description = fields.Text(translate=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            'code_unique',
            'unique(code)',
            'Business type code must be unique.',
        ),
    ]
