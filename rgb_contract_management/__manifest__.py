# -*- coding: utf-8 -*-
{
    'name': 'RGB Contract Management',
    'version': '18.0.1.0.32',
    'category': 'Accounting/Contracts',
    'summary': 'Contract lifecycle, approvals, insurance, guarantees, and invoicing',
    'description': """
RGB Contract Management
=======================
Manage purchase (contractor) and sale (customer) contracts with approval workflow,
insurance documents, bank guarantees, payment conditions, delay penalties,
and linked accounting invoices with analytic distribution.
    """,
    'author': 'RGB / Arabian Nile',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'account',
        'analytic',
        'purchase',
        'sale_management',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'data/insurance_type_data.xml',
        'data/business_type_data.xml',
        'data/mail_template.xml',
        'data/scheduled_actions.xml',
        'views/insurance_type_views.xml',
        'views/business_type_views.xml',
        'views/res_partner_views.xml',
        'views/product_template_views.xml',
        'views/contract_views.xml',
        'views/account_move_views.xml',
        'views/report_invoice.xml',
        'views/report_contract.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
}
