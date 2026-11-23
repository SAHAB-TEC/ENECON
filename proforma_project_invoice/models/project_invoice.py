from odoo import api, fields, models, _
from odoo.exceptions import UserError

G_USER = 'proforma_project_invoice.group_invoice_user'
G_EDITOR = 'proforma_project_invoice.group_invoice_editor'
G_ADMIN = 'proforma_project_invoice.group_invoice_admin'
TECHNICAL_FIELDS = {'message_main_attachment_id', 'message_follower_ids',
                    'message_ids', 'activity_ids'}


class ProjectCustomInvoice(models.Model):
    _name = 'project.custom.invoice'
    _description = 'Project / Service Statement Invoice (Non-Financial)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'invoice_date desc, id desc'

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    name = fields.Char(string='الرقم الداخلي / Number', default='New',
                       readonly=True, copy=False, tracking=True)
    manual_invoice_number = fields.Char(string='فاتورة رقم', required=True, tracking=True)
    project_title = fields.Char(string='وصف المشروع', required=True, tracking=True)
    partner_id = fields.Many2one('res.partner', string='الاخوة /', required=True,
                                 tracking=True)
    pricelist_id = fields.Many2one(
        'product.pricelist', string='قائمة الأسعار / Pricelist', tracking=True,
        compute='_compute_pricelist_id', store=True, readonly=False)
    work_date_from = fields.Date(string='فترة العمل من', tracking=True)
    work_date_to = fields.Date(string='الى', tracking=True)
    invoice_date = fields.Date(string='التاريخ :', default=fields.Date.context_today,
                               tracking=True)
    reference_number = fields.Char(string='الرقم الاشاري :', tracking=True)
    state = fields.Selection(
        [('draft', 'مسودة / Draft'), ('approved', 'معتمد / Approved')],
        default='draft', required=True, tracking=True, copy=False)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    can_edit = fields.Boolean(compute='_compute_can_edit')

    # ------------------------------------------------------------------
    # Signatory
    # ------------------------------------------------------------------
    signatory_user_id = fields.Many2one('res.users', string='الموقّع / Signatory',
                                        default=lambda self: self.env.user, tracking=True)
    signatory_name = fields.Char(string='اسم الموقّع', tracking=True,
                                 compute='_compute_signatory', store=True, readonly=False)
    signatory_job_title = fields.Char(string='المسمى الوظيفي', tracking=True,
                                      compute='_compute_signatory', store=True,
                                      readonly=False)

    # ------------------------------------------------------------------
    # Lines
    # ------------------------------------------------------------------
    material_line_ids = fields.One2many('project.invoice.material.line', 'invoice_id',
                                        string='المواد', copy=True)
    labor_line_ids = fields.One2many('project.invoice.labor.line', 'invoice_id',
                                     string='فريق العمل', copy=True)
    transport_line_ids = fields.One2many('project.invoice.transport.line', 'invoice_id',
                                         string='وسائل النقل', copy=True)
    equipment_line_ids = fields.One2many('project.invoice.equipment.line', 'invoice_id',
                                         string='المعدات وأدوات التشغيل', copy=True)
    catering_line_ids = fields.One2many('project.invoice.catering.line', 'invoice_id',
                                        string='الإعاشة', copy=True)

    notes_materials = fields.Text(string='ملاحظات القسم', tracking=True)
    notes_labor = fields.Text(string='ملاحظات القسم', tracking=True)
    notes_transport = fields.Text(string='ملاحظات القسم', tracking=True)
    notes_equipment = fields.Text(string='ملاحظات القسم', tracking=True)
    notes_catering = fields.Text(string='ملاحظات القسم', tracking=True)

    total_materials = fields.Float(string='المجموع', digits=(16, 3),
                                   compute='_compute_totals', store=True, tracking=True)
    total_labor = fields.Float(string='المجموع', digits=(16, 3),
                               compute='_compute_totals', store=True, tracking=True)
    total_labor_qty = fields.Float(string='إجمالي عدد العاملين', digits=(16, 3),
                                   compute='_compute_totals', store=True)
    total_transport = fields.Float(string='المجموع', digits=(16, 3),
                                   compute='_compute_totals', store=True, tracking=True)
    total_equipment = fields.Float(string='المجموع', digits=(16, 3),
                                   compute='_compute_totals', store=True, tracking=True)
    total_catering = fields.Float(string='المجموع', digits=(16, 3),
                                  compute='_compute_totals', store=True, tracking=True)
    grand_total = fields.Float(string='الاجمالى', digits=(16, 3),
                               compute='_compute_totals', store=True, tracking=True)

    # ------------------------------------------------------------------
    # Computes
    # ------------------------------------------------------------------
    @api.depends('name', 'manual_invoice_number')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = ' - '.join(filter(None, [rec.name, rec.manual_invoice_number]))

    @api.depends('partner_id')
    def _compute_pricelist_id(self):
        for rec in self:
            if rec.partner_id:
                rec.pricelist_id = rec.partner_id.property_product_pricelist
            elif not rec.pricelist_id:
                rec.pricelist_id = False

    @api.model
    def _get_user_job_title(self, user):
        title = ''
        if user:
            employee = user.sudo().employee_id if 'employee_id' in user._fields else False
            title = (employee and employee.job_title) or user.sudo().function or ''
        return title

    @api.depends('signatory_user_id')
    def _compute_signatory(self):
        for rec in self:
            user = rec.signatory_user_id
            rec.signatory_name = user.name if user else False
            rec.signatory_job_title = self._get_user_job_title(user)

    @api.depends('state')
    def _compute_can_edit(self):
        user = self.env.user
        is_admin = user.has_group(G_ADMIN)
        is_editor = user.has_group(G_EDITOR)
        for rec in self:
            if not rec.id:  # new, unsaved record: creator may fill it in
                rec.can_edit = True
            elif is_admin:
                rec.can_edit = True
            else:
                rec.can_edit = is_editor and rec.state == 'draft'

    @api.depends('material_line_ids.subtotal', 'labor_line_ids.subtotal',
                 'labor_line_ids.worker_days_qty', 'transport_line_ids.subtotal',
                 'equipment_line_ids.subtotal', 'catering_line_ids.subtotal')
    def _compute_totals(self):
        for rec in self:
            rec.total_materials = sum(rec.material_line_ids.mapped('subtotal'))
            rec.total_labor = sum(rec.labor_line_ids.mapped('subtotal'))
            rec.total_labor_qty = sum(rec.labor_line_ids.mapped('worker_days_qty'))
            rec.total_transport = sum(rec.transport_line_ids.mapped('subtotal'))
            rec.total_equipment = sum(rec.equipment_line_ids.mapped('subtotal'))
            rec.total_catering = sum(rec.catering_line_ids.mapped('subtotal'))
            rec.grand_total = (rec.total_materials + rec.total_labor + rec.total_transport
                               + rec.total_equipment + rec.total_catering)

    # ------------------------------------------------------------------
    # Access enforcement (Python level)
    # ------------------------------------------------------------------
    def _check_edit_rights(self, vals=None):
        if self.env.su or self.env.context.get('pi_creating'):
            return
        user = self.env.user
        if user.has_group(G_ADMIN):
            return
        if vals is not None and 'state' in vals:
            raise UserError(_('Only a Manager can change the invoice state.'))
        for rec in self:
            if rec.state == 'approved':
                raise UserError(_('Invoice %s is approved. Only a Manager can modify it.',
                                  rec.display_name))
            if not user.has_group(G_EDITOR):
                raise UserError(_('You do not have the Editor permission to modify '
                                  'invoice %s.', rec.display_name))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'project.custom.invoice') or 'New'
        records = super(ProjectCustomInvoice,
                        self.with_context(pi_creating=True)).create(vals_list)
        return records.with_context(pi_creating=False)

    def write(self, vals):
        if not set(vals) <= TECHNICAL_FIELDS:
            self._check_edit_rights(vals)
        return super().write(vals)

    def unlink(self):
        if not self.env.su and not self.env.user.has_group(G_ADMIN):
            for rec in self:
                if rec.state != 'draft' or not self.env.user.has_group(G_EDITOR):
                    raise UserError(_('Only draft invoices can be deleted (Editor/Manager).'))
        return super().unlink()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_approve(self):
        if not self.env.user.has_group(G_ADMIN):
            raise UserError(_('Only a Manager can approve invoices.'))
        self.filtered(lambda r: r.state == 'draft').write({'state': 'approved'})

    def action_reset_draft(self):
        if not self.env.user.has_group(G_ADMIN):
            raise UserError(_('Only a Manager can reset invoices to draft.'))
        self.filtered(lambda r: r.state == 'approved').write({'state': 'draft'})

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref('proforma_project_invoice.action_report_project_invoice') \
            .report_action(self)

    def action_export_xlsx(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/proforma_invoice/xlsx/%s' % self.id,
            'target': 'self',
        }
