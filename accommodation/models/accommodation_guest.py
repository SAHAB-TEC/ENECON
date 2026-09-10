# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccommodationGuest(models.Model):
    """A guest's stay in an accommodation unit. Creating a record here IS the
    check-in event; action_check_out() closes it.
    """
    _name = 'accommodation.guest'
    _description = 'Accommodation Guest / Occupant'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'check_in_date desc'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('hr.employee', string='Guest Name', required=True)
    job_title = fields.Char(related='employee_id.job_title', string='Job Title', readonly=True)
    work_phone = fields.Char(related='employee_id.work_phone', string='Phone Number', readonly=True)

    unit_id = fields.Many2one(
        'accommodation.unit', string='Housing Unit', required=True,
        domain="[('has_vacancy', '=', True)]",
        help="Restricted to units that still have room under their max capacity.")
    location = fields.Char(string='Location')
    project_id = fields.Many2one('project.project', string='Project')

    check_in_date = fields.Datetime(string='Check-in Date', default=fields.Datetime.now, required=True)
    check_out_date = fields.Datetime(string='Expected Check-out Date')

    state = fields.Selection([
        ('checked_in', 'Checked In'),
        ('checked_out', 'Checked Out'),
    ], string='Status', default='checked_in', required=True, tracking=True)

    belonging_ids = fields.One2many(
        'accommodation.guest.belonging', 'guest_id', string='Belongings')

    @api.constrains('unit_id', 'state')
    def _check_unit_capacity(self):
        """Belt-and-braces check mirrored on accommodation.unit: re-validates
        capacity from the guest side so it's caught regardless of which
        model's write triggers first.
        """
        for guest in self.filtered(lambda g: g.state == 'checked_in'):
            unit = guest.unit_id
            current_count = self.search_count([
                ('unit_id', '=', unit.id),
                ('state', '=', 'checked_in'),
            ])
            if unit.max_capacity and current_count > unit.max_capacity:
                raise ValidationError(_(
                    "Cannot check in '%(guest)s': accommodation unit '%(unit)s' "
                    "has reached its maximum capacity of %(max)s guest(s).",
                    guest=guest.employee_id.name, unit=unit.name, max=unit.max_capacity,
                ))

    @api.model_create_multi
    def create(self, vals_list):
        guests = super().create(vals_list)
        for guest in guests:
            if guest.state == 'checked_in':
                guest._create_history_entry()
        guests.mapped('unit_id')._compute_current_guest_count()
        return guests

    def write(self, vals):
        res = super().write(vals)
        if 'state' in vals or 'unit_id' in vals:
            for guest in self:
                if vals.get('state') == 'checked_out':
                    guest._close_history_entry()
            self.mapped('unit_id')._compute_current_guest_count()
        return res

    def unlink(self):
        units = self.mapped('unit_id')
        res = super().unlink()
        units._compute_current_guest_count()
        return res

    def _create_history_entry(self):
        """Uses sudo(): regular check-in users only get read access on the
        audit log itself (see ir.model.access.csv) - the log is written by
        the system on their behalf, not edited by them directly.
        """
        self.ensure_one()
        self.env['accommodation.unit.history'].sudo().create({
            'unit_id': self.unit_id.id,
            'guest_id': self.id,
            'employee_id': self.employee_id.id,
            'location': self.location,
            'project_id': self.project_id.id,
            'check_in_date': self.check_in_date,
            'state': 'in',
        })

    def _close_history_entry(self):
        self.ensure_one()
        history = self.env['accommodation.unit.history'].sudo().search([
            ('guest_id', '=', self.id),
            ('state', '=', 'in'),
        ], limit=1, order='check_in_date desc')
        if history:
            history.sudo().write({
                'check_out_date': self.check_out_date or fields.Datetime.now(),
                'state': 'out',
            })

    def action_check_out(self):
        self.write({
            'state': 'checked_out',
            'check_out_date': fields.Datetime.now(),
        })
