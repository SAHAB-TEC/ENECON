# -*- coding: utf-8 -*-
{
    "name": "Account Invoice Templates",
    "version": "18.0.1.0.25",
    "category": "Accounting",
    "summary": "Custom customer invoice PDF layouts and template fields",
    "depends": [
        "account",
        "rgb_contract_management",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/account_move_views.xml",
        "views/res_partner_bank_views.xml",
        "views/account_report.xml",
        "report/payable_invoices_report.xml",
        "views/invoice_summary_report_wizard_views.xml",
        "views/tax_statement_report_wizard_views.xml",
        "views/payable_invoices_report_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
