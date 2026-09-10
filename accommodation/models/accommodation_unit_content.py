# -*- coding: utf-8 -*-
from odoo import fields, models


class AccommodationUnitContent(models.Model):
    """Furniture / appliance / inventory line belonging to a specific room,
    bathroom or kitchen inside an accommodation unit.

    Also acts as the source list for accommodation.repair's dynamically
    filtered 'Target Item for Repair' field.
    """
    _name = 'accommodation.unit.content'
    _description = 'Accommodation Unit Content / Inventory Item'
    _order = 'unit_id, location_type, sequence'

    sequence = fields.Integer(default=10)
    unit_id = fields.Many2one(
        'accommodation.unit', string='Accommodation Unit',
        required=True, ondelete='cascade', index=True)
    name = fields.Char(string='Item Name', required=True)
    location_type = fields.Selection([
        ('room', 'Room'),
        ('bathroom', 'Bathroom'),
        ('kitchen', 'Kitchen'),
    ], string='Location', required=True, default='room')
    quantity = fields.Integer(string='Quantity', default=1)
    notes = fields.Char(string='Notes')
    active = fields.Boolean(default=True)
