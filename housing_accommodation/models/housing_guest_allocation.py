# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HousingGuestAllocation(models.Model):
    _name = 'housing.guest.allocation'
    _description = 'Guest / Occupant Allocation'
    _order = 'check_in desc'

    employee_id = fields.Many2one(
        'hr.employee', string='Guest Name', required=True, ondelete='restrict'
    )
    job_title = fields.Char(
        related='employee_id.job_title', string='Job Title', store=True, readonly=True
    )
    job_id = fields.Many2one(
        'hr.job', related='employee_id.job_id', string='Job ID', store=True, readonly=True
    )
    phone = fields.Char(
        related='employee_id.work_phone', string='Phone Number', store=True, readonly=True
    )

    unit_id = fields.Many2one(
        'housing.property.unit', string='Property Unit', required=True, ondelete='restrict'
    )
    unit_number = fields.Char(
        related='unit_id.unit_number', string='Unit Number', store=True, readonly=True
    )
    unit_status = fields.Selection(
        related='unit_id.status', string='Unit Status', store=True, readonly=True
    )

    check_in = fields.Datetime(
        string='Check-in Date', required=True, default=fields.Datetime.now
    )
    expected_check_out = fields.Datetime(string='Expected Check-out Date')
    actual_check_out = fields.Datetime(string='Actual Check-out Date')

    belonging_ids = fields.One2many(
        'housing.guest.belonging', 'allocation_id', string='Guest Belongings'
    )

    is_current = fields.Boolean(
        string='Currently Checked-in', compute='_compute_is_current', store=True
    )

    @api.depends('actual_check_out')
    def _compute_is_current(self):
        for rec in self:
            rec.is_current = not rec.actual_check_out

    @api.constrains('unit_id', 'actual_check_out')
    def _check_max_capacity(self):
        for rec in self:
            if rec.unit_id and not rec.actual_check_out:
                other_current = self.search_count([
                    ('unit_id', '=', rec.unit_id.id),
                    ('actual_check_out', '=', False),
                    ('id', '!=', rec.id),
                ])
                total = other_current + 1
                if rec.unit_id.max_capacity and total > rec.unit_id.max_capacity:
                    raise ValidationError(_(
                        "Cannot check in '%(guest)s'. Unit '%(unit)s' has a maximum "
                        "capacity of %(cap)s occupant(s) and already has %(count)s "
                        "currently checked in.",
                        guest=rec.employee_id.name,
                        unit=rec.unit_id.name,
                        cap=rec.unit_id.max_capacity,
                        count=other_current,
                    ))

    @api.constrains('check_in', 'expected_check_out', 'actual_check_out')
    def _check_dates(self):
        for rec in self:
            if rec.check_in and rec.expected_check_out and rec.expected_check_out < rec.check_in:
                raise ValidationError(_(
                    "Expected check-out date cannot be earlier than the check-in date."
                ))
            if rec.check_in and rec.actual_check_out and rec.actual_check_out < rec.check_in:
                raise ValidationError(_(
                    "Actual check-out date cannot be earlier than the check-in date."
                ))
