from odoo import models


class ReportPayrollBank(models.AbstractModel):
    _name = 'report.payroll_bank_report.report_payroll_bank_template'
    _description = 'Payroll Bank Report'

    def _get_report_values(self, docids, data=None):
        wizard = self.env['payroll.bank.report.wizard'].browse(docids).ensure_one()
        lines = self.env['payroll.bank.report.line'].search([('wizard_id', '=', wizard.id)])
        if not lines:
            lines = wizard._prepare_report_lines()

        if wizard.filter_by == 'employees':
            filter_label = ', '.join(wizard.employee_ids.mapped('name')) or 'Selected Employees'
        elif wizard.filter_by == 'departments':
            filter_label = ', '.join(wizard.department_ids.mapped('name')) or 'Selected Departments'
        else:
            filter_label = 'All Employees'

        return {
            'doc_ids': docids,
            'doc_model': 'payroll.bank.report.wizard',
            'docs': wizard,
            'lines': lines,
            'date_from': wizard.date_from,
            'date_to': wizard.date_to,
            'total_net_salary': sum(lines.mapped('net_salary')),
            'filter_label': filter_label,
            'company': wizard.company_id,
            'bank_name': wizard.bank_id.name if wizard.bank_id else '',
     }


class ReportPayrollBankLines(models.AbstractModel):
    _name = 'report.payroll_bank_report.report_payroll_bank_lines_template'
    _description = 'Selected Payroll Bank Report Lines'

    def _get_report_values(self, docids, data=None):
        lines = self.env['payroll.bank.report.line'].browse(docids)
        company = lines[:1].company_id or self.env.company
        date_from = lines[:1].date_from if lines else False
        date_to = lines[:1].date_to if lines else False
        return {
            'doc_ids': docids,
            'doc_model': 'payroll.bank.report.line',
            'docs': lines,
            'lines': lines,
            'date_from': date_from,
            'date_to': date_to,
            'total_net_salary': sum(lines.mapped('net_salary')),
            'filter_label': 'Selected Lines',
            'company': company,
        }
