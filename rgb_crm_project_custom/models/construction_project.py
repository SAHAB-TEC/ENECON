# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError


class ConstructionProject(models.Model):
    _inherit = 'construction.project'

    rgb_opportunity_id = fields.Many2one(
        'crm.lead',
        string='Source Opportunity',
        index=True,
        copy=False,
        ondelete='set null',
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        tracking=True,
    )

    def action_rgb_view_source_opportunity(self):
        self.ensure_one()
        if not self.rgb_opportunity_id:
            raise UserError(_('No CRM opportunity is linked to this construction project.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Opportunity'),
            'res_model': 'crm.lead',
            'view_mode': 'form',
            'res_id': self.rgb_opportunity_id.id,
            'target': 'current',
        }
