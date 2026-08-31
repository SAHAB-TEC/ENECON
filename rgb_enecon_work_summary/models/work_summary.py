from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class EneconTransportType(models.Model):
    _name = 'rgb.enecon.transport.type'
    _description = 'ENECON Transport / Equipment Type'
    _order = 'name'

    name = fields.Char(string='Transport / Equipment Type', required=True, index=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company, index=True,
    )

    _sql_constraints = [
        ('name_company_uniq', 'unique(name, company_id)',
         'The transport / equipment type must be unique per company.'),
    ]


class EneconWorkSummaryEntry(models.Model):
    _name = 'rgb.enecon.work.summary.entry'
    _description = 'ENECON Work Summary Daily Entry'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Reference', required=True, readonly=True, copy=False,
        default='New', tracking=True,
    )
    project_id = fields.Many2one(
        'construction.project', string='Project', required=True,
        tracking=True, ondelete='restrict', index=True,
    )
    company_id = fields.Many2one(
        'res.company', related='project_id.company_id',
        store=True, readonly=True, index=True,
    )
    date = fields.Date(
        string='Date', required=True, default=fields.Date.context_today,
        tracking=True, index=True,
    )
    state = fields.Selection(
        [('new', 'New'), ('approved', 'Approved')],
        string='Status', default='new', required=True,
        tracking=True, copy=False, index=True,
    )
    notes_before_transport = fields.Text(string='Notes Before Transportation / Equipment')
    notes_after_transport = fields.Text(string='Notes After Transportation / Equipment')

    material_line_ids = fields.One2many(
        'rgb.enecon.work.summary.material', 'entry_id', string='Materials', copy=True,
    )
    workforce_line_ids = fields.One2many(
        'rgb.enecon.work.summary.workforce', 'entry_id', string='Workforce', copy=True,
    )
    transport_line_ids = fields.One2many(
        'rgb.enecon.work.summary.transport', 'entry_id',
        string='Transportation / Equipment', copy=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('rgb.enecon.work.summary.entry')
                    or 'New'
                )
        return super().create(vals_list)

    def write(self, vals):
        if self.filtered(lambda entry: entry.state == 'approved'):
            allowed = {
                'message_follower_ids', 'activity_ids', 'message_main_attachment_id',
            }
            if set(vals) - allowed:
                raise UserError(
                    _('Approved work summary entries are locked and cannot be modified.')
                )
        return super().write(vals)

    def unlink(self):
        if any(entry.state == 'approved' for entry in self):
            raise UserError(_('Approved work summary entries cannot be deleted.'))
        return super().unlink()

    def action_approve(self):
        if not self.env.user.has_group(
            'rgb_enecon_work_summary.group_rgb_enecon_work_summary_approver'
        ):
            raise AccessError(_('You are not allowed to approve work summary entries.'))
        for entry in self.filtered(lambda item: item.state == 'new'):
            entry.write({'state': 'approved'})
        return True


class EneconWorkSummaryMaterial(models.Model):
    _name = 'rgb.enecon.work.summary.material'
    _description = 'ENECON Work Summary Material'
    _order = 'id'

    entry_id = fields.Many2one(
        'rgb.enecon.work.summary.entry', required=True, ondelete='cascade', index=True,
    )
    product_id = fields.Many2one(
        'product.product', string='Material', required=True,
        domain=[('rgb_enecon_material', '=', True)], ondelete='restrict',
    )
    quantity = fields.Float(string='Quantity', required=True, default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', required=True)
    uom_category_id = fields.Many2one(
        'uom.category', related='product_id.uom_id.category_id', readonly=True,
    )

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id

    @api.constrains('quantity')
    def _check_quantity(self):
        for line in self:
            if line.quantity < 0:
                raise ValidationError(_('Material quantity cannot be negative.'))


class EneconWorkSummaryWorkforce(models.Model):
    _name = 'rgb.enecon.work.summary.workforce'
    _description = 'ENECON Work Summary Workforce'
    _order = 'id'

    entry_id = fields.Many2one(
        'rgb.enecon.work.summary.entry', required=True, ondelete='cascade', index=True,
    )
    job_id = fields.Many2one(
        'hr.job', string='Job Position', required=True, ondelete='restrict',
    )
    count = fields.Integer(string='Count', required=True, default=1)

    @api.constrains('count')
    def _check_count(self):
        for line in self:
            if line.count < 0:
                raise ValidationError(_('Workforce count cannot be negative.'))


class EneconWorkSummaryTransport(models.Model):
    _name = 'rgb.enecon.work.summary.transport'
    _description = 'ENECON Work Summary Transportation / Equipment'
    _order = 'id'

    entry_id = fields.Many2one(
        'rgb.enecon.work.summary.entry', required=True, ondelete='cascade', index=True,
    )
    transport_type_id = fields.Many2one(
        'rgb.enecon.transport.type', string='Transport / Equipment Type',
        required=True, ondelete='restrict',
    )
    quantity = fields.Integer(string='Count', required=True, default=1)

    @api.constrains('quantity')
    def _check_quantity(self):
        for line in self:
            if line.quantity < 0:
                raise ValidationError(
                    _('Transportation / equipment count cannot be negative.')
                )
