from odoo import fields, models, _


class ConstructionProject(models.Model):
    _inherit = 'construction.project'

    rgb_work_summary_entry_count = fields.Integer(
        string='Work Summary Entries',
        compute='_compute_rgb_work_summary_entry_count',
    )

    def _compute_rgb_work_summary_entry_count(self):
        Entry = self.env['rgb.enecon.work.summary.entry']
        for project in self:
            project.rgb_work_summary_entry_count = Entry.search_count([
                ('project_id', '=', project.id),
            ])

    def action_rgb_view_work_summary_entries(self):
        self.ensure_one()
        return {
            'name': _('Work Summary Entries'),
            'type': 'ir.actions.act_window',
            'res_model': 'rgb.enecon.work.summary.entry',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
        }
