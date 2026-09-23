# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ConstructionProject(models.Model):
    _inherit = 'construction.project'

    risk_ids = fields.One2many(
        'rgb.project.risk',
        'project_id',
        string='Risk Register',
    )
    risk_count = fields.Integer(string='Risks', compute='_compute_risk_count')

    @api.depends('risk_ids')
    def _compute_risk_count(self):
        for project in self:
            project.risk_count = len(project.risk_ids)
