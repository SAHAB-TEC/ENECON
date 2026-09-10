# -*- coding: utf-8 -*-
from odoo import fields, models


class RgbContractInsuranceType(models.Model):
    _name = 'rgb.contract.insurance.type'
    _description = 'Contract Insurance Type'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    description = fields.Text(translate=True)
    applicable_contract_type = fields.Selection(
        selection=[
            ('all', 'All'),
            ('purchase_contract', 'Purchase / Contractor'),
            ('sale_contract', 'Sale / Customer'),
        ],
        string='Applicable Contract Type',
        default='all',
        required=True,
    )
    active = fields.Boolean(default=True)
