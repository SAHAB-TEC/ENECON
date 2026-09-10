# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class MaterialRequisition(models.Model):
    _inherit = "material.requisition"

    partner_id = fields.Many2one(
        "res.partner",
        string="Customer",
        tracking=True,
        domain="[('customer_rank', '>', 0)]",
        help="Required before submitting the requisition. "
             "Old records may be empty until you set a customer.",
    )
    well_id = fields.Many2one(
        "rgb.well",
        string="Well",
        tracking=True,
        domain="['|', ('partner_id', '=', False), ('partner_id', '=', partner_id)]",
    )
    rig_id = fields.Many2one(
        "rgb.rig",
        string="Rig",
        tracking=True,
        domain="[('well_id', '=', well_id)]",
    )
    project_id = fields.Many2one(
        "project.project",
        string="Project",
        tracking=True,
        help="Standard Odoo project (project.project).",
    )
    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Analytic Account",
        tracking=True,
        help="Filled automatically from the selected project analytic account.",
    )
    location_src_display = fields.Char(
        string="From",
        compute="_compute_location_from_to_display",
        help="Source location(s) of linked internal transfers.",
    )
    location_dest_display = fields.Char(
        string="To",
        compute="_compute_location_from_to_display",
        help="Destination location of the requisition / linked transfers.",
    )
    location_id = fields.Many2one(
        domain="['|', ('allowed_user_ids', '=', False), ('allowed_user_ids', 'in', uid)]",
    )

    @api.depends(
        "location_id",
        "requested_product_ids.picking_id",
        "requested_product_ids.picking_id.location_id",
        "requested_product_ids.picking_id.location_dest_id",
        "requested_product_ids.purchase_dispatch_picking_ids",
        "requested_product_ids.purchase_dispatch_picking_ids.location_id",
        "requested_product_ids.purchase_dispatch_picking_ids.location_dest_id",
        "final_dispatch_ids",
        "final_dispatch_ids.location_id",
        "final_dispatch_ids.location_dest_id",
    )
    def _compute_location_from_to_display(self):
        for rec in self:
            pickings = rec.requested_product_ids.mapped("picking_id")
            pickings |= rec.requested_product_ids.mapped("purchase_dispatch_picking_ids")
            pickings |= rec.final_dispatch_ids
            pickings = pickings.filtered(lambda p: p and p.state != "cancel")
            src_names = pickings.mapped("location_id.complete_name")
            dest_names = pickings.mapped("location_dest_id.complete_name")
            rec.location_src_display = ", ".join(
                dict.fromkeys(name for name in src_names if name)
            ) or False
            if dest_names:
                rec.location_dest_display = ", ".join(
                    dict.fromkeys(name for name in dest_names if name)
                )
            else:
                rec.location_dest_display = (
                    rec.location_id.complete_name if rec.location_id else False
                )

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if (
            self.well_id
            and self.well_id.partner_id
            and self.well_id.partner_id != self.partner_id
        ):
            self.well_id = False
            self.rig_id = False

    @api.onchange("well_id")
    def _onchange_well_id(self):
        if self.well_id and self.well_id.partner_id:
            self.partner_id = self.well_id.partner_id
        if self.rig_id and self.rig_id.well_id != self.well_id:
            self.rig_id = False

    @api.onchange("project_id")
    def _onchange_project_id(self):
        if self.project_id and self.project_id.account_id:
            self.analytic_account_id = self.project_id.account_id
        elif not self.project_id:
            self.analytic_account_id = False

    @api.model
    def _rgb_analytic_from_project_vals(self, vals):
        """Fill analytic_account_id from project.account_id when project is set."""
        if vals.get("analytic_account_id") or not vals.get("project_id"):
            return vals
        project = self.env["project.project"].browse(vals["project_id"])
        if project.account_id:
            vals = dict(vals, analytic_account_id=project.account_id.id)
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        Well = self.env["rgb.well"]
        clean_vals = []
        for vals in vals_list:
            vals = dict(vals)
            if not vals.get("partner_id") and vals.get("well_id"):
                well = Well.browse(vals["well_id"])
                if well.partner_id:
                    vals["partner_id"] = well.partner_id.id
            vals = self._rgb_analytic_from_project_vals(vals)
            clean_vals.append(vals)
        return super().create(clean_vals)

    def write(self, vals):
        vals = dict(vals)
        if vals.get("well_id") and not vals.get("partner_id"):
            well = self.env["rgb.well"].browse(vals["well_id"])
            if well.partner_id:
                vals["partner_id"] = well.partner_id.id
        if "project_id" in vals and "analytic_account_id" not in vals:
            vals = self._rgb_analytic_from_project_vals(vals)
            if not vals.get("project_id"):
                vals["analytic_account_id"] = False
        return super().write(vals)

    def action_submit(self):
        for rec in self:
            if not rec.partner_id:
                raise ValidationError(
                    "Customer is required before submitting the requisition."
                )
        return super().action_submit()

    def _get_well_rig_vals(self):
        self.ensure_one()
        vals = {}
        if self.well_id:
            vals["well_id"] = self.well_id.id
        if self.rig_id:
            vals["rig_id"] = self.rig_id.id
        return vals

    def _get_project_analytic_vals(self):
        self.ensure_one()
        vals = {}
        if self.project_id:
            vals["project_id"] = self.project_id.id
        if self.analytic_account_id:
            vals["analytic_account_id"] = self.analytic_account_id.id
        return vals

    def _get_analytic_account(self):
        self.ensure_one()
        return self.analytic_account_id or self.project_id.account_id

    def _rgb_find_from_origin(self, origin):
        if not origin:
            return self.browse()
        requisition_name = origin.split(" - ", 1)[0]
        return self.search([("name", "=", requisition_name)], limit=1)

    def _is_location_allowed_for_user(self, location, user=None):
        """Return True when location is selectable by the given user."""
        self.ensure_one()
        user = user or self.env.user
        if not location:
            return False
        if not location.allowed_user_ids:
            return True
        return user in location.allowed_user_ids

    @api.constrains("location_id")
    def _check_location_id(self):
        """Accept locations allowed for the user; do not force usage=internal."""
        for record in self:
            if not record.location_id:
                continue
            if record.env.user.has_group(
                "material_requisition_and_approval.group_requisition_officer"
            ):
                continue
            if not record._is_location_allowed_for_user(record.location_id):
                raise ValidationError(
                    "You are not allowed to use location '%s'. "
                    "Choose a location that includes you in Allowed Users, "
                    "or leave Allowed Users empty on the location."
                    % record.location_id.display_name
                )

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
            (
                candidate
                for candidate in candidate_locations
                if self._is_location_allowed_for_user(candidate)
            ),
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

            if requisition.env.user.has_group(
                "material_requisition_and_approval.group_requisition_officer"
            ):
                continue

            if not requisition._is_location_allowed_for_user(requisition.location_id):
                raise ValidationError(
                    "You are not allowed to use location '%s'."
                    % requisition.location_id.display_name
                )
