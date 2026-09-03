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
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class MaterialRequisitionApproverRule(models.Model):
    _name = "material.requisition.approver.rule"
    _description = "Material Requisition Approver Rule"

    name = fields.Char(string="Rule Name", required=True)
    approval_rule_type = fields.Selection([
        ("employee", "Employee"),
        ("department", "Department"),
        ("request_type", "Request Type"),
        ("location", "Location(s)"),
    ], string="Approval Rule Type", required=True)

    approver_type = fields.Selection([
        ("by_employee_manager", "By Employee Manager"),
        ("manually_approved", "Manually Approved"),
    ], string="Approved By Type", required=True)

   
    request_type_id = fields.Many2one("requisition.request.type", string="Request Type")
    employee_ids = fields.Many2many("hr.employee", string="Employees")
    user_ids = fields.Many2many("res.users", string="Users")
    department_ids = fields.Many2many("hr.department", string="Department")
    location_ids = fields.Many2many("stock.location", string="Locations")


    requisition_officer_ids = fields.Many2many(
        "res.users", string="Requisition Officers",
        relation="requisition_office_to_requisition_rule_rel",
        column1="config_id", column2="user_id"
    )
    approval_lines = fields.One2many(
        "material.requisition.approver.line", "rule_id", string="Approval Lines"
    )

    store_check_required = fields.Boolean(string="Store Check Required")
    store_checker_ids = fields.Many2many(
        "res.users", string="Store Checkers",
        relation="approval_rule_stock_location_role_config_store_checker_rel",
        column1="config_id", column2="user_id"
    )
    stock_manager_required = fields.Boolean(string="Stock Manager Required")
    stock_manager_ids = fields.Many2many(
        "res.users", string="Stock Managers",
        relation="approval_rule_stock_location_role_config_stock_manager_rel",
        column1="config_id", column2="user_id"
    )

    po_delivery_to_employee_location = fields.Boolean(string="PO Delivery to Employee Location")
    default_location_id = fields.Many2one(
        "stock.location",
        string="Default Location",
        domain=[("usage", "=", "internal")],
    )
    auto_create_dispatch = fields.Boolean(string="Auto Create Dispatch")
    require_stock_manager_dispatch = fields.Boolean(string="Require Stock Manager Dispatch")

   
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._assign_user_groups()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._assign_user_groups()
        return res

    def _assign_user_groups(self):
        stock_checker_group = self.env.ref("material_requisition_and_approval.group_store_checker")
        stock_manager_group = self.env.ref("stock.group_stock_manager")
        for user in self.store_checker_ids:
            if stock_checker_group not in user.groups_id:
                user.groups_id = [(4, stock_checker_group.id)]
        for user in self.stock_manager_ids:
            if stock_manager_group not in user.groups_id:
                user.groups_id = [(4, stock_manager_group.id)]

   
    @api.constrains("po_delivery_to_employee_location", "default_location_id")
    def _check_default_location(self):
        for rec in self:
            if rec.po_delivery_to_employee_location and not rec.default_location_id:
                raise ValidationError("Default location is required when PO delivery to employee location is enabled.")

    @api.constrains("store_check_required", "store_checker_ids")
    def _check_store_checker(self):
        for rec in self:
            if rec.store_check_required and not rec.store_checker_ids:
                raise ValidationError("Store checkers are required when store check is enabled.")

    @api.constrains("stock_manager_required", "stock_manager_ids")
    def _check_stock_manager(self):
        for rec in self:
            if rec.stock_manager_required and not rec.stock_manager_ids:
                raise ValidationError("Stock managers are required when stock manager check is enabled.")

    @api.constrains("approver_type", "approval_lines")
    def _check_approver_type(self):
        for rec in self:
            if "(Copy)" in rec.name:
                continue
            if rec.approver_type == "manually_approved" and not rec.approval_lines:
                raise ValidationError("Please select approval lines.")

    @api.constrains("approval_lines")
    def _check_approval_line_limit(self):
        for rec in self:
            if len(rec.approval_lines) > 5:
                raise ValidationError("You can only define up to 5 approval lines.")

    @api.constrains("approval_rule_type", "employee_ids", "request_type_id", "department_ids", "location_ids")
    def _check_request_type(self):
        for rec in self:
            if rec.approval_rule_type == "request_type" and not rec.request_type_id:
                raise ValidationError("Select Request Type.")
            if rec.approval_rule_type == "employee" and not rec.employee_ids:
                raise ValidationError("Select Employees.")
            if rec.approval_rule_type == "department" and not rec.department_ids:
                raise ValidationError("Select Department.")
            if rec.approval_rule_type == "location" and not rec.location_ids:
                raise ValidationError("Select Location.")

    @api.constrains("approval_lines")
    def _check_approval_line_duplication(self):
        for rec in self:
            seen_levels = set()
            for line in rec.approval_lines:
                if line.level in seen_levels:
                    raise ValidationError("Cannot create duplicate levels in approval lines.")
                seen_levels.add(line.level)

    
    @api.onchange("require_stock_manager_dispatch")
    def _onchange_require_stock_manager_dispatch(self):
        if self.require_stock_manager_dispatch:
            self.auto_create_dispatch = False

    @api.onchange("auto_create_dispatch")
    def _onchange_auto_create_dispatch(self):
        if self.auto_create_dispatch:
            self.require_stock_manager_dispatch = False
            self.store_check_required = False
            self.stock_manager_required = False
            self.store_checker_ids = [(5, 0, 0)]
            self.stock_manager_ids = [(5, 0, 0)]


    def copy(self, default=None):
        default = dict(default or {})
        default["name"] = f"{self.name} (Copy)"
        new_rule = super().copy(default)
        for line in self.approval_lines:
            self.env["material.requisition.approver.line"].create({
                "rule_id": new_rule.id,
                "level": line.level,
                "user_ids": [(6, 0, line.user_ids.ids)],
                "required": line.required,
            })
        return new_rule

    def action_duplicate(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "material_requisition_and_approval.action_material_requisition_approver_rule_form"
        )
        action = dict(action)
        action["context"] = dict(self.env.context)
        return action

    def _get_dynamic_manager_chain(self, employee, max_levels=5):
        """Return a list of dicts for each manager up the chain up to `max_levels`"""
        managers = []
        current = employee.parent_id
        level = 1
        while current and level <= max_levels:
            managers.append({
                "level": level,
                "employee_id": current.id,
                "user_id": current.user_id.id if current.user_id else False,
            })
            current = current.parent_id
            level += 1
        return managers
