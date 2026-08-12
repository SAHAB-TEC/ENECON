# -*- coding: utf-8 -*-
{
    'name': 'RGB CRM Construction Project',
    'version': '18.0.1.0.1',
    'category': 'Sales/CRM',
    'summary': 'Create construction projects from CRM opportunities; wells and rigs master data',
    'depends': [
        'crm',
        'mail',
        'sdlc_construction_management',
    ],
    'data': [
        'security/rgb_crm_project_custom_security.xml',
        'security/ir.model.access.csv',
        'views/crm_lead_views.xml',
        'views/construction_project_views.xml',
        'views/rgb_well_views.xml',
        'views/rgb_rig_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
