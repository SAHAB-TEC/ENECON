# -*- coding: utf-8 -*-

def migrate(cr, version):
    cr.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'rgb_contract'
          AND column_name = 'contract_business_type'
    """)
    if not cr.fetchone():
        return

    cr.execute("""
        CREATE TABLE IF NOT EXISTS rgb_contract_business_type_migration (
            contract_id INTEGER NOT NULL,
            old_code VARCHAR NOT NULL
        )
    """)
    cr.execute("DELETE FROM rgb_contract_business_type_migration")
    cr.execute("""
        INSERT INTO rgb_contract_business_type_migration (contract_id, old_code)
        SELECT id, contract_business_type
        FROM rgb_contract
        WHERE contract_business_type IS NOT NULL
    """)
