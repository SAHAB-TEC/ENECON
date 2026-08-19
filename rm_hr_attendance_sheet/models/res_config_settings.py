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

from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    first_day_of_month = fields.Integer(store=True,
        string='First Day of Month',
        help='Specify the first day of the attendance month (e.g., 1 for 1st, 26 for 26th).',
        default=1
    )
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    first_day_of_month = fields.Integer(related='company_id.first_day_of_month',readonly=False,check_company=True,
    )
