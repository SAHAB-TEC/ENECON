# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HousingPropertyUnit(models.Model):
    _name = 'housing.property.unit'
    _description = 'Housing Property Unit'
    _order = 'name'

    name = fields.Char(string='Unit Name', required=True)
    unit_number = fields.Char(string='Unit Number')
    type_id = fields.Many2one(
        'housing.unit.type', string='Unit Type', ondelete='restrict'
    )

    rooms_count = fields.Integer(string='Number of Rooms')
    bathrooms_count = fields.Integer(string='Number of Bathrooms')
    kitchens_count = fields.Integer(string='Number of Kitchens')
    max_capacity = fields.Integer(string='Max Capacity', default=1)

    status = fields.Selection(
        [
            ('available', 'Available'),
            ('reserved', 'Reserved'),
            ('occupied', 'Occupied'),
        ],
        string='Current Status',
        default='available',
        required=True,
    )

    # Odoo standard kanban color index: 1=red, 3=yellow, 10=green
    color = fields.Integer(string='Kanban Color', compute='_compute_color', store=True)

    # Relations
    allocation_ids = fields.One2many(
        'housing.guest.allocation', 'unit_id', string='Guest Allocations (All)'
    )
    current_allocation_ids = fields.One2many(
        'housing.guest.allocation',
        'unit_id',
        string='Current Occupants',
        domain=[('actual_check_out', '=', False)],
    )

    room_content_ids = fields.One2many(
        'housing.property.content',
        'unit_id',
        string='Room Contents',
        domain=[('content_type', '=', 'room')],
        context={'default_content_type': 'room'},
    )
    bathroom_content_ids = fields.One2many(
        'housing.property.content',
        'unit_id',
        string='Bathroom Contents',
        domain=[('content_type', '=', 'bathroom')],
        context={'default_content_type': 'bathroom'},
    )
    kitchen_content_ids = fields.One2many(
        'housing.property.content',
        'unit_id',
        string='Kitchen Contents',
        domain=[('content_type', '=', 'kitchen')],
        context={'default_content_type': 'kitchen'},
    )

    # Smart button counters
    current_occupant_count = fields.Integer(
        string='Current Occupants', compute='_compute_counts'
    )
    history_log_count = fields.Integer(
        string='History Log', compute='_compute_counts'
    )
    belongings_count = fields.Integer(
        string='Belongings', compute='_compute_counts'
    )
    has_available_capacity = fields.Boolean(
        string='Has Available Capacity', compute='_compute_counts', store=True
    )

    @api.depends('status')
    def _compute_color(self):
        color_map = {'occupied': 1, 'reserved': 3, 'available': 10}
        for rec in self:
            rec.color = color_map.get(rec.status, 0)

    @api.depends('allocation_ids.actual_check_out', 'allocation_ids.belonging_ids', 'max_capacity')
    def _compute_counts(self):
        for rec in self:
            current = rec.allocation_ids.filtered(lambda a: not a.actual_check_out)
            rec.current_occupant_count = len(current)
            rec.history_log_count = len(rec.allocation_ids)
            rec.belongings_count = sum(len(a.belonging_ids) for a in current)
            rec.has_available_capacity = rec.max_capacity > len(current)

    # Smart button actions
    def action_view_current_occupants(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'housing_accommodation.action_housing_guest_allocation'
        )
        action['domain'] = [('unit_id', '=', self.id), ('actual_check_out', '=', False)]
        action['context'] = {'default_unit_id': self.id}
        action['name'] = 'Current Occupants'
        return action

    def action_view_history(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'housing_accommodation.action_housing_guest_allocation'
        )
        action['domain'] = [('unit_id', '=', self.id)]
        action['context'] = {'default_unit_id': self.id}
        action['name'] = 'History Log'
        return action

    def action_view_belongings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Belongings',
            'res_model': 'housing.guest.belonging',
            'view_mode': 'list,form',
            'domain': [
                ('allocation_id.unit_id', '=', self.id),
                ('allocation_id.actual_check_out', '=', False),
            ],
        }
