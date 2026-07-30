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


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    default_location_id = fields.Many2one(
        "stock.location",
        string="Default Location",
        domain=[("usage", "=", "internal")],
    )
    material_requisition_count = fields.Integer(
        string="Material Requisitions", compute="_compute_material_requisition_count"
    )

    @api.depends()
    def _compute_material_requisition_count(self):
        for employee in self:
            employee.material_requisition_count = self.env[
                "material.requisition"
            ].search_count([("employee_id", "=", employee.id)])

    def action_view_material_requisitions(self):
        self.ensure_one()
        return {
            "name": "Material Requisitions",
            "type": "ir.actions.act_window",
            "res_model": "material.requisition",
            "view_mode": "list,form",
            "domain": [
                "|",
                "|",
                ("employee_id", "=", self.id),
                ("requester_id", "=", self.user_id.id),
                ("approval_ids.approver_ids", "in", self.user_id.id),
            ],
            "context": {
                "default_employee_id": self.id,
            },
        }

    def action_create_material_requisition(self):
        self.ensure_one()
        return {
            "name": "Create Material Requisition",
            "type": "ir.actions.act_window",
            "res_model": "material.requisition",
            "view_mode": "form",
            "context": {
                "default_employee_id": self.id,
                "default_department_id": self.department_id.id,
            },
        }
