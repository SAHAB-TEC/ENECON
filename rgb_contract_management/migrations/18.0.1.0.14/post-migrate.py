# -*- coding: utf-8 -*-
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    cr.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'rgb_contract_business_type_migration'
        )
    """)
    if not cr.fetchone()[0]:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    mapping = {
        'supply': 'rgb_contract_management.business_type_supply',
        'supply_install': 'rgb_contract_management.business_type_supply_install',
        'construction': 'rgb_contract_management.business_type_construction',
        'rental': 'rgb_contract_management.business_type_rental',
    }

    cr.execute("SELECT contract_id, old_code FROM rgb_contract_business_type_migration")
    for contract_id, old_code in cr.fetchall():
        xmlid = mapping.get(old_code)
        if not xmlid:
            continue
        business_type = env.ref(xmlid, raise_if_not_found=False)
        if not business_type:
            continue
        env['rgb.contract'].browse(contract_id).write({
            'contract_business_type_id': business_type.id,
        })

    cr.execute("DROP TABLE IF EXISTS rgb_contract_business_type_migration")
