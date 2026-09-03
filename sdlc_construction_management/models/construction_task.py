from odoo import models, fields, api, _


class ConstructionTask(models.Model):
    _name = 'construction.task'
    _description = 'Construction Task'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'

    name = fields.Char(string='Task Name', required=True, tracking=True)
    reference = fields.Char(string='Reference', readonly=True, default='New', copy=False)
    project_id = fields.Many2one('construction.project', string='Project', required=True)
    sub_project_id = fields.Many2one('construction.sub.project', string='Sub Project',
                                      domain="[('project_id', '=', project_id)]")
    phase_id = fields.Many2one('construction.phase', string='Phase',
                                domain="[('project_id', '=', project_id)]")
    work_order_id = fields.Many2one('construction.work.order', string='Work Order',
                                     domain="[('project_id', '=', project_id)]")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Html(string='Description')

    # Assignment
    assigned_to = fields.Many2one('hr.employee', string='Assigned To')
    department_id = fields.Many2one('hr.department', string='Department')

    # Dates
    date_start = fields.Date(string='Start Date')
    date_end = fields.Date(string='End Date')
    date_deadline = fields.Date(string='Deadline')

    # Priority & Status
    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Low'),
        ('2', 'High'),
        ('3', 'Urgent'),
    ], string='Priority', default='0')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    progress = fields.Float(string='Progress (%)')

    # Timesheet
    timesheet_ids = fields.One2many('construction.timesheet', 'task_id', string='Timesheets')
    total_hours = fields.Float(string='Total Hours', compute='_compute_total_hours', store=True)

    notes = fields.Text(string='Notes')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'New') == 'New':
                vals['reference'] = self.env['ir.sequence'].next_by_code('construction.task') or 'New'
        return super().create(vals_list)

    @api.depends('timesheet_ids.hours')
    def _compute_total_hours(self):
        for rec in self:
            rec.total_hours = sum(rec.timesheet_ids.mapped('hours'))

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_done(self):
        self.write({'state': 'done', 'progress': 100.0})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})


class ConstructionTimesheet(models.Model):
    _name = 'construction.timesheet'
    _description = 'Construction Timesheet'

    task_id = fields.Many2one('construction.task', string='Task', ondelete='cascade')
    project_id = fields.Many2one('construction.project', string='Project',
                                  related='task_id.project_id', store=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    date = fields.Date(string='Date', default=fields.Date.context_today)
    hours = fields.Float(string='Hours')
    description = fields.Char(string='Description')
    is_internal = fields.Boolean(string='Internal Timesheet', default=False)
