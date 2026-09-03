{
    'name': 'HR Extended Features',
    'version': '18.0.1.0',
    'category': 'Human Resources',
    'author': 'Marwah Adel',
    'license': 'LGPL-3',
    'summary': 'Unpaid Leave, Appraisal Updates, Multi Shifts',
    'depends': ['hr', 'hr_attendance', 'hr_payroll', 'hr_contract', 'hr_appraisal','hr_holidays','rm_hr_attendance_sheet','planning','spreadsheet'],
    'data': [
        "data/cron.xml",
        "data/unpaid_leave_days_data.xml",
        "views/hr_leave_type_views.xml",
        "views/hr_payslip_views.xml",
        "views/hr_appraisal_view.xml",

    ],
    'installable': True,
    'auto_install': False,
}
