# -*- coding: utf-8 -*-

##############################################################################
#
#
#    Copyright (C) 2020-TODAY .
#    Author: Eng.Ramadan Khalil (<rkhalil1990@gmail.com>)
#
#    It is forbidden to publish, distribute, sublicense, or sell copies
#    of the Software or modified copies of the Software.
#
##############################################################################

import pytz
from datetime import datetime, date, timedelta, time
from dateutil.relativedelta import relativedelta
from odoo import models, fields, tools, api, exceptions, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import format_date
from .utils import time_to_float, tz_localize, interval_to_float
import logging

# from odoo import models, api, _logger
_logger = logging.getLogger()
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
TIME_FORMAT = "%H:%M:%S"


class AttendanceSheet(models.Model):
    _name = 'attendance.sheet'
    _inherit = ['mail.thread.cc', 'mail.activity.mixin']
    _description = 'Hr Attendance Sheet'

    first_day_of_month = fields.Integer(
        string='First Day of Month',
        help='Specify the first day of the attendance month (e.g., 1 for 1st, 26 for 26th).',
        default=1)
    name = fields.Char("name")
    employee_id = fields.Many2one(comodel_name='hr.employee', string='Employee',
                                  required=True)

    batch_id = fields.Many2one(comodel_name='attendance.sheet.batch',
                               string='Attendance Sheet Batch')
    department_id = fields.Many2one(related='employee_id.department_id',
                                    string='Department', store=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True,
                                 copy=False, required=True,
                                 default=lambda self: self.env.company,
                                 states={'draft': [('readonly', False)]})
    date_from = fields.Date(string='Date From', readonly=True, required=True,
                            default=lambda self: fields.Date.to_string(
                                date.today().replace(day=1)), )
    date_to = fields.Date(string='Date To', readonly=True, required=True,
                          default=lambda self: fields.Date.to_string(
                              (datetime.now() + relativedelta(months=+1, day=1,
                                                              days=-1)).date()))
    line_ids = fields.One2many(comodel_name='attendance.sheet.line',
                               string='Attendances', readonly=True,
                               inverse_name='att_sheet_id')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirm', 'Confirmed'),
        ('done', 'Approved')], default='draft', tracking=True,
        string='Status', required=True, readonly=True, index=True,
        help=' * The \'Draft\' status is used when a HR user is creating a new  attendance sheet. '
             '\n* The \'Confirmed\' status is used when  attendance sheet is confirmed by HR user.'
             '\n* The \'Approved\' status is used when  attendance sheet is accepted by the HR Manager.')
    no_overtime = fields.Integer(compute="_compute_sheet_total",
                                 string="No of overtimes", readonly=True,
                                 store=True)
    tot_overtime = fields.Float(compute="_compute_sheet_total",
                                string="Total Over Time", readonly=True,
                                store=True)
    tot_difftime = fields.Float(compute="_compute_sheet_total",
                                string="Total Diff time Hours", readonly=True,
                                store=True)
    no_unpaid_leave = fields.Float(compute="_compute_sheet_total",
                                   string="No Unpaid Leave Times", readonly=True,
                                   store=True)
    tot_unpaid_leave = fields.Float(compute="_compute_sheet_total",
                                    string="Total Unpaid Leave", readonly=True,
                                    store=True)
    no_difftime = fields.Integer(compute="_compute_sheet_total",
                                 string="No of Diff Times", readonly=True,
                                 store=True)
    tot_late = fields.Float(compute="_compute_sheet_total",
                            string="Total Late In", readonly=True, store=True)
    no_late = fields.Integer(compute="_compute_sheet_total",
                             string="No of Lates",
                             readonly=True, store=True)
    no_absence = fields.Integer(compute="_compute_sheet_total",
                                string="No of Absence Days", readonly=True,
                                store=True)
    tot_absence = fields.Float(compute="_compute_sheet_total",
                               string="Total absence Hours", readonly=True,
                               store=True)
    tot_worked_hour = fields.Float(compute="_compute_sheet_total",
                                   string="Total Late In", readonly=True,
                                   store=True)
    att_policy_id = fields.Many2one(comodel_name='hr.attendance.policy',
                                    string="Attendance Policy ", required=True)
    payslip_id = fields.Many2one(comodel_name='hr.payslip', string='PaySlip')

    contract_id = fields.Many2one('hr.contract', string='Contract',
                                  readonly=False)

    unattended_days = fields.Integer(string="Number of Unattended Days", compute="_compute_sheet_total", readonly=True,
                                     store=True)
    attendance_count = fields.Integer(string="Number of Attended Days", compute="_compute_sheet_total", readonly=True,
                                      store=True)
    no_diff_days = fields.Integer(string="No of Diff Days", compute="_compute_diff_days", readonly=True, store=True)
    can_approve = fields.Boolean(compute='_compute_can_approve', string='Can Approve')

    def _compute_can_approve(self):
        for sheet in self:
            can_approve = False
            if self.env.user.has_group('rm_hr_attendance_sheet.group_attendance_sheet_manager'):
                can_approve = True
            elif self.env.user.has_group(
                    'rm_hr_attendance_sheet.group_attendance_sheet_leader') and sheet.employee_id.parent_id.user_id.id == self.env.user.id:
                can_approve = True
            sheet.can_approve = can_approve

    @api.depends('date_from', 'date_to', 'contract_id', 'attendance_count')
    def _compute_diff_days(self):
        for sheet in self:
            sheet.no_diff_days = 0
            contract_id = sheet.contract_id
            days = 0
            if not contract_id:
                contracts = sheet.employee_id._get_contracts(sheet.date_from,
                                                             sheet.date_to)
                if contracts:
                    contract_id = contracts[0]
            if not contract_id:
                sheet.no_diff_days = 0
                continue
            if not contract_id.date_start:
                sheet.no_diff_days = 0
                continue
            if contract_id.date_start <= sheet.date_from and not contract_id.date_end:
                sheet.no_diff_days = 0

            if contract_id.date_start <= sheet.date_from and contract_id.date_end and contract_id.date_end >= sheet.date_to:
                sheet.no_diff_days = 0
            elif contract_id.date_start >= sheet.date_from and (
                    not contract_id.date_end or (
                    contract_id.date_end and contract_id.date_end >= sheet.date_to)):
                sheet.no_diff_days = (contract_id.date_start - sheet.date_from).days
            elif contract_id.date_start <= sheet.date_from and contract_id.date_end and contract_id.date_end <= sheet.date_to:
                sheet.no_diff_days = (sheet.date_to - contract_id.date_end).days

            if sheet.no_diff_days <= 0:
                if sheet.contract_id.date_start and sheet.contract_id.date_start > sheet.date_from \
                        and sheet.contract_id.date_end and sheet.contract_id.date_end < sheet.date_to:
                    sheet.no_diff_days = (sheet.contract_id.date_start - sheet.date_from).days + (
                            sheet.date_to - sheet.contract_id.date_end).days
                elif sheet.contract_id.date_start and sheet.contract_id.date_start > sheet.date_from:
                    sheet.no_diff_days = (sheet.contract_id.date_start - sheet.date_from).days
                elif sheet.contract_id.date_end and sheet.contract_id.date_end < sheet.date_to:
                    sheet.no_diff_days = (sheet.date_to - sheet.contract_id.date_end).days

    def unlink(self):
        if any(self.filtered(
                lambda att: att.state not in ('draft', 'confirm'))):
            # TODO:un comment validation in case on non testing
            pass
            # raise UserError(_(
            #     'You cannot delete an attendance sheet which is '
            #     'not draft or confirmed!'))
        return super(AttendanceSheet, self).unlink()

    @api.constrains('date_from', 'date_to')
    def check_date(self):
        for sheet in self:
            emp_sheets = self.env['attendance.sheet'].search(
                [('employee_id', '=', sheet.employee_id.id),
                 ('id', '!=', sheet.id)])
            for emp_sheet in emp_sheets:
                if max(sheet.date_from, emp_sheet.date_from) < min(
                        sheet.date_to, emp_sheet.date_to):
                    raise UserError(_(
                        'You Have Already Attendance Sheet For That '
                        'Period  Please pick another date !'))

    def _cron_update_attendance_sheet(self, shift_days=0):
        today = date.today()
        start_month = today + relativedelta(day=1, days=shift_days)
        sheet_ids = self.search(
            [('date_from', '=', start_month),
             ('state', '=', 'draft')])
        for sheet in sheet_ids:
            sheet._action_get_attendance()

    def _cron_generate_attendance_sheet(self):
        _logger.info("Starting monthly attendance sheet generation...")

        today = date.today()
        company = self.env.company
        first_day_of_month = company.first_day_of_month
        if first_day_of_month != 1:
            if today.day < first_day_of_month:
                start_month = (today + relativedelta(day=first_day_of_month)) - relativedelta(months=1)
                end_month = today + relativedelta(day=first_day_of_month - 1)
            else:
                start_month = today + relativedelta(day=first_day_of_month)
                end_month = today + relativedelta(months=1, day=first_day_of_month - 1)
        else:
            start_month = today + relativedelta(day=1)
            end_month = today + relativedelta(months=1, day=1, days=-1)

        _logger.info("Start month: %s, End month: %s", start_month, end_month)

        contract_ids = self.env['hr.contract'].search(
            [('state', '=', 'open'), ('auto_attendance_sheet', '=', True),
             ('att_policy_id', '!=', False)]
        )
        _logger.info("Found %s contracts eligible for attendance sheet generation.", len(contract_ids))

        employee_ids = contract_ids.mapped('employee_id')

        for employee in employee_ids:
            try:
                _logger.info("Processing attendance sheet for employee %s", employee.name)

                attendance_sheet_id = self.env['attendance.sheet'].search([
                    ('employee_id', '=', employee.id),
                    ('date_from', '=', start_month),
                    ('date_to', '=', end_month)
                ], limit=1)

                if attendance_sheet_id:
                    _logger.info("Attendance sheet already exists for employee %s for period %s - %s",
                                 employee.name, start_month, end_month)
                    continue

                new_sheet = self.env['attendance.sheet'].new({
                    'employee_id': employee.id,
                    'date_from': start_month,
                    'date_to': end_month,
                })
                new_sheet.onchange_employee()
                values = self.env['attendance.sheet']._convert_to_write(new_sheet._cache)

                if not values.get('att_policy_id'):
                    _logger.warning("No Attendance Policy for Employee %s", employee.name)
                    continue

                att_sheet_id = self.env['attendance.sheet'].create(values)
                att_sheet_id._action_get_attendance()
                _logger.info("Attendance sheet created successfully for employee %s", employee.name)

            except Exception as e:
                _logger.warning("Error while creating monthly attendance sheet for employee %s: %s", employee.name, e)

        _logger.info("Monthly attendance sheet generation completed.")

    # def _cron_generate_attendance_sheet(self):
    #     today = date.today()
    #
    #     # Fetch the first day of the month from configuration
    #     company = self.env.company
    #     first_day_of_month = company.first_day_of_month
    #     if not first_day_of_month:
    #         _logger.warning("First day of the month is not set in company configuration")
    #         return
    #
    #     # Calculate start and end dates
    #     if today.day < first_day_of_month:
    #         start_month = (today + relativedelta(day=first_day_of_month)) - relativedelta(months=1)
    #         end_month = today + relativedelta(day=first_day_of_month - 1)
    #     else:
    #         start_month = today + relativedelta(day=first_day_of_month)
    #         end_month = today + relativedelta(months=1, day=first_day_of_month - 1)
    #
    #     att_sheet_obj = self.env['attendance.sheet']
    #     contract_ids = self.env['hr.contract'].search(
    #         [('state', '=', 'open'), ('auto_attendance_sheet', '=', True),
    #          ('att_policy_id', '!=', False)]
    #     )
    #     employee_ids = contract_ids.mapped('employee_id')
    #
    #     for employee in employee_ids:
    #         try:
    #             # Check if an attendance sheet already exists for this period
    #             attendance_sheet_id = att_sheet_obj.search([
    #                 ('employee_id', '=', employee.id),
    #                 ('date_from', '=', start_month),
    #                 ('date_to', '=', end_month)
    #             ], limit=1)
    #
    #             if attendance_sheet_id:
    #                 _logger.info("Attendance sheet already exists for employee %s for period %s - %s",
    #                              employee.name, start_month, end_month)
    #                 continue
    #
    #             # Prepare a new attendance sheet record
    #             new_sheet = att_sheet_obj.new({
    #                 'employee_id': employee.id,
    #                 'date_from': start_month,
    #                 'date_to': end_month,
    #             })
    #             new_sheet.onchange_employee()
    #             values = att_sheet_obj._convert_to_write(new_sheet._cache)
    #
    #             # Check if attendance policy is set
    #             if not values.get('att_policy_id'):
    #                 _logger.warning("No Attendance Policy for Employee %s", employee.name)
    #                 continue
    #
    #             # Create the attendance sheet and fetch attendances
    #             att_sheet_id = att_sheet_obj.create(values)
    #             att_sheet_id.get_attendances()
    #             _logger.info("Attendance sheet created successfully for employee %s", employee.name)
    #
    #         except ValidationError as e:
    #             _logger.warning("Validation Error while creating attendance sheet for employee %s: %s", employee.name, e)
    #         except Exception as e:
    #             _logger.warning("Error while creating monthly attendance sheet for employee %s: %s", employee.name, e)

    # def _cron_generate_attendance_sheet(self):
    #     today = date.today()
    #
    #     # Fetch the first day of the month from configuration
    #     company = self.env.company
    #     first_day_of_month = company.first_day_of_month
    #     # another way to fetch the first day of the month
    #     # config_settings = self.env['res.config.settings'].sudo().search([('company_id', '=', self.env.company.id)])
    #     # first_day_of_month = config_settings.first_day_of_month
    #     if today.day < first_day_of_month:
    #         start_month = (today + relativedelta(day=first_day_of_month)) - relativedelta(months=1)
    #         end_month = today + relativedelta(day=first_day_of_month - 1)
    #     else:
    #         start_month = today + relativedelta(day=first_day_of_month)
    #         end_month = today + relativedelta(months=1, day=first_day_of_month - 1)
    #
    #     att_sheet_obj = self.env['attendance.sheet']
    #     contract_ids = self.env['hr.contract'].search(
    #         [('state', '=', 'open'), ('auto_attendance_sheet', '=', True),
    #          ('att_policy_id', '!=', False)]
    #     )
    #     employee_ids = contract_ids.mapped('employee_id')
    #
    #     for employee in employee_ids:
    #         try:
    #             attendance_sheet_id = att_sheet_obj.search(
    #                 [('employee_id', '=', employee.id),
    #                  '|',
    #                  ('date_from', '=', start_month),
    #                  ('date_to', '=', end_month)]
    #             )
    #             if attendance_sheet_id:
    #                 continue
    #
    #             new_sheet = att_sheet_obj.new({
    #                 'employee_id': employee.id,
    #                 'date_from': start_month,
    #                 'date_to': end_month,
    #             })
    #             new_sheet.onchange_employee()
    #             values = att_sheet_obj._convert_to_write(new_sheet._cache)
    #
    #             if not values.get('att_policy_id'):
    #                 _logger.warning('No Attendance Policy For Employee %s' % employee.name)
    #                 continue
    #
    #             att_sheet_id = att_sheet_obj.create(values)
    #             att_sheet_id.get_attendances()
    #
    #         except Exception as e:
    #             _logger.warning('Error While Creating monthly attendance sheet %s' % e)

    # def _cron_generate_attendance_sheet(self):
    #     today = date.today()
    #     start_month = today + relativedelta(day=1)
    #     end_month = today + relativedelta(months=1, day=1, days=-1)
    #     att_sheet_obj = self.env['attendance.sheet']
    #     contract_ids = self.env['hr.contract'].search(
    #         [('state', '=', 'open'), ('auto_attendance_sheet', '=', True),
    #          ('att_policy_id', '!=', False)])
    #     employee_ids = contract_ids.mapped('employee_id')
    #     for employee in employee_ids:
    #         try:
    #             attendance_sheet_id = att_sheet_obj.search(
    #                 [('employee_id', '=', employee.id),
    #                  '|',
    #                  ('date_from', '=', start_month),
    #                  ('date_to', '=', end_month),
    #                  ])
    #             if attendance_sheet_id:
    #                 continue
    #
    #             new_sheet = att_sheet_obj.new({
    #                 'employee_id': employee.id,
    #                 'date_from': start_month,
    #                 'date_to': end_month,
    #
    #             })
    #             new_sheet.onchange_employee()
    #             values = att_sheet_obj._convert_to_write(new_sheet._cache)
    #             if not values.get('att_policy_id'):
    #                 _logger.warning(
    #                     (
    #                             'No Attendance Policy For Employee  %s ' % employee.name))
    #                 continue
    #             att_sheet_id = att_sheet_obj.create(values)
    #             att_sheet_id._action_get_attendance()
    #         except Exception as e:
    #             _logger.warning(
    #                 ('Error While Creating monthly attendance sheet %s ' % e))

    def action_confirm(self):
        self.write({'state': 'confirm'})

    def action_approve(self):
        self.action_create_payslip()
        self.write({'state': 'done'})

    def action_draft(self):
        self.write({'state': 'draft'})

    @api.onchange('employee_id', 'date_from', 'date_to')
    def onchange_employee(self):
        if not self.employee_id or not self.date_from or not self.date_to:
            return
        employee = self.employee_id
        date_from = self.date_from
        date_to = self.date_to
        if self.company_id.first_day_of_month != 1:
            display_month = date_from + relativedelta(months=1)
        else:
            display_month = date_from
        self.name = 'Attendance Sheet - %s - %s' % (
            self.employee_id.name or '',
            format_date(self.env, display_month, date_format="MMMM y")
        )
        self.company_id = employee.company_id
        contracts = employee._get_contracts(date_from, date_to)
        if not contracts:
            raise ValidationError(_('There Is No Valid Contract For Employee %s' % employee.name))
        self.contract_id = contracts[0]
        if not self.contract_id.att_policy_id:
            raise ValidationError(_('Employee %s does not have attendance policy' % employee.name))
        self.att_policy_id = self.contract_id.att_policy_id

    # @api.onchange('employee_id', 'date_from', 'date_to')
    # def onchange_employee(self):
    #     if (not self.employee_id) or (not self.date_from) or (not self.date_to):
    #         return
    #     employee = self.employee_id
    #     date_from = self.date_from
    #     date_to = self.date_to
    #     self.name = 'Attendance Sheet - %s - %s' % (self.employee_id.name or '',
    #                                                 format_date(self.env,
    #                                                             self.date_from,
    #                                                             date_format="MMMM y"))
    #     self.company_id = employee.company_id
    #     contracts = employee._get_contracts(date_from, date_to)
    #     if not contracts:
    #         raise ValidationError(
    #             _('There Is No Valid Contract For Employee %s' % employee.name))
    #     self.contract_id = contracts[0]
    #     if not self.contract_id.att_policy_id:
    #         raise ValidationError(_(
    #             "Employee %s does not have attendance policy" % employee.name))
    #     self.att_policy_id = self.contract_id.att_policy_id

    @api.depends('line_ids.overtime', 'line_ids.diff_time', 'line_ids.late_in')
    def _compute_sheet_total(self):
        """
        Compute Total overtime,late ,absence,diff time and worked hours
        :return:
        """
        for sheet in self:
            # Compute Total Overtime
            unpaid_leaves = sheet.line_ids.filtered(lambda l: l.status == 'leave' and l.unpaid_leave == True)
            sheet.no_unpaid_leave = len(unpaid_leaves)
            sheet.tot_unpaid_leave = sum([l.unpaid_leave for l in unpaid_leaves])
            overtime_lines = sheet.line_ids.filtered(lambda l: l.overtime > 0)
            sheet.tot_overtime = sum([l.overtime for l in overtime_lines])
            sheet.no_overtime = len(overtime_lines)
            # Compute Total Late In
            late_lines = sheet.line_ids.filtered(lambda l: l.late_in > 0)
            sheet.tot_late = sum([l.late_in for l in late_lines])
            sheet.no_late = len(late_lines)
            # Compute Absence
            absence_lines = sheet.line_ids.filtered(
                lambda l: l.diff_time > 0 and l.status == "ab")
            sheet.tot_absence = sum([l.diff_time for l in absence_lines])
            sheet.no_absence = len(absence_lines)
            diff_lines = sheet.line_ids.filtered(
                lambda l: l.diff_time > 0 and l.status != "ab")
            sheet.tot_difftime = sum([l.diff_time for l in diff_lines])
            sheet.no_difftime = len(diff_lines)

            from_date = sheet.date_from
            to_date = sheet.date_to
            all_dates = [(from_date + timedelta(days=x)) for x in
                         range((to_date - from_date).days + 1)]
            uwd_cnt = 0
            wd_cnt = 0
            for day in all_dates:
                day_lines = sheet.line_ids.filtered(
                    lambda l:
                    l.date == day and
                    (l.status in ['leave', 'ph', 'ab'])
                )
                if day_lines:
                    uwd_cnt += 1
            sheet.unattended_days = uwd_cnt

            for day in all_dates:
                day_lines = sheet.line_ids.filtered(
                    lambda l: l.date == day and (l.worked_hours > 0))
                if day_lines:
                    wd_cnt += 1
            sheet.attendance_count = wd_cnt

    def _get_float_from_time(self, time):
        str_time = datetime.strftime(time, "%H:%M")
        split_time = [int(n) for n in str_time.split(":")]
        float_time = split_time[0] + split_time[1] / 60.0
        return float_time

    def get_attendance_intervals(self, employee, day_start, day_end, tz):
        """

        :param employee:
        :param day_start:datetime the start of the day in datetime format
        :param day_end: datetime the end of the day in datetime format
        :return:
        """
        day_start_native = day_start.replace(tzinfo=tz).astimezone(
            pytz.utc).replace(tzinfo=None)
        day_end_native = day_end.replace(tzinfo=tz).astimezone(
            pytz.utc).replace(tzinfo=None)
        res = []
        attendances = self.env['hr.attendance'].sudo().search(
            [('employee_id', '=', employee.id),
             ('check_in', '>=', day_start_native),
             ('check_in', '<=', day_end_native)],
            order="check_in")
        for att in attendances:
            check_in = att.check_in
            check_out = att.check_out
            if not check_out:
                continue
            res.append((check_in, check_out))
        return res

    def _get_emp_leave_intervals(self, employee_id, day_start, day_end, wk_intervals):
        leave_obj = self.env['hr.leave']

        # Update the search domain to remove 'holiday_type'
        leave_ids = leave_obj.search([
            ('state', '=', 'validate'),
            ('employee_id', '=', employee_id.id),
            ('request_date_from', '<=', day_end),
            ('request_date_to', '>=', day_start)
        ])

        leave_intervals = []
        for leave in leave_ids:
            leave_intervals.append((leave.date_from, leave.date_to))

        return leave_intervals


    # def _get_emp_leave_intervals(self, emp, start_datetime=None,
    #                              end_datetime=None, work_intervals=None):
    #     leaves = []
    #     leave_obj = self.env['hr.leave']
    #     leave_start_date = start_datetime + relativedelta(days=-1)
    #     leave_end_date = end_datetime + relativedelta(days=1)
    #     leave_ids = leave_obj.search([('state', '=', 'validate'),
    #                                   ('date_from', '>=', leave_start_date),
    #                                   ('date_to', '<=', leave_end_date),
    #                                   '|',
    #                                   '|',
    #                                   '|',
    #                                   '&',
    #                                   ('holiday_type', '=', 'employee'),
    #                                   '|',
    #                                   ('employee_id', '=', emp.id),
    #                                   ('employee_ids', '=', emp.id),
    #                                   '&',
    #                                   ('holiday_type', '=', 'department'),
    #                                   ('department_id.member_ids', '=', emp.id),
    #                                   '&',
    #                                   ('holiday_type', '=', 'company'),
    #                                   ('company_id', '=', emp.company_id.id),
    #                                   '&',
    #                                   ('holiday_type', '=', 'category'),
    #                                   ('category_id.employee_ids', 'in', emp.id),
    #                                   ])
    #
    #     for leave in leave_ids:
    #         date_from = leave.date_from
    #         if end_datetime and date_from > end_datetime:
    #             continue
    #         date_to = leave.date_to
    #         if start_datetime and date_to < start_datetime:
    #             continue
    #         if not work_intervals:
    #             leaves.append((date_from, date_to, leave.holiday_status_id.id))
    #         elif any([max(work_interval[0], date_from) < min(work_interval[1], date_to) for work_interval in
    #                   work_intervals]):
    #             leaves.append((date_from, date_to, leave.holiday_status_id.id))
    #     return leaves

    def get_public_holiday(self, date, emp):
        public_holiday = []
        public_holidays = self.env['hr.public.holiday'].sudo().search(
            [('date_from', '<=', date), ('date_to', '>=', date),
             ('state', '=', 'active')])
        for ph in public_holidays:
            print('ph is', ph.name, [e.name for e in ph.emp_ids])
            if not ph.emp_ids:
                return public_holidays
            if emp.id in ph.emp_ids.ids:
                public_holiday.append(ph.id)
        return public_holiday

    def action_get_attendance(self):
        for sheet in self:
            self._action_get_attendance()

    def _pre_get_attendance(self):
        self.ensure_one()
        self.line_ids.unlink(allow_action=True)

    def _create_ph_lines(self, day, tz, policy_id, att_intervals):
        self.ensure_one()
        ot_type = 'ph'
        day_str = day.strftime('%A')
        att_lines = []
        if att_intervals:
            for att_interval in att_intervals:
                act_overtime, calc_overtime = policy_id.get_overtime(ot_type=ot_type,
                                                                     ot_intervals=[att_interval])
                ac_sign_in = time_to_float(tz_localize(att_interval[0], tz))
                worked_hours = interval_to_float(att_interval)
                ac_sign_out = ac_sign_in + worked_hours
                values = {
                    'date': day,
                    'day': str(day.weekday()),
                    'ac_sign_in': ac_sign_in,
                    'ac_sign_out': ac_sign_out,
                    'worked_hours': worked_hours,
                    'overtime': calc_overtime,
                    'act_overtime': act_overtime,
                    'att_sheet_id': self.id,
                    'status': 'ph',
                    'note': _("working on Public Holiday")
                }
                att_lines.append(values)
        else:
            values = {
                'date': day,
                'day': str(day.weekday()),
                'att_sheet_id': self.id,
                'status': 'ph',
            }
            att_lines.append(values)
        line_ids = self.env['attendance.sheet.line'].create(att_lines)
        return line_ids

    def _create_we_lines(self, day, tz, policy_id, att_intervals):
        self.ensure_one()
        ot_type = 'we'
        day_str = day.strftime('%A')
        day_number = day.weekday()
        att_lines = []
        if att_intervals:
            for att_interval in att_intervals:
                act_overtime, calc_overtime = policy_id.get_overtime(ot_type=ot_type,
                                                                     ot_intervals=[att_interval])
                ac_sign_in = time_to_float(tz_localize(att_interval[0], tz))
                worked_hours = interval_to_float(att_interval)
                ac_sign_out = ac_sign_in + worked_hours
                values = {
                    'date': day,
                    'day': str(day_number),
                    'ac_sign_in': ac_sign_in,
                    'ac_sign_out': ac_sign_out,
                    'overtime': calc_overtime,
                    'act_overtime': act_overtime,
                    'worked_hours': worked_hours,
                    'att_sheet_id': self.id,
                    'status': 'weekend',
                    'note': _("working in weekend")
                }
                att_lines.append(values)
        else:
            values = {
                'date': day,
                'day': str(day_number),
                'att_sheet_id': self.id,
                'status': 'weekend',
                'note': ""
            }
            att_lines.append(values)
        line_ids = self.env['attendance.sheet.line'].create(att_lines)
        return line_ids

    def _create_wd_lines(self, day, tz, policy_id, calendar_id, late_cnt, diff_cnt, leaves, wk_interval,
                             att_wk_intervals):
        self.ensure_one()
        pl_sign_in = time_to_float(tz_localize(wk_interval[0], tz))
        pl_work_hours = interval_to_float(wk_interval)
        pl_sign_out = pl_sign_in + pl_work_hours
        worked_hours = 0
        diff_intervals = []
        ot_type = 'wd'
        status = ""
        note = ""
        act_late = 0
        act_diff = 0
        day_str = day.strftime('%A')
        ac_sign_in = time_to_float(tz_localize(att_wk_intervals[0][0], tz))

        start_time = tz_localize(att_wk_intervals[0][0], tz)
        end_time = tz_localize(att_wk_intervals[-1][1], tz)
        time_difference = end_time - start_time
        tot_wk_hours = time_difference.total_seconds() / 3600

        ac_sign_out = ac_sign_in + tot_wk_hours

        late_interval = (wk_interval[0], att_wk_intervals[0][0])
        ot_interval = (wk_interval[1], att_wk_intervals[-1][1])

        if ot_interval[1] < ot_interval[0] and len(att_wk_intervals) == 1:
            diff_intervals.append((ot_interval[1], ot_interval[0]))
        if len(att_wk_intervals) > 1:
            remain_interval = (att_wk_intervals[0][1], wk_interval[1])
            for att_wk_interval in att_wk_intervals:
                worked_hours += interval_to_float(att_wk_interval)
                if att_wk_interval[1] <= remain_interval[0]:
                    continue
                if att_wk_interval[0] >= remain_interval[1]:
                    break
                if remain_interval[0] < att_wk_interval[0] < remain_interval[1]:
                    diff_intervals.append((remain_interval[0], att_wk_interval[0]))
                    remain_interval = (att_wk_interval[1], remain_interval[1])
            if remain_interval and remain_interval[0] <= wk_interval[1]:
                diff_intervals.append((remain_interval[0], wk_interval[1]))
        else:
            worked_hours = interval_to_float(att_wk_intervals[0])

        if leaves:
            status = "leave"
            # get the diff time for the leave
            for diff_interval in diff_intervals:
                df_intervals = calendar_id.att_interval_without_leaves(diff_interval, leaves)
                for df_interval in df_intervals:
                    act_diff += interval_to_float(df_interval)
            # get the late time for the leave
            lt_intervals = calendar_id.att_interval_without_leaves(late_interval, leaves)
            for lt_interval in lt_intervals:
                act_late += interval_to_float(lt_interval)
        else:
            act_late = interval_to_float(late_interval)
            act_diff = sum([interval_to_float(df_interval) for df_interval in diff_intervals])
        calc_late, late_cnt = policy_id.get_late(act_late, late_cnt)
        calc_diff, diff_cnt = policy_id.get_diff(act_diff, diff_cnt)
        act_overtime, calc_overtime = policy_id.get_overtime(ot_type=ot_type, ot_intervals=[ot_interval])

        # Detect unpaid leave on this day (any overlapping validated leave type marked as unpaid)
        is_unpaid_leave = False
        if status == 'leave':
            day_start = datetime.combine(day, time.min)
            day_end = datetime.combine(day, time.max)
            leave_recs = self.env['hr.leave'].search([
                ('state', '=', 'validate'),
                ('employee_id', '=', self.employee_id.id),
                ('request_date_from', '<=', day_end),
                ('request_date_to', '>=', day_start),
            ], limit=1)
            if leave_recs:
                is_unpaid_leave = any(l.holiday_status_id.unpaid_leave for l in leave_recs)

        values = {
            'date': day,
            'day': str(day.weekday()),
            'pl_sign_in': pl_sign_in,
            'pl_sign_out': pl_sign_out,
            'ac_sign_in': ac_sign_in,
            'ac_sign_out': ac_sign_out,
            'late_in': calc_late,
            'act_late_in': act_late,
            'worked_hours': worked_hours,
            'overtime': calc_overtime,
            'act_overtime': act_overtime,
            'diff_time': calc_diff,
            'act_diff_time': act_diff,
            'status': status,
            'att_sheet_id': self.id,
            'note': note,
            'unpaid_leave': is_unpaid_leave,
        }
        wd_line_id = self.env['attendance.sheet.line'].create(values)
        return wd_line_id, late_cnt, diff_cnt

    def _create_ab_lines(self, day, tz, policy_id, calendar_id, abs_cnt, leaves, wk_interval):
        self.ensure_one()
        day_str = day.strftime('%A')
        day_number = day.weekday()
        pl_sign_in = time_to_float(tz_localize(wk_interval[0], tz))
        pl_work_hours = interval_to_float(wk_interval)
        pl_sign_out = pl_sign_in + pl_work_hours
        status = ""
        note = ""
        abs_flag = False
        act_diff = 0
        unpaid_leave = False
        contract_id = self.contract_id
        contract_start = contract_id.date_start
        contract_end = contract_id.date_end
        if (contract_start and contract_start > day) or (contract_end and contract_end < day):
            note = "Out Of Contract Days"
        else:
            diff_interval = (
                (wk_interval[0], wk_interval[1]))
            if leaves:
                status = "leave"
                # Determine unpaid leave by checking overlapping validated leaves for this day
                day_start = datetime.combine(day, time.min)
                day_end = datetime.combine(day, time.max)
                leave_recs = self.env['hr.leave'].search([
                    ('state', '=', 'validate'),
                    ('employee_id', '=', self.employee_id.id),
                    ('request_date_from', '<=', day_end),
                    ('request_date_to', '>=', day_start),
                ])
                unpaid_leave = any(l.holiday_status_id.unpaid_leave for l in leave_recs)
                # get the diff time for the leave
                df_intervals = calendar_id.att_interval_without_leaves(diff_interval, leaves)
                for df_interval in df_intervals:
                    act_diff += interval_to_float(df_interval)
            else:
                status = "ab"
                act_diff = interval_to_float(diff_interval)
        if status == 'ab':
            if not abs_flag:
                abs_cnt += 1
            abs_flag = True
        calc_diff = policy_id.get_absence(act_diff, abs_cnt)
        values = {
            'date': day,
            'day': str(day_number),
            'pl_sign_in': pl_sign_in,
            'pl_sign_out': pl_sign_out,
            'diff_time': calc_diff,
            'act_diff_time': act_diff,
            'status': status,
            'att_sheet_id': self.id,
            'unpaid_leave': unpaid_leave,
            'note': note
        }
        abs_line_id = self.env['attendance.sheet.line'].create(values)
        return abs_line_id, abs_cnt

    def _create_out_wk_lines(self, day, tz, policy_id, out_wk_intervals):
        self.ensure_one()
        ot_type = 'wd'
        day_str = day.strftime('%A')
        note = _("overtime out of work intervals")
        att_lines = []
        for att_out in out_wk_intervals:
            ot_interval = (att_out[0], att_out[1])
            ac_sign_in = time_to_float(tz_localize(att_out[0], tz))
            # work_hours = time_to_float(att_out)
            work_hours = time_to_float(tz_localize(att_out[-1], tz))
            ac_sign_out = ac_sign_in + work_hours
            act_overtime, calc_overtime = policy_id.get_overtime(ot_type, ot_intervals=[ot_interval])
            values = {
                'date': day,
                'day': str(day.weekday()),
                'pl_sign_in': 0,
                'pl_sign_out': 0,
                'ac_sign_in': ac_sign_in,
                'ac_sign_out': ac_sign_out,
                'overtime': calc_overtime,
                'act_overtime': act_overtime,
                'worked_hours': work_hours,
                'note': note,
                'att_sheet_id': self.id
            }
            att_lines.append(values)
        line_ids = self.env['attendance.sheet.line'].create(att_lines)
        return line_ids

    def _action_get_attendance(self):
        """
        Get Attendance for the employee
        """
        self.ensure_one()
        self._pre_get_attendance()
        employee_id = self.employee_id
        tz = employee_id._get_employee_tz()
        contract_id = self.contract_id
        if not contract_id:
            raise ValidationError(_(
                'Please add contract to the %s `s contract ' % employee_id.name))
        calendar_id = contract_id.resource_calendar_id
        if not calendar_id:
            raise ValidationError(_(
                'Can`t find calendar for the employee %s' % employee_id.name))
        policy_id = self.att_policy_id
        if not policy_id:
            raise ValidationError(_(
                'Please add Attendance Policy to the %s `s contract ' % employee_id.name))
        all_dates = [(self.date_from + timedelta(days=x)) for x in
                     range((self.date_to - self.date_from).days + 1)]
        contract_start = contract_id.date_start
        contract_end = contract_id.date_end
        abs_cnt = 0
        late_cnt = []
        diff_cnt = []
        att_line_ids = self.env['attendance.sheet.line']
        for day in all_dates:
            day_start = datetime.combine(day, time.min)
            day_end = datetime.combine(day, time.max)
            day_str = day.strftime('%A')
            wk_intervals = calendar_id.att_get_work_intervals(self, day_start, day_end, tz)
            att_intervals = self.get_attendance_intervals(employee_id, day_start, day_end, tz)
            leaves = self._get_emp_leave_intervals(employee_id, day_start, day_end, wk_intervals)
            public_holiday = self.get_public_holiday(day, employee_id)
            reserved_intervals = []
            abs_flag = False
            if not wk_intervals:
                # if no work intervals then the day is Weekend
                we_line_ids = self._create_we_lines(day, tz, policy_id,
                                                    att_intervals=att_intervals)
                att_line_ids |= we_line_ids
                continue
            if public_holiday:
                # if public holiday then the day is Public Holiday
                ph_line_ids = self._create_ph_lines(day, tz, policy_id,
                                                    att_intervals=att_intervals)
                att_line_ids |= ph_line_ids
                continue
            for i, wk_interval in enumerate(wk_intervals):
                att_wk_intervals = []
                for j, att_interval in enumerate(att_intervals):
                    if max(wk_interval[0], att_interval[0]) < min(wk_interval[1], att_interval[1]):
                        if i + 1 < len(wk_intervals) and max(wk_intervals[i + 1][0], att_interval[0]) < min(
                                wk_intervals[i + 1][1], att_interval[1]):
                            att_intervals[j] = (att_interval[0], wk_intervals[i + 1][0])
                            att_intervals.insert(j + 1, (wk_intervals[i + 1][0], att_interval[1]))
                        att_wk_intervals.append(att_intervals[j])
                reserved_intervals += att_wk_intervals

                if att_wk_intervals:
                    wd_line_id, late_cnt, diff_cnt = self._create_wd_lines(
                        day=day,
                        tz=tz,
                        policy_id=policy_id,
                        calendar_id=calendar_id,
                        late_cnt=late_cnt,
                        diff_cnt=diff_cnt,
                        leaves=leaves,
                        wk_interval=wk_interval,
                        att_wk_intervals=att_wk_intervals)
                    att_line_ids |= wd_line_id
                else:
                    status = "ab"
                    abs_line_id, abs_cnt = self._create_ab_lines(
                        day=day,
                        tz=tz,
                        policy_id=policy_id,
                        calendar_id=calendar_id,
                        abs_cnt=abs_cnt,
                        leaves=leaves,
                        wk_interval=wk_interval)
                    att_line_ids |= abs_line_id
            out_wk_intervals = [x for x in att_intervals if
                                x not in reserved_intervals]
            if out_wk_intervals:
                # Update the day_end variable to reflect the actual end time of the workday
                day_end = max([x[1] for x in out_wk_intervals])
                out_line_ids = self._create_out_wk_lines(day, tz, policy_id, out_wk_intervals)
                att_line_ids |= out_line_ids
        return att_line_ids

    def action_payslip(self):
        self.ensure_one()
        payslip_id = self.payslip_id
        if not payslip_id:
            payslip_id = self.action_create_payslip()[0]
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payslip',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': payslip_id.id,
            'views': [(False, 'form')],
        }

    def action_create_payslip(self):
        payslip_obj = self.env['hr.payslip']
        payslips = payslip_obj
        for sheet in self:
            contracts = sheet.employee_id._get_contracts(sheet.date_from,
                                                         sheet.date_to)
            if not contracts:
                raise ValidationError(_('There is no active contract for current employee'))
            if sheet.payslip_id:
                raise ValidationError(_('Payslip Has Been Created Before'))
            payslip_name = contracts[0].structure_type_id.default_struct_id.payslip_name or _('Salary Slip')
            name = '%(payslip_name)s - %(employee_name)s - %(dates)s' % {
                'payslip_name': payslip_name,
                'employee_name': sheet.employee_id.name,
                'dates': format_date(self.env, sheet.date_from, date_format="MMMM y")
            }

            payslip_id = payslip_obj.create({
                'name': name,
                'employee_id': sheet.employee_id.id,
                'date_from': sheet.date_from,
                'date_to': sheet.date_to,
                'attendance_sheet_ids': [(4, sheet.id)],
                'contract_id': contracts[0].id,
                'struct_id': contracts[0].structure_type_id.default_struct_id.id,
            })
            payslip_id.compute_sheet()
            sheet.payslip_id = payslip_id
            payslips += payslip_id
        return payslips

    def create_payslip(self):
        payslips = self.env['hr.payslip']
        for att_sheet in self:
            if att_sheet.payslip_id:
                continue
            from_date = att_sheet.date_from
            to_date = att_sheet.date_to
            employee = att_sheet.employee_id
            slip_data = self.env['hr.payslip'].onchange_employee_id(from_date,
                                                                    to_date,
                                                                    employee.id,
                                                                    contract_id=False)
            contract_id = slip_data['value'].get('contract_id')
            if not contract_id:
                raise ValidationError(
                    'There is No Contracts for %s That covers the period of the Attendance sheet' % employee.name)
            res = {
                'employee_id': employee.id,
                'name': slip_data['value'].get('name'),
                'struct_id': slip_data['value'].get('struct_id'),
                'contract_id': contract_id,
                'input_line_ids': [(0, 0, x) for x in
                                   slip_data['value'].get('input_line_ids')],

                'date_from': from_date,
                'date_to': to_date,
            }
            new_payslip = self.env['hr.payslip'].create(res)
            att_sheet.payslip_id = new_payslip
            payslips += new_payslip
        return payslips


class AttendanceSheetLine(models.Model):
    _name = 'attendance.sheet.line'

    state = fields.Selection([
        ('draft', 'Draft'),
        ('sum', 'Summary'),
        ('confirm', 'Confirmed'),
        ('done', 'Approved')], related='att_sheet_id.state', store=True, )

    date = fields.Date("Date")
    day = fields.Selection([
        ('0', 'Monday'),
        ('1', 'Tuesday'),
        ('2', 'Wednesday'),
        ('3', 'Thursday'),
        ('4', 'Friday'),
        ('5', 'Saturday'),
        ('6', 'Sunday')
    ], 'Day of Week', required=True, index=True, )
    att_sheet_id = fields.Many2one(comodel_name='attendance.sheet',
                                   ondelete="cascade",
                                   string='Attendance Sheet', readonly=True)
    employee_id = fields.Many2one(related='att_sheet_id.employee_id',
                                  string='Employee')
    pl_sign_in = fields.Float("Planned sign in", readonly=True)
    pl_sign_out = fields.Float("Planned sign out", readonly=True)
    worked_hours = fields.Float("Worked Hours", readonly=True)
    ac_sign_in = fields.Float("Actual sign in", readonly=True)
    ac_sign_out = fields.Float("Actual sign out", readonly=True)
    overtime = fields.Float("Overtime", readonly=True)
    act_overtime = fields.Float("Actual Overtime", readonly=True)
    late_in = fields.Float("Late In", readonly=True)
    diff_time = fields.Float("Diff Time",
                             help="Difference between the working time and attendance time(s) ",
                             readonly=True)
    act_late_in = fields.Float("Actual Late In", readonly=True)
    act_diff_time = fields.Float("Actual Diff Time",
                                 help="Difference between the working time and attendance time(s) ",
                                 readonly=True)
    status = fields.Selection(string="Status",
                              selection=[('ab', 'Absence'),
                                         ('weekend', 'Week End'),
                                         ('ph', 'Public Holiday'),
                                         ('leave', 'Leave'), ],
                              required=False, readonly=True)
    note = fields.Text("Note", readonly=True)
    unpaid_leave = fields.Boolean(string=('Unpaid Leave'), readonly=True)

    def unlink(self, allow_action=False):
        if not allow_action and not self.env.user.has_group('rm_hr_attendance_sheet.group_attendance_sheet_manager'):
            raise UserError(_('Only managers can delete attendance sheet lines.'))
        return super(AttendanceSheetLine, self).unlink()