{
    'name': 'Construction Management',
    'version': '18.0.1.0.1',
    'summary': 'Construction Management | Job Costing | BOQ | Work Orders | RA Billing | Material Requisition | Subcontracting | Budget',
    'description': """
Construction Management
========================
Complete construction project management for Odoo 18. Manage projects,
sub-projects, BOQ, budgets, rate analysis, phases (WBS), work orders,
material requisitions with approvals, subcontracting, progress billing,
quality checks, tasks, extra expenses, and an advanced real-time dashboard.
Includes RA billing, consume orders, and completion certificates.
Free lifetime support by SDLC Corp.
    """,
    'category': 'Construction',
    'author': 'SDLC Corp',
    'website': 'https://sdlccorp.com/',
    'license': 'LGPL-3',
    'price': 10,
    'currency': 'USD',
    'images': ['static/description/banner.png'],
    'depends': [
        'base',
        'mail',
        'contacts',
        'hr',
        'stock',
        'purchase',
        'account',
        'project',
    ],
    'data': [
        # Security
        'security/construction_security.xml',
        'security/ir.model.access.csv',
        # Data
        'data/sequence_data.xml',
        'data/construction_project_stage_data.xml',
        'data/construction_project_stage_assign.xml',
        'data/configuration_data.xml',
        'views/dashboard_views.xml',
        'views/construction_project_stage_views.xml',
        'views/construction_project_views.xml',
        'views/construction_sub_project_views.xml',
        'views/construction_boq_views.xml',
        'views/construction_rate_analysis_views.xml',
        'views/construction_budget_views.xml',
        'views/construction_phase_views.xml',
        'views/construction_work_order_views.xml',
        'views/construction_material_requisition_views.xml',
        'views/construction_subcontract_views.xml',
        'views/construction_progress_billing_views.xml',
        'views/construction_quality_check_views.xml',
        'views/construction_task_views.xml',
        'views/construction_extra_expense_views.xml',
        'views/construction_configuration_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sdlc_construction_management/static/src/js/dashboard.js',
            'sdlc_construction_management/static/src/xml/dashboard.xml',
            'sdlc_construction_management/static/src/css/dashboard.css',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
}
