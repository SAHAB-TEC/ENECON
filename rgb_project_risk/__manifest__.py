# -*- coding: utf-8 -*-
{
    'name': 'RGB Project Risk Register',
    'version': '18.0.1.0.0',
    'category': 'Construction',
    'summary': 'Risk register tab on construction projects with configurable probability levels',
    'description': """
RGB Project Risk Register
=========================
Adds a Risk Register tab on construction projects with:

- Configurable probability assessment values (master data screen)
- Risk lines: name, probability, impact, response plans
- Multiple stakeholders (contacts) and users
- Expected delay in days
    """,
    'author': 'RGB / ENECON',
    'license': 'LGPL-3',
    'depends': [
        'sdlc_construction_management',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/risk_probability_data.xml',
        'views/risk_probability_views.xml',
        'views/risk_impact_views.xml',
        'views/construction_project_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': False,
}
