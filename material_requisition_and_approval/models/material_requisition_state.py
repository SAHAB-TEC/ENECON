# -*- coding: utf-8 -*-
#################################################################################
# Author      : Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# Copyright(c): 2015-Present Webkul Software Pvt. Ltd.
# All Rights Reserved.
#
#
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#
# You should have received a copy of the License along with this program.
# If not, see <https://store.webkul.com/license.html/>
#################################################################################

from odoo import models, fields


class MaterialRequisitionState(models.Model):
    _name = "material.requisition.state"
    _description = "Material Requisition State"
    _order = "sequence"

    name = fields.Char(string="Internal Code", required=True)
    display_name = fields.Char(string="Label", required=True)
    sequence = fields.Integer(default=1)
    is_final = fields.Boolean(string="Final State", default=False)
