# -*- coding: utf-8 -*-
import json


def migrate(cr, version):
    """Align project stage labels with the new Arabic statuses."""
    updates = [
        ('construction_project_stage_todo', 'جاري', 10, False),
        ('construction_project_stage_in_progress', 'متوقف', 15, False),
        ('construction_project_stage_done', 'معلّق', 20, False),
        ('construction_project_stage_cancelled', 'مغلق', 25, True),
    ]
    for xml_id, name, sequence, fold in updates:
        name_json = json.dumps({'en_US': name, 'ar_001': name})
        cr.execute(
            """
            UPDATE construction_project_stage AS stage
               SET name = %s::jsonb,
                   sequence = %s,
                   fold = %s
              FROM ir_model_data AS imd
             WHERE imd.res_id = stage.id
               AND imd.module = 'sdlc_construction_management'
               AND imd.name = %s
               AND imd.model = 'construction.project.stage'
            """,
            (name_json, sequence, fold, xml_id),
        )

    cr.execute(
        """
        SELECT 1
          FROM ir_model_data
         WHERE module = 'sdlc_construction_management'
           AND name = 'construction_project_stage_completed'
           AND model = 'construction.project.stage'
        """
    )
    if not cr.fetchone():
        name_json = json.dumps({'en_US': 'مكتمل', 'ar_001': 'مكتمل'})
        cr.execute(
            """
            INSERT INTO construction_project_stage (name, sequence, fold, active)
            VALUES (%s::jsonb, 30, TRUE, TRUE)
            RETURNING id
            """,
            (name_json,),
        )
        stage_id = cr.fetchone()[0]
        cr.execute(
            """
            INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
            VALUES (
                'sdlc_construction_management',
                'construction_project_stage_completed',
                'construction.project.stage',
                %s,
                TRUE
            )
            """,
            (stage_id,),
        )
