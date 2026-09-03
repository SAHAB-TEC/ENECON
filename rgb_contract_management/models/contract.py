# -*- coding: utf-8 -*-
import logging
from datetime import date, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class RgbContract(models.Model):
    _name = 'rgb.contract'
    _description = 'Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc, id desc'

    # ── Identification ──
    name = fields.Char(
        string='Contract Number',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    contract_code = fields.Char(
        string='Contract No',
        tracking=True,
        copy=False,
        index=True,
        help='Unique contract number shown on linked invoice prints.',
    )
    indicative_number = fields.Char(
        string='Indicative Number',
        tracking=True,
        copy=False,
        index=True,
        help='Indicative / reference number shown on the contract and linked invoices.',
    )
    contract_name = fields.Char(
        string='Contract Name',
        tracking=True,
        copy=False,
    )
    contract_type = fields.Selection(
        selection=[
            ('purchase_contract', 'Expenses Contract'),
            ('sale_contract', 'Income Contract'),
        ],
        string='Contract Type',
        required=True,
        default='purchase_contract',
        tracking=True,
    )
    contract_business_type_id = fields.Many2one(
        'rgb.contract.business.type',
        string='Business Type',
        tracking=True,
        ondelete='restrict',
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Contractor / Customer',
        required=True,
        tracking=True,
        check_company=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('under_approval', 'Under Approval'),
            ('approved', 'Approved'),
            ('in_progress', 'In Progress'),
            ('done', 'Done Unlocked'),
            ('done_locked', 'Done Locked'),
            ('cancelled', 'Cancelled'),
            ('expired', 'Expired'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        copy=False,
    )

    # ── Dates & duration ──
    date_start = fields.Date(string='Start Date', tracking=True)
    date_end = fields.Date(string='End Date', tracking=True)
    service_duration_days = fields.Integer(string='Service Duration (Days)', tracking=True, compute='_compute_service_duration_days', store=True)

    remaining_days = fields.Integer(
        string='Remaining Days',
        compute='_compute_remaining_days',
        store=True,
    )

    # ── Amounts & currencies ──
    currency_id = fields.Many2one(
        'res.currency',
        string='Contract Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
        tracking=True,
    )
    contract_value_currency = fields.Monetary(
        string='Contract Value',
        currency_field='currency_id',
        tracking=True,
    )
    lyd_currency_id = fields.Many2one(
        'res.currency',
        string='LYD Currency',
        compute='_compute_lyd_currency_id',
        store=True,
        readonly=False,
    )
    exchange_rate = fields.Float(
        string='Exchange Rate',
        digits=(16, 6),
        default=1.0,
        tracking=True,
        help='Multiplier to LYD: Contract Value (LYD) = Contract Value × Exchange Rate '
             '(e.g. rate 5 → 6,000 becomes 30,000 LYD).',
    )
    contract_value_lyd = fields.Monetary(
        string='Contract Value (LYD)',
        currency_field='lyd_currency_id',
        tracking=True,
        compute='_compute_contract_value_lyd',
        store=True,
        readonly=True,
    )

    payment_terms_text = fields.Html(string='Payment Terms')
    price_list_id = fields.Many2one(
        'product.pricelist',
        string='Pricelist',
        check_company=True,
    )
    allow_over_contract_value = fields.Boolean(
        string='Allow Invoicing Over Contract Value',
        help='If unchecked, total posted invoices cannot exceed the contract value.',
    )
    without_advance_payment = fields.Boolean(
        string='Contract Without Advance Payment',
        help='If checked, the Add Advance Payment action is hidden on invoice lines.',
    )
    contract_amendment_percent = fields.Float(
        string='Amendment Limit (%)',
        default=10.0,
        help='Maximum contract value change allowed (increase or decrease).',
    )
    dollar_percentage = fields.Float(
        string='USD %',
        help='Deprecated: migrated to Payment Currency Split. Kept for upgrade migration.',
    )
    libya_dinar_percentage = fields.Float(
        string='LYD %',
        help='Deprecated: migrated to Payment Currency Split. Kept for upgrade migration.',
    )
    usd_amount = fields.Float(
        string='USD Amount',
        compute='_compute_legacy_currency_split_fields',
        store=True,
        help='Contract value share in USD from payment currency split.',
    )
    lyd_amount = fields.Float(
        string='LYD Amount',
        compute='_compute_legacy_currency_split_fields',
        store=True,
        help='Contract value share in LYD from payment currency split.',
    )
    currency_split_ids = fields.One2many(
        'rgb.contract.currency.split',
        'contract_id',
        string='Payment Currency Split',
        copy=True,
    )
    currency_split_percentage_total = fields.Float(
        string='Split Total (%)',
        compute='_compute_currency_split_percentage_total',
        digits=(16, 4),
    )
    invoice_currency_id = fields.Many2one(
        'res.currency',
        string='Invoice Currency',
        help='Currency used for the staged invoice lines and applied when creating the next invoice.',
        default=lambda self: self.env.company.currency_id,
        tracking=True,
        copy=False,
    )
    invoice_exchange_rate = fields.Float(
        string='Invoice Exchange Rate',
        digits=(16, 6),
        default=1.0,
        tracking=True,
        copy=False,
        help='Manual rate for invoice lines: LYD per 1 unit of Invoice Currency. '
             'Used when creating the invoice instead of system currency rates.',
    )
    contract_line_ids = fields.One2many(
        'rgb.contract.line',
        'contract_id',
        string='Invoice Lines',
        copy=True,
    )
    contract_lines_total = fields.Monetary(
        string='Lines Total',
        currency_field='invoice_currency_id',
        compute='_compute_contract_lines_total',
        store=True,
    )
    tax_type_use = fields.Selection(
        selection=[
            ('sale', 'Sales'),
            ('purchase', 'Purchases'),
        ],
        compute='_compute_tax_type_use',
        store=True,
    )

    # ── Accounting & responsibility ──
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Analytic Account',
        check_company=True,
        tracking=True,
    )
    responsible_user_id = fields.Many2one(
        'res.users',
        string='Responsible',
        default=lambda self: self.env.user,
        tracking=True,
    )
    approval_user_id = fields.Many2one(
        'res.users',
        string='Approval Responsible',
        tracking=True,
    )

    # ── Insurance & attachments ──
    insurance_type_ids = fields.Many2many(
        'rgb.contract.insurance.type',
        'rgb_contract_insurance_type_rel',
        'contract_id',
        'insurance_type_id',
        string='Insurance Types',
    )
    insurance_attachment_ids = fields.Many2many(
        'ir.attachment',
        'rgb_contract_insurance_attachment_rel',
        'contract_id',
        'attachment_id',
        string='Insurance Documents',
    )
    performance_guarantee_attachment_ids = fields.Many2many(
        'ir.attachment',
        'rgb_contract_performance_attachment_rel',
        'contract_id',
        'attachment_id',
        string='Performance Guarantee Documents',
    )
    performance_guarantee_expiry_date = fields.Date(
        string='Performance Guarantee Expiry',
        tracking=True,
    )
    # Reminder tracking (catch-up safe: mark sent so missed cron days still fire once)
    reminder_contract_expiry_sent = fields.Boolean(
        string='Contract Expiry Reminder Sent',
        copy=False,
        default=False,
    )
    reminder_guarantee_10_sent = fields.Boolean(
        string='Guarantee 10-Day Reminder Sent',
        copy=False,
        default=False,
    )
    reminder_guarantee_60_sent = fields.Boolean(
        string='Guarantee 60-Day Reminder Sent',
        copy=False,
        default=False,
    )
    reminder_advance_payment_sent = fields.Boolean(
        string='Advance Payment Reminder Sent',
        copy=False,
        default=False,
    )
    reminder_dismissed_guarantee_10 = fields.Boolean(copy=False, default=False)
    reminder_dismissed_guarantee_60 = fields.Boolean(copy=False, default=False)
    reminder_dismissed_contract_expiry = fields.Boolean(copy=False, default=False)
    reminder_dismissed_advance_payment = fields.Boolean(copy=False, default=False)
    reminder_alert = fields.Boolean(
        string='Reminder Alert',
        compute='_compute_reminder_alert',
        store=True,
    )
    reminder_alert_type = fields.Selection(
        selection=[
            ('contract_expiry', 'Contract Expiry Soon'),
            ('guarantee_10', 'Performance Guarantee (10 days)'),
            ('guarantee_60', 'Performance Guarantee (60 days)'),
            ('advance_payment', 'Advance Payment Due'),
        ],
        string='Reminder Alert Type',
        compute='_compute_reminder_alert',
        store=True,
    )
    alert_guarantee_10_active = fields.Boolean(compute='_compute_reminder_banners')
    alert_guarantee_60_active = fields.Boolean(compute='_compute_reminder_banners')
    alert_contract_expiry_active = fields.Boolean(compute='_compute_reminder_banners')
    alert_advance_payment_active = fields.Boolean(compute='_compute_reminder_banners')
    alert_guarantee_10_visible = fields.Boolean(compute='_compute_reminder_banners')
    alert_guarantee_60_visible = fields.Boolean(compute='_compute_reminder_banners')
    alert_contract_expiry_visible = fields.Boolean(compute='_compute_reminder_banners')
    alert_advance_payment_visible = fields.Boolean(compute='_compute_reminder_banners')
    alert_guarantee_10_label = fields.Char(compute='_compute_reminder_banners')
    alert_guarantee_60_label = fields.Char(compute='_compute_reminder_banners')
    alert_contract_expiry_label = fields.Char(compute='_compute_reminder_banners')
    alert_advance_payment_label = fields.Char(compute='_compute_reminder_banners')
    has_hidden_reminder_alerts = fields.Boolean(compute='_compute_reminder_banners')
    bank_guarantee_status = fields.Selection(
        selection=[
            ('sent', 'Correspondence Sent'),
            ('received', 'Received'),
        ],
        string='Bank Guarantee Status',
        tracking=True,
    )
    bank_guarantee_attachment_ids = fields.Many2many(
        'ir.attachment',
        'rgb_contract_bank_attachment_rel',
        'contract_id',
        'attachment_id',
        string='Bank Guarantee Documents',
    )
    bank_guarantee_value = fields.Monetary(
        string='Bank Guarantee Value',
        currency_field='currency_id',
    )

    # ── Payment & penalties ──
    advance_payment_percent = fields.Float(string='Advance Payment (%)', digits=(16, 4))
    advance_payment_amount = fields.Monetary(
        string='Advance Payment Amount',
        currency_field='currency_id',
        compute='_compute_advance_payment_amount',
        store=True,
        readonly=True,
    )
    advance_payment_due_date = fields.Date(
        string='Advance Payment Due Date',
        tracking=True,
    )
    delay_penalty_daily_rate = fields.Float(
        string='Daily Delay Penalty Rate (%)',
        digits=(16, 4),
        help='Percentage of contract value charged per delayed day.',
    )
    delay_penalty_max_percent = fields.Float(
        string='Max Delay Penalty (%)',
        digits=(16, 4),
        default=5.0,
    )
    agreed_execution_date = fields.Date(string='Agreed Execution Date')
    actual_execution_date = fields.Date(string='Actual Execution Date')
    delay_penalty_amount = fields.Monetary(
        string='Delay Penalty Amount',
        currency_field='currency_id',
        compute='_compute_delay_penalty_amount',
        store=True,
    )
    payment_condition_ids = fields.One2many(
        'rgb.contract.payment.condition',
        'contract_id',
        string='Payment Conditions',
    )

    # ── Invoices ──
    invoice_ids = fields.One2many(
        'account.move',
        'contract_id',
        string='Invoices',
        domain=[('move_type', 'in', ('out_invoice', 'out_refund', 'in_invoice', 'in_refund'))],
    )
    invoice_count = fields.Integer(compute='_compute_invoice_count', string='Invoice Count')
    total_invoiced_amount = fields.Monetary(
        string='Total Invoiced',
        currency_field='currency_id',
        compute='_compute_invoice_amounts',
        store=True,
    )
    paid_invoice_amount = fields.Monetary(
        string='Paid Amount',
        currency_field='currency_id',
        compute='_compute_invoice_amounts',
        store=True,
    )
    unpaid_invoice_amount = fields.Monetary(
        string='Unpaid Amount',
        currency_field='currency_id',
        compute='_compute_invoice_amounts',
        store=True,
    )
    paid_percent_currency = fields.Float(
        string='Paid % (Contract Currency)',
        compute='_compute_invoice_amounts',
        digits=(16, 2),
    )
    paid_percent_lyd = fields.Float(
        string='Paid % (LYD)',
        compute='_compute_invoice_amounts',
        digits=(16, 2),
    )

    notes = fields.Html(string='Notes')

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Contract number must be unique.'),
    ]

    @api.constrains('contract_code', 'company_id')
    def _check_contract_code_unique(self):
        for contract in self.filtered('contract_code'):
            code = contract.contract_code.strip()
            if not code:
                continue
            code_key = code.lower()
            duplicates = self.search([
                ('id', '!=', contract.id),
                ('company_id', '=', contract.company_id.id),
                ('contract_code', '!=', False),
            ])
            for duplicate in duplicates:
                if (duplicate.contract_code or '').strip().lower() == code_key:
                    raise ValidationError(_(
                        'Contract No "%(code)s" is already used on contract %(contract)s.',
                        code=code,
                        contract=duplicate.name,
                    ))

    @api.model
    def _deduplicate_contract_codes_for_unique_index(self):
        """Rename duplicate client references so the unique index can be created."""
        self.env.cr.execute("""
            WITH ranked AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY company_id, lower(btrim(contract_code))
                           ORDER BY id
                       ) AS rn
                FROM rgb_contract
                WHERE contract_code IS NOT NULL AND btrim(contract_code) <> ''
            )
            UPDATE rgb_contract c
            SET contract_code = btrim(c.contract_code) || '-' || c.id::text
            FROM ranked r
            WHERE c.id = r.id AND r.rn > 1
            RETURNING c.id, c.contract_code
        """)
        renamed = self.env.cr.fetchall()
        if renamed:
            _logger.warning(
                'Renamed %s duplicate rgb.contract client reference(s) before '
                'creating unique index: %s',
                len(renamed),
                renamed,
            )

    @api.model
    def init(self):
        super().init()
        cr = self.env.cr
        cr.execute("DROP INDEX IF EXISTS rgb_contract_client_ref_unique_ci")
        self._deduplicate_contract_codes_for_unique_index()
        cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS rgb_contract_client_ref_unique_ci
            ON rgb_contract (company_id, lower(btrim(contract_code)))
            WHERE contract_code IS NOT NULL AND btrim(contract_code) <> ''
        """)

    # ── Computes ──

    @api.depends('company_id')
    def _compute_lyd_currency_id(self):
        lyd = self.env['res.currency'].search([('name', '=', 'LYD')], limit=1)
        for contract in self:
            contract.lyd_currency_id = lyd.id if lyd else contract.currency_id.id

    def _get_suggested_exchange_rate(self):
        """Default rate from Odoo (contract currency → LYD at start date). User may override."""
        self.ensure_one()
        lyd_currency = self.env.ref('base.LYD', raise_if_not_found=False)
        if not self.currency_id or not lyd_currency or self.currency_id == lyd_currency:
            return 1.0
        conv_date = self.date_start or fields.Date.context_today(self)
        company = self.company_id or self.env.company
        return self.env['res.currency']._get_conversion_rate(
            self.currency_id,
            lyd_currency,
            company,
            conv_date,
        )

    def _suggest_lyd_per_currency_rate(self, currency):
        """Suggested manual rate: LYD amount for 1 unit of ``currency``."""
        self.ensure_one()
        lyd = self.lyd_currency_id or self.env.ref('base.LYD', raise_if_not_found=False)
        if not currency or not lyd:
            return 1.0
        if currency == lyd:
            return 1.0
        conv_date = self.date_start or fields.Date.context_today(self)
        company = self.company_id or self.env.company
        return currency._convert(1.0, lyd, company, conv_date)

    def _to_odoo_invoice_currency_rate(self, lyd_per_invoice_currency, invoice_currency):
        """Convert LYD-per-invoice-currency to Odoo ``invoice_currency_rate``
        (company currency → invoice currency).
        """
        self.ensure_one()
        if not lyd_per_invoice_currency or not invoice_currency:
            return False
        company_currency = (self.company_id or self.env.company).currency_id
        lyd = self.lyd_currency_id or self.env.ref('base.LYD', raise_if_not_found=False)
        if not company_currency or not lyd:
            return False
        if company_currency == invoice_currency:
            return 1.0
        if company_currency == lyd:
            # Odoo rate = invoice units per 1 LYD
            return 1.0 / lyd_per_invoice_currency
        # 1 company → LYD → invoice
        conv_date = self.date_start or fields.Date.context_today(self)
        company = self.company_id or self.env.company
        company_to_lyd = company_currency._convert(1.0, lyd, company, conv_date)
        if not company_to_lyd:
            return False
        return company_to_lyd / lyd_per_invoice_currency

    @api.onchange('currency_id', 'date_start', 'company_id')
    def _onchange_currency_exchange_rate(self):
        self.exchange_rate = self._get_suggested_exchange_rate()
        if self.currency_id and not self.invoice_currency_id:
            self.invoice_currency_id = self.currency_id
        if self.invoice_currency_id:
            self.invoice_exchange_rate = self._suggest_lyd_per_currency_rate(
                self.invoice_currency_id,
            )
        self._recompute_first_line_from_percent()

    @api.onchange('invoice_currency_id')
    def _onchange_invoice_currency_id_rate(self):
        if self.invoice_currency_id:
            self.invoice_exchange_rate = self._suggest_lyd_per_currency_rate(
                self.invoice_currency_id,
            )
        self._recompute_first_line_from_percent()

    @api.onchange('contract_value_currency', 'exchange_rate', 'invoice_currency_id', 'invoice_exchange_rate')
    def _onchange_recompute_percent_invoice_line(self):
        self._recompute_first_line_from_percent()

    @api.depends('contract_value_currency', 'exchange_rate')
    def _compute_contract_value_lyd(self):
        for contract in self:
            contract.contract_value_lyd = contract.contract_value_currency * (contract.exchange_rate or 0.0)

    @api.constrains('currency_split_ids')
    def _check_currency_split_total(self):
        usd = self.env.ref('base.USD', raise_if_not_found=False)
        lyd = self.env.ref('base.LYD', raise_if_not_found=False)
        for contract in self:
            if not contract.currency_split_ids:
                continue
            total = sum(contract.currency_split_ids.mapped('percentage'))
            if abs(total - 100.0) > 0.0001:
                raise ValidationError(_(
                    'Payment currency split must total 100%% (current total: %(total).2f%%).',
                    total=total,
                ))
            currency_ids = contract.currency_split_ids.mapped('currency_id')
            if len(currency_ids) != len(set(currency_ids.ids)):
                raise ValidationError(_(
                    'Each currency can appear only once in the payment split.',
                ))

    @api.depends('currency_split_ids.percentage')
    def _compute_currency_split_percentage_total(self):
        for contract in self:
            contract.currency_split_percentage_total = sum(
                contract.currency_split_ids.mapped('percentage')
            )

    @api.depends('contract_type')
    def _compute_tax_type_use(self):
        for contract in self:
            contract.tax_type_use = (
                'sale' if contract.contract_type == 'sale_contract' else 'purchase'
            )

    @api.depends('contract_line_ids.price_subtotal')
    def _compute_contract_lines_total(self):
        for contract in self:
            contract.contract_lines_total = sum(contract.contract_line_ids.mapped('price_subtotal'))

    @api.depends(
        'currency_split_ids',
        'currency_split_ids.percentage',
        'currency_split_ids.amount',
        'currency_split_ids.currency_id',
    )
    def _compute_legacy_currency_split_fields(self):
        usd_currency = self.env.ref('base.USD', raise_if_not_found=False)
        lyd_currency = self.env.ref('base.LYD', raise_if_not_found=False)
        for contract in self:
            contract.usd_amount = 0.0
            contract.lyd_amount = 0.0
            for line in contract.currency_split_ids:
                if usd_currency and line.currency_id == usd_currency:
                    contract.usd_amount = line.amount
                if lyd_currency and line.currency_id == lyd_currency:
                    contract.lyd_amount = line.amount

    def _prepare_currency_split_commands(self):
        """Return One2many commands to copy payment split lines to an invoice."""
        self.ensure_one()
        return [
            (0, 0, {
                'sequence': line.sequence,
                'currency_id': line.currency_id.id,
                'exchange_rate': line.exchange_rate or 1.0,
                'percentage': line.percentage,
            })
            for line in self.currency_split_ids
        ]

    def _prepare_invoice_line_commands(self):
        """Return One2many commands to copy contract lines to an invoice."""
        self.ensure_one()
        return [
            (0, 0, line._prepare_invoice_line_vals())
            for line in self.contract_line_ids
        ]

    def _clear_staging_invoice_lines(self):
        """Empty contract invoice lines after they were copied to an invoice."""
        for contract in self:
            if not contract.contract_line_ids:
                continue
            contract.contract_line_ids.unlink()
            contract.message_post(
                body=_(
                    'Invoice lines were cleared after creating an invoice. '
                    'Add new lines to prepare the next invoice.',
                ),
            )

    def _get_expiry_notification_users(self):
        """Responsible user plus optional expiry-notification group members."""
        self.ensure_one()
        users = (self.responsible_user_id | self.approval_user_id).filtered('active')
        group = self.env.ref(
            'rgb_contract_management.group_contract_expiry_notification',
            raise_if_not_found=False,
        )
        if group:
            users |= group.users.filtered('active')
        return users

    @api.depends(
        'reminder_contract_expiry_sent',
        'reminder_guarantee_10_sent',
        'reminder_guarantee_60_sent',
        'reminder_advance_payment_sent',
        'date_end',
        'performance_guarantee_expiry_date',
        'advance_payment_due_date',
        'state',
    )
    def _compute_reminder_alert(self):
        """Any active reminder → list/kanban highlight (primary type for badge)."""
        today = fields.Date.context_today(self)
        for contract in self:
            if contract.state not in ('approved', 'in_progress'):
                contract.reminder_alert = False
                contract.reminder_alert_type = False
                continue
            active = []
            if (
                contract.reminder_guarantee_10_sent
                and contract.performance_guarantee_expiry_date
                and contract.performance_guarantee_expiry_date >= today
            ):
                active.append('guarantee_10')
            if (
                contract.reminder_advance_payment_sent
                and contract.advance_payment_due_date
                and contract.advance_payment_due_date >= today
            ):
                active.append('advance_payment')
            if (
                contract.reminder_contract_expiry_sent
                and contract.date_end
                and contract.date_end >= today
            ):
                active.append('contract_expiry')
            if (
                contract.reminder_guarantee_60_sent
                and contract.performance_guarantee_expiry_date
                and contract.performance_guarantee_expiry_date >= today
            ):
                active.append('guarantee_60')
            contract.reminder_alert = bool(active)
            contract.reminder_alert_type = active[0] if active else False

    @api.depends(
        'reminder_contract_expiry_sent',
        'reminder_guarantee_10_sent',
        'reminder_guarantee_60_sent',
        'reminder_advance_payment_sent',
        'reminder_dismissed_guarantee_10',
        'reminder_dismissed_guarantee_60',
        'reminder_dismissed_contract_expiry',
        'reminder_dismissed_advance_payment',
        'date_end',
        'performance_guarantee_expiry_date',
        'advance_payment_due_date',
        'state',
    )
    def _compute_reminder_banners(self):
        today = fields.Date.context_today(self)
        for contract in self:
            in_force = contract.state in ('approved', 'in_progress')

            g10_active = bool(
                in_force
                and contract.reminder_guarantee_10_sent
                and contract.performance_guarantee_expiry_date
                and contract.performance_guarantee_expiry_date >= today
            )
            g60_active = bool(
                in_force
                and contract.reminder_guarantee_60_sent
                and contract.performance_guarantee_expiry_date
                and contract.performance_guarantee_expiry_date >= today
            )
            expiry_active = bool(
                in_force
                and contract.reminder_contract_expiry_sent
                and contract.date_end
                and contract.date_end >= today
            )
            advance_active = bool(
                in_force
                and contract.reminder_advance_payment_sent
                and contract.advance_payment_due_date
                and contract.advance_payment_due_date >= today
            )

            contract.alert_guarantee_10_active = g10_active
            contract.alert_guarantee_60_active = g60_active
            contract.alert_contract_expiry_active = expiry_active
            contract.alert_advance_payment_active = advance_active

            contract.alert_guarantee_10_visible = g10_active and not contract.reminder_dismissed_guarantee_10
            contract.alert_guarantee_60_visible = g60_active and not contract.reminder_dismissed_guarantee_60
            contract.alert_contract_expiry_visible = (
                expiry_active and not contract.reminder_dismissed_contract_expiry
            )
            contract.alert_advance_payment_visible = (
                advance_active and not contract.reminder_dismissed_advance_payment
            )

            contract.alert_guarantee_10_label = _(
                'Performance guarantee expires on %(date)s — action required',
                date=contract.performance_guarantee_expiry_date or '',
            ) if g10_active else False
            contract.alert_guarantee_60_label = _(
                'Performance guarantee expires on %(date)s — early reminder',
                date=contract.performance_guarantee_expiry_date or '',
            ) if g60_active else False
            contract.alert_contract_expiry_label = _(
                'Contract expires on %(date)s — action required',
                date=contract.date_end or '',
            ) if expiry_active else False
            contract.alert_advance_payment_label = _(
                'Advance payment due on %(date)s — action required',
                date=contract.advance_payment_due_date or '',
            ) if advance_active else False

            contract.has_hidden_reminder_alerts = bool(
                (g10_active and contract.reminder_dismissed_guarantee_10)
                or (g60_active and contract.reminder_dismissed_guarantee_60)
                or (expiry_active and contract.reminder_dismissed_contract_expiry)
                or (advance_active and contract.reminder_dismissed_advance_payment)
            )

    def action_hide_reminder_guarantee_10(self):
        self.write({'reminder_dismissed_guarantee_10': True})
        return True

    def action_hide_reminder_guarantee_60(self):
        self.write({'reminder_dismissed_guarantee_60': True})
        return True

    def action_hide_reminder_contract_expiry(self):
        self.write({'reminder_dismissed_contract_expiry': True})
        return True

    def action_hide_reminder_advance_payment(self):
        self.write({'reminder_dismissed_advance_payment': True})
        return True

    def action_show_reminder_alerts(self):
        """Re-display all previously hidden reminder banners."""
        self.write({
            'reminder_dismissed_guarantee_10': False,
            'reminder_dismissed_guarantee_60': False,
            'reminder_dismissed_contract_expiry': False,
            'reminder_dismissed_advance_payment': False,
        })
        return True

    @api.depends('advance_payment_percent', 'contract_value_currency')
    def _compute_advance_payment_amount(self):
        for contract in self:
            contract.advance_payment_amount = (
                (contract.contract_value_currency or 0.0)
                * (contract.advance_payment_percent or 0.0)
                / 100.0
            )

    def _notify_expiry_group(self, template_xmlid, summary, chatter_body, date_deadline):
        """Notify responsible (+ group): activity, inbox notification, email, chatter."""
        self.ensure_one()
        users = self._get_expiry_notification_users()
        if not users:
            _logger.warning(
                'No users to notify for contract reminder on %s', self.display_name,
            )
            return

        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        for user in users:
            existing = self.activity_ids.filtered(
                lambda a, u=user, s=summary: (
                    a.user_id == u
                    and a.summary == s
                    and a.activity_type_id == activity_type
                )
            ) if activity_type else self.env['mail.activity']
            if not existing:
                self.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=user.id,
                    summary=summary,
                    note=chatter_body,
                    date_deadline=date_deadline,
                )

        self.message_notify(
            partner_ids=users.partner_id.ids,
            subject=summary,
            body=chatter_body,
        )

        template = self.env.ref(template_xmlid, raise_if_not_found=False)
        emails = ','.join(filter(None, users.mapped('email')))
        if template and emails:
            template.send_mail(
                self.id,
                force_send=False,
                email_values={'email_to': emails},
            )

        self.message_post(
            body=chatter_body,
            partner_ids=users.partner_id.ids,
            message_type='notification',
            subtype_xmlid='mail.mt_note',
        )

    @api.model
    def _search_contracts_for_reminder(self, date_field, days_before, sent_field):
        """Catch-up safe: any date in [today, today+days_before] not yet reminded.

        If the cron misses the exact day (today+N), the next run still finds the
        contract while expiry is within the remaining window, then marks it sent.
        """
        today = fields.Date.context_today(self)
        window_end = today + timedelta(days=days_before)
        return self.search([
            (date_field, '>=', today),
            (date_field, '<=', window_end),
            (sent_field, '=', False),
            ('state', 'in', ('approved', 'in_progress')),
        ])

    @api.depends('date_end', 'date_start', 'service_duration_days', 'state')
    def _compute_remaining_days(self):
        today = fields.Date.context_today(self)
        for contract in self:
            end = contract.date_end
            if not end and contract.date_start and contract.service_duration_days:
                from datetime import timedelta
                end = contract.date_start + timedelta(days=contract.service_duration_days)
            if end:
                contract.remaining_days = (end - today).days
            else:
                contract.remaining_days = 0

    @api.depends('date_start', 'date_end')
    def _compute_service_duration_days(self):
        for contract in self:
            if contract.date_start and contract.date_end:
                contract.service_duration_days = (contract.date_end - contract.date_start).days
            else:
                contract.service_duration_days = 0

    @api.depends(
        'agreed_execution_date',
        'actual_execution_date',
        'delay_penalty_daily_rate',
        'delay_penalty_max_percent',
        'contract_value_currency',
    )
    def _compute_delay_penalty_amount(self):
        for contract in self:
            penalty = 0.0
            if (
                contract.agreed_execution_date
                and contract.actual_execution_date
                and contract.actual_execution_date > contract.agreed_execution_date
                and contract.contract_value_currency
            ):
                delay_days = (contract.actual_execution_date - contract.agreed_execution_date).days
                daily = contract.contract_value_currency * (contract.delay_penalty_daily_rate or 0.0) / 100.0
                penalty = delay_days * daily
                max_penalty = contract.contract_value_currency * (contract.delay_penalty_max_percent or 0.0) / 100.0
                if max_penalty:
                    penalty = min(penalty, max_penalty)
            contract.delay_penalty_amount = penalty

    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        for contract in self:
            contract.invoice_count = len(contract.invoice_ids)

    @api.depends(
        'invoice_ids',
        'invoice_ids.amount_total',
        'invoice_ids.amount_residual',
        'invoice_ids.state',
        'contract_value_currency',
        'contract_value_lyd',
    )
    def _compute_invoice_amounts(self):
        for contract in self:
            invoices = contract.invoice_ids.filtered(lambda m: m.state == 'posted')
            contract.total_invoiced_amount = sum(invoices.mapped('amount_total'))
            contract.paid_invoice_amount = sum(
                inv.amount_total - inv.amount_residual for inv in invoices
            )
            contract.unpaid_invoice_amount = sum(invoices.mapped('amount_residual'))
            if contract.contract_value_currency:
                contract.paid_percent_currency = (
                    contract.paid_invoice_amount / contract.contract_value_currency * 100.0
                )
            else:
                contract.paid_percent_currency = 0.0
            if contract.contract_value_lyd:
                contract.paid_percent_lyd = (
                    contract.paid_invoice_amount / contract.contract_value_lyd * 100.0
                )
            else:
                contract.paid_percent_lyd = 0.0

    # ── Constraints ──

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for contract in self:
            if contract.date_start and contract.date_end and contract.date_start > contract.date_end:
                raise ValidationError(_('End date must be after start date.'))

    # ── CRUD ──

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('rgb.contract') or _('New')
            if vals.get('contract_code'):
                vals['contract_code'] = vals['contract_code'].strip()
            if not vals.get('invoice_currency_id') and vals.get('currency_id'):
                vals['invoice_currency_id'] = vals['currency_id']
        contracts = super().create(vals_list)
        for contract in contracts.filtered(lambda c: not c.invoice_currency_id and c.currency_id):
            contract.invoice_currency_id = contract.currency_id
        contracts._link_attachments()
        return contracts

    def init(self):
        """Backfill invoice currency from contract currency on upgrade."""
        self.env.cr.execute("""
            UPDATE rgb_contract
               SET invoice_currency_id = currency_id
             WHERE invoice_currency_id IS NULL
               AND currency_id IS NOT NULL
        """)

    def write(self, vals):
        if vals.get('contract_code'):
            vals['contract_code'] = vals['contract_code'].strip()
        # Block edits on locked contracts except unlocking / chatter-safe fields.
        if not self.env.su and self.filtered(lambda c: c.state == 'done_locked'):
            allowed_keys = {
                'state',
                'message_main_attachment_id',
                'activity_ids',
                'message_follower_ids',
            }
            if set(vals) - allowed_keys:
                raise UserError(_(
                    'This contract is Done Locked. Only users with Unlock permission '
                    'can change the status back to Done Unlocked.'
                ))
            if 'state' in vals and vals['state'] != 'done':
                raise UserError(_(
                    'A locked contract can only be moved back to Done Unlocked.'
                ))
            if 'state' in vals:
                self._check_stage_group(
                    'rgb_contract_management.group_contract_stage_unlock',
                    _('Unlock Done'),
                )
        # Reset reminder flags when the related date changes so a new window can fire.
        if 'date_end' in vals:
            vals['reminder_contract_expiry_sent'] = False
        if 'performance_guarantee_expiry_date' in vals:
            vals['reminder_guarantee_10_sent'] = False
            vals['reminder_guarantee_60_sent'] = False
        if 'advance_payment_due_date' in vals:
            vals['reminder_advance_payment_sent'] = False
        res = super().write(vals)
        if any(k in vals for k in (
            'insurance_attachment_ids',
            'performance_guarantee_attachment_ids',
            'bank_guarantee_attachment_ids',
        )):
            self._link_attachments()
        if {
            'contract_value_currency',
            'exchange_rate',
            'invoice_currency_id',
            'currency_id',
        } & set(vals):
            self._recompute_first_line_from_percent()
        return res

    def _recompute_first_line_from_percent(self):
        """Refresh first invoice line unit price when contract value/FX changes."""
        for contract in self:
            first = contract.contract_line_ids[:1]
            if first and first.contract_value_percent:
                first._apply_contract_value_percent_price()
                first.filtered(lambda l: l.line_role == 'normal')._sync_linked_deduction_lines()

    def _link_attachments(self):
        for contract in self:
            attachments = (
                contract.insurance_attachment_ids
                | contract.performance_guarantee_attachment_ids
                | contract.bank_guarantee_attachment_ids
            )
            attachments.filtered(
                lambda a: a.res_model != 'rgb.contract' or a.res_id != contract.id
            ).write({'res_model': 'rgb.contract', 'res_id': contract.id})

    # ── Business helpers ──

    def _has_insurance_pdf(self):
        self.ensure_one()
        return bool(self.insurance_attachment_ids.filtered(
            lambda a: (a.mimetype or '').lower() == 'application/pdf'
            or (a.name or '').lower().endswith('.pdf')
        ))

    def _check_insurance_for_activation(self):
        for contract in self:
            if not contract._has_insurance_pdf():
                raise UserError(
                    _('Cannot proceed: upload at least one insurance document (PDF) for contract %s.')
                    % contract.name
                )

    def _check_invoice_contract_limit(self, invoice_amount=0.0):
        self.ensure_one()
        if self.allow_over_contract_value or not self.contract_value_currency:
            return
        projected = self.total_invoiced_amount + invoice_amount
        max_value = self.contract_value_currency * (1 + (self.contract_amendment_percent or 0) / 100.0)
        if projected > max_value:
            raise UserError(
                _('Total invoiced amount (%(total)s) would exceed the contract limit (%(limit)s).')
                % {'total': projected, 'limit': max_value}
            )

    def _is_approver(self):
        self.ensure_one()
        user = self.env.user
        return (
            user.has_group('rgb_contract_management.group_contract_manager')
            or user == self.approval_user_id
            or user.has_group('rgb_contract_management.group_contract_approver')
        )

    def _send_approval_request(self):
        template = self.env.ref(
            'rgb_contract_management.mail_template_contract_approval',
            raise_if_not_found=False,
        )
        for contract in self:
            if not contract.approval_user_id:
                continue
            if template:
                template.send_mail(contract.id, force_send=False)
            contract.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=contract.approval_user_id.id,
                summary=_('Contract approval required: %s') % contract.name,
            )

    # ── Workflow actions ──

    def _check_stage_group(self, group_xmlid, action_label):
        if self.env.su:
            return
        if not self.env.user.has_group(group_xmlid):
            raise UserError(_(
                'You are not allowed to perform "%(action)s". Missing security group.',
                action=action_label,
            ))

    def _ensure_not_locked(self):
        locked = self.filtered(lambda c: c.state == 'done_locked')
        if locked:
            raise UserError(_(
                'Contract(s) %(names)s are locked (Done Locked). Unlock them first.',
                names=', '.join(locked.mapped('name')),
            ))

    def action_confirm(self):
        self._check_stage_group(
            'rgb_contract_management.group_contract_stage_confirm',
            _('Confirm'),
        )
        for contract in self.filtered(lambda c: c.state == 'draft'):
            if not contract.approval_user_id:
                raise UserError(_('Set an approval responsible before confirming the contract.'))
            contract.write({'state': 'under_approval'})
            contract.message_post(body=_('Contract submitted for approval.'))
            contract._send_approval_request()
        return True

    def action_approve(self):
        self._check_stage_group(
            'rgb_contract_management.group_contract_stage_approve',
            _('Approve'),
        )
        for contract in self.filtered(lambda c: c.state == 'under_approval'):
            if not contract._is_approver():
                raise UserError(_('You are not allowed to approve this contract.'))
            contract.write({'state': 'approved'})
            contract.message_post(body=_('Contract approved.'))
        return True

    def action_set_in_progress(self):
        self._check_stage_group(
            'rgb_contract_management.group_contract_stage_start',
            _('Start'),
        )
        for contract in self.filtered(lambda c: c.state == 'approved'):
            contract._check_insurance_for_activation()
            contract.write({'state': 'in_progress'})
            contract.message_post(body=_('Contract set to in progress.'))
        return True

    def action_done(self):
        self._check_stage_group(
            'rgb_contract_management.group_contract_stage_done',
            _('Done Unlocked'),
        )
        self.filtered(lambda c: c.state == 'in_progress').write({'state': 'done'})
        return True

    def action_lock_done(self):
        """Move Done Unlocked → Done Locked."""
        self._check_stage_group(
            'rgb_contract_management.group_contract_stage_lock',
            _('Lock Done'),
        )
        contracts = self.filtered(lambda c: c.state == 'done')
        contracts.write({'state': 'done_locked'})
        for contract in contracts:
            contract.message_post(body=_('Contract locked (Done Locked).'))
        return True

    def action_unlock_done(self):
        """Move Done Locked → Done Unlocked."""
        self._check_stage_group(
            'rgb_contract_management.group_contract_stage_unlock',
            _('Unlock Done'),
        )
        contracts = self.filtered(lambda c: c.state == 'done_locked')
        contracts.write({'state': 'done'})
        for contract in contracts:
            contract.message_post(body=_('Contract unlocked (Done Unlocked).'))
        return True

    def action_cancel(self):
        self._check_stage_group(
            'rgb_contract_management.group_contract_stage_cancel',
            _('Cancel'),
        )
        self._ensure_not_locked()
        cancellable = self.filtered(
            lambda c: c.state not in ('done', 'done_locked', 'cancelled', 'expired')
        )
        cancellable.write({'state': 'cancelled'})
        return True

    def action_reset_to_draft(self):
        self._check_stage_group(
            'rgb_contract_management.group_contract_stage_reset',
            _('Reset to Draft'),
        )
        self.filtered(lambda c: c.state in ('under_approval', 'cancelled')).write({'state': 'draft'})
        return True

    def action_expire(self):
        self._check_stage_group(
            'rgb_contract_management.group_contract_stage_expire',
            _('Mark Expired'),
        )
        self._ensure_not_locked()
        self.filtered(
            lambda c: c.state not in ('done', 'done_locked', 'cancelled', 'expired')
        ).write({'state': 'expired'})
        return True

    def action_view_invoices(self):
        self.ensure_one()
        return {
            'name': _('Contract Invoices'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': self._prepare_invoice_context(),
        }

    def action_create_invoice(self):
        self.ensure_one()
        self._check_insurance_for_activation()
        return {
            'name': _('Create Invoice'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'target': 'current',
            'context': self._prepare_invoice_context(),
        }

    def _get_analytic_distribution(self):
        self.ensure_one()
        if self.analytic_account_id:
            return {str(self.analytic_account_id.id): 100}
        return {}

    def _get_invoice_currency(self):
        """Currency for the next invoice created from staged lines."""
        self.ensure_one()
        return self.invoice_currency_id or self.currency_id

    def _prepare_invoice_context(self):
        """Default values passed when opening/creating invoices from this contract."""
        self.ensure_one()
        move_type = 'in_invoice' if self.contract_type == 'purchase_contract' else 'out_invoice'
        invoice_currency = self._get_invoice_currency()
        odoo_rate = self._to_odoo_invoice_currency_rate(
            self.invoice_exchange_rate, invoice_currency,
        )
        context = {
            'default_contract_id': self.id,
            'default_partner_id': self.partner_id.id,
            'default_move_type': move_type,
            'default_currency_id': invoice_currency.id if invoice_currency else False,
            'default_invoice_date': fields.Date.context_today(self),
            'default_analytic_distribution': self._get_analytic_distribution(),
            'default_contract_manual_exchange_rate': self.invoice_exchange_rate or 0.0,
        }
        if odoo_rate:
            context['default_invoice_currency_rate'] = odoo_rate
        if self.contract_line_ids:
            context['default_invoice_line_ids'] = self._prepare_invoice_line_commands()
        return context

    @api.onchange('contract_type')
    def _onchange_contract_type(self):
        if self.contract_type == 'sale_contract':
            self.partner_id = False
        elif self.contract_type == 'purchase_contract':
            self.partner_id = False

    @api.onchange('partner_id', 'contract_type')
    def _onchange_partner_pricelist(self):
        if self.contract_type == 'sale_contract' and self.partner_id:
            self.price_list_id = self.partner_id.property_product_pricelist

    @api.model
    def _cron_performance_guarantee_group_reminder(self):
        """Daily: notify when ≤10 days remain until performance guarantee expiry."""
        contracts = self._search_contracts_for_reminder(
            'performance_guarantee_expiry_date', 10, 'reminder_guarantee_10_sent',
        )
        for contract in contracts:
            remaining = (contract.performance_guarantee_expiry_date - fields.Date.context_today(self)).days
            contract.write({
                'reminder_guarantee_10_sent': True,
                'reminder_dismissed_guarantee_10': False,
            })
            contract._notify_expiry_group(
                'rgb_contract_management.mail_template_performance_guarantee_group_expiry',
                summary=_('Performance guarantee expires in %(days)s days: %(name)s') % {
                    'days': remaining,
                    'name': contract.name,
                },
                chatter_body=_(
                    'Performance guarantee expiry reminder: guarantee for this contract '
                    'expires on %(date)s (%(days)s day(s) remaining).',
                    date=contract.performance_guarantee_expiry_date,
                    days=remaining,
                ),
                date_deadline=contract.performance_guarantee_expiry_date,
            )

    @api.model
    def _cron_performance_guarantee_reminder(self):
        """Daily: notify when ≤60 days remain until performance guarantee expiry."""
        contracts = self._search_contracts_for_reminder(
            'performance_guarantee_expiry_date', 60, 'reminder_guarantee_60_sent',
        )
        for contract in contracts:
            remaining = (contract.performance_guarantee_expiry_date - fields.Date.context_today(self)).days
            contract.write({
                'reminder_guarantee_60_sent': True,
                'reminder_dismissed_guarantee_60': False,
            })
            contract._notify_expiry_group(
                'rgb_contract_management.mail_template_guarantee_expiry',
                summary=_('Performance guarantee expires in %(days)s days: %(name)s') % {
                    'days': remaining,
                    'name': contract.name,
                },
                chatter_body=_(
                    'Performance guarantee early reminder: guarantee for this contract '
                    'expires on %(date)s (%(days)s day(s) remaining).',
                    date=contract.performance_guarantee_expiry_date,
                    days=remaining,
                ),
                date_deadline=contract.performance_guarantee_expiry_date,
            )

    @api.model
    def _cron_contract_expiry_reminder(self):
        """Daily: notify when ≤10 days remain until contract end date."""
        contracts = self._search_contracts_for_reminder(
            'date_end', 10, 'reminder_contract_expiry_sent',
        )
        for contract in contracts:
            remaining = (contract.date_end - fields.Date.context_today(self)).days
            contract.write({
                'reminder_contract_expiry_sent': True,
                'reminder_dismissed_contract_expiry': False,
            })
            contract._notify_expiry_group(
                'rgb_contract_management.mail_template_contract_expiry',
                summary=_('Contract expires in %(days)s days: %(name)s') % {
                    'days': remaining,
                    'name': contract.name,
                },
                chatter_body=_(
                    'Contract expiry reminder: this contract ends on %(date)s '
                    '(%(days)s day(s) remaining).',
                    date=contract.date_end,
                    days=remaining,
                ),
                date_deadline=contract.date_end,
            )

    @api.model
    def _cron_advance_payment_reminder(self):
        """Daily: notify when ≤10 days remain until advance payment due date."""
        contracts = self._search_contracts_for_reminder(
            'advance_payment_due_date', 10, 'reminder_advance_payment_sent',
        )
        for contract in contracts:
            remaining = (contract.advance_payment_due_date - fields.Date.context_today(self)).days
            contract.write({
                'reminder_advance_payment_sent': True,
                'reminder_dismissed_advance_payment': False,
            })
            contract._notify_expiry_group(
                'rgb_contract_management.mail_template_advance_payment_due',
                summary=_('Advance payment due in %(days)s days: %(name)s') % {
                    'days': remaining,
                    'name': contract.name,
                },
                chatter_body=_(
                    'Advance payment reminder: due on %(date)s '
                    '(%(days)s day(s) remaining). Amount: %(amount)s %(currency)s.',
                    date=contract.advance_payment_due_date,
                    days=remaining,
                    amount=contract.advance_payment_amount,
                    currency=contract.currency_id.name if contract.currency_id else '',
                ),
                date_deadline=contract.advance_payment_due_date,
            )
