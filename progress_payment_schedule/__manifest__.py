{
    'name': 'Progress Payment Schedule',
    'version': '18.0.1.0.0',
    'category': 'Services/Project',
    'summary': 'Manage, approve, track and print Progress Payment Schedules',
    'description': """
Standalone document module for Progress Payment Schedules.
No accounting entries or invoices are created.
    """,
    'author': 'Custom',
    'license': 'LGPL-3',
    'depends': ['base', 'mail'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'report/report_paperformat.xml',
        'report/report_templates.xml',
        'report/report_actions.xml',
        'views/progress_payment_schedule_views.xml',
        'views/menus.xml',
    ],
    'application': True,
    'installable': True,
}
