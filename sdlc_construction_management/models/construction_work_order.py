from odoo import models, fields, api, _


class ConstructionWorkOrder(models.Model):
    _name = 'construction.work.order'
    _description = 'Construction Work Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Reference', readonly=True, default='New', copy=False)
    project_id = fields.Many2one('construction.project', string='Project', required=True)
    sub_project_id = fields.Many2one('construction.sub.project', string='Sub Project',
                                      domain="[('project_id', '=', project_id)]")
    phase_id = fields.Many2one('construction.phase', string='Phase',
                                domain="[('project_id', '=', project_id)]")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    date = fields.Date(string='Date', default=fields.Date.context_today)
    date_start = fields.Date(string='Start Date')
    date_end = fields.Date(string='End Date')

    responsible_id = fields.Many2one('hr.employee', string='Responsible')
    description = fields.Text(string='Description')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    # Cost Lines
    material_line_ids = fields.One2many('construction.work.order.line', 'work_order_id',
                                         string='Material Lines', domain=[('line_type', '=', 'material')])
    equipment_line_ids = fields.One2many('construction.work.order.line', 'work_order_id',
                                          string='Equipment Lines', domain=[('line_type', '=', 'equipment')])
    labour_line_ids = fields.One2many('construction.work.order.line', 'work_order_id',
                                       string='Labour Lines', domain=[('line_type', '=', 'labour')])
    overhead_line_ids = fields.One2many('construction.work.order.line', 'work_order_id',
                                         string='Overhead Lines', domain=[('line_type', '=', 'overhead')])

    # Totals
    material_total = fields.Float(string='Material Total', compute='_compute_totals', store=True)
    equipment_total = fields.Float(string='Equipment Total', compute='_compute_totals', store=True)
    labour_total = fields.Float(string='Labour Total', compute='_compute_totals', store=True)
    overhead_total = fields.Float(string='Overhead Total', compute='_compute_totals', store=True)
    total_amount = fields.Float(string='Total Amount', compute='_compute_totals', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('construction.work.order') or 'New'
        return super().create(vals_list)

    @api.depends('material_line_ids.amount', 'equipment_line_ids.amount',
                 'labour_line_ids.amount', 'overhead_line_ids.amount')
    def _compute_totals(self):
        for rec in self:
            all_lines = self.env['construction.work.order.line'].search([('work_order_id', '=', rec.id)])
            rec.material_total = sum(l.amount for l in all_lines if l.line_type == 'material')
            rec.equipment_total = sum(l.amount for l in all_lines if l.line_type == 'equipment')
            rec.labour_total = sum(l.amount for l in all_lines if l.line_type == 'labour')
            rec.overhead_total = sum(l.amount for l in all_lines if l.line_type == 'overhead')
            rec.total_amount = rec.material_total + rec.equipment_total + rec.labour_total + rec.overhead_total

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})


class ConstructionWorkOrderLine(models.Model):
    _name = 'construction.work.order.line'
    _description = 'Work Order Line'

    work_order_id = fields.Many2one('construction.work.order', string='Work Order', ondelete='cascade')
    line_type = fields.Selection([
        ('material', 'Material'),
        ('equipment', 'Equipment'),
        ('labour', 'Labour'),
        ('overhead', 'Overhead'),
    ], string='Type', required=True, default='material')

    product_id = fields.Many2one('product.product', string='Product')
    description = fields.Char(string='Description')
    quantity = fields.Float(string='Quantity', default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    unit_price = fields.Float(string='Unit Price')
    amount = fields.Float(string='Amount', compute='_compute_amount', store=True)

    @api.depends('quantity', 'unit_price')
    def _compute_amount(self):
        for line in self:
            line.amount = line.quantity * line.unit_price

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.description = self.product_id.name
            self.uom_id = self.product_id.uom_id.id
            self.unit_price = self.product_id.standard_price
