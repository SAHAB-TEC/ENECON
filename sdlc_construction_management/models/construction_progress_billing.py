from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ConstructionProgressBilling(models.Model):
    _name = 'construction.progress.billing'
    _description = 'Progress Billing'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Milestone Name', required=True)
    reference = fields.Char(string='Reference', readonly=True, default='New', copy=False)
    project_id = fields.Many2one('construction.project', string='Project', required=True)
    sub_project_id = fields.Many2one('construction.sub.project', string='Sub Project',
                                      domain="[('project_id', '=', project_id)]")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    date = fields.Date(string='Date', default=fields.Date.context_today)

    # Customer
    partner_id = fields.Many2one('res.partner', string='Customer')
    invoice_type = fields.Selection([
        ('type_wise', 'Type Wise Invoice'),
        ('single', 'Single Invoice'),
    ], string='Invoice Type', default='single')

    # Phase & Work Order
    phase_id = fields.Many2one('construction.phase', string='Phase',
                                domain="[('project_id', '=', project_id)]")
    work_order_id = fields.Many2one('construction.work.order', string='Work Order',
                                     domain="[('project_id', '=', project_id)]")

    # Include options
    include_material = fields.Boolean(string='Material Lines', default=True)
    include_equipment = fields.Boolean(string='Equipment Lines', default=True)
    include_labour = fields.Boolean(string='Labour Lines', default=True)
    include_overhead = fields.Boolean(string='Overhead Lines', default=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ], string='Status', default='draft', tracking=True)

    # Billing Lines
    material_line_ids = fields.One2many('construction.progress.billing.line', 'billing_id',
                                         string='Material Lines', domain=[('line_type', '=', 'material')])
    equipment_line_ids = fields.One2many('construction.progress.billing.line', 'billing_id',
                                          string='Equipment Lines', domain=[('line_type', '=', 'equipment')])
    labour_line_ids = fields.One2many('construction.progress.billing.line', 'billing_id',
                                       string='Labour Lines', domain=[('line_type', '=', 'labour')])
    overhead_line_ids = fields.One2many('construction.progress.billing.line', 'billing_id',
                                         string='Overhead Lines', domain=[('line_type', '=', 'overhead')])
    other_line_ids = fields.One2many('construction.progress.billing.line', 'billing_id',
                                      string='Other Lines', domain=[('line_type', '=', 'other')])

    # Totals
    material_total = fields.Float(string='Material Total', compute='_compute_totals', store=True)
    equipment_total = fields.Float(string='Equipment Total', compute='_compute_totals', store=True)
    labour_total = fields.Float(string='Labour Total', compute='_compute_totals', store=True)
    overhead_total = fields.Float(string='Overhead Total', compute='_compute_totals', store=True)
    other_total = fields.Float(string='Other Total', compute='_compute_totals', store=True)
    total_amount = fields.Float(string='Total Amount', compute='_compute_totals', store=True)

    # Invoices
    invoice_ids = fields.Many2many('account.move', string='Invoices')
    invoice_count = fields.Integer(compute='_compute_invoice_count', string='Invoices')

    notes = fields.Text(string='Notes')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'New') == 'New':
                vals['reference'] = self.env['ir.sequence'].next_by_code('construction.progress.billing') or 'New'
        return super().create(vals_list)

    @api.depends('material_line_ids.total_amount', 'equipment_line_ids.total_amount',
                 'labour_line_ids.total_amount', 'overhead_line_ids.total_amount',
                 'other_line_ids.total_amount')
    def _compute_totals(self):
        for rec in self:
            all_lines = self.env['construction.progress.billing.line'].search([('billing_id', '=', rec.id)])
            rec.material_total = sum(l.total_amount for l in all_lines if l.line_type == 'material')
            rec.equipment_total = sum(l.total_amount for l in all_lines if l.line_type == 'equipment')
            rec.labour_total = sum(l.total_amount for l in all_lines if l.line_type == 'labour')
            rec.overhead_total = sum(l.total_amount for l in all_lines if l.line_type == 'overhead')
            rec.other_total = sum(l.total_amount for l in all_lines if l.line_type == 'other')
            rec.total_amount = (rec.material_total + rec.equipment_total + rec.labour_total +
                                rec.overhead_total + rec.other_total)

    def _compute_invoice_count(self):
        for rec in self:
            rec.invoice_count = len(rec.invoice_ids)

    def action_load_work_order_lines(self):
        """Load lines from the selected work order"""
        if not self.work_order_id:
            raise UserError(_('Please select a Work Order first.'))

        wo = self.work_order_id
        lines_to_create = []

        if self.include_material:
            for line in wo.material_line_ids:
                lines_to_create.append((0, 0, {
                    'billing_id': self.id,
                    'line_type': 'material',
                    'product_id': line.product_id.id,
                    'description': line.description,
                    'quantity': line.quantity,
                    'uom_id': line.uom_id.id,
                    'unit_price': line.unit_price,
                }))

        if self.include_equipment:
            for line in wo.equipment_line_ids:
                lines_to_create.append((0, 0, {
                    'billing_id': self.id,
                    'line_type': 'equipment',
                    'product_id': line.product_id.id,
                    'description': line.description,
                    'quantity': line.quantity,
                    'uom_id': line.uom_id.id,
                    'unit_price': line.unit_price,
                }))

        if self.include_labour:
            for line in wo.labour_line_ids:
                lines_to_create.append((0, 0, {
                    'billing_id': self.id,
                    'line_type': 'labour',
                    'product_id': line.product_id.id,
                    'description': line.description,
                    'quantity': line.quantity,
                    'uom_id': line.uom_id.id,
                    'unit_price': line.unit_price,
                }))

        if self.include_overhead:
            for line in wo.overhead_line_ids:
                lines_to_create.append((0, 0, {
                    'billing_id': self.id,
                    'line_type': 'overhead',
                    'product_id': line.product_id.id,
                    'description': line.description,
                    'quantity': line.quantity,
                    'uom_id': line.uom_id.id,
                    'unit_price': line.unit_price,
                }))

        if lines_to_create:
            # Clear existing lines before loading new ones
            existing_lines = self.env['construction.progress.billing.line'].search([('billing_id', '=', self.id)])
            existing_lines.unlink()
            # Create new lines
            for line_vals in lines_to_create:
                self.env['construction.progress.billing.line'].create(line_vals[2])

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_complete(self):
        self.write({'state': 'completed'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_create_invoice(self):
        """Create customer invoice from progress billing"""
        if not self.partner_id:
            raise UserError(_('Please select a Customer.'))

        invoice_lines = []
        all_lines = self.env['construction.progress.billing.line'].search([('billing_id', '=', self.id)])
        for line in all_lines:
            invoice_lines.append((0, 0, {
                'name': line.description or line.product_id.name or 'Billing Line',
                'product_id': line.product_id.id if line.product_id else False,
                'quantity': line.quantity,
                'price_unit': line.unit_price,
                'tax_ids': [(6, 0, line.tax_ids.ids)] if line.tax_ids else [],
            }))

        if not invoice_lines:
            raise UserError(_('No billing lines to invoice.'))

        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'invoice_origin': self.reference,
            'invoice_line_ids': invoice_lines,
        })

        self.invoice_ids = [(4, invoice.id)]
        return {
            'name': _('Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
        }

    def action_view_invoices(self):
        return {
            'name': _('Invoices'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.invoice_ids.ids)],
        }


class ConstructionProgressBillingLine(models.Model):
    _name = 'construction.progress.billing.line'
    _description = 'Progress Billing Line'

    billing_id = fields.Many2one('construction.progress.billing', string='Billing', ondelete='cascade')
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
    tax_ids = fields.Many2many('account.tax', string='Taxes')
    tax_amount = fields.Float(string='Tax Amount', compute='_compute_amounts', store=True)
    total_amount = fields.Float(string='Total Amount', compute='_compute_amounts', store=True)

    @api.depends('quantity', 'unit_price', 'tax_ids')
    def _compute_amounts(self):
        for line in self:
            subtotal = line.quantity * line.unit_price
            tax_amount = 0.0
            if line.tax_ids:
                taxes = line.tax_ids.compute_all(line.unit_price, quantity=line.quantity)
                tax_amount = taxes['total_included'] - taxes['total_excluded']
            line.tax_amount = tax_amount
            line.total_amount = subtotal + tax_amount

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.description = self.product_id.name
            self.uom_id = self.product_id.uom_id.id
            self.unit_price = self.product_id.lst_price
