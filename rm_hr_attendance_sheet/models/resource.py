# -*- coding: utf-8 -*-

##############################################################################
#
#
#    Copyright (C) 2024-TODAY .
#    Author: Eng.Ramadan Khalil (<rkhalil1990@gmail.com>)
#
#    It is forbidden to publish, distribute, sublicense, or sell copies
#    of the Software or modified copies of the Software.
#
##############################################################################


import pytz
from operator import itemgetter
from odoo import api, fields, models, _
from datetime import datetime, time, timedelta
from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, DAILY, WEEKLY
from odoo.osv import expression
from odoo.tools import format_time, float_round
from odoo.addons.resource.models.utils import float_to_time
from collections import defaultdict, OrderedDict, deque
from pytz import timezone, utc
from odoo.addons.resource.models.resource_resource import Intervals


class ResourceCalendarAttendance(models.Model):
    _inherit = "resource.calendar.attendance"

    @api.onchange('hour_from', 'hour_to')
    def _onchange_hours(self):
        # avoid negative or after midnight
        self.hour_from = min(self.hour_from, 23.99)
        self.hour_from = max(self.hour_from, 0.0)
        self.hour_to = min(self.hour_to, 48)
        self.hour_to = max(self.hour_to, 0.0)

        # avoid wrong order
        self.hour_to = max(self.hour_to, self.hour_from)


class ResourceCalendar(models.Model):
    _inherit = "resource.calendar"

    def _attendance_intervals(self, start_dt, end_dt, resource=None, domain=None, tz=None):
        if resource is None:
            resource = self.env['resource.resource']
        return self._cds_attendance_intervals_batch(
            start_dt, end_dt, resources=resource, domain=domain, tz=tz
        )[resource.id]

    def att_get_work_intervals(self, sheet, day_start, day_end, tz):
        day_start = day_start.replace(tzinfo=tz)
        day_end = day_end.replace(tzinfo=tz)
        attendance_intervals = self._attendance_intervals(day_start, day_end)
        working_intervals = []
        for interval in attendance_intervals:
            working_interval_tz = (
                interval[0].astimezone(pytz.UTC).replace(
                    tzinfo=None),
                interval[1].astimezone(pytz.UTC).replace(
                    tzinfo=None))
            working_intervals.append(working_interval_tz)
        clean_work_intervals = self.att_interval_clean(working_intervals)

        return clean_work_intervals

    def att_interval_clean(self, intervals):
        intervals = sorted(intervals,
                           key=itemgetter(0))  # sort on first datetime
        cleaned = []
        working_interval = None
        while intervals:
            current_interval = intervals.pop(0)
            if not working_interval:  # init
                working_interval = [current_interval[0], current_interval[1]]

            elif working_interval[1] < current_interval[
                0]:
                cleaned.append(tuple(working_interval))
                working_interval = [current_interval[0], current_interval[1]]
            elif working_interval[1] < current_interval[
                1]:
                working_interval[1] = current_interval[1]
        if working_interval:
            cleaned.append(tuple(working_interval))
        return cleaned

    def att_interval_without_leaves(self, interval, leave_intervals):
        if not interval:
            return interval
        if leave_intervals is None:
            leave_intervals = []
        intervals = []
        leave_intervals = self.att_interval_clean(leave_intervals)
        current_interval = [interval[0], interval[1]]
        for leave in leave_intervals:
            if leave[1] <= current_interval[0]:
                continue
            if leave[0] >= current_interval[1]:
                break
            if current_interval[0] < leave[0] < current_interval[1]:
                current_interval[1] = leave[0]
                intervals.append((current_interval[0], current_interval[1]))
                current_interval = [leave[1], interval[1]]
            if current_interval[0] <= leave[1]:
                current_interval[0] = leave[1]
        if current_interval and current_interval[0] < interval[
            1]:  # remove intervals moved outside base interval due to leaves
            intervals.append((current_interval[0], current_interval[1]))
        return intervals

    def _cds_attendance_intervals_batch(self, start_dt, end_dt, resources=None, domain=None, tz=None):
        """ Return the attendance intervals in the given datetime range.
            The returned intervals are expressed in specified tz or in the resource's timezone.
        """
        self.ensure_one()
        resources = self.env['resource.resource'] if not resources else resources
        assert start_dt.tzinfo and end_dt.tzinfo
        self.ensure_one()
        combine = datetime.combine
        required_tz = tz

        resources_list = list(resources) + [self.env['resource.resource']]
        resource_ids = [r.id for r in resources_list]
        domain = domain if domain is not None else []
        domain = expression.AND([domain, [
            ('calendar_id', '=', self.id),
            ('resource_id', 'in', resource_ids),
            ('display_type', '=', False),
        ]])

        # for each attendance spec, generate the intervals in the date range
        cache_dates = defaultdict(dict)
        cache_deltas = defaultdict(dict)
        result = defaultdict(list)
        for attendance in self.env['resource.calendar.attendance'].search(domain):
            for resource in resources_list:
                # express all dates and times in specified tz or in the resource's timezone
                tz = required_tz if required_tz else timezone((resource or self).tz)
                if (tz, start_dt) in cache_dates:
                    start = cache_dates[(tz, start_dt)]
                else:
                    start = start_dt.astimezone(tz)
                    cache_dates[(tz, start_dt)] = start
                if (tz, end_dt) in cache_dates:
                    end = cache_dates[(tz, end_dt)]
                else:
                    end = end_dt.astimezone(tz)
                    cache_dates[(tz, end_dt)] = end

                start = start.date()
                if attendance.date_from:
                    start = max(start, attendance.date_from)
                until = end.date()
                if attendance.date_to:
                    until = min(until, attendance.date_to)
                if attendance.week_type:
                    start_week_type = self.env['resource.calendar.attendance'].get_week_type(start)
                    if start_week_type != int(attendance.week_type):
                        # start must be the week of the attendance
                        # if it's not the case, we must remove one week
                        start = start + relativedelta(weeks=-1)
                weekday = int(attendance.dayofweek)

                if self.two_weeks_calendar and attendance.week_type:
                    days = rrule(WEEKLY, start, interval=2, until=until, byweekday=weekday)
                else:
                    days = rrule(DAILY, start, until=until, byweekday=weekday)

                for day in days:
                    # We need to exclude incorrect days according to re-defined start previously
                    # with weeks=-1 (Note: until is correctly handled)
                    if (self.two_weeks_calendar and attendance.date_from and attendance.date_from > day.date()):
                        continue
                    # attendance hours are interpreted in the resource's timezone
                    hour_from = attendance.hour_from
                    if (tz, day, hour_from) in cache_deltas:
                        dt0 = cache_deltas[(tz, day, hour_from)]
                    else:
                        dt0 = tz.localize(combine(day, float_to_time(hour_from)))
                        cache_deltas[(tz, day, hour_from)] = dt0

                    hour_to = attendance.hour_to
                    if (tz, day, hour_to) in cache_deltas:
                        dt1 = cache_deltas[(tz, day, hour_to)]
                    else:
                        if hour_to >= 24:
                            hour_to -= 24
                            day += timedelta(days=1)
                            day_time = day + relativedelta(hours=hour_to)
                            dt1 = tz.localize(day_time)
                        else:
                            dt1 = tz.localize(combine(day, float_to_time(hour_to)))
                        cache_deltas[(tz, day, hour_to)] = dt1
                    result[resource.id].append((max(cache_dates[(tz, start_dt)], dt0), min(dt1, dt1), attendance))
        return {r.id: Intervals(result[r.id]) for r in resources_list}
