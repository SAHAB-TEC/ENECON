# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccommodationRepair(models.Model):
    """Maintenance / repair ticket raised against an accommodation unit and,
    optionally, one specific inventory item inside that unit.

    NOTE: the ir.sequence record with code 'accommodation.repair' (for the
    REPAIR/2026/0001-style serials) is data-layer content delivered in a
    later step, not in this models pass.
    """
    _name = 'accommodation.repair'
    _description = 'Accommodation Maintenance / Repair Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'request_date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Serial Number', required=True, copy=False,
        readonly=True, default=lambda self: _('New'))
    reason = fields.Text(string='Reason for Maintenance', required=True)
    faulty_party_id = fields.Many2one('hr.employee', string='Responsible / Faulty Party')
    unit_id = fields.Many2one('accommodation.unit', string='Housing Unit', required=True)
    item_id = fields.Many2one(
        'accommodation.unit.content', string='Target Item for Repair',
        domain="[('unit_id', '=', unit_id)]",
        help="Filtered to the furniture/contents belonging to the selected unit.")
    request_date = fields.Date(
        string='Request Date', default=fields.Date.context_today, required=True)
    notes = fields.Text(string='Notes')
    location = fields.Char(string='Location')
    project_id = fields.Many2one('project.project', string='Project')

    state = fields.Selection([
        ('draft', 'New'),
        ('in_progress', 'In Progress'),
        ('done', 'Completed'),
    ], string='Status', default='draft', required=True, tracking=True, copy=False)
    completed_by = fields.Many2one('res.users', string='Approved By', readonly=True, copy=False)
    completed_date = fields.Datetime(string='Completion Date', readonly=True, copy=False)

    @api.onchange('unit_id')
    def _onchange_unit_id(self):
        if self.item_id and self.item_id.unit_id != self.unit_id:
            self.item_id = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'accommodation.repair') or _('New')
        return super().create(vals_list)

    def action_start_progress(self):
        self.write({'state': 'in_progress'})

    def action_mark_completed(self):
        """Restricted server-side (not just via a view 'groups' attribute) so
        the rule holds under RPC/automation too.
        """
        if not self.env.user.has_group('accommodation.group_approve_repair'):
            raise UserError(_(
                "You are not allowed to close maintenance requests. This "
                "action is restricted to approved maintenance supervisors."))
        self.write({
            'state': 'done',
            'completed_by': self.env.user.id,
            'completed_date': fields.Datetime.now(),
        })

    def action_reset_draft(self):
        self.write({'state': 'draft', 'completed_by': False, 'completed_date': False})
