# -*- coding: utf-8 -*-
#################################################################################
# Author      : Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# Copyright(c): 2015-Present Webkul Software Pvt. Ltd.
# All Rights Reserved.
#
#
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#
# You should have received a copy of the License along with this program.
# If not, see <https://store.webkul.com/license.html/>
#################################################################################
{
    "name": "Material Requisition and Approval",
    "summary": """This module helps to manage employee material requisitions and approvals. 
                Track requests | Approval workflows | Inventory management | Material requests""",
    "category": "Human Resources/Employees",
    "version": "1.0.1",
    "author": "Webkul Software Pvt. Ltd.",
    "license": "Other proprietary",
    "website": "https://store.webkul.com/odoo-material-requisition-and-approval.html",
    "live_test_url": "http://odoodemo.webkul.in/?module=material_requisition_and_approval",
    "description": """This module provides functionality to:
                    - Create and track material requisition requests
                    - Multi-level approval workflows
                    - Inventory availability checks
                    - Request fulfillment tracking
                    - Reports and dashboards
                    """,
    "depends": [
        "base",
        "hr",
        "stock",
        "purchase",
        "product",
        "purchase_stock",
    ],
    "data": [
        "security/material_requisition_groups.xml",
        "security/ir.model.access.csv",
        "security/material_requisition_security.xml",
        "views/material_requisition_approval_view.xml",
        "views/material_requisition_view.xml",
        "views/material_requisition_approver_line_view.xml",
        "views/material_requisition_approver_rule_view.xml",
        "views/stock_location_role_config_view.xml",
        "views/material_requisition_line_view.xml",
        "views/res_user_view.xml",
        "views/hr_employee_view.xml",
        "views/material_requisition_dashboard.xml",
        "views/menus.xml",
        "wizard/fullfillment_wizard.xml",
        "wizard/product_availability_lookup_wizard_view.xml",
        "wizard/material_requisition_remark_wizard_view.xml",
        "wizard/material_requisition_cancel_wizard_view.xml",
        "wizard/material_requisition_bulk_cancel_wizard_view.xml",
        "report/material_requisition_summary_report.xml",
        "report/approval_log_report.xml",
        "report/stock_movement_log_report.xml",
        "report/dispatch_log_report.xml",
        "report/material_reqisition_summar_csv_report.xml",
        "report/approval_log_csv_report.xml",
        "report/dispatch_log_csv_report.xml",
        "data/000.xml",
        "data/material_requisition_approval_mail.xml",
        "data/material_requisition_cancellation_mail.xml",
        "data/material_requisition_server_actions.xml",
        "data/email_template_rejection.xml",
        "data/email_template_cancellation.xml",
    ],
    "demo": ["data/demo_data.xml"],
    "assets": {
        "web.assets_backend": [
            "material_requisition_and_approval/static/src/dashboard/material_requisition_dashboard_screen.js",
            "material_requisition_and_approval/static/src/dashboard/material_requisition_dashboard_screen.xml",
            "material_requisition_and_approval/static/src/dashboard/material_requisition_dashboard_screen.scss",
            "material_requisition_and_approval/static/src/state_type_dashboard_graph/state_type_dashboard_graph_field.js",
            "material_requisition_and_approval/static/src/state_type_dashboard_graph/state_type_dashboard_graph_field.scss",
            "material_requisition_and_approval/static/src/widget/ribbon/ribbon.js",
            "material_requisition_and_approval/static/src/widget/ribbon/ribbon.scss",
            "material_requisition_and_approval/static/src/widget/ribbon/ribbon.xml",
        ],
    },
    "images": ["static/description/banner.png"],
    "application": True,
    "installable": True,
    "auto_install": False,
    "price": 59,
    "currency": "USD",
    "pre_init_hook": "pre_init_check",
}
