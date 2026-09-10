# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['rgb.contract']._deduplicate_contract_codes_for_unique_index()
    cr.execute("DROP INDEX IF EXISTS rgb_contract_client_ref_unique_ci")
    cr.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS rgb_contract_client_ref_unique_ci
        ON rgb_contract (company_id, lower(btrim(contract_code)))
        WHERE contract_code IS NOT NULL AND btrim(contract_code) <> ''
    """)
