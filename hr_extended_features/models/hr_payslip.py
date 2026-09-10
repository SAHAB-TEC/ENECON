from odoo import api, fields, models, _
from odoo.tools.date_utils import start_of
from odoo.tools.misc import formatLang
from odoo import models, api
from datetime import date
from dateutil.relativedelta import relativedelta
from math import ceil

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    unpaid_leave_days = fields.Float(string="Unpaid Leave Days", compute="_compute_unpaid_leave_days")

    @api.depends('employee_id', 'date_from', 'date_to')
    def _compute_unpaid_leave_days(self):
        for payslip in self:
            domain = [
                ('employee_id', '=', payslip.employee_id.id),
                ('state', '=', 'validate'),
                ('request_date_from', '<=', payslip.date_to),
                ('request_date_to', '>=', payslip.date_from),
                ('holiday_status_id.unpaid_off', '=', True),
            ]
            unpaid_leaves = self.env['hr.leave'].search(domain)

            total_days = 0.0
            for leave in unpaid_leaves:
                # Determine the overlap range with the payslip
                leave_start = max(leave.request_date_from, payslip.date_from)
                leave_end = min(leave.request_date_to, payslip.date_to)
                total_days += (leave_end - leave_start).days + 1  # Inclusive of both start and end

            payslip.unpaid_leave_days = total_days
   

    
    def _get_inputs(self, contracts, payslip_id):
        res = super()._get_inputs(contracts, payslip_id)

        payslip = self.browse(payslip_id)
        date_from = payslip.date_from
        date_to = payslip.date_to

        for contract in contracts:
            employee = contract.employee_id

            # Mark expired attachments as closed
            expired_attachments = employee.salary_attachment_ids.filtered(
                lambda a: a.date_estimated_end and a.date_estimated_end < date_from
            )
            expired_attachments.write({'state': 'close'})

            # Only include salary attachments valid for this payslip
            valid_attachments = employee.salary_attachment_ids.filtered(
                lambda a: a.state == 'open'
                and a.date_start <= date_to
                and (not a.date_estimated_end or a.date_estimated_end >= date_from)
            )

            # Now you can apply your logic to create input lines from valid_attachments
            # (your logic might already exist in super call — customize if needed)

        return res


    def action_open_salary_attachments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Salary Attachments'),
            'res_model': 'hr.salary.attachment',
            'view_mode': 'list,form',
            'target': 'current',
            'domain': [
                ('employee_ids', 'in', self.employee_id.id),
                ('date_start', '<=', self.date_to),
                '|',
                ('date_estimated_end', '=', False),
                ('date_estimated_end', '>=', self.date_from),
            ],
            'context': {
                'default_employee_ids': [self.employee_id.id],
            }
        }

    salary_attachment_count = fields.Integer(
        string="Salary Attachment Count",
        compute='_compute_salary_attachment_count'
    )

    def _compute_salary_attachment_count(self):
        for payslip in self:
            attachments = self.env['hr.salary.attachment'].search_count([
                ('employee_ids', 'in', payslip.employee_id.id),
                ('date_start', '<=', payslip.date_to),
                '|',
                ('date_estimated_end', '=', False),
                ('date_estimated_end', '>=', payslip.date_from),
            ])
            payslip.salary_attachment_count = attachments


class HrSalaryAttachment(models.Model):
    _inherit = 'hr.salary.attachment'

    date_estimated_end = fields.Date(
        'Estimated End Date',
        compute='_compute_estimated_end',
        readonly=False,
        store=True,
        help='Approximated end date.',
    )

    @api.depends('state', 'total_amount', 'monthly_amount', 'date_start')
    def _compute_estimated_end(self):
        for record in self:
            if (
                record.state not in ['close', 'cancel']
                and record.has_total_amount
                and record.monthly_amount
                and record.date_start
            ):
                months = record.remaining_amount / record.monthly_amount
                months = int(months) if months.is_integer() else ceil(months)
                record.date_estimated_end = start_of(
                    record.date_start + relativedelta(months=months - 1),
                    'month'
                )
              
            else:
                record.date_estimated_end = False
    @api.model
    def action_auto_complete_salary_attachments(self):
        today = date.today()
        records = self.search([
            ('date_estimated_end', '<=', today),
            ('state', 'not in', ['cancel', 'close']),
        ])
        for rec in records:
            rec.state = 'close'

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            if rec.date_estimated_end and rec.date_estimated_end <= fields.Date.today():
                if rec.state not in ['close', 'cancel']:
                    rec.state = 'close'
        return res


    payslip_ids = fields.Many2many(
        'hr.payslip',
        string="Payslips",
        compute="_compute_payslips",
        store=False,
    )

    @api.depends('employee_ids', 'date_start', 'date_estimated_end')
    def _compute_payslips(self):
        for attachment in self:
            if not attachment.employee_ids or not attachment.date_start:
                attachment.payslip_ids = False
                continue

            domain = [
                ('employee_id', 'in', attachment.employee_ids.ids),
                ('date_from', '<=', attachment.date_estimated_end),
                ('date_to', '>=', attachment.date_start),
            ]
            attachment.payslip_ids = self.env['hr.payslip'].search(domain)
