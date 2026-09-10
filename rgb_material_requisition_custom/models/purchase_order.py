# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    well_id = fields.Many2one("rgb.well", string="Well", copy=False, tracking=True)
    rig_id = fields.Many2one(
        "rgb.rig",
        string="Rig",
        copy=False,
        tracking=True,
        domain="[('well_id', '=', well_id)]",
    )
    project_id = fields.Many2one(
        "project.project",
        string="Project",
        copy=False,
        tracking=True,
    )
    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Analytic Account",
        copy=False,
        tracking=True,
    )

    @api.onchange("well_id")
    def _onchange_well_id(self):
        if self.rig_id and self.rig_id.well_id != self.well_id:
            self.rig_id = False

    @api.onchange("project_id")
    def _onchange_project_id(self):
        if self.project_id and self.project_id.account_id:
            self.analytic_account_id = self.project_id.account_id

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

    def _get_material_requisition(self):
        """Return the material requisition linked to this purchase order."""
        self.ensure_one()
        line = self.env["material.requisition.line"].search(
            [
                ("rfq_id", "=", self.id),
                ("state", "!=", "cancelled"),
            ],
            limit=1,
        )
        if line and line.requisition_id:
            return line.requisition_id
        return self.env["material.requisition"]._rgb_find_from_origin(self.origin)

    def _get_destination_location(self):
        """Use the requisition location as PO receipt destination when linked."""
        requisition = self._get_material_requisition()
        if requisition and requisition.location_id:
            return requisition.location_id.id
        return super()._get_destination_location()

    def _get_final_location_record(self):
        requisition = self._get_material_requisition()
        if requisition and requisition.location_id:
            return requisition.location_id
        return super()._get_final_location_record()

    def _prepare_picking(self):
        res = super()._prepare_picking()
        res.update(self._get_well_rig_vals())
        res.update(self._get_project_analytic_vals())
        requisition = self._get_material_requisition()
        if requisition:
            if requisition.location_id:
                res["location_dest_id"] = requisition.location_id.id
            if "material_requisition_id" in self.env["stock.picking"]._fields:
                res["material_requisition_id"] = requisition.id
        return res

    def write(self, vals):
        res = super().write(vals)
        tracked = {"well_id", "rig_id", "project_id", "analytic_account_id"} & set(vals)
        if tracked:
            for order in self:
                sync_vals = {
                    **order._get_well_rig_vals(),
                    **order._get_project_analytic_vals(),
                }
                for field_name in tracked:
                    if field_name in vals and not vals.get(field_name):
                        sync_vals[field_name] = False
                order.picking_ids.with_context(
                    rgb_skip_move_well_rig_log=True
                ).write(sync_vals)
                order.order_line.move_ids.with_context(
                    rgb_skip_move_well_rig_log=True
                ).write(sync_vals)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        MaterialRequisition = self.env["material.requisition"]
        for vals in vals_list:
            if (vals.get("well_id") and vals.get("project_id")) or not vals.get("origin"):
                continue
            requisition = MaterialRequisition._rgb_find_from_origin(vals["origin"])
            if requisition:
                for key, value in {
                    **requisition._get_well_rig_vals(),
                    **requisition._get_project_analytic_vals(),
                }.items():
                    vals.setdefault(key, value)
        return super().create(vals_list)
