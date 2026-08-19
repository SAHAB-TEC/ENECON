# -*- coding: utf-8 -*-

##############################################################################
#    Copyright (c) 2021 CDS Solutions SRL. (http://cdsegypt.com)
#    Maintainer: Eng.Ramadan Khalil (<ramadan.khalil@cdsegypt.com>)
#    It is forbidden to publish, distribute, sublicense, or sell copies
#    of the Software or modified copies of the Software.
##############################################################################

import itertools

from collections import defaultdict
from datetime import datetime, timedelta
from functools import partial
from itertools import chain

from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, DAILY
from pytz import timezone, utc

from odoo import api, fields, models, _
from odoo.addons.base.models.res_partner import _tz_get
from odoo.exceptions import ValidationError
from odoo.osv import expression
from dateutil.rrule import rrule, DAILY
from odoo.tools.float_utils import float_round

from odoo.tools import date_utils, float_utils
from odoo.addons.resource.models.utils import Intervals, float_to_time, make_aware, datetime_to_string, string_to_datetime, ROUNDING_FACTOR




class ResourceCalendar(models.Model):
    _inherit = "resource.calendar"

    day_start_delay = fields.Float('Start Day Delay', default=0)
    normal_working_hours = fields.Float('Normal Working Hours', default=0)
    min_working_hours = fields.Float('Minimum Working Hours', default=0)
    flex_line_ids = fields.One2many('resource.calendar.flex',
                                    inverse_name='calendar_id',
                                    string='Flexable Hours Per Day')

    def _attendance_intervals_batch(self, start_dt, end_dt, resources=None, domain=None, tz=None, lunch=False):
        assert start_dt.tzinfo and end_dt.tzinfo
        self.ensure_one()
        if not resources:
            resources = self.env['resource.resource']
            resources_list = [resources]
        else:
            resources_list = list(resources) + [self.env['resource.resource']]
        resource_ids = [r.id for r in resources_list]
        domain = domain if domain is not None else []
        domain = expression.AND([domain, [
            ('calendar_id', '=', self.id),
            ('resource_id', 'in', resource_ids),
            ('display_type', '=', False),
            ('day_period', '!=' if not lunch else '=', 'lunch'),
        ]])

        attendances = self.env['resource.calendar.attendance'].search(domain)
        # Since we only have one calendar to take in account
        # Group resources per tz they will all have the same result
        resources_per_tz = defaultdict(list)
        for resource in resources_list:
            resources_per_tz[tz or timezone((resource or self).tz)].append(resource)
        # Resource specific attendances
        attendance_per_resource = defaultdict(lambda: self.env['resource.calendar.attendance'])
        # Calendar attendances per day of the week
        # * 7 days per week * 2 for two week calendars
        attendances_per_day = [self.env['resource.calendar.attendance']] * 7 * 2
        weekdays = set()
        for attendance in attendances:
            if attendance.resource_id:
                attendance_per_resource[attendance.resource_id] |= attendance
            weekday = int(attendance.dayofweek)
            weekdays.add(weekday)
            if self.two_weeks_calendar:
                weektype = int(attendance.week_type)
                attendances_per_day[weekday + 7 * weektype] |= attendance
            else:
                attendances_per_day[weekday] |= attendance
                attendances_per_day[weekday + 7] |= attendance

        start = start_dt.astimezone(utc)
        end = end_dt.astimezone(utc)
        bounds_per_tz = {
            tz: (start_dt.astimezone(tz), end_dt.astimezone(tz))
            for tz in resources_per_tz.keys()
        }
        # Use the outer bounds from the requested timezones
        for tz, bounds in bounds_per_tz.items():
            start = min(start, bounds[0].replace(tzinfo=utc))
            end = max(end, bounds[1].replace(tzinfo=utc))
        # Generate once with utc as timezone
        days = rrule(DAILY, start.date(), until=end.date(), byweekday=weekdays)
        ResourceCalendarAttendance = self.env['resource.calendar.attendance']
        base_result = []
        per_resource_result = defaultdict(list)
        for day in days:
            week_type = ResourceCalendarAttendance.get_week_type(day)
            attendances = attendances_per_day[day.weekday() + 7 * week_type]
            for attendance in attendances:
                if (attendance.date_from and day.date() < attendance.date_from) or\
                    (attendance.date_to and attendance.date_to < day.date()):
                    continue
                day_from = datetime.combine(day, float_to_time(attendance.hour_from))
                if attendance.hour_to >= 24.0:
                    day_to = datetime.combine(day, float_to_time(attendance.hour_to - 24.0)) + timedelta(days=1)
                else:
                    day_to = datetime.combine(day, float_to_time(attendance.hour_to))
                if attendance.resource_id:
                    per_resource_result[attendance.resource_id].append((day_from, day_to, attendance))
                else:
                    base_result.append((day_from, day_to, attendance))


        # Copy the result localized once per necessary timezone
        # Strictly speaking comparing start_dt < time or start_dt.astimezone(tz) < time
        # should always yield the same result. however while working with dates it is easier
        # if all dates have the same format
        result_per_tz = {
            tz: [(max(bounds_per_tz[tz][0], tz.localize(val[0])),
                min(bounds_per_tz[tz][1], tz.localize(val[1])),
                val[2])
                    for val in base_result]
            for tz in resources_per_tz.keys()
        }
        result_per_resource_id = dict()
        for tz, resources in resources_per_tz.items():
            res = result_per_tz[tz]
            res_intervals = Intervals(res)
            for resource in resources:
                if resource in per_resource_result:
                    resource_specific_result = [(max(bounds_per_tz[tz][0], tz.localize(val[0])), min(bounds_per_tz[tz][1], tz.localize(val[1])), val[2])
                        for val in per_resource_result[resource]]
                    result_per_resource_id[resource.id] = Intervals(itertools.chain(res, resource_specific_result))
                else:
                    result_per_resource_id[resource.id] = res_intervals
        return result_per_resource_id

class ResourceCalendarflex(models.Model):
    _name = "resource.calendar.flex"

    calendar_id = fields.Many2one('resource.calendar', 'Calendar')

    dayofweek = fields.Selection([
        ('0', 'Monday'),
        ('1', 'Tuesday'),
        ('2', 'Wednesday'),
        ('3', 'Thursday'),
        ('4', 'Friday'),
        ('5', 'Saturday'),
        ('6', 'Sunday')
    ], 'Day of Week', required=True, index=True, default='0')
    min_working_hours = fields.Float('Minimum Working Hours', default=0)
    normal_working_hours = fields.Float('Normal Working Hours', default=0)
