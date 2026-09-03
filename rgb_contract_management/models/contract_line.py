# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class RgbContractLine(models.Model):
    _name = 'rgb.contract.line'
    _description = 'Contract Invoice Line'
    _order = 'sequence, id'

    contract_id = fields.Many2one(
        'rgb.contract',
        string='Contract',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    line_role = fields.Selection(
        selection=[
            ('normal', 'Normal'),
            ('advance_payment', 'Advance Payment'),
            ('retention_guarantee', 'Retention Guarantee'),
            ('performance_guarantee', 'Performance Guarantee'),
        ],
        string='Line Role',
        default='normal',
        required=True,
    )
    source_line_id = fields.Many2one(
        'rgb.contract.line',
        string='Source Line',
        ondelete='cascade',
        copy=False,
    )
    advance_payment_line_id = fields.Many2one(
        'rgb.contract.line',
        string='Advance Payment Line',
        copy=False,
        ondelete='set null',
    )
    retention_guarantee_line_id = fields.Many2one(
        'rgb.contract.line',
        string='Retention Guarantee Line',
        copy=False,
        ondelete='set null',
    )
    performance_guarantee_line_id = fields.Many2one(
        'rgb.contract.line',
        string='Performance Guarantee Line',
        copy=False,
        ondelete='set null',
    )
    show_advance_button = fields.Boolean(compute='_compute_button_visibility')
    show_retention_button = fields.Boolean(compute='_compute_button_visibility')
    show_performance_button = fields.Boolean(compute='_compute_button_visibility')
    is_first_invoice_line = fields.Boolean(
        string='First Invoice Line',
        compute='_compute_is_first_invoice_line',
    )
    contract_value_percent = fields.Float(
        string='Contract Value %',
        digits=(16, 4),
        help='Only on the first line: price = this %% of contract value (LYD), '
             'converted to the invoice lines currency using the contract exchange rate.',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
    )
    name = fields.Text(string='Description', required=True)
    quantity = fields.Float(
        string='Quantity',
        default=1.0,
        digits='Product Unit of Measure',
    )
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
    )
    price_unit = fields.Float(
        string='Unit Price',
        digits='Product Price',
    )
    discount = fields.Float(
        string='Discount (%)',
        digits='Discount',
        default=0.0,
    )
    tax_ids = fields.Many2many(
        'account.tax',
        string='Taxes',
        check_company=True,
        domain="[('type_tax_use', '=?', parent.tax_type_use), ('company_id', 'parent_of', parent.company_id)]",
    )
    account_id = fields.Many2one(
        'account.account',
        string='Account',
        check_company=True,
        domain="[('deprecated', '=', False)]",
    )
    price_subtotal = fields.Monetary(
        string='Subtotal',
        currency_field='currency_id',
        compute='_compute_amount',
        store=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        compute='_compute_currency_id',
        store=True,
    )
    company_id = fields.Many2one(
        related='contract_id.company_id',
        store=True,
    )
    tax_type_use = fields.Selection(
        related='contract_id.tax_type_use',
    )

    @api.depends('contract_id.invoice_currency_id', 'contract_id.currency_id')
    def _compute_currency_id(self):
        for line in self:
            line.currency_id = (
                line.contract_id.invoice_currency_id
                or line.contract_id.currency_id
            )

    @api.depends(
        'contract_id',
        'contract_id.contract_line_ids',
        'contract_id.contract_line_ids.sequence',
        'sequence',
    )
    def _compute_is_first_invoice_line(self):
        for line in self:
            if not line.contract_id:
                line.is_first_invoice_line = False
                continue
            first = line.contract_id.contract_line_ids[:1]
            line.is_first_invoice_line = bool(first and first == line)

    def _get_price_from_contract_percent(self):
        """LYD share of contract value, converted to invoice lines currency."""
        self.ensure_one()
        contract = self.contract_id
        percent = self.contract_value_percent or 0.0
        if not percent:
            return 0.0
        lyd_amount = (contract.contract_value_lyd or 0.0) * percent / 100.0
        target = contract.invoice_currency_id or contract.currency_id
        lyd = contract.lyd_currency_id or self.env.ref('base.LYD', raise_if_not_found=False)
        if not target or not lyd or target == lyd:
            return lyd_amount
        # Prefer manual invoice exchange rate (LYD per 1 invoice currency).
        if contract.invoice_exchange_rate:
            return lyd_amount / contract.invoice_exchange_rate
        if target == contract.currency_id and contract.exchange_rate:
            return lyd_amount / contract.exchange_rate
        company = contract.company_id or self.env.company
        conv_date = contract.date_start or fields.Date.context_today(self)
        return lyd._convert(lyd_amount, target, company, conv_date)

    def _apply_contract_value_percent_price(self):
        for line in self:
            if not line.contract_value_percent or not line.contract_id:
                continue
            first = line.contract_id.contract_line_ids[:1]
            if first and first != line:
                continue
            line.price_unit = line._get_price_from_contract_percent()
            if not line.quantity:
                line.quantity = 1.0

    @api.onchange('contract_value_percent')
    def _onchange_contract_value_percent(self):
        if self.contract_value_percent and not self.is_first_invoice_line:
            # Allow setting on empty first row in the editor
            siblings = self.contract_id.contract_line_ids if self.contract_id else self
            if siblings and siblings[0] != self:
                self.contract_value_percent = 0.0
                return
        if self.contract_value_percent:
            self._apply_contract_value_percent_price()
            if self.line_role == 'normal':
                self._sync_linked_deduction_lines()

    @api.constrains('contract_value_percent')
    def _check_contract_value_percent_first_line(self):
        for line in self.filtered('contract_value_percent'):
            first = line.contract_id.contract_line_ids[:1]
            if first and first != line:
                raise UserError(_(
                    'Contract Value %% can only be set on the first invoice line.'
                ))

    @api.depends('quantity', 'price_unit', 'discount', 'tax_ids', 'currency_id')
    def _compute_amount(self):
        for line in self:
            subtotal = line.quantity * line.price_unit * (1 - (line.discount or 0.0) / 100.0)
            line.price_subtotal = subtotal

    @api.depends(
        'line_role',
        'product_id',
        'product_id.product_tmpl_id.is_contract_advance_payment',
        'product_id.product_tmpl_id.is_contract_retention_guarantee',
        'product_id.product_tmpl_id.is_contract_performance_guarantee',
        'advance_payment_line_id',
        'retention_guarantee_line_id',
        'performance_guarantee_line_id',
        'contract_id.without_advance_payment',
    )
    def _compute_button_visibility(self):
        for line in self:
            is_deduction = line._is_deduction_line()
            line.show_advance_button = (
                not is_deduction
                and not line.advance_payment_line_id
                and not line.contract_id.without_advance_payment
            )
            line.show_retention_button = not is_deduction and not line.retention_guarantee_line_id
            line.show_performance_button = not is_deduction and not line.performance_guarantee_line_id

    def _is_deduction_line(self):
        self.ensure_one()
        if self.line_role in ('advance_payment', 'retention_guarantee', 'performance_guarantee'):
            return True
        template = self.product_id.product_tmpl_id
        if not template:
            return False
        return (
            template.is_contract_advance_payment
            or template.is_contract_retention_guarantee
            or template.is_contract_performance_guarantee
        )

    def _get_deduction_percent(self, deduction):
        product = deduction.product_id
        template = product.product_tmpl_id
        if deduction.line_role == 'advance_payment':
            return template.contract_advance_payment_percent
        if deduction.line_role == 'retention_guarantee':
            return template.contract_retention_percent
        return template.contract_performance_guarantee_percent

    def _get_line_base_amount(self):
        """Line subtotal excluding tax."""
        self.ensure_one()
        return self.quantity * self.price_unit * (1 - (self.discount or 0.0) / 100.0)

    @api.model
    def _get_contract_advance_payment_product(self):
        product = self.env['product.product'].search([
            ('product_tmpl_id.is_contract_advance_payment', '=', True),
        ], limit=1)
        if not product:
            raise UserError(_(
                'No advance payment product is configured. '
                'Mark exactly one product as "Contract Advance Payment".'
            ))
        return product

    @api.model
    def _get_contract_retention_product(self):
        product = self.env['product.product'].search([
            ('product_tmpl_id.is_contract_retention_guarantee', '=', True),
        ], limit=1)
        if not product:
            raise UserError(_(
                'No retention guarantee product is configured. '
                'Mark exactly one product as "Contract Retention Guarantee".'
            ))
        return product

    @api.model
    def _get_contract_performance_product(self):
        product = self.env['product.product'].search([
            ('product_tmpl_id.is_contract_performance_guarantee', '=', True),
        ], limit=1)
        if not product:
            raise UserError(_(
                'No performance guarantee product is configured. '
                'Mark exactly one product as "Contract Performance Guarantee".'
            ))
        return product

    def _deduction_description(self, product, percent):
        self.ensure_one()
        return _(
            '%(product)s (%(percent).2f%% of %(line_name)s)',
            product=product.display_name,
            percent=percent,
            line_name=self.name,
        )

    def _sync_one_deduction(self, deduction, base_amount):
        self.ensure_one()
        percent = self._get_deduction_percent(deduction)
        product = deduction.product_id
        vals = {
            'price_unit': base_amount * (percent / 100.0) if base_amount > 0 else 0.0,
            'name': self._deduction_description(product, percent),
        }
        if deduction.id:
            deduction.write(vals)
        else:
            deduction.price_unit = vals['price_unit']
            deduction.name = vals['name']

    def _sync_linked_deduction_lines(self):
        """Recalculate linked deduction lines from the parent line subtotal."""
        for line in self.filtered(lambda l: l.line_role == 'normal'):
            base_amount = line._get_line_base_amount()
            if line.advance_payment_line_id:
                line._sync_one_deduction(line.advance_payment_line_id, base_amount)
            if line.retention_guarantee_line_id:
                line._sync_one_deduction(line.retention_guarantee_line_id, base_amount)
            if line.performance_guarantee_line_id:
                line._sync_one_deduction(line.performance_guarantee_line_id, base_amount)

    def _prepare_deduction_line_vals(self, product, percent, line_role):
        self.ensure_one()
        base_amount = self._get_line_base_amount()
        if base_amount <= 0.0:
            raise UserError(_(
                'Cannot add a deduction on line "%(line)s" with zero or negative subtotal.',
                line=self.name,
            ))
        return {
            'contract_id': self.contract_id.id,
            'sequence': self.sequence + 1,
            'line_role': line_role,
            'source_line_id': self.id,
            'product_id': product.id,
            'name': self._deduction_description(product, percent),
            'quantity': -1.0,
            'price_unit': base_amount * (percent / 100.0),
            'discount': 0.0,
            'product_uom_id': product.uom_id.id,
            'tax_ids': [(5, 0, 0)],
        }

    def action_add_advance_payment(self):
        for line in self:
            if line.contract_id.without_advance_payment:
                raise UserError(_(
                    'This contract is marked as without advance payment.'
                ))
            if line.advance_payment_line_id:
                raise UserError(_(
                    'Advance payment was already added for line "%(line)s".',
                    line=line.name,
                ))
            if line._is_deduction_line():
                raise UserError(_('Advance payment cannot be added on deduction lines.'))
            product = line._get_contract_advance_payment_product()
            percent = product.product_tmpl_id.contract_advance_payment_percent
            deduction = line.create(line._prepare_deduction_line_vals(
                product,
                percent,
                'advance_payment',
            ))
            line.advance_payment_line_id = deduction.id
        return True

    def action_add_retention_guarantee(self):
        for line in self:
            if line.retention_guarantee_line_id:
                raise UserError(_(
                    'Retention guarantee was already added for line "%(line)s".',
                    line=line.name,
                ))
            if line._is_deduction_line():
                raise UserError(_('Retention guarantee cannot be added on deduction lines.'))
            product = line._get_contract_retention_product()
            percent = product.product_tmpl_id.contract_retention_percent
            deduction = line.create(line._prepare_deduction_line_vals(
                product,
                percent,
                'retention_guarantee',
            ))
            line.retention_guarantee_line_id = deduction.id
        return True

    def action_add_performance_guarantee(self):
        for line in self:
            if line.performance_guarantee_line_id:
                raise UserError(_(
                    'Performance guarantee was already added for line "%(line)s".',
                    line=line.name,
                ))
            if line._is_deduction_line():
                raise UserError(_('Performance guarantee cannot be added on deduction lines.'))
            product = line._get_contract_performance_product()
            percent = product.product_tmpl_id.contract_performance_guarantee_percent
            deduction = line.create(line._prepare_deduction_line_vals(
                product,
                percent,
                'performance_guarantee',
            ))
            line.performance_guarantee_line_id = deduction.id
        return True

    def write(self, vals):
        res = super().write(vals)
        if 'contract_value_percent' in vals:
            self.filtered('contract_value_percent')._apply_contract_value_percent_price()
            self.filtered(lambda l: l.line_role == 'normal')._sync_linked_deduction_lines()
        elif {'quantity', 'price_unit', 'discount', 'name'} & set(vals):
            self.filtered(lambda l: l.line_role == 'normal')._sync_linked_deduction_lines()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        percent_lines = lines.filtered('contract_value_percent')
        if percent_lines:
            percent_lines._apply_contract_value_percent_price()
        lines.filtered(lambda l: l.line_role == 'normal')._sync_linked_deduction_lines()
        return lines

    @api.onchange('quantity', 'price_unit', 'discount', 'name')
    def _onchange_sync_deduction_lines(self):
        self._sync_linked_deduction_lines()

    def unlink(self):
        links_to_clear = []
        for line in self:
            if not line.source_line_id:
                continue
            parent = line.source_line_id
            if parent.advance_payment_line_id == line:
                links_to_clear.append((parent, 'advance_payment_line_id'))
            if parent.retention_guarantee_line_id == line:
                links_to_clear.append((parent, 'retention_guarantee_line_id'))
            if parent.performance_guarantee_line_id == line:
                links_to_clear.append((parent, 'performance_guarantee_line_id'))
        res = super().unlink()
        for parent, field_name in links_to_clear:
            if parent.exists():
                parent.write({field_name: False})
        return res

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if not self.product_id:
            return
        contract = self.contract_id
        product = self.product_id
        template = product.product_tmpl_id
        self.product_uom_id = product.uom_id
        if template.is_contract_advance_payment or template.is_contract_retention_guarantee or template.is_contract_performance_guarantee:
            self.tax_ids = [(5, 0, 0)]
            self.name = product.display_name
            self.price_unit = 0.0
            return
        if contract.contract_type == 'sale_contract':
            self.name = product.get_product_multiline_description_sale() or product.display_name
            if not self.contract_value_percent:
                if contract.price_list_id:
                    self.price_unit = contract.price_list_id._get_product_price(
                        product,
                        self.quantity or 1.0,
                    )
                else:
                    self.price_unit = product.lst_price
            self.tax_ids = product.taxes_id.filtered(
                lambda tax: tax.company_id == contract.company_id
            )
        else:
            self.name = product.display_name
            if not self.contract_value_percent:
                self.price_unit = product.standard_price
            self.tax_ids = product.supplier_taxes_id.filtered(
                lambda tax: tax.company_id == contract.company_id
            )
        if self.contract_value_percent:
            self._apply_contract_value_percent_price()
        if self.line_role == 'normal':
            self._sync_linked_deduction_lines()

    def _get_invoice_account(self):
        self.ensure_one()
        if self.account_id:
            return self.account_id
        product = self.product_id
        contract = self.contract_id
        if not product:
            return self.env['account.account']
        if contract.contract_type == 'sale_contract':
            account = product.property_account_income_id or product.categ_id.property_account_income_categ_id
        else:
            account = product.property_account_expense_id or product.categ_id.property_account_expense_categ_id
        return account

    def _get_invoice_taxes(self):
        self.ensure_one()
        if self.line_role in ('advance_payment', 'retention_guarantee', 'performance_guarantee'):
            return self.env['account.tax']
        template = self.product_id.product_tmpl_id
        if template and (
            template.is_contract_advance_payment
            or template.is_contract_retention_guarantee
            or template.is_contract_performance_guarantee
        ):
            return self.env['account.tax']
        if self.tax_ids:
            return self.tax_ids
        product = self.product_id
        contract = self.contract_id
        if not product:
            return self.env['account.tax']
        if contract.contract_type == 'sale_contract':
            return product.taxes_id.filtered(lambda tax: tax.company_id == contract.company_id)
        return product.supplier_taxes_id.filtered(lambda tax: tax.company_id == contract.company_id)

    def _prepare_invoice_line_vals(self):
        self.ensure_one()
        contract = self.contract_id
        distribution = contract._get_analytic_distribution()
        account = self._get_invoice_account()
        taxes = self._get_invoice_taxes()
        vals = {
            'sequence': self.sequence,
            'name': self.name,
            'quantity': self.quantity,
            'price_unit': self.price_unit,
            'discount': self.discount,
            'tax_ids': [(6, 0, taxes.ids)],
        }
        if self.product_id:
            vals['product_id'] = self.product_id.id
            vals['product_uom_id'] = (self.product_uom_id or self.product_id.uom_id).id
        if account:
            vals['account_id'] = account.id
        if distribution:
            vals['analytic_distribution'] = distribution
        return vals
