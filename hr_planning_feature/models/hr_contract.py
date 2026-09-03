
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
import pytz
import logging

_logger = logging.getLogger(__name__)

class HrContract(models.Model):
    _inherit = 'hr.contract'

    planning = fields.Boolean(string="Use Planning Shift")

class AttendanceSheet(models.Model):
    _inherit = 'attendance.sheet'

    def _get_float_from_time(self, time_obj):
        if not time_obj:
            return 0.0
        try:
            return time_obj.hour + (time_obj.minute / 60.0)
        except Exception as e:
            _logger.error("Error converting time %s: %s", time_obj, str(e))
            return 0.0

    def get_attendances(self):
        for att_sheet in self:
            try:
                _logger.info("Processing attendance sheet for %s", att_sheet.employee_id.name)

                # Clear existing lines
                att_sheet.line_ids.unlink()
                att_line = self.env["attendance.sheet.line"]

                emp = att_sheet.employee_id
                if not emp or not emp.resource_id:
                    _logger.warning("Employee or resource missing for sheet %s", att_sheet.id)
                    continue

                if not emp.tz:
                    raise UserError(_("Please set timezone for employee %s") % emp.name)

                tz = pytz.timezone(emp.tz)
                from_date = att_sheet.date_from
                to_date = att_sheet.date_to

                # Get all dates in the range
                all_dates = [(from_date + timedelta(days=x)) 
                           for x in range((to_date - from_date).days + 1)]

                # PLANNING MODE
                if emp.contract_id and emp.contract_id.planning:
                    _logger.info("Processing in PLANNING mode")

                    # Get all published slots for this period
                    slots = self.env['planning.slot'].search([
                        ('resource_id', '=', emp.resource_id.id),
                        ('start_datetime', '>=', from_date),
                        ('end_datetime', '<=', to_date),
                    ], order='start_datetime')

                    # Create a dictionary of slots by date
                    slots_by_date = {}
                    for slot in slots:
                        slot_date = slot.start_datetime.astimezone(tz).date()
                        if slot_date not in slots_by_date:
                            slots_by_date[slot_date] = []
                        slots_by_date[slot_date].append(slot)

                    # Process each date in the range
                    for day in all_dates:
                        day_str = str(day.weekday())
                        date_str = day.strftime('%Y-%m-%d')
                        
                        if day in slots_by_date:
                            # Process each slot for this date
                            for slot in slots_by_date[day]:
                                try:
                                    start_utc = slot.start_datetime
                                    end_utc = slot.end_datetime

                                    # Convert to employee timezone
                                    start_local = start_utc.astimezone(tz)
                                    end_local = end_utc.astimezone(tz)

                                    worked_hours = (end_local - start_local).total_seconds() / 3600.0

                                    line_vals = {
                                        'date': date_str,
                                        'day': day_str,
                                        'pl_sign_in': self._get_float_from_time(start_local.time()),
                                        'pl_sign_out': self._get_float_from_time(end_local.time()),
                                        'worked_hours': worked_hours,
                                        'ac_sign_in': self._get_float_from_time(start_local.time()),
                                        'ac_sign_out': self._get_float_from_time(end_local.time()),
                                        'att_sheet_id': att_sheet.id,
                                       
                                    }
                                    att_line.create(line_vals)

                                except Exception as e:
                                    _logger.error("Error processing planning slot %s: %s", slot.id, str(e))
                                    continue
                        else:
                            # No shift for this date - create empty line
                            values = {
                                'date': date_str,
                                'day': day_str,
                                'pl_sign_in': 0,
                                'pl_sign_out': 0,
                                'worked_hours': 0,
                                'ac_sign_in': 0,
                                'ac_sign_out': 0,
                                'att_sheet_id': att_sheet.id,
                                'note': _("Weekend")
                            }
                            att_line.create(values)

                # DEFAULT MODE
                else:
                    _logger.info("Processing in DEFAULT mode")
                    calendar_id = emp.contract_id.resource_calendar_id
                    if not calendar_id:
                        raise ValidationError(_('Please add working hours to the contract of %s') % emp.name)

                    policy_id = att_sheet.att_policy_id
                    if not policy_id:
                        raise ValidationError(_('Please add Attendance Policy to the contract of %s') % emp.name)

                    abs_cnt = 0
                    late_cnt = []
                    diff_cnt = []
                    
                    for day in all_dates:
                        day_start = datetime(day.year, day.month, day.day)
                        day_end = day_start.replace(hour=23, minute=59, second=59)
                        day_str = str(day.weekday())
                        date_str = day.strftime('%Y-%m-%d')
                        
                        work_intervals = calendar_id.att_get_work_intervals(
                            att_sheet, day_start, day_end, tz)
                        attendance_intervals = self.get_attendance_intervals(
                            emp, day_start, day_end, tz)
                        leaves = self._get_emp_leave_intervals(emp, day_start, day_end)
                        public_holiday = self.get_public_holiday(date_str, emp)
                        reserved_intervals = []
                        overtime_policy = policy_id.get_overtime()
                        abs_flag = False

                        if work_intervals:
                            if public_holiday:
                                if attendance_intervals:
                                    for attendance_interval in attendance_intervals:
                                        overtime = attendance_interval[1] - attendance_interval[0]
                                        float_overtime = overtime.total_seconds() / 3600
                                        if float_overtime <= overtime_policy['ph_after']:
                                            act_float_overtime = float_overtime = 0
                                        else:
                                            act_float_overtime = (float_overtime - overtime_policy['ph_after'])
                                            float_overtime = (float_overtime - overtime_policy['ph_after']) * overtime_policy['ph_rate']
                                        
                                        ac_sign_in = pytz.utc.localize(attendance_interval[0]).astimezone(tz)
                                        float_ac_sign_in = self._get_float_from_time(ac_sign_in.time())
                                        ac_sign_out = pytz.utc.localize(attendance_interval[1]).astimezone(tz)
                                        worked_hours = attendance_interval[1] - attendance_interval[0]
                                        float_worked_hours = worked_hours.total_seconds() / 3600
                                        float_ac_sign_out = float_ac_sign_in + float_worked_hours
                                        
                                        values = {
                                            'date': date_str,
                                            'day': day_str,
                                            'ac_sign_in': float_ac_sign_in,
                                            'ac_sign_out': float_ac_sign_out,
                                            'worked_hours': float_worked_hours,
                                            'overtime': float_overtime,
                                            'act_overtime': act_float_overtime,
                                            'att_sheet_id': att_sheet.id,
                                            'status': 'ph',
                                            'note': _("Working on public holiday")
                                        }
                                        att_line.create(values)
                                else:
                                    values = {
                                        'date': date_str,
                                        'day': day_str,
                                        'att_sheet_id': att_sheet.id,
                                        'status': 'ph',
                                        'note': _("Public holiday")
                                    }
                                    att_line.create(values)
                            else:
                                for i, work_interval in enumerate(work_intervals):
                                    float_worked_hours = 0
                                    att_work_intervals = []
                                    diff_intervals = []
                                    late_in_interval = []
                                    diff_time = timedelta(0)
                                    late_in = timedelta(0)
                                    overtime = timedelta(0)
                                    
                                    # Find attendance intervals that overlap with work interval
                                    for j, att_interval in enumerate(attendance_intervals):
                                        if max(work_interval[0], att_interval[0]) < min(work_interval[1], att_interval[1]):
                                            current_att_interval = att_interval
                                            if i + 1 < len(work_intervals):
                                                next_work_interval = work_intervals[i + 1]
                                                if max(next_work_interval[0], current_att_interval[0]) < min(next_work_interval[1], current_att_interval[1]):
                                                    split_att_interval = (next_work_interval[0], current_att_interval[1])
                                                    current_att_interval = (current_att_interval[0], next_work_interval[0])
                                                    attendance_intervals[j] = current_att_interval
                                                    attendance_intervals.insert(j + 1, split_att_interval)
                                            att_work_intervals.append(current_att_interval)
                                    
                                    reserved_intervals += att_work_intervals
                                    
                                    # Get planned times
                                    pl_sign_in = self._get_float_from_time(pytz.utc.localize(work_interval[0]).astimezone(tz).time())
                                    pl_sign_out = self._get_float_from_time(pytz.utc.localize(work_interval[1]).astimezone(tz).time())
                                    
                                    ac_sign_in = 0
                                    ac_sign_out = 0
                                    status = ""
                                    
                                    if att_work_intervals:
                                        if len(att_work_intervals) > 1:
                                            # Multiple attendance intervals for this work interval
                                            late_in_interval = (work_interval[0], att_work_intervals[0][0])
                                            overtime_interval = (work_interval[1], att_work_intervals[-1][1])
                                            
                                            if overtime_interval[1] > overtime_interval[0]:
                                                overtime = overtime_interval[1] - overtime_interval[0]
                                            
                                            remain_interval = (att_work_intervals[0][1], work_interval[1])
                                            
                                            for att_work_interval in att_work_intervals:
                                                float_worked_hours += (att_work_interval[1] - att_work_interval[0]).total_seconds() / 3600
                                                
                                                if att_work_interval[1] <= remain_interval[0]:
                                                    continue
                                                if att_work_interval[0] >= remain_interval[1]:
                                                    break
                                                if remain_interval[0] < att_work_interval[0] < remain_interval[1]:
                                                    diff_intervals.append((remain_interval[0], att_work_interval[0]))
                                                    remain_interval = (att_work_interval[1], remain_interval[1])
                                            
                                            if remain_interval and remain_interval[0] < work_interval[1]:
                                                diff_intervals.append((remain_interval[0], work_interval[1]))
                                            
                                            ac_sign_in = self._get_float_from_time(pytz.utc.localize(att_work_intervals[0][0]).astimezone(tz).time())
                                            total_work_time = (att_work_intervals[-1][1] - att_work_intervals[0][0]).total_seconds() / 3600
                                            ac_sign_out = ac_sign_in + total_work_time
                                        else:
                                            # Single attendance interval for this work interval
                                            late_in_interval = (work_interval[0], att_work_intervals[0][0])
                                            overtime_interval = (work_interval[1], att_work_intervals[0][1])
                                            
                                            if overtime_interval[1] > overtime_interval[0]:
                                                overtime = overtime_interval[1] - overtime_interval[0]
                                            
                                            ac_sign_in = self._get_float_from_time(pytz.utc.localize(att_work_intervals[0][0]).astimezone(tz).time())
                                            worked_hours = att_work_intervals[0][1] - att_work_intervals[0][0]
                                            float_worked_hours = worked_hours.total_seconds() / 3600
                                            ac_sign_out = ac_sign_in + float_worked_hours
                                    else:
                                        # No attendance for this work interval
                                        late_in_interval = []
                                        diff_intervals.append((work_interval[0], work_interval[1]))
                                        status = "ab"
                                    
                                    # Calculate difference time (missing work time)
                                    if diff_intervals:
                                        for diff_in in diff_intervals:

                                            if leaves:
                                                note = _("Leave")  # Default if no specific leave type is matched
                                                status = "leave"
                                                
                                                leave_obj = self.env['hr.leave'].search([
                                                    ('employee_id', '=', emp.id),
                                                    ('state', '=', 'validate'),
                                                    ('request_date_from', '<=', day),
                                                    ('request_date_to', '>=', day),
                                                ], limit=1)
                                                leave_type = leave_obj.holiday_status_id
                                                
                                                # Set note based on leave type
                                                if leave_type.unpaid_off:
                                                    note = _("Unpaid Leave")
                                                else:
                                                    note = _("Paid Leave")
                                                diff_clean_intervals = calendar_id.att_interval_without_leaves(diff_in, leaves)
                                                for diff_clean in diff_clean_intervals:
                                                    diff_time += diff_clean[1] - diff_clean[0]
                                            else:
                                                diff_time += diff_in[1] - diff_in[0]
                                    
                                    # Calculate late in time
                                    if late_in_interval:
                                        if late_in_interval[1] > late_in_interval[0]:
                                            if leaves:
                                                late_clean_intervals = calendar_id.att_interval_without_leaves(late_in_interval, leaves)
                                                for late_clean in late_clean_intervals:
                                                    late_in += late_clean[1] - late_clean[0]
                                            else:
                                                late_in = late_in_interval[1] - late_in_interval[0]
                                    
                                    # Calculate overtime
                                    float_overtime = overtime.total_seconds() / 3600
                                    if float_overtime <= overtime_policy['wd_after']:
                                        act_float_overtime = float_overtime = 0
                                    else:
                                        act_float_overtime = float_overtime
                                        float_overtime = float_overtime * overtime_policy['wd_rate']
                                    
                                    # Calculate late time
                                    float_late = late_in.total_seconds() / 3600
                                    act_float_late = float_late
                                    policy_late, late_cnt = policy_id.get_late(float_late, late_cnt)
                                    
                                    # Calculate difference time
                                    float_diff = diff_time.total_seconds() / 3600
                                    if status == 'ab':
                                        if not abs_flag:
                                            abs_cnt += 1
                                        abs_flag = True
                                        act_float_diff = float_diff
                                        float_diff = policy_id.get_absence(float_diff, abs_cnt)
                                    else:
                                        act_float_diff = float_diff
                                        float_diff, diff_cnt = policy_id.get_diff(float_diff, diff_cnt)
                                    
                                    # Create attendance line
                                    values = {
                                        'date': date_str,
                                        'day': day_str,
                                        'pl_sign_in': pl_sign_in,
                                        'pl_sign_out': pl_sign_out,
                                        'ac_sign_in': ac_sign_in,
                                        'ac_sign_out': ac_sign_out,
                                        'late_in': policy_late,
                                        'act_late_in': act_float_late,
                                        'worked_hours': float_worked_hours,
                                        'overtime': float_overtime,
                                        'act_overtime': act_float_overtime,
                                        'diff_time': float_diff,
                                        'act_diff_time': act_float_diff,
                                        'status': status if status else False,
                                        'note': note if status == 'leave' else '',  # Include note for leave cases

                                        'att_sheet_id': att_sheet.id
                                    }
                                    att_line.create(values)
                                
                                # Handle attendance outside work intervals (pure overtime)
                                out_work_intervals = [x for x in attendance_intervals if x not in reserved_intervals]
                                if out_work_intervals:
                                    for att_out in out_work_intervals:
                                        overtime = att_out[1] - att_out[0]
                                        ac_sign_in = self._get_float_from_time(pytz.utc.localize(att_out[0]).astimezone(tz).time())
                                        ac_sign_out = self._get_float_from_time(pytz.utc.localize(att_out[1]).astimezone(tz).time())
                                        float_worked_hours = overtime.total_seconds() / 3600
                                        ac_sign_out = ac_sign_in + float_worked_hours
                                        float_overtime = float_worked_hours
                                        
                                        if float_overtime <= overtime_policy['wd_after']:
                                            float_overtime = act_float_overtime = 0
                                        else:
                                            act_float_overtime = float_overtime
                                            float_overtime = act_float_overtime * overtime_policy['wd_rate']
                                        
                                        values = {
                                            'date': date_str,
                                            'day': day_str,
                                            'pl_sign_in': 0,
                                            'pl_sign_out': 0,
                                            'ac_sign_in': ac_sign_in,
                                            'ac_sign_out': ac_sign_out,
                                            'overtime': float_overtime,
                                            'worked_hours': float_worked_hours,
                                            'act_overtime': act_float_overtime,
                                            'note': _("Overtime outside work hours"),
                                            'att_sheet_id': att_sheet.id,
                                            'status': 'overtime'
                                        }
                                        att_line.create(values)
                        else:
                            # No work intervals (weekend or holiday)
                            if attendance_intervals:
                                for attendance_interval in attendance_intervals:
                                    overtime = attendance_interval[1] - attendance_interval[0]
                                    float_overtime = overtime.total_seconds() / 3600
                                    
                                    if float_overtime <= overtime_policy['we_after']:
                                        act_float_overtime = float_overtime = 0
                                    else:
                                        act_float_overtime = float_overtime
                                        float_overtime = act_float_overtime * overtime_policy['we_rate']
                                    
                                    ac_sign_in = pytz.utc.localize(attendance_interval[0]).astimezone(tz)
                                    ac_sign_out = pytz.utc.localize(attendance_interval[1]).astimezone(tz)
                                    worked_hours = attendance_interval[1] - attendance_interval[0]
                                    float_worked_hours = worked_hours.total_seconds() / 3600
                                    
                                    values = {
                                        'date': date_str,
                                        'day': day_str,
                                        'ac_sign_in': self._get_float_from_time(ac_sign_in.time()),
                                        'ac_sign_out': self._get_float_from_time(ac_sign_out.time()),
                                        'overtime': float_overtime,
                                        'act_overtime': act_float_overtime,
                                        'worked_hours': float_worked_hours,
                                        'att_sheet_id': att_sheet.id,
                                        'status': 'weekend',
                                        'note': _("Working on weekend")
                                    }
                                    att_line.create(values)
                            else:
                                values = {
                                    'date': date_str,
                                    'day': day_str,
                                    'att_sheet_id': att_sheet.id,
                                    'status': 'weekend',
                                    'note': _("Weekend day")
                                }
                                att_line.create(values)

            except Exception as e:
                _logger.error("Error processing sheet %s: %s", att_sheet.id, str(e))
                raise UserError(_("Error processing attendance sheet: %s") % str(e))


    unpaid_leave_days = fields.Float(string="Unpaid Leave Days", compute="_compute_unpaid_leave_days", store=True, readonly=True)

    @api.depends('employee_id', 'date_from', 'date_to')
    def _compute_unpaid_leave_days(self):
        for sheet in self:
            if not sheet.employee_id or not sheet.date_from or not sheet.date_to:
                sheet.unpaid_leave_days = 0.0
                continue

            domain = [
                ('employee_id', '=', sheet.employee_id.id),
                ('state', '=', 'validate'),
                ('request_date_from', '<=', sheet.date_to),
                ('request_date_to', '>=', sheet.date_from),
                ('holiday_status_id.unpaid_off', '=', True),
            ]
            unpaid_leaves = self.env['hr.leave'].search(domain)

            total_days = 0.0
            for leave in unpaid_leaves:
                leave_start = max(leave.request_date_from, sheet.date_from)
                leave_end = min(leave.request_date_to, sheet.date_to)
                total_days += (leave_end - leave_start).days + 1

            sheet.unpaid_leave_days = total_days
