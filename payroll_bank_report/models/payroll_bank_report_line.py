from odoo import fields, models


class PayrollBankReportLine(models.TransientModel):
    _name = 'payroll.bank.report.line'
    _description = 'Payroll Bank Report Line'
    _order = 'department_id, employee_id'

    wizard_id = fields.Many2one(
        'payroll.bank.report.wizard',
        string='Wizard',
        ondelete='cascade',
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        readonly=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        readonly=True,
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        readonly=True,
    )
    date_from = fields.Date(
        string='From Date',
        readonly=True,
    )
    date_to = fields.Date(
        string='To Date',
        readonly=True,
    )
    net_salary = fields.Monetary(
        string='Net Salary',
        readonly=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        readonly=True,
    )
    bank_account_id = fields.Many2one(
        'res.partner.bank',
        string='Bank Account',
        readonly=True,
    )
    account_number = fields.Char(
        string='Account Number',
        readonly=True,
    )
    bank_id = fields.Many2one(
        'res.bank',
        string='Bank',
        readonly=True,
    )
    payslip_count = fields.Integer(
        string='Payslip Count',
        readonly=True,
    )
