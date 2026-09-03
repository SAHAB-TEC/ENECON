# -*- coding: utf-8 -*-
from odoo import fields, models


class AccommodationUnitHistory(models.Model):
    """Immutable audit trail of check-in / check-out movements per unit.

    Rows are written and closed exclusively from accommodation.guest
    (create/write); this model itself exposes no user-facing create button -
    it is a log, not a workflow.
    """
    _name = 'accommodation.unit.history'
    _description = 'Accommodation Unit Occupancy History Log'
    _order = 'check_in_date desc'

    unit_id = fields.Many2one(
        'accommodation.unit', string='Accommodation Unit',
        required=True, ondelete='cascade', index=True)
    guest_id = fields.Many2one(
        'accommodation.guest', string='Guest Record', ondelete='set null')
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    location = fields.Char(string='Site / Location')
    project_id = fields.Many2one('project.project', string='Project')
    check_in_date = fields.Datetime(string='Check-in Date', required=True)
    check_out_date = fields.Datetime(string='Check-out Date')
    state = fields.Selection([
        ('in', 'Checked In'),
        ('out', 'Checked Out'),
    ], string='Status', default='in', required=True)
