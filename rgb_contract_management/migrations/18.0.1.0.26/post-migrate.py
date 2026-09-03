# -*- coding: utf-8 -*-


def migrate(cr, version):
    """Backfill partner internal references starting from 1, then sync sequence."""
    cr.execute(
        """
        SELECT id
          FROM ir_sequence
         WHERE code = 'rgb.partner.ref'
         ORDER BY id
         LIMIT 1
        """
    )
    row = cr.fetchone()
    if not row:
        return
    sequence_id = row[0]

    # Prefer no_gap so number_next in ir_sequence is the source of truth.
    cr.execute(
        """
        UPDATE ir_sequence
           SET implementation = 'no_gap',
               padding = 1,
               prefix = '',
               number_increment = 1
         WHERE id = %s
        """,
        (sequence_id,),
    )

    cr.execute(
        """
        SELECT COALESCE(MAX(ref::integer), 0)
          FROM res_partner
         WHERE ref ~ '^[0-9]+$'
        """
    )
    max_existing = cr.fetchone()[0] or 0
    next_number = max_existing + 1

    cr.execute(
        """
        SELECT id
          FROM res_partner
         WHERE (ref IS NULL OR ref = '')
           AND parent_id IS NULL
           AND active = TRUE
           AND (
                customer_rank > 0
                OR supplier_rank > 0
                OR is_company = TRUE
           )
         ORDER BY id
        """
    )
    partner_ids = [r[0] for r in cr.fetchall()]
    for partner_id in partner_ids:
        cr.execute(
            "UPDATE res_partner SET ref = %s WHERE id = %s AND (ref IS NULL OR ref = '')",
            (str(next_number), partner_id),
        )
        next_number += 1

    cr.execute(
        """
        UPDATE ir_sequence
           SET number_next = %s
         WHERE id = %s
        """,
        (next_number, sequence_id),
    )
