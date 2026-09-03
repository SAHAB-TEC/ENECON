from odoo import models, fields, api, _


class ConstructionBudget(models.Model):
    _name = 'construction.budget'
    _description = 'Construction Budget'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Reference', readonly=True, default='New', copy=False)
    project_id = fields.Many2one('construction.project', string='Project', required=True)
    sub_project_id = fields.Many2one('construction.sub.project', string='Sub Project',
                                      domain="[('project_id', '=', project_id)]")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    date = fields.Date(string='Date', default=fields.Date.context_today)
    notes = fields.Text(string='Notes')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('approved', 'Approved'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    line_ids = fields.One2many('construction.budget.line', 'budget_id', string='Budget Lines')

    total_planned = fields.Float(string='Total Planned', compute='_compute_totals', store=True)
    total_actual = fields.Float(string='Total Actual', compute='_compute_totals', store=True)
    total_variance = fields.Float(string='Total Variance', compute='_compute_totals', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('construction.budget') or 'New'
        return super().create(vals_list)

    @api.depends('line_ids.planned_amount', 'line_ids.actual_amount')
    def _compute_totals(self):
        for rec in self:
            rec.total_planned = sum(rec.line_ids.mapped('planned_amount'))
            rec.total_actual = sum(rec.line_ids.mapped('actual_amount'))
            rec.total_variance = rec.total_planned - rec.total_actual

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})


class ConstructionBudgetLine(models.Model):
    _name = 'construction.budget.line'
    _description = 'Construction Budget Line'

    budget_id = fields.Many2one('construction.budget', string='Budget', ondelete='cascade')
    project_id = fields.Many2one('construction.project', string='Project',
                                  related='budget_id.project_id', store=True)
    sub_project_id = fields.Many2one('construction.sub.project', string='Sub Project',
                                      related='budget_id.sub_project_id', store=True)

    work_type_id = fields.Many2one('construction.work.type', string='Work Type')
    product_id = fields.Many2one('product.product', string='Product')
    description = fields.Char(string='Description')
    planned_amount = fields.Float(string='Planned Amount')
    actual_amount = fields.Float(string='Actual Amount')
    variance = fields.Float(string='Variance', compute='_compute_variance', store=True)
    progress = fields.Float(string='Progress (%)', compute='_compute_progress', store=True)

    @api.depends('planned_amount', 'actual_amount')
    def _compute_variance(self):
        for line in self:
            line.variance = line.planned_amount - line.actual_amount

    @api.depends('planned_amount', 'actual_amount')
    def _compute_progress(self):
        for line in self:
            if line.planned_amount:
                line.progress = (line.actual_amount / line.planned_amount) * 100
            else:
                line.progress = 0.0
