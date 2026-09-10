# -*- coding: utf-8 -*-
from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

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

    @api.model
    def _rgb_well_rig_from_origin(self, origin):
        if not origin:
            return {}
        requisition = self.env["material.requisition"]._rgb_find_from_origin(origin)
        if requisition:
            vals = requisition._get_well_rig_vals()
            vals.update(requisition._get_project_analytic_vals())
            return vals
        purchase = self.env["purchase.order"].search([("name", "=", origin)], limit=1)
        if purchase:
            vals = purchase._get_well_rig_vals()
            vals.update(purchase._get_project_analytic_vals())
            return vals
        purchase = self.env["purchase.order"].search([("origin", "=", origin)], limit=1)
        if purchase:
            vals = purchase._get_well_rig_vals()
            vals.update(purchase._get_project_analytic_vals())
            return vals
        return {}

    def _rgb_move_project_vals(self):
        self.ensure_one()
        move_vals = {}
        if self.well_id:
            move_vals["well_id"] = self.well_id.id
        if self.rig_id:
            move_vals["rig_id"] = self.rig_id.id
        if self.project_id:
            move_vals["project_id"] = self.project_id.id
        if self.analytic_account_id:
            move_vals["analytic_account_id"] = self.analytic_account_id.id
        return move_vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not (vals.get("well_id") and vals.get("project_id")):
                origin_vals = self._rgb_well_rig_from_origin(vals.get("origin"))
                if origin_vals:
                    for key, value in origin_vals.items():
                        vals.setdefault(key, value)
                elif vals.get("material_requisition_id"):
                    requisition = self.env["material.requisition"].browse(
                        vals["material_requisition_id"]
                    )
                    for key, value in {
                        **requisition._get_well_rig_vals(),
                        **requisition._get_project_analytic_vals(),
                    }.items():
                        vals.setdefault(key, value)

            # Inject project/analytic onto inline move_ids at create time
            move_commands = vals.get("move_ids") or vals.get("move_ids_without_package")
            if move_commands:
                move_defaults = {
                    k: vals[k]
                    for k in (
                        "well_id",
                        "rig_id",
                        "project_id",
                        "analytic_account_id",
                    )
                    if vals.get(k)
                }
                if move_defaults:
                    new_commands = []
                    for command in move_commands:
                        if (
                            isinstance(command, (list, tuple))
                            and len(command) >= 3
                            and command[0] in (0, 1)
                            and isinstance(command[2], dict)
                        ):
                            move_vals = dict(command[2])
                            for key, value in move_defaults.items():
                                move_vals.setdefault(key, value)
                            new_commands.append((command[0], command[1], move_vals))
                        else:
                            new_commands.append(command)
                    if vals.get("move_ids"):
                        vals["move_ids"] = new_commands
                    if vals.get("move_ids_without_package"):
                        vals["move_ids_without_package"] = new_commands

        pickings = super().create(vals_list)
        for picking in pickings:
            move_vals = picking._rgb_move_project_vals()
            if move_vals:
                picking.move_ids.with_context(
                    rgb_skip_move_well_rig_log=True
                ).write(move_vals)
        return pickings

    def write(self, vals):
        res = super().write(vals)
        tracked = {"well_id", "rig_id", "project_id", "analytic_account_id"} & set(vals)
        if tracked:
            for picking in self:
                move_vals = picking._rgb_move_project_vals()
                # Clear fields removed on picking
                for field_name in tracked:
                    if field_name in vals and not vals.get(field_name):
                        move_vals[field_name] = False
                if move_vals:
                    picking.move_ids.with_context(
                        rgb_skip_move_well_rig_log=True
                    ).write(move_vals)
        return res
