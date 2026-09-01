# -*- coding: utf-8 -*-
from odoo import fields, models


class HousingGuestBelonging(models.Model):
    _name = 'housing.guest.belonging'
    _description = 'Guest Belonging'
    _order = 'name'

    allocation_id = fields.Many2one(
        'housing.guest.allocation', string='Allocation',
        required=True, ondelete='cascade'
    )
    name = fields.Char(string='Item Name', required=True)
    quantity = fields.Integer(string='Qty', default=1)
    condition = fields.Selection(
        [
            ('new', 'New'),
            ('good', 'Good'),
            ('damaged', 'Damaged'),
        ],
        string='Condition', default='good',
    )
    notes = fields.Text(string='Notes')
