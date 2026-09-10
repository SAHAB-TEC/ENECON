from odoo import models, fields

class HrLeaveType(models.Model):
    _inherit = 'hr.leave.type'

    unpaid_off = fields.Boolean(string="Unpaid Time Off")
