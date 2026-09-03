# -*- coding: utf-8 -*-
from odoo import fields, models


class RgbRig(models.Model):
    _name = 'rgb.rig'
    _description = 'Rig'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(translate=True)
    active = fields.Boolean(default=True)
    partner_id = fields.Many2one('res.partner', string='Partner')
    well_id = fields.Many2one('rgb.well', string='Well')
