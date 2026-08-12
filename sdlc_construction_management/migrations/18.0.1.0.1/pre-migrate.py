# -*- coding: utf-8 -*-


def migrate(cr, version):
    """Map legacy project states before Selection values are replaced."""
    cr.execute(
        """
        UPDATE construction_project
           SET state = CASE state
                WHEN 'draft' THEN 'ongoing'
                WHEN 'in_progress' THEN 'ongoing'
                WHEN 'short_closed' THEN 'closed'
                WHEN 'completed' THEN 'completed'
                ELSE COALESCE(state, 'ongoing')
           END
         WHERE state IN ('draft', 'in_progress', 'short_closed', 'completed')
            OR state IS NULL
        """
    )
