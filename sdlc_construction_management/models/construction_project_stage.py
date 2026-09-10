from odoo import fields, models, _
from odoo.exceptions import UserError


class ConstructionProjectStage(models.Model):
    _name = 'construction.project.stage'
    _description = 'Construction Project Stage'
    _order = 'sequence, id'

    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=50)
    name = fields.Char(required=True, translate=True)
    mail_template_id = fields.Many2one(
        'mail.template',
        string='Email Template',
        domain=[('model', '=', 'construction.project')],
        help="If set, an email is sent when the project reaches this stage.",
    )
    fold = fields.Boolean(
        string='Folded in Kanban',
        help="Folded stages are considered closed in the Kanban view.",
    )
    company_id = fields.Many2one('res.company', string='Company')

    def copy_data(self, default=None):
        vals_list = super().copy_data(default=default)
        return [dict(vals, name=_("%s (copy)", stage.name)) for stage, vals in zip(self, vals_list)]

    def write(self, vals):
        if vals.get('company_id'):
            project = self.env['construction.project'].search([
                ('stage_id', 'in', self.ids),
                ('company_id', '!=', vals['company_id']),
            ], limit=1)
            if project:
                company = self.env['res.company'].browse(vals['company_id'])
                raise UserError(_(
                    "You cannot switch this stage's company to %(company_name)s because it "
                    "includes projects linked to %(project_company_name)s.",
                    company_name=company.name,
                    project_company_name=project.company_id.name or _("no company"),
                ))
        if 'active' in vals and not vals['active']:
            self.env['construction.project'].search([('stage_id', 'in', self.ids)]).write({'active': False})
        return super().write(vals)
