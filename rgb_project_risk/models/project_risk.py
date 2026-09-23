# -*- coding: utf-8 -*-
from odoo import fields, models


class RgbProjectRisk(models.Model):
    _name = 'rgb.project.risk'
    _description = 'Project Risk'
    _order = 'sequence, id'

    project_id = fields.Many2one(
        'construction.project',
        string='Project',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Risk Name', required=True)
    probability_id = fields.Many2one(
        'rgb.risk.probability',
        string='Probability Assessment',
        required=True,
        ondelete='restrict',
        domain="[('active', '=', True)]",
    )
    impact_id = fields.Many2one(
        'rgb.risk.impact',
        string='Impact Assessment',
        required=True,
        ondelete='restrict',
        domain="[('active', '=', True)]",
    )
    response_plan = fields.Text(string='Response Plans')
    stakeholder_ids = fields.Many2many(
        'res.partner',
        'rgb_project_risk_stakeholder_rel',
        'risk_id',
        'partner_id',
        string='Stakeholders',
    )
    user_ids = fields.Many2many(
        'res.users',
        'rgb_project_risk_user_rel',
        'risk_id',
        'user_id',
        string='Users',
    )
    expected_delay_days = fields.Integer(string='Expected Delay (Days)')
    company_id = fields.Many2one(
        related='project_id.company_id',
        store=True,
        readonly=True,
    )
