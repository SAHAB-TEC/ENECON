# -*- coding: utf-8 -*-
{
    "name": "RGB Material Requisition Custom",
    "version": "18.0.1.0.11",
    "category": "Human Resources/Employees",
    "summary": "Al-Abar customizations for material requisitions",
    "description": """
Custom material requisition extensions for Al-Abar:
- Customer (required), well and rig on requisitions and linked documents
- Project (project.project) and analytic account auto-filled from the project
- Analytic account on stock locations for transfer journal entries
- Allowed users per stock location for requisition destination selection
- Purchase receipts for material-requisition POs use the requisition location
    """,
    "author": "RGB / Al-Abar",
    "license": "LGPL-3",
    "depends": [
        "material_requisition_and_approval",
        "rgb_crm_project_custom",
        "purchase_stock",
        "project",
        "analytic",
        "stock_account",
    ],
    "data": [
        "views/material_requisition_views.xml",
        "views/material_requisition_line_views.xml",
        "views/material_requisition_approval_views.xml",
        "views/stock_purchase_views.xml",
        "views/stock_location_views.xml",
        "report/material_requisition_summary_report.xml",
    ],
    "installable": True,
    "application": False,
}
