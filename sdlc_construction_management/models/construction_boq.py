from odoo import models, fields, api, _


class ConstructionBoq(models.Model):
    _name = 'construction.boq'
    _description = 'Bill of Quantities'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Reference', readonly=True, default='New', copy=False)
    project_id = fields.Many2one('construction.project', string='Project', required=True)
    sub_project_id = fields.Many2one('construction.sub.project', string='Sub Project',
                                      domain="[('project_id', '=', project_id)]")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    work_type_id = fields.Many2one('construction.work.type', string='Work Type')
    work_sub_type_id = fields.Many2one('construction.work.sub.type', string='Work Sub Type',
                                        domain="[('work_type_id', '=', work_type_id)]")

    # Measurement
    length = fields.Float(string='Length', default=1.0)
    width = fields.Float(string='Width', default=1.0)
    height = fields.Float(string='Height', default=1.0)
    nos = fields.Float(string='Nos', default=1.0)
    quantity = fields.Float(string='Quantity', compute='_compute_quantity', store=True)

    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    description = fields.Text(string='Description')

    line_ids = fields.One2many('construction.boq.line', 'boq_id', string='BOQ Lines')

    total_amount = fields.Float(string='Total Amount', compute='_compute_total_amount', store=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('construction.boq') or 'New'
        return super().create(vals_list)

    @api.depends('length', 'width', 'height', 'nos')
    def _compute_quantity(self):
        for rec in self:
            rec.quantity = rec.length * rec.width * rec.height * rec.nos

    @api.depends('line_ids.amount')
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = sum(rec.line_ids.mapped('amount'))

    def action_create_budget(self):
        """Create or update budget based on BOQ"""
        budget = self.env['construction.budget'].search([
            ('project_id', '=', self.project_id.id),
            ('sub_project_id', '=', self.sub_project_id.id),
        ], limit=1)
        if not budget:
            budget = self.env['construction.budget'].create({
                'project_id': self.project_id.id,
                'sub_project_id': self.sub_project_id.id,
            })
        for line in self.line_ids:
            existing_budget_line = self.env['construction.budget.line'].search([
                ('budget_id', '=', budget.id),
                ('product_id', '=', line.product_id.id),
            ], limit=1)
            vals = {
                'description': line.description or line.product_id.name,
                'planned_amount': line.amount,
                'work_type_id': self.work_type_id.id,
            }
            if existing_budget_line:
                existing_budget_line.write(vals)
            else:
                vals.update({
                    'budget_id': budget.id,
                    'product_id': line.product_id.id,
                })
                self.env['construction.budget.line'].create(vals)
        return {
            'name': _('Budget'),
            'type': 'ir.actions.act_window',
            'res_model': 'construction.budget',
            'view_mode': 'form',
            'res_id': budget.id,
        }


class ConstructionBoqLine(models.Model):
    _name = 'construction.boq.line'
    _description = 'BOQ Line'

    boq_id = fields.Many2one('construction.boq', string='BOQ', ondelete='cascade')
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
