# -*- coding: utf-8 -*-
from odoo import fields, models


class HousingPropertyContent(models.Model):
    _name = 'housing.property.content'
    _description = 'Housing Property Unit Content (Room / Bathroom / Kitchen)'
    _order = 'content_type, name'

    unit_id = fields.Many2one(
        'housing.property.unit', string='Property Unit',
        required=True, ondelete='cascade'
    )
    content_type = fields.Selection(
        [
            ('room', 'Room'),
            ('bathroom', 'Bathroom'),
            ('kitchen', 'Kitchen'),
        ],
        string='Content Type', required=True,
    )
    name = fields.Char(string='Item / Furniture Name', required=True)
    quantity = fields.Integer(string='Quantity', default=1)
    condition = fields.Selection(
        [
            ('new', 'New'),
            ('good', 'Good'),
            ('damaged', 'Damaged'),
        ],
        string='Condition', default='good',
    )
    notes = fields.Text(string='Notes')
