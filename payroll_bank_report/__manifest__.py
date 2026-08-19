{
    'name': 'Payroll Bank Report',
    'version': '18.0.1.0.0',
    'category': 'Payroll',
    'summary': 'Printable payroll report with employee net salary and bank account details',
    'description': '''
Payroll Bank Report
===================
Adds a wizard to print a monthly payroll bank report showing:
- Employee name
- Department
- Net salary
- Bank account number
- Bank name

Filters:
- Month and year
- All employees
- Multiple selected employees
- Multiple selected departments
- View list with filters/group by
- Print PDF from wizard or selected list lines
''',
    'author': 'Custom',
    'depends': [
        'hr',
        'hr_payroll',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/payroll_bank_report_wizard_views.xml',
        'views/payroll_bank_report_line_views.xml',
        'reports/payroll_bank_report.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
