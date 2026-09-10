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



class MaterialRequisitionApproval(models.Model):
    _name = "material.requisition.approval"
    _description = "Material Requisition Approval"
    _rec_name = "requisition_id"

    requisition_id = fields.Many2one("material.requisition", string="Requisition")
    approver_ids = fields.Many2many("res.users", string="Approvers")
    approved_by_id = fields.Many2one("res.users", string="Approved By")
    level = fields.Integer(string="Level")
    status = fields.Selection(
        [("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")],
        string="Status",
    )
    approver_type = fields.Selection(
        [("approvers", "Approvers"), ("stock_manager", "Stock Manager")],
        string="Approver Type",
    )
    remark_required = fields.Boolean("Remark Required")
    remarks = fields.Text(string="Remarks")
    date = fields.Datetime(string="Approval Date")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        approver_group = self.env.ref(
            "material_requisition_and_approval.group_requisition_approver"
        )
        for user in records.mapped("approver_ids"):
            if approver_group not in user.groups_id:
                user.groups_id = [(4, approver_group.id)]
        return records
