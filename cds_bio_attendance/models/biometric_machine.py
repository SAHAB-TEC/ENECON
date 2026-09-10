# -*- coding: utf-8 -*-

##############################################################################
#    Copyright (c) 2021 CDS Solutions SRL. (https://cdsegypt.com)
#    Maintainer: Eng.Ramadan Khalil (<ramadan.khalil@cdsegypt.com>)
#    It is forbidden to publish, distribute, sublicense, or sell copies
#    of the Software or modified copies of the Software.
##############################################################################

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from itertools import groupby

from datetime import datetime, timedelta

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
TIME_FORMAT = "%H:%M:%S"
import logging
from itertools import zip_longest

_logger = logging.getLogger("CDS BIO-ATTENDANCE==>")
from odoo.addons.cds_bio_attendance.zk import ZK, const
from odoo import api, fields, models
import pytz
import sys
from pytz.exceptions import AmbiguousTimeError,NonExistentTimeError


PY3 = sys.version_info >= (3, 0)

if PY3:
    xrange = range


def get_time_from_float(float_type):
    str_off_time = str(float_type)
    official_hour = str_off_time.split('.')[0]
    official_minute = (
            "%2d" % int(
        str(float("0." + str_off_time.split('.')[1]) * 60).split('.')[
            0])).replace(
        ' ', '0')
    str_off_time = official_hour + ":" + official_minute
    str_off_time = datetime.strptime(str_off_time, "%H:%M").time()
    return str_off_time


def convert_date_to_utc(date, tz):
    local = pytz.timezone(tz)
    try:
        date = local.localize(date, is_dst=None)
        date = date.astimezone(pytz.utc)
    except AmbiguousTimeError:
        date = local.localize(date+relativedelta(hours=-2), is_dst=True)
        date = (date.astimezone(pytz.utc)) + relativedelta(hours=2)
    except NonExistentTimeError:
        date = local.localize(date + relativedelta(hours=-2), is_dst=True)
        date = (date.astimezone(pytz.utc)) + relativedelta(hours=2)
    date.strftime('%Y-%m-%d: %H:%M:%S')
    return date.replace(tzinfo=None)


def convert_date_to_local(date, tz):
    local = pytz.timezone(tz)
    date = date.replace(tzinfo=pytz.utc)
    date = date.astimezone(local)
    date.strftime('%Y-%m-%d: %H:%M:%S')
    return date.replace(tzinfo=None)


class biometric_record(models.Model):
    _name = 'biometric.record'
    _order = "name desc"

    name = fields.Datetime('Time')
    machine = fields.Many2one('biometric.machine', 'Machine Name',
                              ondelete='cascade')
    state = fields.Selection([
        ('success', 'Success'),
        ('failed', 'Failed')], default='success',
        string='Status', required=True, readonly=True, index=True, )
    note = fields.Char('Notes')


class biometric_log(models.Model):
    _name = 'biometric.log'
    _order = "name desc"
    _description = "Biometric Logs"
    name = fields.Datetime('Time')
    user = fields.Char('User No')
    employee_id = fields.Many2one('hr.employee', 'Employee', ondelete='cascade')
    machine = fields.Many2one('biometric.machine', 'Machine Name',
                              ondelete='cascade')
    type = fields.Selection([
        ('in', 'In'),
        ('out', 'Out')], default='in')


class biometric_machine(models.Model):
    _name = 'biometric.machine'
    _description = "Biometric Machine"

    @api.model
    def _cron_att_download(self):
        for mc in self.search([('state', '=', 'active')]):
            mc.download_attendancenew()
        self.download_attendance_from_log()

    @api.model
    def _cron_check_connection(self):
        print("iam in crone method")
        for mc in self.search([('state', '=', 'active')]):
            mc.check_notification()

    def check_notification(self):
        for mc in self:
            now = datetime.strftime(datetime.now(), DATETIME_FORMAT)
            yesterday = datetime.strftime(datetime.now() + timedelta(days=-1),
                                          DATETIME_FORMAT)

            records = self.env['biometric.record'].search(
                [('machine', '=', mc.id), ('name', '>=', yesterday),
                 ('name', '<=', now)])
            if any([r.state != 'failed' for r in records]):
                continue

            if mc.state != 'active':
                continue

            partners = self.env['res.partner']

            for user in self.env['res.users'].search([]):
                if user.has_group(
                        'cds_bio_attendance.group_check_bio_attendance'):
                    partners += user.partner_id
            if partners:
                mail_content = _(
                    'Dear Sir, <br> Attendance Biometric Machine:%s Has connection Error Please Check.<br> '
                    'Regards<br>') % (
                                   mc.name)
                main_content = {
                    'subject': _(
                        'Connection Error For Biometric MAchine Of :%s ') % (
                                   mc.name),
                    'author_id': self.env.user.partner_id.id,
                    'body_html': mail_content,
                    'recipient_ids': [(4, pid) for pid in partners.ids],
                }
                self.env['mail.mail'].sudo().create(main_content).send()

    @property
    def min_time(self):
        # Get min time
        if self.interval_min == 'sec':
            min_time = timedelta(seconds=self.time_interval_min)
        elif self.interval_min == 'min':
            min_time = timedelta(minutes=self.time_interval_min)
        elif self.interval_min == 'hour':
            min_time = timedelta(hours=self.time_interval_min)
        else:
            min_time = timedelta(days=self.time_interval_min)
        return min_time

    @property
    def max_time(self):
        # Get min time
        if self.interval_max == 'sec':
            max_time = timedelta(seconds=self.time_interval_max)
        elif self.interval_max == 'min':
            max_time = timedelta(minutes=self.time_interval_max)
        elif self.interval_max == 'hour':
            max_time = timedelta(hours=self.time_interval_max)
        else:
            max_time = timedelta(days=self.time_interval_max)
        return max_time

    @api.model
    def _tz_get(self):
        return [
            (tz, tz) for tz in
            sorted(
                pytz.all_timezones,
                key=lambda tz: tz if not
                tz.startswith('Etc/') else '_')]

    name = fields.Char('Name')
    ip_address = fields.Char('Ip address')
    type = fields.Selection(string="Machine Type",
                            selection=[('in', 'In Only'), ('out', 'Out Only'),
                                       ('inout', 'In/Out')], required=True,
                            default='inout')
    port = fields.Integer('Port', default=4370)
    sequence = fields.Integer('Sequence')
    timezone = fields.Selection(
        _tz_get, 'Timezone',
        help='Device timezone',
    )
    log_ids = fields.One2many(comodel_name="biometric.record",
                              inverse_name="machine", string="Log",
                              required=False, )
    time_interval_min = fields.Integer(
        'Min time',
        help='Min allowed time  between two registers', default=1)
    interval_min = fields.Selection(
        [('sec', 'Sec(s)'), ('min', 'Min(s)'),
         ('hour', 'Hour(s)'), ('days', 'Day(s)'), ],
        'Min allowed time', help='Min allowed time between two registers',
        default='sec')
    time_interval_max = fields.Integer(
        'Max time',
        help='Max allowed time  between two registers', default=1)
    interval_max = fields.Selection(
        [('sec', 'Sec(s)'), ('min', 'Min(s)'),
         ('hour', 'Hour(s)'), ('days', 'Day(s)'), ],
        'Max allowed time', help='Max allowed time between two registers',
        default='days')
    state = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'InActive')], default='inactive',
        tracking=True,
        string='Status', required=False, index=True, )

    attendance_log_ids = fields.One2many('biometric.log', 'machine',
                                         'Logs')
    password = fields.Integer('Communication Key')
    start_date = fields.Datetime('Start Fetching Date')
    employee_create = fields.Boolean('Create Employee  For Undefined ID')

    att_log_cnt = fields.Integer(compute='_compute_attendance_log_cnt')
    convert_type = fields.Selection(
        [('act', 'Actual'), ('filo', 'First In/Last Out')],
        string='Conversion Type', default='act')

    def action_active(self):
        for bio in self:
            bio.state = "active"

    def action_inactive(self):
        for bio in self:
            bio.state = "inactive"
    def _compute_attendance_log_cnt(self):
        for machine in self:
            machine.att_log_cnt = len(machine.attendance_log_ids)

    def action_view_attendance_log(self):
        self.ensure_one()
        action = self.env.ref(
            'cds_bio_attendance.action_view_biometric_log').read()[0]
        action['domain'] = [('machine', '=', self.id)]
        return action

    def download_attendance_from_log(self, employees=None):
        employee_obj = self.env['hr.employee']
        log_obj = self.env['biometric.log']
        logs = self.env['biometric.log'].search([('employee_id', '!=', False)], order='name ASC')
        if employees:
            logs = self.env['biometric.log'].search([('employee_id', 'in', employees)], order='name ASC')

        employee_ids = logs.mapped('employee_id')

        atts = []
        for i, employee_id in enumerate(employee_ids):
            employee_id = employee_id.sudo()
            user_log_ids = logs.filtered(lambda l: l.employee_id == employee_id)
            day_start_delay = False
            min_att_time = False
            calendar_id = employee_id.resource_calendar_id
            contract = employee_id.contract_id

            if calendar_id and calendar_id.day_start_delay:
                day_start_delay = relativedelta(
                    hours=calendar_id.day_start_delay)
            if calendar_id and calendar_id.min_working_hours:
                min_att_time = relativedelta(
                    hours=calendar_id.min_working_hours)
            _logger.info(
                '{}  ====> {} :Convert Log To Attendance For Employee : {} == > {}'.format(i, len(employee_ids),
                                                                                           employee_id.name, len(
                        user_log_ids)))
            for log in user_log_ids:
                type = 0
                atttime = log.name
                if log.type == 'in':
                    type = 0
                if log.type == 'out':
                    type = 1
                if not log.machine:
                    continue
                if log.machine and log.machine.start_date and log.name < log.machine.start_date:
                    continue
                tz_info = log.machine.timezone
                local_atttime = convert_date_to_local(atttime, tz_info)
                record_vals = {'name': datetime.now()}
                convert_type = log.machine.convert_type
                att = [employee_id.att_user_id, False, local_atttime, type]
                flex_lines = calendar_id.flex_line_ids.filtered(lambda l: local_atttime.weekday() == l.dayofweek)
                if flex_lines:
                    min_att_time = relativedelta(
                        hours=flex_lines[0].min_working_hours)
                try:
                    if convert_type == 'filo':
                        log.machine.action_create_atts_delay_filo([att],
                                                                  day_start_delay,
                                                                  min_att_time)
                        # if contract and contract.flexible_hours:
                        #     log.machine.action_create_atts_delay_filo([att],
                        #                                               day_start_delay,
                        #                                               min_att_time)
                        #
                        # else:
                        #     log.machine.action_create_atts_filo([att])


                    else:
                        log.machine.action_create_atts([att])
                except Exception as e:
                    _logger.info("++++++++++++Exception++++++++++++++++++++++",
                                 e)
                    record_vals['state'] = 'failed'
                    record_vals[
                        'note'] = 'Successful Connection But there is error while writing attendances from logs as -->log time:%s  log employee:%s the error is **%s**' % (
                        e, log.name, log.employee_id.name)
                    new_record = self.env['biometric.record'].sudo().create(
                        record_vals)
                    break

    # def download_from_log(self):
    #     employee_obj = self.env['hr.employee']
    #     logs = self.env['biometric.log'].search([])
    #     atts = []
    #     for log in logs.sorted(key=lambda l: l.name):
    #         employee_id = log.employee_id
    #         if not employee_id:
    #             employee_id = employee_obj.search(
    #                 [('att_user_id', '=', log.user)],
    #                 limit=1)
    #         if not employee_id:
    #             continue
    #
    #         atttime = log.name
    #         day_start_delay = False
    #         min_att_time = False
    #         calendar_id = employee_id.resource_calendar_id
    #         if calendar_id and calendar_id.day_start_delay:
    #             day_start_delay = relativedelta(
    #                 hours=calendar_id.day_start_delay)
    #             min_att_time = relativedelta(
    #                 hours=calendar_id.min_working_hours)
    #
    #         type = 0
    #         if log.type == 'in':
    #             type = 0
    #         if log.type == 'out':
    #             type = 1
    #         if log.machine:
    #             tz_info = log.machine.timezone
    #             local_atttime = convert_date_to_local(atttime, tz_info)
    #             record_vals = {'name': datetime.now()}
    #             att = [log.employee_id.att_user_id, False, local_atttime, type]
    #             try:
    #                 convert_type = log.machine.convert_type
    #                 if convert_type == 'filo':
    #                     if day_start_delay == False:
    #                         log.machine.action_create_atts_filo([att])
    #                     else:
    #                         log.machine.action_create_atts_delay_filo([att],
    #                                                                   day_start_delay,min_att_time)
    #
    #                 else:
    #                     log.machine.action_create_atts([att])
    #             except Exception as e:
    #                 _logger.info("++++++++++++Exception++++++++++++++++++++++",
    #                              e)
    #                 record_vals['state'] = 'failed'
    #                 record_vals[
    #                     'note'] = 'Successful Connection But there is error while writing attendances from logs as -->log time:%s  log employee:%s the error is **%s**' % (
    #                     e, log.name, log.employee_id.name)
    #                 new_record = self.env['biometric.record'].sudo().create(
    #                     record_vals)
    #                 break

    def action_download_from_log(self):
        employee_ids = self.env['hr.employee'].search(
            [('att_user_id', '!=', False), ('att_user_id', '>', 0)])
        for employee in employee_ids:
            employee.convert_log_to_attendance()

    def download_attendancenew(self):
        employee_obj = self.env['hr.employee']
        for machine in self:
            machine_ip = machine.ip_address
            port = machine.port
            res = False
            password = machine.password or 0
            zk = ZK(machine_ip, int(port), password=password, timeout=90,
                    ommit_ping=True)
            record_vals = {'name': datetime.now(),
                           'machine': machine.id}
            try:
                res = zk.connect()
                if res:
                    attendance = res.get_attendance()
                    if attendance:
                        try:
                            if machine.start_date:
                                attendance = [at for at in attendance if
                                              at.timestamp > machine.start_date]
                            self.action_create_log(attendance, machine.id)
                            record_vals['state'] = 'success'
                            record_vals[
                                'note'] = 'successful connection and attendance logs have been updated'
                            new_record = self.env[
                                'biometric.record'].sudo().create(record_vals)
                        except Exception as e:
                            zk.enableDevice()
                            try:
                                zk.disconnect()
                            except BaseException as exp:
                                _logger.info(
                                    "++++++++++++Exception++++++++++++++++++++++",
                                    exp)

                            record_vals['state'] = 'failed'
                            record_vals[
                                'note'] = 'Successful Connection But there is error while writing attendance logs as the error is **%s**' % e
                            new_record = self.env[
                                'biometric.record'].sudo().create(record_vals)

                    else:
                        record_vals['state'] = 'success'
                        record_vals[
                            'note'] = 'successful connection but there is no attendance logs'
                        new_record = self.env['biometric.record'].sudo().create(
                            record_vals)
            except Exception as exps:
                _logger.info("++++++++++++Exception++++++++++++++++++++++",
                             exps)
                record_vals['state'] = 'failed'
                record_vals[
                    'note'] = 'Failed ,please check the parameters and network connections.'
                new_record = self.env['biometric.record'].sudo().create(
                    record_vals)
                self.env.cr.commit()

    def action_create_atts(self, bio_attendances):
        employee_obj = self.env['hr.employee']
        for res in self:
            tz_info = res.timezone
            att_users = []
            users_atts = {}
            if not bio_attendances:
                continue
            bio_attendances.sort(key=lambda b: b[2])

            for att in bio_attendances:
                user_no = att[0]
                employee = employee_obj.search([('att_user_id', '=', user_no)],
                                               limit=1)
                att_time = att[2]
                time_utc = convert_date_to_utc(att_time, tz_info)
                att_type = att[3]

                if not employee:
                    if not res.employee_create:
                        continue
                    employee = employee_obj.create({
                        'name': 'Undefined user ID ' + str(user_no),
                        'att_user_id': user_no
                    })
                min_time = res.min_time
                str_att_time_utc = datetime.strftime(
                    convert_date_to_utc(att_time, tz_info),
                    DATETIME_FORMAT)
                emp_prev_atts = self.env['hr.attendance'].search(
                    [('employee_id.id', '=', employee.id),
                     ('check_in', '>=', str_att_time_utc)],
                    order='check_in DESC')
                if emp_prev_atts:
                    continue
                prev_att = self.env['hr.attendance'].search(
                    [('employee_id.id', '=', employee.id),
                     ('check_in', '<', str_att_time_utc)],
                    limit=1, order='check_in DESC', )
                if prev_att and prev_att.check_out:
                    checkout_time = prev_att.check_out
                    if checkout_time >= time_utc:
                        print(
                            "i will cintinue because the alste attendance checkout in bigger than current")
                        continue
                elif prev_att and not prev_att.check_out:
                    checkin_time = prev_att.check_in
                    if att_type == 0:
                        if min_time >= (time_utc - checkin_time):
                            # print('iam in the main and there in multi punch ')
                            continue
                if user_no not in att_users:
                    users_atts[user_no] = []
                    att_users.append(user_no)
                users_atts[user_no].append((att_time, att_type))
            for user, atts in users_atts.items():
                employee = employee_obj.search([('att_user_id', '=', user)],
                                               limit=1)
                attendances = sorted(atts, key=lambda t: t[0])
                if attendances:
                    for user_att in attendances:
                        res.create_attendance(employee.id, user_att[0],
                                              user_att[1])

    def create_attendance(self, emp_id, time, type):
        employee_obj = self.env['hr.employee']
        att_obj = self.env['hr.attendance']
        for res in self:
            tz_info = res.timezone
            if emp_id and time and type in (0, 1):
                time_utc = convert_date_to_utc(time, tz_info)
                str_att_time_utc = datetime.strftime(
                    convert_date_to_utc(time, tz_info),
                    DATETIME_FORMAT)
                max_time = res.max_time
                min_time = res.min_time
                prev_att = self.env['hr.attendance'].search(
                    [('employee_id.id', '=', emp_id),
                     ('check_in', '<=', str_att_time_utc)],
                    limit=1, order='check_in DESC', )
                if not prev_att:
                    # print('there is no prev atts and i will create new')
                    if type == 0:
                        print('type is check in')
                        new_attendance = att_obj.create({
                            'employee_id': emp_id,
                            'check_in': str_att_time_utc,
                            'state': 'right'
                        })
                    elif type == 1:
                        new_time = time_utc - timedelta(milliseconds=1)
                        str_new_time_utc = datetime.strftime(new_time,
                                                             DATETIME_FORMAT)
                        new_attendance = att_obj.create({
                            'employee_id': emp_id,
                            'check_in': str_new_time_utc,
                            'check_out': str_att_time_utc,
                            'state': 'fixin'
                        })
                else:
                    if prev_att.check_out:
                        checkout_time = prev_att.check_out
                        if checkout_time >= time_utc:
                            continue
                        if type == 0:
                            new_attendance = att_obj.create({
                                'employee_id': emp_id,
                                'check_in': str_att_time_utc,
                                'state': 'right'
                            })
                        elif type == 1:

                            if checkout_time >= (time_utc - min_time):
                                prev_att.write({
                                    'check_out': str_att_time_utc,
                                })
                            else:
                                new_checkin_time = time_utc - timedelta(
                                    milliseconds=1)
                                new_attendance = att_obj.create({
                                    'employee_id': emp_id,
                                    'check_in': datetime.strftime(
                                        new_checkin_time, DATETIME_FORMAT),
                                    'check_out': str_att_time_utc,
                                    'state': 'fixin'

                                })
                    else:
                        checkin_time = prev_att.check_in
                        if checkin_time >= time_utc:
                            continue
                        if type == 0:
                            if min_time >= (time_utc - checkin_time):
                                continue
                            str_new_checkout_time = datetime.strftime(
                                checkin_time + timedelta(milliseconds=1),
                                DATETIME_FORMAT)

                            prev_att.write({
                                'check_out': str_new_checkout_time,
                                'state': 'fixout'
                            })
                            new_attendance = att_obj.create({
                                'employee_id': emp_id,
                                'check_in': str_att_time_utc,
                            })
                        elif type == 1:
                            if max_time >= (time_utc - checkin_time):
                                prev_att.write({
                                    'check_out': str_att_time_utc,
                                })
                            else:
                                new_time = time_utc - timedelta(milliseconds=1)
                                str_new_time_utc = datetime.strftime(new_time,
                                                                     DATETIME_FORMAT)

                                str_new_checkout_time = datetime.strftime(
                                    checkin_time + timedelta(milliseconds=1),
                                    DATETIME_FORMAT)
                                prev_att.write({
                                    'check_out': str_new_checkout_time,
                                    'state': 'fixout'
                                })

                                new_attendance = att_obj.create({
                                    'employee_id': emp_id,
                                    'check_in': str_new_time_utc,
                                    'check_out': str_att_time_utc,
                                    'state': 'fixin'

                                })

    def action_create_log(self, atts, machine_id):
        if not atts:
            return
        for res in self:
            employee_obj = self.env['hr.employee']
            log_obj = self.env['biometric.log']
            machine = self.env['biometric.machine'].browse(machine_id)
            if not machine:
                continue

            tz_info = res.timezone
            for i, att in enumerate(atts):
                user_no = att.user_id
                att_time = att.timestamp
                employee = employee_obj.search([('att_user_id', '=', user_no)],
                                               limit=1)
                str_att_time_utc = datetime.strftime(
                    convert_date_to_utc(att_time, tz_info),
                    DATETIME_FORMAT)
                if not employee:
                    if not res.employee_create:
                        continue
                    employee = employee_obj.create({
                        'name': 'Undefined user ID ' + str(user_no),
                        'att_user_id': user_no
                    })
                prev_log = self.env['biometric.log'].search(
                    [('employee_id', '=', employee.id),
                     ('name', '>=', str_att_time_utc),
                     ('machine', '=', machine_id)],
                    limit=1)
                if prev_log:
                    continue
                att_type = att.punch
                type_att = 'in'
                if att_type == 1:
                    type_att = 'out'
                _logger.info(
                    "Create Bio Log For Employee : {}   On Machine : {} with Time : {}".format(
                        employee.name, machine_id, str_att_time_utc))
                new_log = log_obj.sudo().create({
                    'user': user_no,
                    'employee_id': employee.id,
                    'name': str_att_time_utc,
                    'machine': machine_id,
                    'type': type_att if machine.type == 'inout' else machine.type
                })

    def action_create_atts_filo(self, bio_attendances):
        if not bio_attendances:
            return
        employee_obj = self.env['hr.employee']
        self.ensure_one()
        tz_info = self.timezone
        att_users = []
        users_atts = {}
        min_time = self.min_time
        bio_attendances.sort(key=lambda b: b[2])
        for i, att in enumerate(bio_attendances):
            user_no = att[0]
            employee = employee_obj.search(
                [('att_user_id', '=', user_no)], limit=1)
            if not employee:
                if not self.employee_create:
                    continue
                employee = employee_obj.create({
                    'name': 'Undefined user ID ' + str(user_no),
                    'att_user_id': user_no
                })
            att_time = att[2]
            time_utc = convert_date_to_utc(att[2], tz_info)
            emp_prev_att = self.env['hr.attendance'].search(
                [('employee_id.id', '=', employee.id),
                 ('check_in', '>=', time_utc)],
                order="check_in DESC")
            if emp_prev_att:
                continue
            if i + 1 < len(bio_attendances):
                next_att = bio_attendances[i + 1]
                if (next_att[2] - att[2]) <= min_time:
                    continue
            if user_no not in att_users:
                users_atts[user_no] = []
            users_atts[user_no].append(att_time)
        for user, atts in users_atts.items():
            employee = employee_obj.search([('att_user_id', '=', user)])
            attendances = sorted(atts)
            if attendances:
                start_date = convert_date_to_utc(attendances[0], tz_info)
            else:
                continue
            end_date = datetime.now()
            all_dates = [(start_date + timedelta(days=x)) for x in
                         range((end_date - start_date).days + 1)]
            for day in all_dates:
                day_start = day.replace(hour=0, minute=0, second=0)
                day_end = day.replace(hour=23, minute=59, second=59)
                day_st_utc = convert_date_to_utc(day_start, tz_info)
                day_end_utc = convert_date_to_utc(day_end, tz_info)
                att_records = []
                day_current_atts = [i for i in attendances if
                                    day_start <= i <= day_end]
                if day_current_atts:
                    prev_day_atts = self.env['hr.attendance'].search(
                        [('employee_id.id', '=', employee.id),
                         ('check_in', '<', day_st_utc)],
                        limit=1, order='check_in DESC', )
                    if prev_day_atts:
                        if not prev_day_atts.check_out:
                            check_in = prev_day_atts.check_in
                            p_check_out = check_in + timedelta(seconds=1)
                            prev_day_atts.write(
                                {'check_out': p_check_out, 'state': 'fixout'})

                day_prev_atts = self.env['hr.attendance'].search(
                    [('employee_id.id', '=', employee.id),
                     ('check_in', '>=', day_st_utc),
                     ('check_in', '<=', day_end_utc)],
                    order="check_in")
                if day_prev_atts:
                    last_prev_att = self.env['hr.attendance'].search(
                        [('employee_id.id', '=', employee.id),
                         ('check_in', '>=', day_st_utc),
                         ('check_in', '<=', day_end_utc)], limit=1,
                        order='check_in DESC', )
                    if last_prev_att.check_out:
                        last_att_time = last_prev_att.check_out
                        last_att_time_loc = convert_date_to_local(
                            last_att_time, tz_info)

                        remain_atts = [x for x in day_current_atts if
                                       x > last_att_time_loc]
                        if remain_atts:
                            att_records = list(
                                zip_longest(remain_atts[0::2],
                                            remain_atts[1::2]))
                    else:
                        last_att_time = last_prev_att.check_in
                        last_att_time_loc = convert_date_to_local(
                            last_att_time, tz_info)
                        remain_atts = [x for x in day_current_atts if
                                       x > last_att_time_loc]
                        if remain_atts:
                            last_check_out = convert_date_to_utc(
                                remain_atts[0], tz_info)
                            last_prev_att.write(
                                {'check_out': last_check_out})
                            att_records = list(
                                zip_longest(remain_atts[1::2],
                                            remain_atts[2::2]))
                else:
                    att_records = list(zip_longest(day_current_atts[0::2],
                                                   day_current_atts[1::2]))
                for record in att_records:
                    value = {
                        'employee_id': employee.id,
                        'check_in': convert_date_to_utc(record[0], tz_info),

                    }
                    if record[1]:
                        value['check_out'] = convert_date_to_utc(record[1],
                                                                 tz_info)
                        value['state'] = 'right'
                    new_att = self.env['hr.attendance'].create(value)

    def action_create_atts_delay_filo(self, bio_attendances, start_delay=False, min_att_time=False):
        if not bio_attendances:
            return
        employee_obj = self.env['hr.employee']
        self.ensure_one()
        tz_info = self.timezone
        att_users = []
        users_atts = {}
        min_time = self.min_time
        bio_attendances.sort(key=lambda b: b[2])
        for i, att in enumerate(bio_attendances):
            user_no = att[0]
            employee = employee_obj.search(
                [('att_user_id', '=', user_no)], limit=1)
            if not employee:
                if not self.employee_create:
                    continue
                employee = employee_obj.create({
                    'name': 'Undefined user ID ' + str(user_no),
                    'att_user_id': user_no
                })
            att_time = att[2]
            _logger.info('BIO Log ofr employee : {} with time : {}'.format(employee.name,att))
            time_utc = convert_date_to_utc(att[2], tz_info)
            emp_prev_att = self.env['hr.attendance'].search(
                [('employee_id.id', '=', employee.id),
                 ('check_in', '>=', time_utc)],
                order="check_in DESC")
            if emp_prev_att:
                continue
            if i + 1 < len(bio_attendances):
                next_att = bio_attendances[i + 1]
                if (next_att[2] - att[2]) <= min_time:
                    continue
            if user_no not in att_users:
                users_atts[user_no] = []
            users_atts[user_no].append(att_time)
        for user, atts in users_atts.items():
            employee = employee_obj.search([('att_user_id', '=', user)])
            attendances = sorted(atts)
            if attendances:
                start_date = convert_date_to_utc(attendances[0], tz_info) + timedelta(days=-1)
            else:
                continue
            end_date = datetime.now()
            if attendances:
                end_date = convert_date_to_utc(attendances[-1], tz_info)
            all_dates = [(start_date + timedelta(days=x)) for x in
                         range((end_date - start_date).days + 1)]
            for day in all_dates:
                day_start = day.replace(hour=0, minute=0, second=0)
                day_end = day.replace(hour=23, minute=59, second=59)
                if start_delay:
                    day_start += start_delay
                    day_end += start_delay
                day_st_utc = convert_date_to_utc(day_start, tz_info)
                day_end_utc = convert_date_to_utc(day_end, tz_info)
                prev_end_utc = day_end_utc + timedelta(days=-1)
                prev_start_utc = day_st_utc + timedelta(days=-1)
                att_records = []
                day_current_atts = [i for i in attendances if
                                    day_start <= i <= day_end]
                if day_current_atts:
                    prev_day_atts = self.env['hr.attendance'].search(
                        [('employee_id.id', '=', employee.id),
                         ('check_in', '<', day_st_utc)],
                        limit=1, order='check_in DESC', )
                    if prev_day_atts:
                        if not prev_day_atts.check_out:
                            check_in = prev_day_atts.check_in
                            if min_att_time:
                                att_prev_start_utc = convert_date_to_utc(
                                    check_in.replace(hour=0, minute=0,
                                                     second=0), tz_info)
                                att_prev_end_utc = convert_date_to_utc(
                                    check_in.replace(hour=23, minute=59,
                                                     second=59), tz_info)
                                if start_delay:
                                    att_prev_start_utc += start_delay
                                    att_prev_end_utc += start_delay
                                if check_in <= att_prev_start_utc:
                                    att_prev_start_utc += timedelta(days=-1)
                                    att_prev_end_utc += timedelta(days=-1)
                                p_check_out = check_in + min_att_time
                                p_check_out_minus = check_in - min_att_time
                                if (att_prev_end_utc - check_in) < (
                                        check_in - att_prev_start_utc) and p_check_out_minus > att_prev_start_utc:
                                    prev_day_atts.write(
                                        {'check_in': p_check_out_minus,
                                         'check_out': check_in,
                                         'state': 'fixed_in'})


                                else:
                                    prev_day_atts.write(
                                        {'check_out': p_check_out,
                                         'state': 'fixed'})
                            else:
                                p_check_out = check_in + timedelta(seconds=1)
                                prev_day_atts.write(
                                    {'check_out': p_check_out, 'state': 'fixout'})

                day_prev_atts = self.env['hr.attendance'].search(
                    [('employee_id.id', '=', employee.id),
                     ('check_in', '>=', day_st_utc),
                     ('check_in', '<=', day_end_utc)],
                    order="check_in")
                if day_prev_atts:
                    last_prev_att = self.env['hr.attendance'].search(
                        [('employee_id.id', '=', employee.id),
                         ('check_in', '>=', day_st_utc),
                         ('check_in', '<=', day_end_utc)], limit=1,
                        order='check_in DESC', )
                    if last_prev_att.check_out:

                        last_att_time = last_prev_att.check_out
                        last_att_time_loc = convert_date_to_local(
                            last_att_time, tz_info)

                        remain_atts = [x for x in day_current_atts if
                                       x > last_att_time_loc]

                        if remain_atts:
                            last_day_check_out = convert_date_to_utc(
                                remain_atts[-1], tz_info)
                            last_prev_att.write(
                                {'check_out': last_day_check_out})
                            # att_records = list(
                            #     zip_longest(remain_atts[1::2],
                            #                 remain_atts[2::2]))

                            # att_records = list(
                            #     zip_longest(remain_atts[0::2],
                            #                 remain_atts[1::2]))
                    else:
                        last_att_time = last_prev_att.check_in
                        last_att_time_loc = convert_date_to_local(
                            last_att_time, tz_info)
                        remain_atts = [x for x in day_current_atts if
                                       x > last_att_time_loc]
                        if remain_atts:
                            last_check_out = convert_date_to_utc(
                                remain_atts[-1], tz_info)
                            last_prev_att.write(
                                {'check_out': last_check_out})
                            # att_records = list(
                            #     zip_longest(remain_atts[1::2],
                            #                 remain_atts[2::2]))
                else:
                    # att_records = list(zip_longest(day_current_atts[0::2],
                    #                                day_current_atts[1::2]))

                    if day_current_atts:
                        day_check_in = day_current_atts[0]

                        value = {
                            'employee_id': employee.id,
                            'check_in': convert_date_to_utc(day_check_in, tz_info),

                        }
                        if len(day_current_atts) > 1:
                            day_check_out = day_current_atts[-1]
                            value['check_out'] = convert_date_to_utc(day_check_out,
                                                                     tz_info)
                            value['state'] = 'right'
                        new_att = self.env['hr.attendance'].create(value)
                # for record in att_records:
                #     value = {
                #         'employee_id': employee.id,
                #         'check_in': convert_date_to_utc(record[0], tz_info),
                #
                #     }
                #     if record[1]:
                #         value['check_out'] = convert_date_to_utc(record[1],
                #                                                  tz_info)
                #         value['state'] = 'right'
                #     new_att = self.env['hr.attendance'].create(value)



