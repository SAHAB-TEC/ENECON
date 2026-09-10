# -*- coding: utf-8 -*-


def migrate(cr, version):
    cr.execute("""
        DELETE FROM rgb_account_move_currency_split s
        WHERE NOT EXISTS (
            SELECT 1 FROM account_move m WHERE m.id = s.move_id
        )
    """)
