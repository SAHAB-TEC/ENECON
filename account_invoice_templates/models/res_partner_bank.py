# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    ait_print_instruction = fields.Char(
        string="Payment Instruction (EN)",
        help="Printed on the invoice, e.g. Please make payment in USD to:",
    )
    ait_print_instruction_ar = fields.Char(
        string="Payment Instruction (AR)",
        help="Arabic payment instruction printed next to the English text.",
    )
    ait_print_bank_name = fields.Char(string="Bank Name (EN)")
    ait_print_bank_name_ar = fields.Char(string="Bank Name (AR)")
    ait_print_bank_address = fields.Char(string="Bank Address (EN)")
    ait_print_bank_address_ar = fields.Char(string="Bank Address (AR)")
    ait_print_swift = fields.Char(
        string="SWIFT",
        help="Leave empty to use the bank BIC.",
    )
    ait_print_acc_holder = fields.Char(string="Account Holder (EN)")
    ait_print_acc_holder_ar = fields.Char(string="Account Holder (AR)")
    ait_print_acc_number = fields.Char(
        string="Account Number (Print)",
        help="IBAN / account number printed on the invoice. "
             "Do not use the standard Account Number field for print text.",
    )
    ait_print_acc_number_label = fields.Char(
        string="Account Number Label (EN)",
        help="Caption only, e.g. Account Number USD — not the IBAN.",
    )
    ait_print_acc_number_label_ar = fields.Char(
        string="Account Number Label (AR)",
        help="Caption only, e.g. رقم الحساب بالدولار الأمريكي — not the IBAN.",
    )

    def _ait_print_bank_name(self):
        self.ensure_one()
        return self.ait_print_bank_name or self.bank_id.name or ""

    def _ait_print_bank_address(self):
        self.ensure_one()
        if self.ait_print_bank_address:
            return self.ait_print_bank_address
        bank = self.bank_id
        if not bank:
            return ""
        parts = [bank.street, bank.street2, bank.city, bank.zip]
        if bank.country:
            parts.append(bank.country.name)
        return ", ".join(p for p in parts if p)

    def _ait_print_swift(self):
        self.ensure_one()
        return self.ait_print_swift or self.bank_bic or ""

    def _ait_print_acc_holder(self):
        self.ensure_one()
        return self.ait_print_acc_holder or self.acc_holder_name or ""

    def _ait_looks_like_acc_number(self, value):
        value = (value or "").strip()
        if not value or len(value) > 42:
            return False
        if any("\u0600" <= ch <= "\u06FF" for ch in value):
            return False
        compact = value.replace(" ", "")
        return compact.isalnum() and any(ch.isdigit() for ch in compact)

    def _ait_print_acc_number(self):
        self.ensure_one()
        if self.ait_print_acc_number:
            return self.ait_print_acc_number.strip()
        for candidate in (
            self.ait_print_acc_number_label,
            self.ait_print_acc_number_label_ar,
            self.acc_number,
        ):
            if self._ait_looks_like_acc_number(candidate):
                return candidate.strip()
        return ""

    def _ait_print_acc_number_label_en(self):
        self.ensure_one()
        label = (self.ait_print_acc_number_label or "").strip()
        if not label or self._ait_looks_like_acc_number(label):
            return "Account Number"
        return label

    def _ait_print_acc_number_label_ar(self):
        self.ensure_one()
        label = (self.ait_print_acc_number_label_ar or "").strip()
        if not label or self._ait_looks_like_acc_number(label):
            return "رقم الحساب"
        return label

    def _ait_has_print_details(self):
        self.ensure_one()
        return bool(
            self.ait_print_instruction
            or self.ait_print_instruction_ar
            or self.ait_print_bank_name
            or self.ait_print_bank_name_ar
            or self.ait_print_bank_address
            or self.ait_print_bank_address_ar
            or self.ait_print_swift
            or self.ait_print_acc_holder
            or self.ait_print_acc_holder_ar
            or self._ait_print_acc_number()
        )
