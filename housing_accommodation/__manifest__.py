# -*- coding: utf-8 -*-
{
    'name': 'Housing Accommodation Management',
    'version': '18.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Manage property units, guest/occupant allocations and belongings',
    'description': """
Housing Accommodation Management
=================================
Manage company-owned housing/accommodation units, track guest (employee)
allocations, enforce maximum occupancy capacity, and log belongings and
room/bathroom/kitchen contents per unit.

Features
--------
* Unit Type configuration (Apartment, Trailer, Studio, ...)
* Property Units with Kanban view color-coded by status
  (Red = Occupied, Yellow = Reserved, Green = Available)
* Guest / Occupant allocations linked to hr.employee
* Automatic validation: checked-in guests can never exceed a unit's
  maximum capacity
* Smart buttons for Current Occupants, History Log and Belongings
* Room / Bathroom / Kitchen content tracking per unit
* Guest belongings tracking per allocation
""",
    'author': 'Custom Development',
    'website': '',
    'license': 'LGPL-3',
    'depends': ['base', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'views/housing_unit_type_views.xml',
        'views/housing_property_unit_views.xml',
        'views/housing_guest_allocation_views.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
