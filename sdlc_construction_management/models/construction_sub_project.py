from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ConstructionSubProject(models.Model):
    _name = 'construction.sub.project'
    _description = 'Construction Sub Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Sub Project Name', required=True, tracking=True)
    reference = fields.Char(string='Reference', readonly=True, default='New', copy=False)
    project_id = fields.Many2one('construction.project', string='Project', required=True, tracking=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse',
                                   related='project_id.warehouse_id', store=True, readonly=False)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    # Duration
    date_start = fields.Date(string='Start Date', tracking=True)
    date_end = fields.Date(string='End Date', tracking=True)

    # Status
    state = fields.Selection([
        ('planning', 'Planning'),
        ('procurement', 'Procurement'),
        ('construction', 'Construction'),
        ('handover', 'Handover'),
    ], string='Status', default='planning', tracking=True)

    # Customer
    partner_id = fields.Many2one('res.partner', string='Customer')

    # BOQ
    boq_ids = fields.One2many('construction.boq', 'sub_project_id', string='Bill of Quantities')

    # Engineers
    engineer_ids = fields.Many2many('hr.employee', string='Engineers')

    # Documents
    document_ids = fields.One2many('construction.sub.project.document', 'sub_project_id', string='Documents')

    # Insurance
    insurance_company = fields.Char(string='Insurance Company')
    insurance_policy_no = fields.Char(string='Policy Number')
    insurance_start_date = fields.Date(string='Insurance Start Date')
    insurance_end_date = fields.Date(string='Insurance End Date')
    insurance_amount = fields.Float(string='Insurance Amount')
    insurance_document = fields.Binary(string='Insurance Document', attachment=True)
    insurance_document_name = fields.Char(string='Insurance File Name')

    # Extra Expenses
    extra_expense_ids = fields.One2many('construction.extra.expense', 'sub_project_id', string='Extra Expenses')

    # Tasks
    task_ids = fields.One2many('construction.task', 'sub_project_id', string='Tasks')

    # Phases
    phase_ids = fields.One2many('construction.phase', 'sub_project_id', string='Project Phases (WBS)')

    # Work Orders
    work_order_ids = fields.One2many('construction.work.order', 'sub_project_id', string='Work Orders')

    # Material Requisitions
    material_requisition_ids = fields.One2many('construction.material.requisition', 'sub_project_id',
                                                string='Material Requisitions')

    # Budget Lines
    budget_line_ids = fields.One2many('construction.budget.line', 'sub_project_id', string='Budget Lines')

    # Progress Billing
    progress_billing_ids = fields.One2many('construction.progress.billing', 'sub_project_id',
                                            string='Progress Billings')

    # Computed counts
    task_count = fields.Integer(compute='_compute_counts', string='Tasks')
    phase_count = fields.Integer(compute='_compute_counts', string='Phases')
    work_order_count = fields.Integer(compute='_compute_counts', string='Work Orders')
    mreq_count = fields.Integer(compute='_compute_counts', string='Material Requisitions')
    boq_count = fields.Integer(compute='_compute_counts', string='BOQ')
    billing_count = fields.Integer(compute='_compute_counts', string='Progress Billings')
    expense_count = fields.Integer(compute='_compute_counts', string='Extra Expenses')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'New') == 'New':
                vals['reference'] = self.env['ir.sequence'].next_by_code('construction.sub.project') or 'New'
        return super().create(vals_list)

    def _compute_counts(self):
        for rec in self:
            rec.task_count = len(rec.task_ids)
            rec.phase_count = len(rec.phase_ids)
            rec.work_order_count = len(rec.work_order_ids)
            rec.mreq_count = len(rec.material_requisition_ids)
            rec.boq_count = len(rec.boq_ids)
            rec.billing_count = len(rec.progress_billing_ids)
            rec.expense_count = len(rec.extra_expense_ids)

    def action_planning(self):
        self.write({'state': 'planning'})

    def action_procurement(self):
        self.write({'state': 'procurement'})

    def action_construction(self):
        self.write({'state': 'construction'})

    def action_handover(self):
        self.write({'state': 'handover'})

    def action_view_tasks(self):
        return {
            'name': _('Tasks'),
            'type': 'ir.actions.act_window',
            'res_model': 'construction.task',
            'view_mode': 'list,form',
            'domain': [('sub_project_id', '=', self.id)],
            'context': {'default_sub_project_id': self.id, 'default_project_id': self.project_id.id},
        }

    def action_view_phases(self):
        return {
            'name': _('Phases (WBS)'),
            'type': 'ir.actions.act_window',
            'res_model': 'construction.phase',
            'view_mode': 'list,form',
            'domain': [('sub_project_id', '=', self.id)],
            'context': {'default_sub_project_id': self.id, 'default_project_id': self.project_id.id},
        }

    def action_view_work_orders(self):
        return {
            'name': _('Work Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'construction.work.order',
            'view_mode': 'list,form',
            'domain': [('sub_project_id', '=', self.id)],
            'context': {'default_sub_project_id': self.id, 'default_project_id': self.project_id.id},
        }

    def action_view_mreq(self):
        return {
            'name': _('Material Requisitions'),
            'type': 'ir.actions.act_window',
            'res_model': 'construction.material.requisition',
            'view_mode': 'list,form',
            'domain': [('sub_project_id', '=', self.id)],
            'context': {'default_sub_project_id': self.id, 'default_project_id': self.project_id.id},
        }

    def action_view_boq(self):
        return {
            'name': _('Bill of Quantities'),
            'type': 'ir.actions.act_window',
            'res_model': 'construction.boq',
            'view_mode': 'list,form',
            'domain': [('sub_project_id', '=', self.id)],
            'context': {'default_sub_project_id': self.id, 'default_project_id': self.project_id.id},
        }

    def action_view_billings(self):
        return {
            'name': _('Progress Billings'),
            'type': 'ir.actions.act_window',
            'res_model': 'construction.progress.billing',
            'view_mode': 'list,form',
            'domain': [('sub_project_id', '=', self.id)],
            'context': {'default_sub_project_id': self.id, 'default_project_id': self.project_id.id},
        }

    def action_view_expenses(self):
        return {
            'name': _('Extra Expenses'),
            'type': 'ir.actions.act_window',
            'res_model': 'construction.extra.expense',
            'view_mode': 'list,form',
            'domain': [('sub_project_id', '=', self.id)],
            'context': {'default_sub_project_id': self.id, 'default_project_id': self.project_id.id},
        }

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_start > rec.date_end:
                raise ValidationError(_('End Date must be after Start Date.'))


class ConstructionSubProjectDocument(models.Model):
    _name = 'construction.sub.project.document'
    _description = 'Sub Project Document'

    sub_project_id = fields.Many2one('construction.sub.project', string='Sub Project', ondelete='cascade')
    name = fields.Char(string='Document Name', required=True)
    document = fields.Binary(string='Document', attachment=True, required=True)
    document_name = fields.Char(string='File Name')
    doc_type = fields.Selection([
        ('drawing', 'Drawing'),
        ('specification', 'Specification'),
        ('contract', 'Contract'),
        ('report', 'Report'),
        ('other', 'Other'),
    ], string='Type', default='other')
    notes = fields.Text(string='Notes')
