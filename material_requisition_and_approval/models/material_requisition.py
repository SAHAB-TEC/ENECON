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

import logging
from ast import literal_eval
from datetime import timedelta, datetime

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class MaterialRequisition(models.Model):
    _name = "material.requisition"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name desc, id desc"

    name = fields.Char(string="Name", default="New")
    requester_id = fields.Many2one(
        "res.users",
        string="Requester User",
        default=lambda self: self.env.user.id,
        tracking=True,
        required=True,
    )
    state_id = fields.Many2one(
        "material.requisition.state",
        string="State",
        default=lambda self: self.env.ref("material_requisition_and_approval.draft").id,
        tracking=True,
    )
    approval_ids = fields.One2many(
        "material.requisition.approval", "requisition_id", string="Approvals"
    )
    employee_id = fields.Many2one(
        "hr.employee",
        string="Requester",
        required=True,
        default=lambda self: self.env.user.employee_id,
    )
    department_id = fields.Many2one(
        "hr.department",
        string="Department",
        related="employee_id.department_id",
        store=True,
    )
    department_manager_id = fields.Many2one(
        "hr.employee", related="department_id.manager_id"
    )
    designation_id = fields.Many2one(
        "hr.job", string="Designation", related="employee_id.job_id", store=True
    )
    request_type_id = fields.Many2one(
        comodel_name="requisition.request.type", string="Request Type"
    )
    requested_date = fields.Date(string="Requested Date", default=fields.Date.today)
    purpose = fields.Text(string="Purpose", required=True)
    remarks = fields.Text(string="Remarks")
    requested_product_ids = fields.One2many(
        "material.requisition.line",
        "requisition_id",
        string="Requested Products",
        required=True,
    )
    required_date = fields.Date(string="Required Date", required=True)
    location_id = fields.Many2one(
        "stock.location",
        string="Location",
        domain=[("usage", "=", "internal")],
        compute="_compute_employee_id_extract_default_location_id",
        inverse="_inverse_location_id",
        store=True,
    )
    store_checker_ids = fields.Many2many(
        "res.users",
        string="Store Checkers",
        compute="_compute_location_roles",
    )
    stock_manager_ids = fields.Many2many(
        "res.users",
        string="Stock Managers",
        compute="_compute_location_roles",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("waiting_for_approval", "Waiting for Approval"),
            ("waiting_stock_check", "Waiting for Stock Check"),
            ("in_dispatch_process", "In Dispatch Process"),
            ("fulfilled", "Fulfilled"),
            ("cancel", "Cancel"),
            ("rejected", "Rejected"),
        ],
        string="Approval Status",
        compute="_compute_current_state",
        store=True,
    )
    state_ids = fields.Many2many(
        comodel_name="material.requisition.state",
    )
    state_manage = fields.Boolean(compute="_compute_state_id", store=True)

    state_code = fields.Char(related="state_id.name", store=True, default="draft")
    internal_picking_count = fields.Integer(
        string="Internal Pickings", compute="_compute_internal_picking_count"
    )
    approval_rule_id = fields.Many2one("material.requisition.approver.rule")
    rfq_count = fields.Integer(string="Purchase Orders", compute="_compute_rfq_count")
    can_current_user_approve = fields.Boolean(
        string="Can Current User Approve", compute="_compute_can_current_user_approve"
    )
    final_dispatch_ids = fields.Many2many(
        "stock.picking", compute="_compute_final_dipatch_ids", store=True
    )
    can_dipatch = fields.Boolean(default=False, compute="_compute_can_dispatch")
    can_cancel_button = fields.Boolean(compute="_compute_can_cancel")
    can_mark_received = fields.Boolean(compute="_compute_can_mark_received")

    any_line_state_update = fields.Boolean(compute="_compute_updated_status_line")

    def copy(self, default=None):
        default = dict(default or {})
        default.update(
            {
                "name": self.name + " (Copy)",
                "state": "draft",
                "required_date": datetime.today(),
                "requested_date": datetime.today(),
            }
        )

        new_requisition = super().copy(default)

        for line in self.requested_product_ids:
            self.env["material.requisition.line"].create(
                {
                    "requisition_id": new_requisition.id,
                    "product_id": line.product_id.id,
                    "uom_id": line.uom_id.id,
                    "quantity": line.quantity,
                }
            )

        return new_requisition

    def action_duplicate(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "material_requisition_and_approval.action_material_requisition_form"
        )
        action = dict(action)
        action["context"] = dict(self.env.context)
        return action

    @api.model_create_multi
    def create(self, vals_list):
        context = dict(self.env.context or {})
        context["mail_create_nolog"] = True
        records = super(MaterialRequisition, self.with_context(context)).create(vals_list)
        draft_state = self.env.ref("material_requisition_and_approval.draft")
        for record in records:
            record["name"] = self.env["ir.sequence"].next_by_code(
                "material.requisition.sequence"
            )
            record["state_id"] = draft_state
            record.message_post(body="Material Requisition Created")

        return records

    @api.depends("requested_product_ids.state")
    def _compute_state_id(self):
        for record in self:
            states = record.requested_product_ids.mapped("state")
            if not states:
                continue
            _logger.info(f"@hey i am running @ {states}")

            if all(state == "fulfilled" for state in states):
                record._set_state_by_code("in_dispatch")

            elif all(state == "cancelled" for state in states):
                record._set_state_by_code("cancel")
            elif all(state in ["fulfilled", "partially_fulfilled"] for state in states):
                record._set_state_by_code("partial_fulfillment")
            elif any(state == "cancelled" for state in states) and any(
                state in ["fulfilled", "partially_fulfilled"] for state in states
            ):
                record._set_state_by_code("partial_fulfillment")
            record.state_manage = False

    @api.depends("requested_product_ids.state")
    def _compute_can_dispatch(self):
        for record in self:
            record.can_dipatch = all(
                line.state != "draft" for line in record.requested_product_ids
            )

    @api.constrains("requested_product_ids")
    def _check_requested_product_ids(self):
        for rule in self:
            if not rule.requested_product_ids:
                raise ValidationError("please select at least one  product")

    @api.constrains("required_date")
    def _check_required_date(self):
        for record in self:
            if record.required_date:
                _logger.info(f"@ {record.required_date}  {datetime.now().date()}@")
                if record.required_date < datetime.now().date():
                    raise ValidationError("Previous Date is not Consider")

    @api.constrains("location_id")
    def _check_location_id(self):
        # Allow non-internal destinations (e.g. well virtual locations).
        # Allowed-users validation lives in rgb_material_requisition_custom.
        return

    @api.depends(
        "employee_id",
        "employee_id.default_location_id",
        "employee_id.user_id",
        "employee_id.user_id.default_location_id",
        "requester_id",
        "requester_id.default_location_id",
        "approval_rule_id",
        "approval_rule_id.default_location_id",
    )
    def _compute_employee_id_extract_default_location_id(self):
        for record in self:
            if not bool(record.location_id):
                record.location_id = record._get_fallback_location()

    def _inverse_location_id(self):
        """Allow users to override the computed location on the form."""
        return

    def _get_fallback_location(self, rule=False):
        self.ensure_one()
        candidate_locations = [
            self.employee_id.default_location_id,
            self.employee_id.user_id.default_location_id,
            self.requester_id.default_location_id,
        ]
        if rule and rule.default_location_id:
            candidate_locations.append(rule.default_location_id)
        elif self.approval_rule_id.default_location_id:
            candidate_locations.append(self.approval_rule_id.default_location_id)

        return next(
            (location for location in candidate_locations if location),
            self.env["stock.location"],
        )

    def _ensure_destination_location(self, rule=False):
        for requisition in self:
            if not requisition.location_id:
                requisition.location_id = requisition._get_fallback_location(rule=rule)

            if not requisition.location_id:
                raise ValidationError(
                    "No destination location is configured for this requisition. "
                    "Set a default location on the employee, requester user, or approval rule, "
                    "or select the Location directly on the requisition before continuing."
                )

    def _get_delivery_partner(self):
        self.ensure_one()
        employee = self.employee_id
        partner = self.env["res.partner"]
        if employee and "work_contact_id" in employee._fields:
            partner = employee.work_contact_id
        if not partner and employee:
            partner = employee.user_id.partner_id
        return partner or self.requester_id.partner_id
                    

    @api.depends("state_id")
    def _compute_current_state(self):
        for record in self:
            if record.state is False:
                record.state = "draft"
            else:
                if record.state_id.name in [
                    "draft",
                    "submitted",
                    "fulfilled",
                    "waiting_stock_check",
                ]:
                    record.state = record.state_id.name
                elif record.state_id.name in [
                    "waiting_stock_manager_approval",
                    "waiting_level_5_approval",
                    "waiting_level_4_approval",
                    "waiting_level_3_approval",
                    "waiting_level_2_approval",
                    "waiting_level_1_approval",
                ]:
                    record.state = "waiting_for_approval"
                elif record.state_id.name in [
                    "partial_internal_transfer",
                    "internal_transfer_created",
                    "partial_rfq_created",
                    "rfq_created",
                    "in_dispatch"
                ]:
                    record.state = "in_dispatch_process"
                elif record.state_id.name == "cancel":
                    record.state = "cancel"
                elif record.state_id.name == "rejected":
                    record.state = "rejected"
                    pass

    @api.depends("location_id")
    def _compute_location_roles(self):
        config_model = self.env["stock.location.role.config"]
        for rec in self:
            rec.store_checker_ids = False
            rec.stock_manager_ids = False
            if rec.location_id:
                config = config_model.search(
                    [("location_id", "=", rec.location_id.id)], limit=1
                )
                if config:
                    rec.store_checker_ids = config.store_checker_ids
                    rec.stock_manager_ids = config.stock_manager_ids

    @api.depends(
        "requested_product_ids.picking_id",
        "requested_product_ids.purchase_dispatch_picking_ids",
    )
    def _compute_internal_picking_count(self):
        for rec in self:
            pickings = rec.requested_product_ids.filtered(
                lambda line: line.picking_id
            ).mapped("picking_id")
            pickings |= rec.requested_product_ids.mapped("purchase_dispatch_picking_ids")
            rec.internal_picking_count = len(pickings)

    @api.depends("requested_product_ids.rfq_id")
    def _compute_rfq_count(self):
        for rec in self:
            rfqs = rec.requested_product_ids.filtered(lambda line: line.rfq_id).mapped(
                "rfq_id"
            )
            rec.rfq_count = len(rfqs)

    @api.depends("approval_ids.status", "approval_ids.approved_by_id")
    def _compute_can_current_user_approve(self):
        current_user = self.env.user
        for rec in self:
            rec.can_current_user_approve = False
            pending = rec.sudo().approval_ids.filtered(lambda a: a.status == "pending")
            if not pending:
                continue

            current = pending[0]

            rec.can_current_user_approve = current_user in current.approver_ids

    @api.depends(
        "requested_product_ids.picking_id.state",
        "requested_product_ids.purchase_dispatch_picking_ids",
        "requested_product_ids.purchase_dispatch_picking_ids.state",
        "requested_product_ids.rfq_id.picking_ids.state",
        "requested_product_ids.rfq_id.state",
    )
    def _compute_final_dipatch_ids(self):
        for requisition in self:
            if requisition.state_code == "fulfilled":
                continue

            lines = requisition.requested_product_ids

            transfer_pickings = lines.filtered(
                lambda li: li.requisition_action == "transfer" and li.picking_id
            ).mapped("picking_id")

            po_lines = lines.filtered(
                lambda li: li.requisition_action == "purchase" and li.rfq_id
            )
            po_ids = po_lines.mapped("rfq_id")
            po_pickings = po_ids.mapped("picking_ids")
            purchase_dispatch_pickings = po_lines.mapped("purchase_dispatch_picking_ids")

            all_pickings = transfer_pickings + purchase_dispatch_pickings + po_pickings
            requisition.final_dispatch_ids = [(6, 0, all_pickings.ids)]

    def action_submit(self):
        for rec in self:
            rec.sudo().generate_approval_flow()
            rec.sudo()._ensure_destination_location(rule=rec.approval_rule_id)
            rec.sudo()._set_state_by_code("submitted")
            rec.state = "submitted"
            if not rec.required_date:
                rec.required_date = datetime.today()

            pending = rec.sudo().approval_ids.filtered(lambda a: a.status == "pending")

            if pending:
                level = pending[0].level

                if pending[0].approver_type == "approvers":
                    rec.sudo()._set_state_by_code(f"waiting_level_{level}_approval")

                elif pending[0].approver_type == "stock_manager":
                    rec.sudo()._set_state_by_code("waiting_stock_manager_approval")
                rec.sudo()._send_approval_notification(pending[0])

            else:
                rec.sudo()._set_state_by_code("waiting_stock_check")

    def _send_approval_notification(self, approval):
        template = self.env.ref(
            "material_requisition_and_approval.email_template_material_requisition_approval",
            raise_if_not_found=False,
        )
        if not template:
            return

        all_recipients = []

        if approval.approver_ids:
            all_recipients.extend(approval.approver_ids)

        if self.department_manager_id.user_id:
            all_recipients.append(self.department_manager_id.user_id)

        rule = self.approval_rule_id

        if rule and rule.stock_manager_required:
            all_recipients.extend(rule.stock_manager_ids)

        unique_recipients = list(
            set(user for user in all_recipients if user and user.email)
        )

        if unique_recipients:
            recipient_emails = [user.email for user in unique_recipients]
            recipient_names = [user.name for user in unique_recipients]

            template.with_context(email_to=",".join(recipient_emails)).send_mail(
                approval.id, force_send=True
            )

            # Get OdooBot user
            odoo_bot = self.env.ref("base.user_root", raise_if_not_found=False)
            if not odoo_bot:
                odoo_bot = (
                    self.env["res.users"]
                    .sudo()
                    .search([("login", "=", "__system__")], limit=1)
                )

            self.with_user(odoo_bot).message_post(
                body=f"Approval notification sent to: {', '.join(recipient_names)}",
                message_type="notification",
                author_id=odoo_bot.partner_id.id if odoo_bot else False,
            )
    
    def _send_rejection_notification(self):
        template = self.env.ref(
            "material_requisition_and_approval.email_template_material_requisition_rejection",
            raise_if_not_found=False,
        )
        if not template:
            return
            
        recipients = []
        if self.requester_id:
            recipients.append(self.requester_id)
        if self.department_manager_id.user_id:
            recipients.append(self.department_manager_id.user_id)
            
        unique_recipients = list(set(user for user in recipients if user and user.email))
        
        if unique_recipients:
            recipient_emails = [user.email for user in unique_recipients]
            recipient_names = [user.name for user in unique_recipients]
            
            template.with_context(email_to=",".join(recipient_emails)).send_mail(
                self.id, force_send=True
            )
            
            self.message_post(
                body=f"Rejection notification sent to: {', '.join(recipient_names)}",
                message_type="notification"
            )

    def _set_state_by_code(self, code):
        state = self.env["material.requisition.state"].search(
            [("name", "=", code)], limit=1
        )

        if state:
            self.state_id = state.id

        else:
            raise UserError(f"State with code '{code}' not found.")


    def action_approve(self):
        self.ensure_one()
        user = self.env.user


        pending = self.sudo().approval_ids.filtered(lambda a: a.status == "pending")
        if not pending:
            raise UserError("There are no pending approvals.")

        current = pending[0]
        authorized = user in current.approver_ids

        if not authorized:
            raise UserError("You are not authorized to approve this level.")

        self._force_approve(user)

    
    def _force_approve(self, user):
        self.ensure_one()

        pending = self.sudo().approval_ids.filtered(lambda a: a.status == "pending")
        if not pending:
            return

        current = pending[0]
        real_current = self.approval_ids.filtered(lambda a: a.id == current.id)
        if real_current:
            real_current.status = "approved"
            real_current.approved_by_id = user
            real_current.date = fields.Datetime.now()
        else:
            raise UserError("Approval line not accessible for update.")

        remaining = self.sudo().approval_ids.filtered(lambda a: a.status == "pending")
        if remaining:
            next_approval = remaining[0]
            if next_approval.approver_type == "approvers":
                self._set_state_by_code(f"waiting_level_{next_approval.level}_approval")
            elif next_approval.approver_type == "stock_manager":
                self._set_state_by_code("waiting_stock_manager_approval")
            self.sudo()._send_approval_notification(next_approval)
        else:
            self._set_state_by_code("waiting_stock_check")



    def action_reject(self):
        self.ensure_one()
        user = self.env.user
       
        pending = self.sudo().approval_ids.filtered(lambda a: a.status == "pending")
        if not pending:
            raise UserError("There are no pending approvals.")

        current = pending[0]
        authorized = user in current.approver_ids

        if not authorized:
            raise UserError("You are not authorized to reject this level.")

        return self._force_reject(user)

    def _force_reject(self, user):
        self.ensure_one()
        
        pending = self.sudo().approval_ids.filtered(lambda a: a.status == "pending")
        if not pending:
            return

        current = pending[0]
        real_current = self.approval_ids.filtered(lambda a: a.id == current.id)

        if real_current and real_current.remark_required:
            _logger.info(f"@ reject is called @")
            return {
                "name": "Add Remark",
                "type": "ir.actions.act_window", 
                "res_model": "material.requisition.remark.wizard",
                "view_mode": "form",
                "target": "new",
                "context": {
                    "default_approval_id": real_current.id,
                    "action_type": "rejected",
                },
            }

        _logger.info(f"\n\n \n \n this is hit and show on the web - ")
        if real_current:
            real_current.write({
                "status": "rejected",
                "approved_by_id": user.id,
                "date": fields.Datetime.now(),
            })

            remaining_pending = self.sudo().approval_ids.filtered(
                lambda a: a.status == "pending"
            )
            remaining_pending.write({"status": "rejected"})

            self.write({
                "state_id": self.env.ref(
                    "material_requisition_and_approval.rejected"
                ).id,
            })

            # Send rejection notification
            self._send_rejection_notification()

            # Post message
            self.message_post(
                body=f"Request rejected by {user.name}",
                message_type="notification"
            )
            
            
    def generate_approval_flow(self):
        for requisition in self:
            _all_states = [
                "draft",
                "submitted",
                "waiting_stock_manager_approval",
                "waiting_stock_check",
                "partial_rfq_created",
                "rfq_created",
                "partial_internal_transfer",
                "internal_transfer_created",
                "in_dispatch",
                "partial_fulfillment",
                "fulfilled",
                "rejected",
                "cancel",
            ]

            search_rule = self.env["material.requisition.approver.rule"]
            rule = self.env["material.requisition.approver.rule"]

            rule = search_rule.search(
                [("request_type_id", "=", requisition.request_type_id.id)], limit=1
            )

            if not rule:
                rule = search_rule.search(
                    [("user_ids", "in", requisition.requester_id.id)], limit=1
                )

            if not rule:
                rule = search_rule.search(
                    [("department_ids", "=", requisition.department_id.id)], limit=1
                )

            if not rule:
                rule = search_rule.search(
                    [("employee_ids", "in", requisition.employee_id.id)], limit=1
                )

            if not rule:
                rule = search_rule.search(
                    [("location_ids", "in", requisition.location_id.id)], limit=1
                )

            if not rule:
                raise ValidationError(
                    "No matching approval rule found for this requisition."
                )

            requisition.approval_rule_id = rule
            requisition._ensure_destination_location(rule=rule)
            approval_vals = []

            if rule.approver_type == "by_employee_manager" and requisition.employee_id:
                dynamic_chain = rule._get_dynamic_manager_chain(requisition.employee_id)
                for line in dynamic_chain:
                    if line["user_id"]:
                        approval_vals.append(
                            (
                                0,
                                0,
                                {
                                    "level": line["level"],
                                    "approver_ids": [(6, 0, [line["user_id"]])],
                                    "status": "pending",
                                    "approver_type": "approvers",
                                    "remark_required": True,
                                },
                            )
                        )
                        _all_states.append(f"waiting_level_{line['level']}_approval")

            if rule.approver_type == "manually_approved" and requisition.employee_id:
                for static_line in sorted(rule.approval_lines, key=lambda l_: l_.level):
                    user_ids = static_line.user_ids.ids
                    if user_ids:
                        approval_vals.append(
                            (
                                0,
                                0,
                                {
                                    "level": static_line.level,
                                    "approver_ids": [(6, 0, user_ids)],
                                    "status": "pending",
                                    "approver_type": "approvers",
                                    "remark_required": static_line.required,
                                },
                            )
                        )
                        _all_states.append(f"waiting_level_{static_line.level}_approval")

            if rule.stock_manager_required:
                stock_manager_ids = (
                    rule.stock_manager_ids
                    if rule.stock_manager_ids
                    else requisition.stock_manager_ids
                    if requisition.stock_manager_ids
                    else self.env.ref('base.user_admin')
                )
                store_checker_ids = (
                    rule.store_checker_ids
                    if rule.store_checker_ids
                    else requisition.store_checker_ids
                    if requisition.store_checker_ids
                    else self.env.ref('base.user_admin')
                )

                stock_checker_group = self.env.ref(
                    "material_requisition_and_approval.group_store_checker"
                )
                stock_manager_group = self.env.ref("stock.group_stock_manager")

                for user in store_checker_ids:
                    if stock_checker_group not in user.groups_id:
                        user.groups_id = [(4, stock_checker_group.id)]

                for user in stock_manager_ids:
                    if stock_manager_group not in user.groups_id:
                        user.groups_id = [(4, stock_manager_group.id)]

                approval_vals.append(
                    (
                        0,
                        0,
                        {
                            "level": len(approval_vals) + 1,
                            "approver_ids": [(6, 0, stock_manager_ids.ids)],
                            "status": "pending",
                            "approver_type": "stock_manager",
                            "remark_required": True,
                        },
                    )
                )
                _all_states.append("waiting_stock_manager_approval")

            requisition.sudo().approval_ids.unlink()

            requisition.sudo().write({"approval_ids": approval_vals})

            requisition.state_ids = requisition.env[
                "material.requisition.state"
            ].search([("name", "in", _all_states)])

    def action_mark_received(self):
        """Mark requisition as received/fulfilled"""
        self.ensure_one()
        user = self.env.user

      
        if not self.can_mark_received:
            raise UserError("You are not authorized to mark this requisition as received.")

        self._force_mark_received(user)

    def _force_mark_received(self, user):
        self.ensure_one()


        unprocessed_lines = self.requested_product_ids.filtered(
            lambda line: line.state == "draft"
        )
        if unprocessed_lines:
            product_names = ", ".join(unprocessed_lines.mapped('product_id.name'))
            raise UserError(
                f"Cannot mark as received. The following products have not been processed yet: {product_names}"
            )

       
        self._set_state_by_code("fulfilled")

        self._send_received_notification()

 
        self.message_post(
            body=f"Request marked as received by {user.name}",
            message_type="notification"
        )
            
    def _send_received_notification(self):
        """Send notification when requisition is marked as received"""
        recipients = []
        if self.department_manager_id.user_id:
            recipients.append(self.department_manager_id.user_id)
        
        # Add approved users
        approved_users = self.approval_ids.filtered(
            lambda a: a.status == 'approved'
        ).mapped('approved_by_id')
        recipients.extend(approved_users)
        
        valid_recipients = [user for user in recipients if user and user.email]
        
        if valid_recipients:
            recipient_names = [user.name for user in valid_recipients]
            self.message_post(
                body=f"Fulfillment notification sent to: {', '.join(recipient_names)}",
                message_type="notification"
            )

    def open_internal_transfer_wizard(self):
        self._ensure_destination_location(rule=self.approval_rule_id)
        return {
            "type": "ir.actions.act_window",
            "name": "Internal Transfer Fulfillment",
            "res_model": "material.requisition.fulfillment.wizard",
            "view_mode": "form",
            "target": "new",
            "view_id": self.env.ref(
                "material_requisition_and_approval.view_fulfillment_wizard_internal_transfer_form"
            ).id,
            "context": {
                "default_requisition_id": self.id,
                "default_action_type": "internal_transfer",
            },
        }

    def open_rfq_wizard(self):
        self._ensure_destination_location(rule=self.approval_rule_id)
        return {
            "type": "ir.actions.act_window",
            "name": "RFQ Fulfillment",
            "res_model": "material.requisition.fulfillment.wizard",
            "view_mode": "form",
            "target": "new",
            "view_id": self.env.ref(
                "material_requisition_and_approval.view_fulfillment_wizard_purchase_order_form"
            ).id,
            "context": {
                "default_requisition_id": self.id,
                "default_action_type": "rfq",
            },
        }

    def action_check_availability_other_location(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Check Product Availability In Other Location",
            "res_model": "product.availability.lookup.wizard",
            "view_mode": "form",
            "target": "new",
            "view_id": self.env.ref(
                "material_requisition_and_approval.view_product_availability_lookup_form"
            ).id,
            "context": {"default_requisition_id": self.id},
        }

    def action_check_availablity_current_location(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Check Product Availability In Current Location",
            "res_model": "product.availability.lookup.wizard",
            "view_mode": "form",
            "target": "new",
            "view_id": self.env.ref(
                "material_requisition_and_approval.view_product_availability_lookup_form"
            ).id,
            "context": {"default_requisition_id": self.id, "current_location": True},
        }

    def action_get_internal_picking_info(self):
        self.ensure_one()
        pickings = self.requested_product_ids.mapped("picking_id").filtered(
            lambda p: p.picking_type_id.code == "internal"
        )
        pickings |= self.requested_product_ids.mapped("purchase_dispatch_picking_ids")

        return {
            "type": "ir.actions.act_window",
            "name": "Internal Pickings",
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "domain": [("id", "in", pickings.ids)],
            "context": {"create": False},
        }

    def action_cancel(self):
        if self.state_code == "draft":
            self._set_state_by_code("cancel")
        else:
            return {
                "name": "Cancel Material Requisition",
                "type": "ir.actions.act_window",
                "res_model": "material.requisition.cancel.wizard",
                "view_mode": "form",
                "view_id": self.env.ref(
                    "material_requisition_and_approval.view_material_requisition_cancel_wizard_form"
                ).id,
                "target": "new",
                "context": {
                    "active_model": "material.requisition",
                    "active_id": self.id,
                },
            }

    def action_get_rfq_info(self):
        self.ensure_one()
        rfq_ids = self.requested_product_ids.mapped("rfq_id")

        return {
            "type": "ir.actions.act_window",
            "name": "Purchase Orders",
            "res_model": "purchase.order",
            "view_mode": "list,form",
            "domain": [("id", "in", rfq_ids.ids)],
            "context": {"create": False},
        }

    def action_open_form(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Requisition",
            "res_model": "material.requisition",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

    @api.model
    def get_action_click_graph(self):
        return self._get_action(
            "material_requisition_and_approval.action_material_requisition_graph"
        )

    def _get_action(self, action_xmlid):
        action = self.env["ir.actions.actions"]._for_xml_id(action_xmlid)
        context = self.env.context.copy()

        if action.get("context"):
            context.update(literal_eval(action["context"]))
        _logger.info(f"@  context {context}  @")

        filters = {
            "before": ("requested_date", "<", fields.Date.today() - timedelta(days=1)),
            "yesterday": (
                "requested_date",
                "=",
                fields.Date.today() - timedelta(days=1),
            ),
            "today": ("requested_date", "=", fields.Date.today()),
        }
        _logger.info(f"@  {filters}  @")
        for key, domain in filters.items():
            if context.get(f"search_default_{key}"):
                action["domain"] = [domain]
                break
        if context.get("search_default_department_id"):
            action["domain"] = [
                ("department_id", "=", context.get("search_default_department_id"))
            ]
       

        action["context"] = context

        action["help"] = (
            "<p class='o_view_nocontent_smiling_face'>No requisitions found for this period.</p>"
        )

        return action

    def unlink(self):
        for requisition in self:
            active_po_lines = requisition.requested_product_ids.filtered(
                lambda li: li.rfq_id and li.rfq_id.state != "cancel"
            )

            active_transfer_lines = requisition.requested_product_ids.filtered(
                lambda li: li.picking_id and li.picking_id.state != "cancel"
            )

            if active_po_lines or active_transfer_lines:
                raise UserError(
                    "Cannot delete this requisition. Please cancel all associated purchase orders and internal transfers first."
                )

        return super(MaterialRequisition, self).unlink()

    @api.depends(
        "state_code",
        "name",
        "can_dipatch",
        "requester_id",
        "employee_id",
        "stock_manager_ids",
        "store_checker_ids",
    )
    def _compute_can_cancel(self):
        for rec in self:
            uid = self.env.uid
            rec.can_cancel_button = (
                rec.state_code not in ["cancel", "fulfilled", "in_dispatch","rejected"]
                and rec.name != "New"
                and not rec.can_dipatch
                and (
                    rec.requester_id.id == uid
                    or rec.sudo().employee_id.user_id.id == uid
                    or uid in rec.stock_manager_ids.user_id.ids
                    or uid in rec.store_checker_ids.user_id.ids
                )
            )
    
    @api.depends(
        "state_code",
        "can_dipatch",
        "requester_id",
        "employee_id",
    )
    def _compute_can_mark_received(self):
        """Compute visibility for Mark as Received button"""
        for rec in self:
            uid = self.env.uid
            rec.can_mark_received = (
                rec.state_code not in [
                    'draft', 'submitted', 'fulfilled', 'waiting_stock_check',
                    'waiting_stock_manager_approval', 'waiting_level_5_approval',
                    'waiting_level_4_approval', 'waiting_level_3_approval',
                    'waiting_level_2_approval', 'waiting_level_1_approval',
                    'rejected', 'cancel'
                ]
                and rec.can_dipatch
                and (
                    rec.requester_id.id == uid
                    or rec.employee_id.user_id.id == uid
                )
            )


    @api.depends("requested_product_ids.state")
    def _compute_updated_status_line(self):
        for requisition in self:
            requisition.any_line_state_update = all(
                line.state == "draft" for line in requisition.requested_product_ids
            )
