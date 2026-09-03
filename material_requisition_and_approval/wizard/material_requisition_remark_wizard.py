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
import logging

_logger = logging.getLogger(__name__)


class MaterialRequisitionRemarkWizard(models.TransientModel):
    _name = "material.requisition.remark.wizard"
    _description = "Requisition Remark Wizard"

    approval_id = fields.Many2one(
        "material.requisition.approval", required=True, ondelete="cascade"
    )
    remark = fields.Text(string="Remark", required=True)

    def action_remark(self):
        self.ensure_one()
        action_type = self.env.context.get("action_type")
        self.approval_id.write(
            {
                "status": action_type,
                "remarks": self.remark,
                "approved_by_id": self.env.user.id,
                "date": fields.Datetime.now(),
            }
        )
        requisition = self.approval_id.requisition_id

        if action_type == "rejected":
            # Cancel all remaining pending approvals
            remaining_pending = requisition.sudo().approval_ids.filtered(
                lambda a: a.status == "pending"
            )
            remaining_pending.write({"status": "rejected"})
            requisition.write(
                {"state_id": self.env.ref("material_requisition_and_approval.rejected").id}
            )
            requisition._send_rejection_notification()
        else:
            # Advance to next pending approval or waiting_stock_check
            remaining = requisition.sudo().approval_ids.filtered(
                lambda a: a.status == "pending"
            )
            if remaining:
                next_approval = remaining[0]
                if next_approval.approver_type == "approvers":
                    requisition._set_state_by_code(
                        f"waiting_level_{next_approval.level}_approval"
                    )
                elif next_approval.approver_type == "stock_manager":
                    requisition._set_state_by_code("waiting_stock_manager_approval")
                requisition.sudo()._send_approval_notification(next_approval)
            else:
                requisition._set_state_by_code("waiting_stock_check")
