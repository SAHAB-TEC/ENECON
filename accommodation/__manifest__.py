# -*- coding: utf-8 -*-
{
    'name': 'Accommodation Management',
    'version': '18.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Manage accommodation units, guest check-ins/outs and maintenance requests',
    'description': """
Accommodation Management
=========================
Track housing units (fixed/mobile), assign employees as guests, log
occupancy history automatically, manage per-unit furniture/inventory,
raise and approve maintenance requests against a specific unit or item,
and report on maintenance activity by location, project and unit.

Access to every screen and action button is governed by dedicated
checkboxes on each user's Access Rights tab (Settings > Users):
module access, configuration access, create/edit guest, create/edit
maintenance request, and maintenance approval.

Includes an Arabic translation starter file.
""",
    'author': 'Your Company',
    'website': '',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'hr', 'project'],
    'data': [
        'security/accommodation_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/accommodation_type_views.xml',
        'views/accommodation_unit_views.xml',
        'views/accommodation_guest_views.xml',
        'views/accommodation_unit_history_views.xml',
        'views/accommodation_guest_belonging_views.xml',
        'views/accommodation_repair_views.xml',
        'views/accommodation_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'accommodation/static/src/css/accommodation.css',
        ],
    },
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
