# -*- coding: utf-8 -*-

##############################################################################
#    Copyright (C) 2020.
#    Author: Eng.Ramadan Khalil (<rkhalil1990@gmail.com>)
#    website': https://www.linkedin.com/in/ramadan-khalil-a7088164
#
#    It is forbidden to publish, distribute, sublicense, or sell copies
#    of the Software or modified copies of the Software.
##############################################################################

import pytz
from datetime import datetime, date, timedelta, time
from dateutil.relativedelta import relativedelta
from odoo import models, fields, tools, api, exceptions, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import format_date
from odoo.addons.resource.models.utils import float_to_time, float_round


def time_to_float(t):
    """
    Convert Time to Float
    """
    return float_round(t.hour + t.minute / 60 + t.second / 3600, precision_digits=2)


def tz_localize(dt, tz):
    """
    Localize Datetime to Specific Timezone
    """
    return pytz.utc.localize(dt).astimezone(tz).replace(tzinfo=None)


def interval_to_float(interval):
    """
    Convert Interval (Start Date, End Date) to float
    """
    interval_time = interval[1] - interval[0]
    return float_round(interval_time.total_seconds() / 3600, precision_digits=2)
