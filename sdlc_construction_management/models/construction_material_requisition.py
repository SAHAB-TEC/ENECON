from odoo import models, fields, api, _
from odoo.exceptions import UserError

class PurchaseLine(models.Model):
    _inherit = 'purchase.order.line'

    product_uom_id = fields.Many2one('uom.uom')

class ConstructionMaterialRequisition(models.Model):
    _name = 'construction.material.requisition'
    _description = 'Material Requisition'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Reference', readonly=True, default='New', copy=False)
    project_id = fields.Many2one('construction.project', string='Project', required=True)
    sub_project_id = fields.Many2one('construction.sub.project', string='Sub Project',
                                      domain="[('project_id', '=', project_id)]")
    work_order_id = fields.Many2one('construction.work.order', string='Work Order',
                                     domain="[('project_id', '=', project_id)]")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    date = fields.Date(string='Date', default=fields.Date.context_today)
    required_date = fields.Date(string='Required Date')
    requested_by = fields.Many2one('hr.employee', string='Requested By')
    approved_by = fields.Many2one('res.users', string='Approved By')
    department_id = fields.Many2one('hr.department', string='Department')
    warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('under_approval', 'Under Approval'),
        ('approved', 'Approved'),
        ('in_progress', 'In Progress'),
        ('ready', 'Ready for Delivery'),
        ('withdrawal', 'Withdrawal'),
        ('done', 'Done'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    line_ids = fields.One2many('construction.material.requisition.line', 'requisition_id',
                                string='Requisition Lines')

    notes = fields.Text(string='Notes')
    rejection_reason = fields.Text(string='Rejection Reason')

    # Purchase / Transfer counts
    purchase_order_count = fields.Integer(compute='_compute_po_count', string='Purchase Orders')
    purchase_order_ids = fields.Many2many('purchase.order', string='Purchase Orders',
                                          compute='_compute_po_count', store=False)
    internal_transfer_count = fields.Integer(compute='_compute_transfer_count', string='Internal Transfers')
    picking_ids = fields.Many2many('stock.picking', string='Internal Transfers',
                                    compute='_compute_transfer_count', store=False)

    total_amount = fields.Float(string='Total Amount', compute='_compute_total', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('construction.material.requisition') or 'New'
        return super().create(vals_list)

    @api.depends('line_ids.amount')
    def _compute_total(self):
        for rec in self:
            rec.total_amount = sum(rec.line_ids.mapped('amount'))

    def _compute_po_count(self):
        for rec in self:
            orders = self.env['purchase.order'].search([
                ('origin', 'like', rec.name),
            ])
            rec.purchase_order_ids = orders
            rec.purchase_order_count = len(orders)

    def _compute_transfer_count(self):
        for rec in self:
            pickings = self.env['stock.picking'].search([
                ('origin', 'like', rec.name),
            ])
            rec.picking_ids = pickings
            rec.internal_transfer_count = len(pickings)

    def action_submit_approval(self):
        self.write({'state': 'under_approval'})

    def action_approve(self):
        self.write({
            'state': 'approved',
            'approved_by': self.env.uid,
        })

    def action_in_progress(self):
        self.write({'state': 'in_progress'})

    def action_ready(self):
        self.write({'state': 'ready'})

    def action_withdrawal(self):
        self.write({'state': 'withdrawal'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_reject(self):
        self.write({'state': 'rejected'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_create_purchase_order(self):
        """Create purchase order from material requisition lines"""
        if not self.line_ids:
            raise UserError(_('Please add requisition lines first.'))

        vendor_lines = {}
        for line in self.line_ids.filtered(lambda l: l.vendor_id):
            if line.vendor_id.id not in vendor_lines:
                vendor_lines[line.vendor_id.id] = []
            vendor_lines[line.vendor_id.id].append(line)

        if not vendor_lines:
            raise UserError(_('Please set vendors on requisition lines.'))

        orders = self.env['purchase.order']
        for vendor_id, lines in vendor_lines.items():
            po = self.env['purchase.order'].create({
                'partner_id': vendor_id,
                'origin': self.name,
                'construction_project_id': self.project_id.id,
            })
            for line in lines:
                self.env['purchase.order.line'].create({
                    'order_id': po.id,
                    'product_id': line.product_id.id,
                    'name': line.description or line.product_id.name,
                    'product_qty': line.quantity,
                    'product_uom_id': line.uom_id.id or line.product_id.uom_id.id,
                    'price_unit': line.unit_price,
                })
            orders |= po

        self.action_in_progress()
        if len(orders) == 1:
            return {
                'name': _('Purchase Order'),
                'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'view_mode': 'form',
                'res_id': orders.id,
            }
        return {
            'name': _('Purchase Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', orders.ids)],
        }

    def action_create_internal_transfer(self):
        """Create internal transfer from material requisition"""
        if not self.warehouse_id:
            raise UserError(_('Please select a warehouse.'))

        picking_type = self.env['stock.picking.type'].search([
            ('warehouse_id', '=', self.warehouse_id.id),
            ('code', '=', 'internal'),
        ], limit=1)

        if not picking_type:
            raise UserError(_('No internal transfer type found for the selected warehouse.'))

        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'origin': self.name,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': picking_type.default_location_dest_id.id,
        })

        for line in self.line_ids:
            self.env['stock.move'].create({
                'name': line.description or line.product_id.name,
                'picking_id': picking.id,
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity,
                'product_uom': line.uom_id.id or line.product_id.uom_id.id,
                'location_id': picking_type.default_location_src_id.id,
                'location_dest_id': picking_type.default_location_dest_id.id,
            })

        return {
            'name': _('Internal Transfer'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': picking.id,
        }

    def action_view_purchase_orders(self):
        return {
            'name': _('Purchase Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('origin', 'like', self.name)],
        }

    def action_view_transfers(self):
        return {
            'name': _('Internal Transfers'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('origin', 'like', self.name)],
        }


class ConstructionMaterialRequisitionLine(models.Model):
    _name = 'construction.material.requisition.line'
    _description = 'Material Requisition Line'

    requisition_id = fields.Many2one('construction.material.requisition', string='Requisition', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    description = fields.Char(string='Description')
    quantity = fields.Float(string='Quantity', default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    unit_price = fields.Float(string='Unit Price')
    amount = fields.Float(string='Amount', compute='_compute_amount', store=True)
    vendor_id = fields.Many2one('res.partner', string='Vendor', domain="[('supplier_rank', '>', 0)]")
    notes = fields.Char(string='Notes')

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
