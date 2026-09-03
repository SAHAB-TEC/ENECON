from odoo import models, fields, api, tools


class HrAppraisal(models.Model):
    _inherit = 'hr.appraisal'

    assessment_note = fields.Many2one('hr.appraisal.note', string='Final Rating')
    assessment_rating_label = fields.Char(string="Final Rating ", compute='_compute_rating_label', store=True)
    assessment_rating_value = fields.Float(string="Final Rating Value", compute='_compute_rating_label', store=True)

    @api.depends('assessment_note')
    def _compute_rating_label(self):
        for rec in self:
            rec.assessment_rating_label = rec.assessment_note.name if rec.assessment_note else ''
            # Safely convert to float, handling non-numeric values
            if rec.assessment_note and rec.assessment_note.name:
                try:
                    rec.assessment_rating_value = float(rec.assessment_note.name)
                except (ValueError, TypeError):
                    # If name is not numeric (e.g., "Good", "Excellent"), set to 0.0
                    rec.assessment_rating_value = 0.0
            else:
                rec.assessment_rating_value = 0.0


class HrAppraisalReport(models.Model):
    _inherit = 'hr.appraisal.report'

    assessment_rating_label = fields.Char(string="Final Rating")
    assessment_rating_value = fields.Float(string="Final Rating Value", group_operator='avg')

    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'hr_appraisal_report')
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW hr_appraisal_report AS (
                SELECT
                    MIN(a.id) AS id,
                    DATE(a.create_date) AS create_date,
                    a.employee_id,
                    a.assessment_rating_label AS assessment_rating_label,
                    a.assessment_rating_value AS assessment_rating_value,
                    e.department_id AS department_id,
                    a.date_close AS deadline,
                    CASE WHEN MIN(ce.start) >= NOW() AT TIME ZONE 'UTC' THEN MIN(ce.start) ELSE MAX(ce.start) END AS final_interview,
                    a.state
                FROM hr_appraisal a
                    LEFT JOIN hr_employee e ON (e.id = a.employee_id)
                    LEFT OUTER JOIN calendar_event ce ON ce.res_id = a.id AND ce.res_model = 'hr.appraisal'
                GROUP BY
                    a.id,
                    a.create_date,
                    a.state,
                    a.employee_id,
                    a.date_close,
                    e.department_id,
                    a.assessment_note,
                    a.assessment_rating_label,
                    a.assessment_rating_value
            )
        """)
