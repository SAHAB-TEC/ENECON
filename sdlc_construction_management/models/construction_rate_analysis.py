from odoo import models, fields, api, _


class ConstructionRateAnalysis(models.Model):
    _name = 'construction.rate.analysis'
    _description = 'Rate Analysis'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Reference', readonly=True, default='New', copy=False)
    title = fields.Char(string='Title', required=True)
    project_id = fields.Many2one('construction.project', string='Project', required=True)
    sub_project_id = fields.Many2one('construction.sub.project', string='Sub Project',
                                      domain="[('project_id', '=', project_id)]")
    date = fields.Date(string='Date', default=fields.Date.context_today)

    work_type_id = fields.Many2one('construction.work.type', string='Work Type')
    work_sub_type_id = fields.Many2one('construction.work.sub.type', string='Work Sub Type',
                                        domain="[('work_type_id', '=', work_type_id)]")
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    per_unit = fields.Char(string='Per Unit')

    # Lines
    material_line_ids = fields.One2many('construction.rate.analysis.line', 'rate_analysis_id',
                                         string='Material Lines', domain=[('line_type', '=', 'material')])
    equipment_line_ids = fields.One2many('construction.rate.analysis.line', 'rate_analysis_id',
                                          string='Equipment Lines', domain=[('line_type', '=', 'equipment')])
    labour_line_ids = fields.One2many('construction.rate.analysis.line', 'rate_analysis_id',
                                       string='Labour Lines', domain=[('line_type', '=', 'labour')])
    overhead_line_ids = fields.One2many('construction.rate.analysis.line', 'rate_analysis_id',
                                         string='Overhead Lines', domain=[('line_type', '=', 'overhead')])
    other_line_ids = fields.One2many('construction.rate.analysis.line', 'rate_analysis_id',
                                      string='Other Lines', domain=[('line_type', '=', 'other')])

    # Totals
    material_total = fields.Float(string='Material Total', compute='_compute_totals', store=True)
    equipment_total = fields.Float(string='Equipment Total', compute='_compute_totals', store=True)
    labour_total = fields.Float(string='Labour Total', compute='_compute_totals', store=True)
    overhead_total = fields.Float(string='Overhead Total', compute='_compute_totals', store=True)
    other_total = fields.Float(string='Other Total', compute='_compute_totals', store=True)
    total_amount = fields.Float(string='Total Amount', compute='_compute_totals', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('construction.rate.analysis') or 'New'
        return super().create(vals_list)

    @api.depends('material_line_ids.amount', 'equipment_line_ids.amount',
                 'labour_line_ids.amount', 'overhead_line_ids.amount', 'other_line_ids.amount')
    def _compute_totals(self):
        for rec in self:
            all_lines = self.env['construction.rate.analysis.line'].search([('rate_analysis_id', '=', rec.id)])
            rec.material_total = sum(l.amount for l in all_lines if l.line_type == 'material')
            rec.equipment_total = sum(l.amount for l in all_lines if l.line_type == 'equipment')
            rec.labour_total = sum(l.amount for l in all_lines if l.line_type == 'labour')
            rec.overhead_total = sum(l.amount for l in all_lines if l.line_type == 'overhead')
            rec.other_total = sum(l.amount for l in all_lines if l.line_type == 'other')
            rec.total_amount = rec.material_total + rec.equipment_total + rec.labour_total + rec.overhead_total + rec.other_total


class ConstructionRateAnalysisLine(models.Model):
    _name = 'construction.rate.analysis.line'
    _description = 'Rate Analysis Line'

    rate_analysis_id = fields.Many2one('construction.rate.analysis', string='Rate Analysis', ondelete='cascade')
    line_type = fields.Selection([
        ('material', 'Material'),
        ('equipment', 'Equipment'),
        ('labour', 'Labour'),
        ('overhead', 'Overhead'),
        ('other', 'Other'),
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
