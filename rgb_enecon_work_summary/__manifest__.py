# -*- coding: utf-8 -*-
{
    'name': 'RGB ENECON Work Summary',
    'version': '18.0.1.0.0',
    'summary': 'Daily work summary entries and dynamic period reports for ENECON',
    'category': 'Construction',
    'author': 'RGB',
    'license': 'LGPL-3',
    'depends': [
        'sdlc_construction_management',
        'rgb_enecon_daily_report',
        'hr',
        'mail',
    ],
    'data': [
        'security/work_summary_security.xml',
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'views/transport_type_views.xml',
        'views/work_summary_views.xml',
        'views/construction_project_views.xml',
        'wizard/work_summary_report_wizard_views.xml',
        'reports/work_summary_report.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
