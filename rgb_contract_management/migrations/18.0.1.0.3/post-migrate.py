# -*- coding: utf-8 -*-


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.rgb_contract_management.hooks import (
        _migrate_contract_currency_split,
        _migrate_invoice_currency_split,
    )
    _migrate_contract_currency_split(env)
    _migrate_invoice_currency_split(env)
