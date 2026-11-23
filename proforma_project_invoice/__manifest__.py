{
    'name': 'Project Invoices (Non-Financial) / فواتير المشاريع',
    'version': '18.0.1.0.0',
    'category': 'Services/Project',
    'summary': 'Non-accounting project/service statement invoices with PDF & Excel export',
    'description': """
Standalone, non-financial project/service statement invoices.
No journal entries, no impact on account.move or the general ledger.
    """,
    'author': 'Custom',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'product', 'contacts', 'hr'],
    'external_dependencies': {'python': ['xlsxwriter']},
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/invoice_views.xml',
        'report/report.xml',
        'report/report_template.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True,
}
