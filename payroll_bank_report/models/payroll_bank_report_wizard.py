from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import date
import calendar


class PayrollBankReportWizard(models.TransientModel):
    _name = 'payroll.bank.report.wizard'
    _description = 'Payroll Bank Report Wizard'

    month = fields.Selection(
        selection=[
            ('1', 'January'), ('2', 'February'), ('3', 'March'),
            ('4', 'April'), ('5', 'May'), ('6', 'June'),
            ('7', 'July'), ('8', 'August'), ('9', 'September'),
            ('10', 'October'), ('11', 'November'), ('12', 'December'),
        ],
        string='Month',
        required=True,
        default=lambda self: str(fields.Date.today().month),
    )
    year = fields.Integer(
        string='Year',
        required=True,
        default=lambda self: fields.Date.today().year,
    )
    filter_by = fields.Selection(
        selection=[
            ('all', 'All Employees'),
            ('employees', 'Selected Employees'),
            ('departments', 'Selected Departments'),
        ],
        string='Filter By',
        required=True,
        default='all',
    )
    employee_ids = fields.Many2many(
        'hr.employee',
        'payroll_bank_report_wizard_employee_rel',
        'wizard_id',
        'employee_id',
        string='Employees',
    )
    department_ids = fields.Many2many(
        'hr.department',
        'payroll_bank_report_wizard_department_rel',
        'wizard_id',
        'department_id',
        string='Departments',
    )
    bank_id = fields.Many2one(
    'res.bank',
    string='Bank',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    date_from = fields.Date(string='From Date', compute='_compute_dates', store=False)
    date_to = fields.Date(string='To Date', compute='_compute_dates', store=False)

    @api.depends('month', 'year')
    def _compute_dates(self):
        for wizard in self:
            if wizard.month and wizard.year:
                month = int(wizard.month)
                last_day = calendar.monthrange(wizard.year, month)[1]
                wizard.date_from = date(wizard.year, month, 1)
                wizard.date_to = date(wizard.year, month, last_day)
            else:
                wizard.date_from = False
                wizard.date_to = False

    @api.onchange('filter_by')
    def _onchange_filter_by(self):
        if self.filter_by != 'employees':
            self.employee_ids = [(5, 0, 0)]
        if self.filter_by != 'departments':
            self.department_ids = [(5, 0, 0)]

    def _get_period(self):
        self.ensure_one()
        if not self.month or not self.year:
            raise UserError(_('Please select month and year.'))
        month = int(self.month)
        last_day = calendar.monthrange(self.year, month)[1]
        return date(self.year, month, 1), date(self.year, month, last_day)

    def _check_filters(self):
        self.ensure_one()
        if self.filter_by == 'employees' and not self.employee_ids:
            raise UserError(_('Please select at least one employee.'))
        if self.filter_by == 'departments' and not self.department_ids:
            raise UserError(_('Please select at least one department.'))

    def _get_employee_bank_account(self, employee):
        if 'bank_account_id' in employee._fields and employee.bank_account_id:
            return employee.bank_account_id
        if 'address_home_id' in employee._fields and employee.address_home_id:
            partner = employee.address_home_id
            if 'bank_ids' in partner._fields and partner.bank_ids:
                return partner.bank_ids[:1]
        return self.env['res.partner.bank']

    def _get_net_salary(self, slip):
        net_lines = slip.line_ids.filtered(lambda line: line.code == 'NET')
        if net_lines:
            return sum(net_lines.mapped('total'))
        if 'net_wage' in slip._fields:
            return slip.net_wage or 0.0
        return 0.0

    def _get_payslip_domain(self):
        self.ensure_one()
        date_from, date_to = self._get_period()
        domain = [
            ('date_from', '>=', date_from),
            ('date_to', '<=', date_to),
            ('state', 'in', ['done', 'paid']),
            ('company_id', '=', self.company_id.id),
        ]
        if self.filter_by == 'employees' and self.employee_ids:
            domain.append(('employee_id', 'in', self.employee_ids.ids))
        elif self.filter_by == 'departments' and self.department_ids:
            domain.append(('employee_id.department_id', 'child_of', self.department_ids.ids))
        return domain

    def _prepare_report_lines(self):
        self.ensure_one()
        self._check_filters()
        date_from, date_to = self._get_period()

        old_lines = self.env['payroll.bank.report.line'].search([('wizard_id', '=', self.id)])
        old_lines.unlink()

        payslips = self.env['hr.payslip'].search(
            self._get_payslip_domain(),
            order='employee_id, date_from'
        )

        grouped = {}

        for slip in payslips:
            employee = slip.employee_id
            if not employee:
                continue

            bank_account = self._get_employee_bank_account(employee)

            # Filter by selected bank
            if self.bank_id:
                if not bank_account or not bank_account.bank_id:
                    continue
                if bank_account.bank_id.id != self.bank_id.id:
                    continue

            if employee.id not in grouped:
                currency = (
                    slip.currency_id
                    or slip.company_id.currency_id
                    or self.company_id.currency_id
                )

                grouped[employee.id] = {
                    'wizard_id': self.id,
                    'company_id': self.company_id.id,
                    'employee_id': employee.id,
                    'department_id': employee.department_id.id or False,
                    'date_from': date_from,
                    'date_to': date_to,
                    'net_salary': 0.0,
                    'currency_id': currency.id,
                    'bank_account_id': bank_account.id or False,
                    'account_number': bank_account.acc_number or '',
                    'bank_id': bank_account.bank_id.id if bank_account and bank_account.bank_id else False,
                    'payslip_count': 0,
                }

            grouped[employee.id]['net_salary'] += self._get_net_salary(slip)
            grouped[employee.id]['payslip_count'] += 1

        values = sorted(
            grouped.values(),
            key=lambda value: (
                self.env['hr.department'].browse(value['department_id']).name if value['department_id'] else '',
                self.env['hr.employee'].browse(value['employee_id']).name or '',
            )
        )
        if values:
            self.env['payroll.bank.report.line'].create(values)

        return self.env['payroll.bank.report.line'].search([('wizard_id', '=', self.id)])

    def action_view_lines(self):
        self.ensure_one()
        lines = self._prepare_report_lines()
        return {
            'name': _('Payroll Bank Report'),
            'type': 'ir.actions.act_window',
            'res_model': 'payroll.bank.report.line',
            'view_mode': 'list,pivot,graph',
            'domain': [('id', 'in', lines.ids)],
            'context': {
                'search_default_group_by_department': 1,
                'create': False,
                'edit': False,
            },
            'target': 'current',
        }

    def action_print_pdf(self):
        self.ensure_one()
        self._prepare_report_lines()
        return self.env.ref('payroll_bank_report.action_report_payroll_bank').report_action(self)
