from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ConstructionProject(models.Model):
    _name = 'construction.project'
    _description = 'Construction Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name, id'

    def _default_stage_id(self):
        return self.env['construction.project.stage'].search([], order='sequence, id', limit=1)

    @api.model
    def _assign_default_stages(self):
        """Called on module install/upgrade for projects without a stage."""
        stage = self.env['construction.project.stage'].search([], order='sequence, id', limit=1)
        if stage:
            self.search([('stage_id', '=', False)]).write({'stage_id': stage.id})

    name = fields.Char(string='Project Name', required=True, tracking=True)
    active = fields.Boolean(default=True, copy=False)
    sequence = fields.Integer(default=10)
    color = fields.Integer(string='Color Index')
    reference = fields.Char(string='Reference', readonly=True, default='New', copy=False)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse', tracking=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    # Address
    street = fields.Char(string='Street')
    street2 = fields.Char(string='Suite/Apt')
    city = fields.Char(string='City')
    state_id = fields.Many2one('res.country.state', string='State/Province')
    zip = fields.Char(string='ZIP Code')
    country_id = fields.Many2one('res.country', string='Country')

    # Duration
    date_start = fields.Date(string='Start Date', tracking=True)
    date_end = fields.Date(string='End Date', tracking=True)

    # Location
    longitude = fields.Float(string='Longitude', digits=(16, 6))
    latitude = fields.Float(string='Latitude', digits=(16, 6))

    # Contact
    phone = fields.Char(string='Phone')
    mobile = fields.Char(string='Mobile')
    email = fields.Char(string='Email')

    # Status
    stage_id = fields.Many2one(
        'construction.project.stage',
        string='Stage',
        ondelete='restrict',
        tracking=True,
        index=True,
        copy=False,
        default=_default_stage_id,
        group_expand='_read_group_expand_full',
        domain="[('company_id', 'in', (company_id, False))]",
    )
    state = fields.Selection([
        ('ongoing', 'جاري'),
        ('stopped', 'متوقف'),
        ('suspended', 'معلّق'),
        ('closed', 'مغلق'),
        ('completed', 'مكتمل'),
    ], string='Status', default='ongoing', tracking=True, required=True,
       group_expand='_group_expand_states')

    # Relational
    sub_project_ids = fields.One2many('construction.sub.project', 'project_id', string='Sub Projects')
    image_ids = fields.One2many('construction.project.image', 'project_id', string='Images')
    purchase_order_ids = fields.One2many(
        'purchase.order',
        'construction_project_id',
        string='Purchase Orders',
    )

    # Computed
    sub_project_count = fields.Integer(compute='_compute_counts', string='Sub Projects')
    budget_count = fields.Integer(compute='_compute_counts', string='Budgets')
    work_order_count = fields.Integer(compute='_compute_counts', string='Work Orders')
    mreq_count = fields.Integer(compute='_compute_counts', string='Material Requisitions')
    task_count = fields.Integer(compute='_compute_counts', string='Tasks')
    phase_count = fields.Integer(compute='_compute_counts', string='Phases')
    expense_count = fields.Integer(compute='_compute_counts', string='Expenses')
    purchase_order_count = fields.Integer(compute='_compute_counts', string='Purchases')

    # Permits
    permit_ids = fields.One2many('construction.permit', 'project_id', string='Permits & Approvals')

    @api.model
    def _group_expand_states(self, states, domain):
        return [key for key, _label in self._fields['state'].selection]

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self.stage_id.company_id and self.stage_id.company_id != self.company_id:
            self.stage_id = self.env['construction.project.stage'].search(
                [('company_id', 'in', [self.company_id.id, False])],
                order='sequence asc, id',
                limit=1,
            )

    @api.model_create_multi
    def create(self, vals_list):
        stages = self.env['construction.project.stage'].search([])
        for vals in vals_list:
            if vals.get('reference', 'New') == 'New':
                vals['reference'] = self.env['ir.sequence'].next_by_code('construction.project') or 'New'
            if not vals.get('stage_id'):
                company_id = vals.get('company_id', self.env.company.id)
                stage = stages.filtered(
                    lambda s: s.company_id.id in (False, company_id)
                )[:1]
                if stage:
                    vals['stage_id'] = stage.id
        return super().create(vals_list)

    def write(self, vals):
        company_id = vals.get('company_id')
        if company_id is not None:
            projects_with_wrong_stage = self.filtered(
                lambda p: p.stage_id.company_id and p.stage_id.company_id.id != company_id
            )
            if projects_with_wrong_stage:
                new_stage = self.env['construction.project.stage'].search(
                    [('company_id', 'in', (company_id, False))],
                    order='sequence asc, id',
                    limit=1,
                )
                if new_stage:
                    super(ConstructionProject, projects_with_wrong_stage).write({'stage_id': new_stage.id})
        return super().write(vals)

    def _compute_counts(self):
        PurchaseOrder = self.env['purchase.order']
        for rec in self:
            rec.sub_project_count = self.env['construction.sub.project'].search_count([('project_id', '=', rec.id)])
            rec.budget_count = self.env['construction.budget'].search_count([('project_id', '=', rec.id)])
            rec.work_order_count = self.env['construction.work.order'].search_count([('project_id', '=', rec.id)])
            rec.mreq_count = self.env['construction.material.requisition'].search_count([('project_id', '=', rec.id)])
            rec.task_count = self.env['construction.task'].search_count([('project_id', '=', rec.id)])
            rec.phase_count = self.env['construction.phase'].search_count([('project_id', '=', rec.id)])
            rec.expense_count = self.env['construction.extra.expense'].search_count([('project_id', '=', rec.id)])
            rec.purchase_order_count = PurchaseOrder.search_count([
                ('construction_project_id', '=', rec.id),
            ])

    def action_set_ongoing(self):
        self.write({'state': 'ongoing'})

    def action_set_stopped(self):
        self.write({'state': 'stopped'})

    def action_set_suspended(self):
        self.write({'state': 'suspended'})

    def action_set_closed(self):
        self.write({'state': 'closed'})

    def action_complete(self):
        self.write({'state': 'completed'})

    def action_view_purchase_orders(self):
        self.ensure_one()
        return {
            'name': _('Purchases'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('construction_project_id', '=', self.id)],
            'context': {
                'default_construction_project_id': self.id,
            },
        }

    def action_view_sub_projects(self):
        return {
            'name': _('Sub Projects'),
            'type': 'ir.actions.act_window',
            'res_model': 'construction.sub.project',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_budgets(self):
        return {
            'name': _('Budgets'),
            'type': 'ir.actions.act_window',
            'res_model': 'construction.budget',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_work_orders(self):
        return {
            'name': _('Work Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'construction.work.order',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_mreq(self):
        return {
            'name': _('Material Requisitions'),
            'type': 'ir.actions.act_window',
            'res_model': 'construction.material.requisition',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_tasks(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window'].with_context(active_id=self.id)._for_xml_id(
            'sdlc_construction_management.act_construction_project_2_construction_task_all'
        )
        action['display_name'] = self.name
        return action

    def action_view_phases(self):
        return {
            'name': _('Phases (WBS)'),
            'type': 'ir.actions.act_window',
            'res_model': 'construction.phase',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    def action_view_expenses(self):
        return {
            'name': _('Extra Expenses'),
            'type': 'ir.actions.act_window',
            'res_model': 'construction.extra.expense',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_start > rec.date_end:
                raise ValidationError(_('End Date must be after Start Date.'))


class ConstructionProjectImage(models.Model):
    _name = 'construction.project.image'
    _description = 'Construction Project Image'

    project_id = fields.Many2one('construction.project', string='Project', ondelete='cascade')
    name = fields.Char(string='Description')
    image = fields.Binary(string='Image', attachment=True)


class ConstructionPermit(models.Model):
    _name = 'construction.permit'
    _description = 'Construction Permit & Approval'

    project_id = fields.Many2one('construction.project', string='Project', ondelete='cascade')
    name = fields.Char(string='Permit Name', required=True)
    permit_type = fields.Selection([
        ('building', 'Building Permit'),
        ('environmental', 'Environmental Clearance'),
        ('fire', 'Fire Safety'),
        ('electrical', 'Electrical'),
        ('plumbing', 'Plumbing'),
        ('other', 'Other'),
    ], string='Type', default='building')
    issue_date = fields.Date(string='Issue Date')
    expiry_date = fields.Date(string='Expiry Date')
    issuing_authority = fields.Char(string='Issuing Authority')
    document = fields.Binary(string='Document', attachment=True)
    document_name = fields.Char(string='File Name')
    state = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('expired', 'Expired'),
        ('rejected', 'Rejected'),
    ], string='Status', default='pending')
    notes = fields.Text(string='Notes')
