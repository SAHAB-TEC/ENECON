from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class EneconDailyReport(models.Model):
    _name = 'rgb.enecon.daily.report'
    _description = 'ENECON Daily Report'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Report Reference',
        required=True,
        readonly=True,
        copy=False,
        default='New',
        tracking=True,
    )
    project_id = fields.Many2one(
        'construction.project',
        string='Project / Work Order',
        required=True,
        tracking=True,
        ondelete='restrict',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        related='project_id.company_id',
        store=True,
        readonly=True,
        index=True,
    )
    date = fields.Date(
        string='Report Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        index=True,
    )
    customer_id = fields.Many2one(
        'res.partner',
        string='Customer',
        related='project_id.partner_id',
        store=True,
        readonly=True,
    )
    location = fields.Char(
        string='Location',
        compute='_compute_location',
        store=True,
        readonly=True,
    )
    stage_name = fields.Char(string='Stage', tracking=True)
    tank_name = fields.Char(string='Tank Name', tracking=True)
    work_type = fields.Char(string='Work Type', tracking=True)
    work_hours = fields.Float(
        string='Working Hours',
        help='Normal working hours for the reporting day.',
    )
    overtime_hours = fields.Float(
        string='Overtime Hours',
        help='Additional working hours entered manually.',
    )
    work_description = fields.Text(
        string='Work Completed / Daily Report',
        help='Detailed description of the work completed during the day.',
    )
    state = fields.Selection(
        [('new', 'New'), ('approved', 'Approved')],
        string='Status',
        default='new',
        required=True,
        tracking=True,
        copy=False,
        index=True,
    )

    material_line_ids = fields.One2many(
        'rgb.enecon.daily.report.material', 'report_id',
        string='Materials', copy=True,
    )
    equipment_line_ids = fields.One2many(
        'rgb.enecon.daily.report.equipment', 'report_id',
        string='Equipment', copy=True,
    )
    transport_line_ids = fields.One2many(
        'rgb.enecon.daily.report.transport', 'report_id',
        string='Transportation', copy=True,
    )
    image_ids = fields.One2many(
        'rgb.enecon.daily.report.image', 'report_id',
        string='Work Images', copy=True,
    )

    @api.depends(
        'project_id.street', 'project_id.street2', 'project_id.city',
        'project_id.state_id', 'project_id.country_id',
        'project_id.latitude', 'project_id.longitude',
    )
    def _compute_location(self):
        for report in self:
            project = report.project_id
            parts = [
                project.street,
                project.street2,
                project.city,
                project.state_id.name if project.state_id else False,
                project.country_id.name if project.country_id else False,
            ]
            location = ', '.join(part for part in parts if part)
            if not location and project and (project.latitude or project.longitude):
                location = f'{project.latitude:.6f}, {project.longitude:.6f}'
            report.location = location

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('rgb.enecon.daily.report')
                    or 'New'
                )
        return super().create(vals_list)

    def write(self, vals):
        if self.filtered(lambda report: report.state == 'approved'):
            allowed = {'message_follower_ids', 'activity_ids', 'message_main_attachment_id'}
            if set(vals) - allowed:
                raise UserError(
                    _('Approved daily reports are locked and cannot be modified.')
                )
        return super().write(vals)

    def unlink(self):
        if any(report.state == 'approved' for report in self):
            raise UserError(_('Approved daily reports cannot be deleted.'))
        return super().unlink()

    def action_approve(self):
        if not self.env.user.has_group(
            'rgb_enecon_daily_report.group_rgb_enecon_daily_report_approver'
        ):
            raise AccessError(_('You are not allowed to approve daily reports.'))
        for report in self.filtered(lambda item: item.state == 'new'):
            report.write({'state': 'approved'})
        return True


class EneconDailyReportMaterial(models.Model):
    _name = 'rgb.enecon.daily.report.material'
    _description = 'ENECON Daily Report Material'
    _inherit = "rgb.enecon.approval.lock.mixin"
    _parent_lock_field = "report_id"
    _order = 'id'

    report_id = fields.Many2one(
        'rgb.enecon.daily.report', required=True, ondelete='cascade', index=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Material',
        required=True,
        domain=[('rgb_enecon_material', '=', True)],
        ondelete='restrict',
    )
    quantity = fields.Float(string='Used Quantity', required=True, default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', required=True)
    uom_category_id = fields.Many2one(
        'uom.category',
        related='product_id.uom_id.category_id',
        readonly=True,
    )
    notes = fields.Char(string='Notes')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id


class EneconDailyReportEquipment(models.Model):
    _name = 'rgb.enecon.daily.report.equipment'
    _description = 'ENECON Daily Report Equipment'
    _inherit = "rgb.enecon.approval.lock.mixin"
    _parent_lock_field = "report_id"
    _order = 'id'

    report_id = fields.Many2one(
        'rgb.enecon.daily.report', required=True, ondelete='cascade', index=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Equipment',
        required=True,
        domain=[('rgb_enecon_equipment', '=', True)],
        ondelete='restrict',
    )
    quantity = fields.Float(string='Quantity', required=True, default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', required=True)
    uom_category_id = fields.Many2one(
        'uom.category',
        related='product_id.uom_id.category_id',
        readonly=True,
    )
    notes = fields.Char(string='Notes')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id


class EneconDailyReportTransport(models.Model):
    _name = 'rgb.enecon.daily.report.transport'
    _description = 'ENECON Daily Report Transportation'
    _inherit = "rgb.enecon.approval.lock.mixin"
    _parent_lock_field = "report_id"
    _order = 'id'

    report_id = fields.Many2one(
        'rgb.enecon.daily.report', required=True, ondelete='cascade', index=True,
    )
    name = fields.Char(string='Transportation / Vehicle', required=True)
    quantity = fields.Float(string='Quantity', required=True, default=1.0)
    notes = fields.Char(string='Notes')


class EneconDailyReportImage(models.Model):
    _name = 'rgb.enecon.daily.report.image'
    _description = 'ENECON Daily Report Image'
    _inherit = "rgb.enecon.approval.lock.mixin"
    _parent_lock_field = "report_id"
    _order = 'sequence, id'

    report_id = fields.Many2one(
        'rgb.enecon.daily.report', required=True, ondelete='cascade', index=True,
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Description')
    image = fields.Image(
        string='Image',
        required=True,
        attachment=True,
        max_width=1920,
        max_height=1920,
    )
