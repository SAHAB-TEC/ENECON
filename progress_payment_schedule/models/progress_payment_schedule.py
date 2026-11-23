from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

MANAGER_GROUP = 'progress_payment_schedule.group_progress_payment_manager'


class ProgressPaymentSchedule(models.Model):
    _name = 'progress.payment.schedule'
    _description = 'Progress Payment Schedule'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'period_ending desc, id desc'

    name = fields.Char(
        string='Reference', required=True, readonly=True, copy=False,
        default='New', tracking=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('approved', 'Approved')],
        string='Status', default='draft', required=True, copy=False,
        tracking=True)
    partner_id = fields.Many2one(
        'res.partner', string='Client / Vendor', required=True, tracking=True)
    partner_image_128 = fields.Image(
        related='partner_id.image_128', string='Partner Image', readonly=True)
    partner_department = fields.Char(
        string='Department / Subtitle', default='MAINTENANCE DEPARTMENT',
        tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    schedule_title_line = fields.Char(
        string='Schedule Header', required=True,
        default='No 01 FOR TOBRUQ', tracking=True)
    contract_no = fields.Char(string='Contract No.', required=True, tracking=True)
    project_title = fields.Char(string='Title', required=True, tracking=True)
    period_ending = fields.Date(
        string='Progress For Period Ending', required=True, tracking=True)
    line_ids = fields.One2many(
        'progress.payment.schedule.line', 'schedule_id',
        string='Work Items', copy=True)

    approved_by = fields.Many2one(
        'res.users', string='Approved By', readonly=True, copy=False,
        tracking=True)
    approved_date = fields.Datetime(
        string='Approval Date', readonly=True, copy=False, tracking=True)

    # ---- Totals (LYD, 3 decimals) ----
    total_wtg_pct = fields.Float(
        string='Total WTG %', digits=(16, 2), compute='_compute_totals', store=True)
    total_value_per_item = fields.Float(
        string='Total Value', digits=(16, 3), compute='_compute_totals', store=True)
    total_prev_period_pct = fields.Float(
        string='Total Previous Period %', digits=(16, 2),
        compute='_compute_totals', store=True)
    total_this_period_pct = fields.Float(
        string='Total This Period %', digits=(16, 2),
        compute='_compute_totals', store=True)
    total_overall_pct = fields.Float(
        string='Total Overall %', digits=(16, 2),
        compute='_compute_totals', store=True)
    total_prev_period_amount = fields.Float(
        string='Total Previous Period', digits=(16, 3),
        compute='_compute_totals', store=True)
    total_this_period_amount = fields.Float(
        string='Total This Period', digits=(16, 3),
        compute='_compute_totals', store=True)
    total_cumulative_amount = fields.Float(
        string='Total Cumulative', digits=(16, 3),
        compute='_compute_totals', store=True)
    less_previous_payment = fields.Float(
        string='Less Previous Payment', digits=(16, 3),
        compute='_compute_totals', store=True)
    net_amount_due = fields.Float(
        string='Net Amount Due This Period', digits=(16, 3),
        compute='_compute_totals', store=True)

    # ---- Endorsements ----
    endorsement_1 = fields.Char(default='CONTRACTORS SITE REPRESENTATIVE.')
    endorsement_2 = fields.Char(default='AGOCO SITE ENGINEER')
    endorsement_3 = fields.Char(default='TOBRUQ MAINTENACE COORDENATOR')
    endorsement_4 = fields.Char(default='AGOCO MAINTENANCE MANAGER')

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    @api.depends(
        'line_ids.is_section', 'line_ids.wtg_pct', 'line_ids.value_per_item',
        'line_ids.prev_period_pct', 'line_ids.overall_pct',
        'line_ids.prev_period_amount', 'line_ids.this_period_amount',
        'line_ids.cumulative_amount')
    def _compute_totals(self):
        for rec in self:
            lines = rec.line_ids.filtered(lambda l: not l.is_section)
            total_value = sum(lines.mapped('value_per_item'))
            prev_amount = sum(lines.mapped('prev_period_amount'))
            this_amount = sum(lines.mapped('this_period_amount'))
            cumulative = sum(lines.mapped('cumulative_amount'))
            rec.total_wtg_pct = sum(lines.mapped('wtg_pct'))
            rec.total_value_per_item = total_value
            rec.total_prev_period_amount = prev_amount
            rec.total_this_period_amount = this_amount
            rec.total_cumulative_amount = cumulative
            rec.total_prev_period_pct = (
                sum(l.value_per_item * l.prev_period_pct for l in lines)
                / total_value) if total_value else 0.0
            rec.total_this_period_pct = (
                this_amount / total_value * 100.0) if total_value else 0.0
            rec.total_overall_pct = (
                sum(l.value_per_item * l.overall_pct for l in lines)
                / total_value) if total_value else 0.0
            rec.less_previous_payment = prev_amount
            rec.net_amount_due = cumulative - prev_amount

    # ------------------------------------------------------------------
    # ORM overrides
    # ------------------------------------------------------------------
    def _is_manager(self):
        return self.env.su or self.env.user.has_group(MANAGER_GROUP)

    @api.model_create_multi
    def create(self, vals_list):
        is_manager = self._is_manager()
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code(
                    'progress.payment.schedule') or 'New'
            if not is_manager:
                vals['state'] = 'draft'
                vals.pop('approved_by', None)
                vals.pop('approved_date', None)
        return super().create(vals_list)

    def write(self, vals):
        if not self._is_manager():
            if any(rec.state == 'approved' for rec in self):
                raise UserError(_(
                    "Approved schedules cannot be modified. "
                    "Ask a manager to reset the document to draft."))
            if {'state', 'approved_by', 'approved_date'} & set(vals):
                raise AccessError(_(
                    "Only managers can change the approval status."))
        return super().write(vals)

    def unlink(self):
        if not self._is_manager() and any(r.state == 'approved' for r in self):
            raise UserError(_("Approved schedules cannot be deleted."))
        return super().unlink()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_approve(self):
        if not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError(_("Only managers can approve a schedule."))
        for rec in self:
            if rec.state != 'draft':
                continue
            if not rec.line_ids.filtered(lambda l: not l.is_section):
                raise UserError(_(
                    "Add at least one work item before approving %s.", rec.name))
            rec.write({
                'state': 'approved',
                'approved_by': self.env.user.id,
                'approved_date': fields.Datetime.now(),
            })
            rec.message_post(body=_(
                "Schedule approved by %s.", self.env.user.name))
        return True

    def action_draft(self):
        if not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError(_("Only managers can reset a schedule to draft."))
        for rec in self:
            if rec.state != 'approved':
                continue
            rec.write({
                'state': 'draft',
                'approved_by': False,
                'approved_date': False,
            })
            rec.message_post(body=_(
                "Schedule reset to draft by %s.", self.env.user.name))
        return True

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref(
            'progress_payment_schedule.action_report_progress_payment_schedule'
        ).report_action(self)
