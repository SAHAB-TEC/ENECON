# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccommodationUnit(models.Model):
    _name = 'accommodation.unit'
    _description = 'Accommodation Unit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'
    _rec_name = 'name'

    name = fields.Char(string='Unit Name', required=True)
    unit_number = fields.Char(string='Unit Number')
    structure_type = fields.Selection([
        ('fixed', 'Fixed Unit'),
        ('mobile', 'Mobile Unit'),
    ], string='Unit Nature', default='fixed', required=True)
    type_id = fields.Many2one('accommodation.type', string='Unit Type')

    # Stored + computed + inverse: auto-forces 'occupied' the instant a guest
    # checks in, but stays freely editable between vacant/reserved while the
    # unit is empty (used for Kanban card colour: red/yellow/green).
    status = fields.Selection([
        ('vacant', 'Vacant'),
        ('reserved', 'Reserved'),
        ('occupied', 'Occupied'),
    ], string='Status', compute='_compute_status', inverse='_inverse_status',
        store=True, default='vacant', tracking=True)

    room_count = fields.Integer(string='Number of Rooms', default=0)
    bathroom_count = fields.Integer(string='Number of Bathrooms', default=0)
    kitchen_count = fields.Integer(string='Number of Kitchens', default=0)

    max_capacity = fields.Integer(string='Max Guest Capacity', default=1, required=True)
    current_guest_count = fields.Integer(
        string='Current Guest Count', compute='_compute_current_guest_count', store=True)
    has_vacancy = fields.Boolean(
        string='Has Vacancy', compute='_compute_has_vacancy', store=True,
        help="Technical field used to filter the Guest form's Housing Unit dropdown "
             "to units that still have room under their max capacity.")

    guest_ids = fields.One2many('accommodation.guest', 'unit_id', string='Guests')
    content_ids = fields.One2many('accommodation.unit.content', 'unit_id', string='Unit Contents')
    history_ids = fields.One2many('accommodation.unit.history', 'unit_id', string='History Log')

    history_count = fields.Integer(string='History Count', compute='_compute_smart_button_counts')
    belonging_count = fields.Integer(string='Belonging Count', compute='_compute_smart_button_counts')

    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('max_capacity_positive', 'CHECK(max_capacity >= 0)',
         'Max guest capacity cannot be negative.'),
    ]

    @api.depends('guest_ids.state')
    def _compute_current_guest_count(self):
        for unit in self:
            unit.current_guest_count = len(
                unit.guest_ids.filtered(lambda g: g.state == 'checked_in'))

    @api.depends('current_guest_count', 'max_capacity')
    def _compute_has_vacancy(self):
        for unit in self:
            unit.has_vacancy = unit.current_guest_count < unit.max_capacity

    @api.depends('current_guest_count')
    def _compute_status(self):
        for unit in self:
            if unit.current_guest_count > 0:
                unit.status = 'occupied'
            elif not unit.status or unit.status == 'occupied':
                # Guests just left, or record is new: fall back to vacant.
                # A manually-set 'reserved' status is left untouched here.
                unit.status = 'vacant'

    def _inverse_status(self):
        """Lets a user freely toggle vacant <-> reserved from the form/kanban,
        but refuses to overwrite 'occupied' while guests are still checked in.
        """
        for unit in self:
            if unit.current_guest_count > 0 and unit.status != 'occupied':
                raise ValidationError(_(
                    "Unit '%(unit)s' currently has %(count)s guest(s) checked in "
                    "and cannot be manually set to a different status until they "
                    "check out.",
                    unit=unit.name, count=unit.current_guest_count,
                ))

    @api.depends('history_ids', 'guest_ids.belonging_ids')
    def _compute_smart_button_counts(self):
        for unit in self:
            unit.history_count = len(unit.history_ids)
            unit.belonging_count = sum(len(g.belonging_ids) for g in unit.guest_ids)

    @api.constrains('max_capacity', 'current_guest_count')
    def _check_capacity_not_exceeded(self):
        for unit in self:
            if unit.current_guest_count > unit.max_capacity:
                raise ValidationError(_(
                    "Accommodation unit '%(unit)s' exceeds its maximum capacity: "
                    "%(count)s guest(s) checked in versus a maximum of %(max)s.",
                    unit=unit.name, count=unit.current_guest_count, max=unit.max_capacity,
                ))

    # ------------------------------------------------------------------
    # Smart button actions
    # NOTE: the XML ids referenced below (action_accommodation_guest,
    # action_accommodation_unit_history, action_accommodation_guest_belonging)
    # are defined in the views/actions step, not yet delivered.
    # ------------------------------------------------------------------
    def action_view_current_guests(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'accommodation.action_accommodation_guest')
        action.update({
            'domain': [('unit_id', '=', self.id), ('state', '=', 'checked_in')],
            'context': {'default_unit_id': self.id},
        })
        return action

    def action_view_history(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'accommodation.action_accommodation_unit_history')
        action.update({
            'domain': [('unit_id', '=', self.id)],
            'context': {'default_unit_id': self.id},
        })
        return action

    def action_view_belongings(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'accommodation.action_accommodation_guest_belonging')
        action.update({
            'domain': [('guest_id.unit_id', '=', self.id)],
        })
        return action
