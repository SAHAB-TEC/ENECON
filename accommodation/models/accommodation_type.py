# -*- coding: utf-8 -*-
from odoo import fields, models


class AccommodationType(models.Model):
    """Configuration model: housing type catalogue (Apartment, Trailer, Studio...).

    Managed through a simple editable list view in the Configuration menu.
    """
    _name = 'accommodation.type'
    _description = 'Accommodation Unit Type'
    _order = 'name'

    name = fields.Char(string='Type Name', required=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'This accommodation type already exists.'),
    ]
