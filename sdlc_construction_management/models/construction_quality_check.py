from odoo import models, fields, api, _


class ConstructionQualityCheck(models.Model):
    _name = 'construction.quality.check'
    _description = 'Construction Quality Check'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Reference', readonly=True, default='New', copy=False)
    project_id = fields.Many2one('construction.project', string='Project', required=True)
    sub_project_id = fields.Many2one('construction.sub.project', string='Sub Project',
                                      domain="[('project_id', '=', project_id)]")
    phase_id = fields.Many2one('construction.phase', string='Phase',
                                domain="[('project_id', '=', project_id)]")
    work_order_id = fields.Many2one('construction.work.order', string='Work Order',
                                     domain="[('project_id', '=', project_id)]")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    date = fields.Date(string='Inspection Date', default=fields.Date.context_today)
    inspector_id = fields.Many2one('hr.employee', string='Inspector')

    check_type = fields.Selection([
        ('material', 'Material Inspection'),
        ('workmanship', 'Workmanship Inspection'),
        ('safety', 'Safety Check'),
        ('structural', 'Structural Inspection'),
        ('electrical', 'Electrical Inspection'),
        ('plumbing', 'Plumbing Inspection'),
        ('final', 'Final Inspection'),
        ('other', 'Other'),
    ], string='Check Type', default='material')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('pass', 'Pass'),
        ('fail', 'Fail'),
        ('conditional', 'Conditional Pass'),
    ], string='Status', default='draft', tracking=True)

    # Check Lines
    check_line_ids = fields.One2many('construction.quality.check.line', 'quality_check_id',
                                      string='Check Points')

    # Results
    result_notes = fields.Text(string='Result Notes')
    corrective_action = fields.Text(string='Corrective Action Required')
    recheck_date = fields.Date(string='Re-check Date')

    # Documents
    document = fields.Binary(string='Inspection Report', attachment=True)
    document_name = fields.Char(string='File Name')
    image_ids = fields.One2many('construction.quality.check.image', 'quality_check_id', string='Images')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('construction.quality.check') or 'New'
        return super().create(vals_list)

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_pass(self):
        self.write({'state': 'pass'})

    def action_fail(self):
        self.write({'state': 'fail'})

    def action_conditional(self):
        self.write({'state': 'conditional'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})


class ConstructionQualityCheckLine(models.Model):
    _name = 'construction.quality.check.line'
    _description = 'Quality Check Point'

    quality_check_id = fields.Many2one('construction.quality.check', string='Quality Check', ondelete='cascade')
    name = fields.Char(string='Check Point', required=True)
    description = fields.Text(string='Description')
    standard = fields.Char(string='Standard/Specification')
    result = fields.Selection([
        ('pass', 'Pass'),
        ('fail', 'Fail'),
        ('na', 'N/A'),
    ], string='Result', default='na')
    remarks = fields.Text(string='Remarks')


class ConstructionQualityCheckImage(models.Model):
    _name = 'construction.quality.check.image'
    _description = 'Quality Check Image'

    quality_check_id = fields.Many2one('construction.quality.check', string='Quality Check', ondelete='cascade')
    name = fields.Char(string='Description')
    image = fields.Binary(string='Image', attachment=True)
