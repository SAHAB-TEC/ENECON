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

from odoo import models, fields, api, tools, _
import babel
import time
from datetime import datetime, timedelta
import logging
_logger = logging.getLogger()

class HrAttendancePolicy(models.Model):
    _name = 'hr.attendance.policy'
    _description = 'Attendance Sheet Policies'

    name = fields.Char(string="Name", required=True)
    overtime_rule_ids = fields.Many2many(comodel_name="hr.overtime.rule",
                                         relation="overtime_rule_policy_rel",
                                         column1="attendance_policy_col",
                                         column2="overtime_rule_col",
                                         string="Overtime Rules", )
    late_rule_id = fields.Many2one(comodel_name="hr.late.rule", required=True,
                                   string="Late In Rule")
    absence_rule_id = fields.Many2one(comodel_name="hr.absence.rule",
                                      string="Absence Rule", required=True)
    diff_rule_id = fields.Many2one(comodel_name="hr.diff.rule",
                                   string="Difference Time Rule", required=True)
    def get_overtime(self, ot_type, ot_intervals):
        """Calculate the overtime for the given overtime type and intervals.
        :param ot_type: the type of the overtime (weekend, workday, ph)
        :param ot_intervals: the intervals of the overtime
        """
        act_overtime = calc_overtime = 0
        overtime_rules = self.overtime_rule_ids.filtered(lambda r: r.type == ot_type)
        if not overtime_rules:
            return act_overtime, calc_overtime
        for ot in ot_intervals:
            if ot[1] < ot[0]:
                continue
            ot_time = (ot[1] - ot[0]).total_seconds() / 3600
            act_overtime += ot_time
        rule_id = overtime_rules[0]
        if act_overtime >= rule_id.active_after:
            calc_overtime = act_overtime * rule_id.rate
        return act_overtime, calc_overtime


    def get_late(self, act_late, cnt):
        calc_late = act_late
        flag = False
        no = 1
        cnt_flag = False
        factor = 1
        if act_late <= 0:
            calc_late = act_late = 0
            return calc_late, cnt
        if self.late_rule_id:
            time_ids = self.late_rule_id.line_ids.sorted(
                key=lambda r: r.time, reverse=True)
            for line in time_ids:
                if act_late >= line.time:
                    for counter in cnt:
                        if counter[0] == line.time:
                            cnt_flag = True
                            no = counter[1]
                            counter[1] += 1
                            break
                    if no >= 5 and line.fifth >= 0:
                        factor = line.fifth
                    elif no >= 4 and line.fourth >= 0:
                        factor = line.fourth
                    elif no >= 3 and line.third >= 0:
                        factor = line.third
                    elif no >= 2 and line.second >= 0:
                        factor = line.second
                    elif no >= 1 and line.first >= 0:
                        factor = line.first
                    elif no == 0:
                        factor = 0
                    if not cnt_flag:
                        cnt.append([line.time, 2])
                    flag = True
                    if line.type == 'rate':
                        calc_late = line.rate * act_late * factor
                    elif line.type == 'fix':
                        calc_late = line.amount * factor

                    break

            if not flag:
                calc_late = 0
        return calc_late, cnt

    def get_diff(self, period, cnt):
        self.ensure_one()
        res = period
        flag = False
        no = 1
        cnt_flag = False
        factor = 1
        if period <= 0:
            return 0, cnt

        if self.diff_rule_id:
            time_ids = self.diff_rule_id.line_ids.sorted(
                key=lambda r: r.time, reverse=True)
            for line in time_ids:
                if period >= line.time:
                    for counter in cnt:
                        if counter[0] == line.time:
                            cnt_flag = True
                            no = counter[1]
                            counter[1] += 1
                            break
                    if no >= 5 and line.fifth >= 0:
                        factor = line.fifth
                    elif no >= 4 and line.fourth >= 0:
                        factor = line.fourth
                    elif no >= 3 and line.third >= 0:
                        factor = line.third
                    elif no >= 2 and line.second >= 0:
                        factor = line.second
                    elif no >= 1 and line.first >= 0:
                        factor = line.first
                    elif no == 0:
                        factor = 0
                    if not cnt_flag:
                        cnt.append([line.time, 2])
                    flag = True
                    if line.type == 'rate':
                        res = line.rate * period * factor
                    elif line.type == 'fix':
                        res = line.amount * factor

                    break

            if not flag:
                res = 0
        return res, cnt

    def get_absence(self, period, cnt):
        res = period
        flag = False
        if self:
            if self.absence_rule_id:
                abs_ids = self.absence_rule_id.line_ids.sorted(
                    key=lambda r: r.counter, reverse=True)
                for ln in abs_ids:
                    if cnt >= int(ln.counter):
                        res = ln.rate * period
                        flag = True
                        break
                if not flag:
                    res = 0
        return res


class HrPolicyOvertimeLine(models.Model):
    _name = 'hr.policy.overtime.line'
    _description = 'Overtime Policy Lines'
    type = [
        ('we', 'Week End'),
        ('wd', 'Working Day'),
        ('ph', 'Public Holiday')

    ]
    overtime_rule_id = fields.Many2one(comodel_name='hr.overtime.rule',
                                       string='Name', required=True)
    type = fields.Selection(selection=type, string="Type", default='wd')
    active_after = fields.Float(string="Apply after",
                                help="After this time the overtime will be calculated")
    rate = fields.Float(string='Rate')
    attendance_policy_id = fields.Many2one(comodel_name='hr.attendance.policy')

    @api.onchange('overtime_rule_id')
    def onchange_ov_id(self):
        for line in self:
            line.type = line.overtime_rule_id.type
            line.active_after = line.overtime_rule_id.active_after
            line.rate = line.overtime_rule_id.rate


class HrOvertimeRule(models.Model):
    _name = 'hr.overtime.rule'
    _description = 'Over time Rules'
    TYPE_OT = [
        ('we', 'Week End'),
        ('wd', 'Working Day'),
        ('ph', 'Public Holiday')

    ]

    name = fields.Char(string="name")
    type = fields.Selection(selection=TYPE_OT, string="Type", default='wd')
    active_after = fields.Float(string="Apply after",
                                help="After this time the overtime will be calculated")
    rate = fields.Float(string='Rate')


class HrLateRule(models.Model):
    _name = 'hr.late.rule'
    _description = 'Late In Rules'

    name = fields.Char(string='name', required=True)
    line_ids = fields.One2many(comodel_name='hr.late.rule.line',
                               inverse_name='late_id', string='Late In Periods')


class HrLateRuleLine(models.Model):
    _name = 'hr.late.rule.line'
    _description = 'Late In Rule Lines'
    type = [
        ('fix', 'Fixed'),
        ('rate', 'Rate')
    ]

    late_id = fields.Many2one(comodel_name='hr.late.rule', string='Late Rule')
    type = fields.Selection(string="Type", selection=type, required=True, )
    rate = fields.Float(string='Rate')
    time = fields.Float('Time')
    amount = fields.Float('Amount')
    first = fields.Float('First Time', default=1)
    second = fields.Float('Second Time', default=1)
    third = fields.Float('Third Time', default=1)
    fourth = fields.Float('Fourth Time', default=1)
    fifth = fields.Float('Fifth Time', default=1)


class HrDiffRule(models.Model):
    _name = 'hr.diff.rule'
    _description = 'Diff Time Rule'

    name = fields.Char(string='name', required=True)
    line_ids = fields.One2many(comodel_name='hr.diff.rule.line',
                               inverse_name='diff_id',
                               string='Difference time Periods')


class HrDiffRuleLine(models.Model):
    _name = 'hr.diff.rule.line'
    _description = 'Diff Time Rule Line'
    type = [
        ('fix', 'Fixed'),
        ('rate', 'Rate')
    ]

    diff_id = fields.Many2one(comodel_name='hr.diff.rule', string='Diff Rule')
    type = fields.Selection(string="Type", selection=type, required=True, )
    rate = fields.Float(string='Rate')
    time = fields.Float('Time')
    amount = fields.Float('Amount')
    first = fields.Float('First Time', default=1)
    second = fields.Float('Second Time', default=1)
    third = fields.Float('Third Time', default=1)
    fourth = fields.Float('Fourth Time', default=1)
    fifth = fields.Float('Fifth Time', default=1)


class HrAbsenceRule(models.Model):
    _name = 'hr.absence.rule'
    _description = 'Absence Rules'

    name = fields.Char(string='name', required=True)
    line_ids = fields.One2many(comodel_name='hr.absence.rule.line',
                               inverse_name='absence_id',
                               string='Late In Periods')


class HrAbsenceRuleLine(models.Model):
    _name = 'hr.absence.rule.line'
    _description = 'Absence Rule Lines'
    times = [
        ('1', 'First Time'),
        ('2', 'Second Time'),
        ('3', 'Third Time'),
        ('4', 'Fourth Time'),
        ('5', 'Fifth Time'),

    ]
    absence_id = fields.Many2one(comodel_name='hr.absence.rule', string='name')
    rate = fields.Float(string='Rate', required=True)
    counter = fields.Selection(string="Times", selection=times, required=True, )
