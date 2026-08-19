# -*- coding: utf-8 -*-

##############################################################################
#    Copyright (C) 2020.
#    Author: Eng.Ramadan Khalil (<rkhalil1990@gmail.com>)
#    website': https://www.linkedin.com/in/ramadan-khalil-a7088164
#
#    It is forbidden to publish, distribute, sublicense, or sell copies
#    of the Software or modified copies of the Software.
##############################################################################

from odoo import api, fields, models, _
import pytz

class HrEmployee(models.Model):
    _inherit = "hr.employee"

    def _get_employee_tz(self):
        self.ensure_one()
        tz = self.tz or self.env.user.tz or 'UTC'
        return pytz.timezone(tz)

    def _get_employee_contract(self):
        self.ensure_one()
        contract
        return contract

    # @api.model
    # def _get_calendar(self, automation, record):
    #     return automation.trg_date_calendar_id

    # @api.model
    # def _get_calendar(self, automation, record):
    #     if automation.trg_date_range_type == 'day' and automation.trg_date_resource_field_id:
    #         user = record[automation.trg_date_resource_field_id.name]
    #         calendar = user.employee_id.contract_id.resource_calendar_id
    #         if calendar:
    #             return calendar
    #     return super()._get_calendar(automation, record)

    # def _get_calendar(self, date_from=None):
    #     res = super()._get_calendar()
    #     if not date_from:
    #         return res
    #     contracts = self.env['hr.contract'].sudo().search([
    #         '|',
    #             ('state', 'in', ['open', 'close']),
    #             '&',
    #                 ('state', '=', 'draft'),
    #                 ('kanban_state', '=', 'done'),
    #         ('employee_id', '=', self.id),
    #         ('date_start', '<=', date_from),
    #         '|',
    #             ('date_end', '=', False),
    #             ('date_end', '>=', date_from)
    #     ])
    #     if not contracts:
    #         return res
    #     return contracts[0].resource_calendar_id.sudo(False)