{
    'name': 'ENECON Work Summary Report',
    'version': '18.0.1.0.0',
    'summary': 'Independent printable period summary for workforce, materials and transport',
    'category': 'Construction',
    'author': 'RGB / ENECON',
    'license': 'LGPL-3',
    'depends': ['rgb_enecon_work_summary'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/work_summary_report_wizard_views.xml',
        'reports/work_summary_report.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
