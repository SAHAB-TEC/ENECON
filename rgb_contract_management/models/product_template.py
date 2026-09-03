# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_contract_advance_payment = fields.Boolean(
        string='Contract Advance Payment',
        help='Mark this product as the unique advance payment deduction line for contracts.',
    )
    contract_advance_payment_percent = fields.Float(
        string='Advance Payment (%)',
        digits=(16, 4),
        default=15.0,
        help='Percentage of the contract line subtotal (excl. tax) used when adding advance payment.',
    )
    is_contract_retention_guarantee = fields.Boolean(
        string='Contract Retention Guarantee',
        help='Mark this product as the unique retention guarantee deduction line for contracts.',
    )
    contract_retention_percent = fields.Float(
        string='Retention (%)',
        digits=(16, 4),
        default=10.0,
        help='Percentage of the contract line subtotal (excl. tax) used when adding retention guarantee.',
    )
    is_contract_performance_guarantee = fields.Boolean(
        string='Contract Performance Guarantee',
        help='Mark this product as the unique performance guarantee deduction line for contracts.',
    )
    contract_performance_guarantee_percent = fields.Float(
        string='Performance Guarantee (%)',
        digits=(16, 4),
        default=5.0,
        help='Percentage of the contract line subtotal (excl. tax) used when adding performance guarantee.',
    )

    @api.constrains('is_contract_advance_payment')
    def _check_unique_advance_payment_product(self):
        for template in self.filtered('is_contract_advance_payment'):
            duplicate = self.search([
                ('is_contract_advance_payment', '=', True),
                ('id', '!=', template.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'Only one product can be marked as contract advance payment. '
                    'It is already set on "%(product)s".',
                    product=duplicate.display_name,
                ))

    @api.constrains('is_contract_retention_guarantee')
    def _check_unique_retention_product(self):
        for template in self.filtered('is_contract_retention_guarantee'):
            duplicate = self.search([
                ('is_contract_retention_guarantee', '=', True),
                ('id', '!=', template.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'Only one product can be marked as contract retention guarantee. '
                    'It is already set on "%(product)s".',
                    product=duplicate.display_name,
                ))

    @api.constrains('contract_advance_payment_percent', 'is_contract_advance_payment')
    def _check_advance_payment_percent(self):
        for template in self.filtered('is_contract_advance_payment'):
            if template.contract_advance_payment_percent <= 0.0:
                raise ValidationError(_(
                    'Advance payment percentage must be greater than zero on "%(product)s".',
                    product=template.display_name,
                ))

    @api.constrains('contract_retention_percent', 'is_contract_retention_guarantee')
    def _check_retention_percent(self):
        for template in self.filtered('is_contract_retention_guarantee'):
            if template.contract_retention_percent <= 0.0:
                raise ValidationError(_(
                    'Retention percentage must be greater than zero on "%(product)s".',
                    product=template.display_name,
                ))

    @api.constrains('is_contract_performance_guarantee')
    def _check_unique_performance_guarantee_product(self):
        for template in self.filtered('is_contract_performance_guarantee'):
            duplicate = self.search([
                ('is_contract_performance_guarantee', '=', True),
                ('id', '!=', template.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'Only one product can be marked as contract performance guarantee. '
                    'It is already set on "%(product)s".',
                    product=duplicate.display_name,
                ))

    @api.constrains('contract_performance_guarantee_percent', 'is_contract_performance_guarantee')
    def _check_performance_guarantee_percent(self):
        for template in self.filtered('is_contract_performance_guarantee'):
            if template.contract_performance_guarantee_percent <= 0.0:
                raise ValidationError(_(
                    'Performance guarantee percentage must be greater than zero on "%(product)s".',
                    product=template.display_name,
                ))
