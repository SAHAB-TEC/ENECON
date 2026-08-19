# Payroll Bank Report for Odoo 18 Enterprise

This module adds a printable PDF wizard for a monthly payroll bank report.

## Report fields

- Employee name
- Department
- Net salary
- Bank account number
- Bank name

## Filters

- Month
- Year
- Employee, optional
- Department, optional

## Installation

1. Copy the `payroll_bank_report` folder into your Odoo addons path.
2. Restart Odoo.
3. Update Apps List.
4. Install **Payroll Bank Report**.
5. Open **Payroll Bank Report > Print Report**.

## Notes

- The report reads paid/done payslips only.
- Net salary is calculated from salary rule code `NET`.
- Bank details are read from the employee bank account.
- If the Bank field is empty on the employee bank account, the report will also show an empty bank name.
