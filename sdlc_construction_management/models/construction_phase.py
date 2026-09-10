from odoo import models, fields, api, _


class ConstructionPhase(models.Model):
    _name = 'construction.phase'
    _description = 'Construction Phase / Work Breakdown Structure'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'

    name = fields.Char(string='Reference', readonly=True, default='New', copy=False)
    title = fields.Char(string='Phase Title', required=True)
    project_id = fields.Many2one('construction.project', string='Project', required=True)
    sub_project_id = fields.Many2one('construction.sub.project', string='Sub Project',
                                      domain="[('project_id', '=', project_id)]")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    sequence = fields.Integer(string='Sequence', default=10)

    # Hierarchy
    parent_id = fields.Many2one('construction.phase', string='Parent Phase')
    child_ids = fields.One2many('construction.phase', 'parent_id', string='Child Phases')

    # Duration
    date_start = fields.Date(string='Start Date')
    date_end = fields.Date(string='End Date')

    # Costing
    material_cost = fields.Float(string='Material Cost')
    equipment_cost = fields.Float(string='Equipment Cost')
    labour_cost = fields.Float(string='Labour Cost')
    overhead_cost = fields.Float(string='Overhead Cost')
    total_cost = fields.Float(string='Total Cost', compute='_compute_total_cost', store=True)

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('on_hold', 'On Hold'),
    ], string='Status', default='draft', tracking=True)

    # Work Orders
    work_order_ids = fields.One2many('construction.work.order', 'phase_id', string='Work Orders')
    work_order_count = fields.Integer(compute='_compute_work_order_count', string='Work Orders')

    # Phase Entries
    entry_ids = fields.One2many('construction.phase.entry', 'phase_id', string='Phase Entries')

    description = fields.Text(string='Description')
    progress = fields.Float(string='Progress (%)', compute='_compute_progress', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('construction.phase') or 'New'
        return super().create(vals_list)

    @api.depends('material_cost', 'equipment_cost', 'labour_cost', 'overhead_cost')
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost = rec.material_cost + rec.equipment_cost + rec.labour_cost + rec.overhead_cost

    @api.depends('work_order_ids.state', 'child_ids.progress')
    def _compute_progress(self):
        for rec in self:
            if rec.child_ids:
                child_progress = rec.child_ids.mapped('progress')
                rec.progress = sum(child_progress) / len(child_progress) if child_progress else 0.0
            else:
                valid_orders = rec.work_order_ids.filtered(lambda wo: wo.state not in ('draft', 'cancelled'))
                if valid_orders:
                    done_count = len(valid_orders.filtered(lambda wo: wo.state == 'done'))
                    rec.progress = (done_count / len(valid_orders)) * 100
                else:
                    rec.progress = 0.0

    def _compute_work_order_count(self):
        for rec in self:
            rec.work_order_count = len(rec.work_order_ids)

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_complete(self):
        self.write({'state': 'completed'})

    def action_hold(self):
        self.write({'state': 'on_hold'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_view_work_orders(self):
        return {
            'name': _('Work Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'construction.work.order',
            'view_mode': 'list,form',
            'domain': [('phase_id', '=', self.id)],
            'context': {
                'default_phase_id': self.id,
                'default_project_id': self.project_id.id,
                'default_sub_project_id': self.sub_project_id.id,
            },
        }


class ConstructionPhaseEntry(models.Model):
    _name = 'construction.phase.entry'
    _description = 'Phase Entry'

    phase_id = fields.Many2one('construction.phase', string='Phase', ondelete='cascade')
    date = fields.Date(string='Date', default=fields.Date.context_today)
    description = fields.Text(string='Description')
    entry_type = fields.Selection([
        ('material', 'Material'),
        ('equipment', 'Equipment'),
        ('labour', 'Labour'),
        ('overhead', 'Overhead'),
        ('other', 'Other'),
    ], string='Type', default='material')
    product_id = fields.Many2one('product.product', string='Product')
    quantity = fields.Float(string='Quantity', default=1.0)
    unit_price = fields.Float(string='Unit Price')
    amount = fields.Float(string='Amount', compute='_compute_amount', store=True)

    @api.depends('quantity', 'unit_price')
    def _compute_amount(self):
        for entry in self:
            entry.amount = entry.quantity * entry.unit_price
