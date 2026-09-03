# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    construction_project_id = fields.Many2one(
        'construction.project',
        string='Construction Project',
        copy=False,
        help='Construction project created from this opportunity.',
    )
    rgb_allow_duplicate_construction_project = fields.Boolean(
        string='Allow Another Construction Project',
        default=False,
        help='Allow creating another construction project from this opportunity.',
    )

    def action_rgb_create_construction_project_from_opportunity(self):
        self.ensure_one()
        if not self.env.user.has_group(
            'rgb_crm_project_custom.group_rgb_create_construction_project_from_crm'
        ):
            raise UserError(_('You are not allowed to create a construction project from CRM.'))
        if self.type != 'opportunity':
            raise UserError(_('You can only create a construction project from an opportunity.'))
        if self.construction_project_id and not self.rgb_allow_duplicate_construction_project:
            raise UserError(
                _('A construction project is already linked. '
                  'Enable "Allow Another Construction Project" to create another one.')
            )

        construction_vals = {
            'name': self.name or self.partner_id.display_name or _('New Construction Project'),
            'partner_id': self.partner_id.id if self.partner_id else False,
            'company_id': self.company_id.id or self.env.company.id,
            'rgb_opportunity_id': self.id,
            'email': self.email_from,
            'phone': self.phone,
            'mobile': self.mobile,
        }
        if self.street or self.city or self.country_id:
            construction_vals.update({
                'street': self.street,
                'street2': self.street2,
                'city': self.city,
                'zip': self.zip,
                'state_id': self.state_id.id if self.state_id else False,
                'country_id': self.country_id.id if self.country_id else False,
            })

        construction_project = self.env['construction.project'].create(construction_vals)
        self.construction_project_id = construction_project.id
        self.message_post(
            body=_('Construction project %s created from this opportunity.')
            % construction_project._get_html_link(),
        )
        return {
            'type': 'ir.actions.act_window',
            'name': _('Construction Project'),
            'res_model': 'construction.project',
            'view_mode': 'form',
            'res_id': construction_project.id,
            'target': 'current',
        }

    def action_rgb_view_construction_project(self):
        self.ensure_one()
        if not self.construction_project_id:
            raise UserError(_('No construction project is linked to this opportunity.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Construction Project'),
            'res_model': 'construction.project',
            'view_mode': 'form',
            'res_id': self.construction_project_id.id,
            'target': 'current',
        }
