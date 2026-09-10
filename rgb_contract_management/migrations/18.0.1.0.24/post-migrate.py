# -*- coding: utf-8 -*-


def migrate(cr, version):
    """Ensure Arabic label for state 'done' is 'منتهي غير مقفل' (not 'منتهي')."""
    cr.execute(
        """
        UPDATE ir_model_fields_selection AS sel
           SET name = jsonb_set(
                   COALESCE(sel.name, '{}'::jsonb),
                   '{ar_001}',
                   to_jsonb('منتهي غير مقفل'::text),
                   true
               )
          FROM ir_model_fields AS f
         WHERE sel.field_id = f.id
           AND f.model = 'rgb.contract'
           AND f.name = 'state'
           AND sel.value = 'done'
           AND (
                sel.name->>'ar_001' IS NULL
                OR sel.name->>'ar_001' = 'منتهي'
           )
        """
    )
