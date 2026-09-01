# -*- coding: utf-8 -*-
from odoo import fields, models


class HousingUnitType(models.Model):
    _name = 'housing.unit.type'
    _description = 'Housing Unit Type'
    _order = 'name'

    name = fields.Char(string='Type Name', required=True)
    description = fields.Text(string='Description')

    unit_ids = fields.One2many(
        'housing.property.unit', 'type_id', string='Property Units'
    )
    unit_count = fields.Integer(
        string='Units', compute='_compute_unit_count'
    )

    def _compute_unit_count(self):
        for rec in self:
            rec.unit_count = len(rec.unit_ids)

    def action_view_units(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Property Units',
            'res_model': 'housing.property.unit',
            'view_mode': 'kanban,list,form',
            'domain': [('type_id', '=', self.id)],
            'context': {'default_type_id': self.id},
        }

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'A unit type with this name already exists.'),
    ]
