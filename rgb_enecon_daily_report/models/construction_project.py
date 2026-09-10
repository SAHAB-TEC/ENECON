from odoo import fields, models, _


class ConstructionProject(models.Model):
    _inherit = 'construction.project'

    rgb_daily_report_count = fields.Integer(
        string='Daily Reports',
        compute='_compute_rgb_daily_report_count',
    )

    def _compute_rgb_daily_report_count(self):
        Report = self.env['rgb.enecon.daily.report']
        for project in self:
            project.rgb_daily_report_count = Report.search_count([
                ('project_id', '=', project.id),
            ])

    def action_rgb_view_daily_reports(self):
        self.ensure_one()
        return {
            'name': _('Daily Reports'),
            'type': 'ir.actions.act_window',
            'res_model': 'rgb.enecon.daily.report',
            'view_mode': 'list,kanban,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
