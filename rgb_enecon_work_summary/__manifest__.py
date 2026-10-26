# -*- coding: utf-8 -*-
{
    'name': 'RGB ENECON Work Summary',
    'version': '18.0.1.0.1',
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
        'views/work_summary_app_menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
