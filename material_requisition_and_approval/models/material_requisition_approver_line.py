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

from odoo import models, fields, api


class MaterialRequisitionApproverLine(models.Model):
    _name = "material.requisition.approver.line"
    _description = "Material Requisition Approver Line"
    _rec_name = "rule_id"
    _order = "sequence"

    sequence = fields.Integer(string="sequence")
    rule_id = fields.Many2one(
        "material.requisition.approver.rule", string="Approver Rule"
    )
    level = fields.Integer(string="Level", default=1)
    user_ids = fields.Many2many("res.users", string="Approvers", required=True)
    required = fields.Boolean(string="Remark Required")

    @api.model_create_multi
    def create(self, vals_list):
        next_levels = {}
        for vals in vals_list:
            if "level" in vals and vals.get("level"):
                continue
            rule_id = vals.get("rule_id")
            if rule_id:
                if rule_id not in next_levels:
                    next_levels[rule_id] = self.search_count([("rule_id", "=", rule_id)])
                next_levels[rule_id] += 1
                vals["level"] = next_levels[rule_id]
            else:
                vals["level"] = 1
        return super().create(vals_list)
