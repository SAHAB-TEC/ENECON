from odoo import models, fields, api, _


class ConstructionSubcontract(models.Model):
    _name = 'construction.subcontract'
    _description = 'Construction Subcontracting'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Reference', readonly=True, default='New', copy=False)
    project_id = fields.Many2one('construction.project', string='Project', required=True)
    sub_project_id = fields.Many2one('construction.sub.project', string='Sub Project',
                                      domain="[('project_id', '=', project_id)]")
    partner_id = fields.Many2one('res.partner', string='Subcontractor', required=True,
                                  domain="[('supplier_rank', '>', 0)]")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    date = fields.Date(string='Date', default=fields.Date.context_today)
    date_start = fields.Date(string='Start Date')
    date_end = fields.Date(string='End Date')

    work_description = fields.Text(string='Scope of Work')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    # Lines
    line_ids = fields.One2many('construction.subcontract.line', 'subcontract_id', string='Work Lines')

    # Consume Orders
    consume_order_ids = fields.One2many('construction.consume.order', 'subcontract_id', string='Consume Orders')
    consume_order_count = fields.Integer(compute='_compute_consume_count', string='Consume Orders')

    # RA Billing
    ra_billing_ids = fields.One2many('construction.ra.billing', 'subcontract_id', string='RA Billings')
    ra_billing_count = fields.Integer(compute='_compute_ra_count', string='RA Billings')

    # Totals
    contract_amount = fields.Float(string='Contract Amount', compute='_compute_total', store=True)
    billed_amount = fields.Float(string='Billed Amount', compute='_compute_billed_amount')

    # Work Completion
    completion_certificate = fields.Binary(string='Completion Certificate', attachment=True)
    completion_certificate_name = fields.Char(string='Certificate File Name')
    completion_date = fields.Date(string='Completion Date')
    completion_notes = fields.Text(string='Completion Notes')

    notes = fields.Text(string='Notes')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('construction.subcontract') or 'New'
        return super().create(vals_list)

    @api.depends('line_ids.amount')
    def _compute_total(self):
        for rec in self:
            rec.contract_amount = sum(rec.line_ids.mapped('amount'))

    def _compute_billed_amount(self):
        for rec in self:
            rec.billed_amount = sum(rec.ra_billing_ids.filtered(
                lambda b: b.state == 'approved'
            ).mapped('total_amount'))

    def _compute_consume_count(self):
        for rec in self:
            rec.consume_order_count = len(rec.consume_order_ids)

    def _compute_ra_count(self):
        for rec in self:
            rec.ra_billing_count = len(rec.ra_billing_ids)

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_complete(self):
        self.write({
            'state': 'completed',
            'completion_date': fields.Date.context_today(self),
        })

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_view_consume_orders(self):
        return {
            'name': _('Consume Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'construction.consume.order',
            'view_mode': 'list,form',
            'domain': [('subcontract_id', '=', self.id)],
            'context': {'default_subcontract_id': self.id},
        }

    def action_view_ra_billings(self):
        return {
            'name': _('RA Billings'),
            'type': 'ir.actions.act_window',
            'res_model': 'construction.ra.billing',
            'view_mode': 'list,form',
            'domain': [('subcontract_id', '=', self.id)],
            'context': {'default_subcontract_id': self.id},
        }

    def action_create_bill(self):
        """Create vendor bill from subcontract"""
        invoice = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_id.id,
            'invoice_origin': self.name,
            'invoice_line_ids': [(0, 0, {
                'name': line.description or line.work_description,
                'quantity': line.quantity,
                'price_unit': line.rate,
            }) for line in self.line_ids],
        })
        return {
            'name': _('Vendor Bill'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': invoice.id,
        }


class ConstructionSubcontractLine(models.Model):
    _name = 'construction.subcontract.line'
    _description = 'Subcontract Line'

    subcontract_id = fields.Many2one('construction.subcontract', string='Subcontract', ondelete='cascade')
    work_description = fields.Char(string='Work Description', required=True)
    description = fields.Char(string='Details')
    quantity = fields.Float(string='Quantity', default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    rate = fields.Float(string='Rate')
    amount = fields.Float(string='Amount', compute='_compute_amount', store=True)

    @api.depends('quantity', 'rate')
    def _compute_amount(self):
        for line in self:
            line.amount = line.quantity * line.rate


class ConstructionConsumeOrder(models.Model):
    _name = 'construction.consume.order'
    _description = 'Material Consume Order'
    _inherit = ['mail.thread']
    _order = 'id desc'

    name = fields.Char(string='Reference', readonly=True, default='New', copy=False)
    subcontract_id = fields.Many2one('construction.subcontract', string='Subcontract')
    project_id = fields.Many2one('construction.project', string='Project',
                                  related='subcontract_id.project_id', store=True)
    date = fields.Date(string='Date', default=fields.Date.context_today)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    line_ids = fields.One2many('construction.consume.order.line', 'consume_order_id', string='Lines')
    notes = fields.Text(string='Notes')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('construction.consume.order') or 'New'
        return super().create(vals_list)

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})


class ConstructionConsumeOrderLine(models.Model):
    _name = 'construction.consume.order.line'
    _description = 'Consume Order Line'

    consume_order_id = fields.Many2one('construction.consume.order', string='Consume Order', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    description = fields.Char(string='Description')
    quantity = fields.Float(string='Quantity', default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.description = self.product_id.name
            self.uom_id = self.product_id.uom_id.id


class ConstructionRaBilling(models.Model):
    _name = 'construction.ra.billing'
    _description = 'RA Billing (Running Account)'
    _inherit = ['mail.thread']
    _order = 'id desc'

    name = fields.Char(string='Reference', readonly=True, default='New', copy=False)
    subcontract_id = fields.Many2one('construction.subcontract', string='Subcontract', required=True)
    project_id = fields.Many2one('construction.project', string='Project',
                                  related='subcontract_id.project_id', store=True)
    partner_id = fields.Many2one('res.partner', string='Subcontractor',
                                  related='subcontract_id.partner_id', store=True)
    date = fields.Date(string='Date', default=fields.Date.context_today)
    billing_no = fields.Integer(string='Billing No.')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', tracking=True)

    line_ids = fields.One2many('construction.ra.billing.line', 'ra_billing_id', string='Lines')
    total_amount = fields.Float(string='Total Amount', compute='_compute_total', store=True)
    previous_amount = fields.Float(string='Previous Billing Amount')
    current_amount = fields.Float(string='Current Amount', compute='_compute_current', store=True)
    notes = fields.Text(string='Notes')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('construction.ra.billing') or 'New'
        return super().create(vals_list)

    @api.depends('line_ids.amount')
    def _compute_total(self):
        for rec in self:
            rec.total_amount = sum(rec.line_ids.mapped('amount'))

    @api.depends('total_amount', 'previous_amount')
    def _compute_current(self):
        for rec in self:
            rec.current_amount = rec.total_amount - rec.previous_amount

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_reject(self):
        self.write({'state': 'rejected'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})


class ConstructionRaBillingLine(models.Model):
    _name = 'construction.ra.billing.line'
    _description = 'RA Billing Line'

    ra_billing_id = fields.Many2one('construction.ra.billing', string='RA Billing', ondelete='cascade')
    description = fields.Char(string='Description', required=True)
    quantity = fields.Float(string='Quantity', default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    rate = fields.Float(string='Rate')
    amount = fields.Float(string='Amount', compute='_compute_amount', store=True)
    completion_percentage = fields.Float(string='Completion (%)')

    @api.depends('quantity', 'rate')
    def _compute_amount(self):
        for line in self:
            line.amount = line.quantity * line.rate
