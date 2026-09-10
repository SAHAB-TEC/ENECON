# -*- coding: utf-8 -*-
from odoo import fields, models


class AccommodationGuestBelonging(models.Model):
    """Personal item / tool / equipment a guest brought in upon check-in."""
    _name = 'accommodation.guest.belonging'
    _description = 'Guest Personal Belonging'
    _order = 'guest_id, sequence'

    sequence = fields.Integer(default=10)
    guest_id = fields.Many2one(
        'accommodation.guest', string='Guest', required=True, ondelete='cascade')
    name = fields.Char(string='Item Description', required=True)
    quantity = fields.Integer(string='Quantity', default=1)
    notes = fields.Char(string='Notes')
