# -*- coding: utf-8 -*-
{
    'name': "HR Attendance Sheet And Policies",

    'summary': """Managing  Attendance Sheets for Employees
        """,
    'description': """
        Employees Attendance Sheet Management   
    """,
    'author': "CDS Solutions SRL,Ramadan Khalil",
    'website': "rkhalil1990@gmail.com",
    'price': 99,
    'currency': 'USD',

    'category': 'hr',
    'version': '18.0',
    'images': ['static/description/banner.gif'],

    'depends': ['base',
                'hr',
                'hr_payroll',
                'hr_holidays',
                'hr_payroll_holidays',
                'hr_attendance'],
    'data': [
        'data/ir_sequence.xml',
        'data/data.xml',
        'data/ir_cron.xml',
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/rule.xml',
        'wizard/change_att_data_view.xml',
        'views/hr_attendance_sheet_view.xml',
        'views/hr_attendance_policy_view.xml',
        'views/hr_contract_view.xml',
        'views/hr_public_holiday_view.xml',
        'views/attendance_sheet_batch_view.xml',
        'views/hr_payslip_view.xml',
        'views/hr_leave_type_view.xml',
        'views/res_config_settings.xml',
    ],

    'license': 'OPL-1',
    'demo': [
        'demo/demo.xml',
    ],
}
