{
    'name': 'HR Planning Feature',
    'version': '18.0.1.0',
    'category': 'Human Resources',
    'author': 'Marwah Adel',
    'license': 'LGPL-3',
    'depends': ['hr', 'hr_attendance', 'hr_payroll', 'hr_contract','rm_hr_attendance_sheet','planning','rm_hr_attendance_sheet','hr_extended_features'],
    'data': [
       
        "views/hr_contract_view.xml",

    ],
    'installable': True,
    'auto_install': False,
}
