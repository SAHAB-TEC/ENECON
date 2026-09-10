# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    well_id = fields.Many2one("rgb.well", string="Well", copy=False, index=True)
    rig_id = fields.Many2one(
        "rgb.rig",
        string="Rig",
        copy=False,
        index=True,
        domain="[('well_id', '=', well_id)]",
    )
    project_id = fields.Many2one(
        "project.project",
        string="Project",
        copy=False,
        index=True,
    )
    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        string="Analytic Account",
        copy=False,
        index=True,
    )

    @api.onchange("well_id")
    def _onchange_well_id(self):
        if self.rig_id and self.rig_id.well_id != self.well_id:
            self.rig_id = False

    def _rgb_resolve_analytic_account(self):
        """Priority: move → requisition → picking → destination location → source."""
        self.ensure_one()
        if self.analytic_account_id:
            return self.analytic_account_id
        if self.project_id and self.project_id.account_id:
            return self.project_id.account_id
        origin = (self.picking_id.origin if self.picking_id else False) or self.origin
        if origin:
            requisition = self.env["material.requisition"]._rgb_find_from_origin(origin)
            if requisition:
                account = requisition._get_analytic_account()
                if account:
                    return account
        if self.picking_id and self.picking_id.analytic_account_id:
            return self.picking_id.analytic_account_id
        if (
            self.picking_id
            and self.picking_id.project_id
            and self.picking_id.project_id.account_id
        ):
            return self.picking_id.project_id.account_id
        return (
            self.location_dest_id.analytic_account_id
            or self.location_id.analytic_account_id
        )

    def _get_analytic_distribution(self):
        distribution = super()._get_analytic_distribution()
        if distribution:
            return distribution
        account = self._rgb_resolve_analytic_account()
        if account:
            return {str(account.id): 100}
        return distribution

    def _generate_valuation_lines_data(
        self,
        partner_id,
        qty,
        debit_value,
        credit_value,
        debit_account_id,
        credit_account_id,
        svl_id,
        description,
    ):
        rslt = super()._generate_valuation_lines_data(
            partner_id,
            qty,
            debit_value,
            credit_value,
            debit_account_id,
            credit_account_id,
            svl_id,
            description,
        )
        distribution = self._get_analytic_distribution()
        if distribution:
            for line_key in rslt:
                rslt[line_key].setdefault("analytic_distribution", distribution)
        return rslt

    @api.model
    def _rgb_well_rig_from_picking(self, picking):
        if not picking:
            return {}
        vals = {}
        if picking.well_id:
            vals["well_id"] = picking.well_id.id
        if picking.rig_id:
            vals["rig_id"] = picking.rig_id.id
        if picking.project_id:
            vals["project_id"] = picking.project_id.id
        if picking.analytic_account_id:
            vals["analytic_account_id"] = picking.analytic_account_id.id
        return vals

    @api.model
    def _rgb_well_rig_from_vals(self, vals):
        extra = {}
        if vals.get("picking_id"):
            picking_vals = self._rgb_well_rig_from_picking(
                self.env["stock.picking"].browse(vals["picking_id"])
            )
            if picking_vals:
                extra.update(picking_vals)
        if vals.get("purchase_line_id") and not vals.get("well_id"):
            order = self.env["purchase.order.line"].browse(
                vals["purchase_line_id"]
            ).order_id
            order_vals = order._get_well_rig_vals()
            if order_vals:
                extra.update(order_vals)
        if vals.get("origin") and not vals.get("well_id"):
            picking = (
                self.env["stock.picking"].browse(vals["picking_id"])
                if vals.get("picking_id")
                else self.env["stock.picking"]
            )
            well_rig = picking._rgb_well_rig_from_origin(vals["origin"])
            if well_rig:
                extra.update(well_rig)
        # Do not overwrite explicit vals
        return {k: v for k, v in extra.items() if k not in vals}

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.update(self._rgb_well_rig_from_vals(vals))
        return super().create(vals_list)

    def write(self, vals):
        track_well_rig = {"well_id", "rig_id"} & set(vals)
        previous = {}
        if track_well_rig:
            for move in self:
                previous[move.id] = (move.well_id, move.rig_id)
        res = super().write(vals)
        if "picking_id" in vals:
            for move in self.filtered(lambda m: m.picking_id and not m.well_id):
                move_vals = self._rgb_well_rig_from_picking(move.picking_id)
                if move_vals:
                    super(StockMove, move).write(move_vals)
        if track_well_rig and not self.env.context.get("rgb_skip_move_well_rig_log"):
            for move in self:
                old_well, old_rig = previous.get(move.id, (False, False))
                if (
                    move.well_id == old_well
                    and move.rig_id == old_rig
                ) or not move.picking_id:
                    continue
                move.picking_id.message_post(
                    body=Markup(
                        "<b>Stock move updated</b> (%s)<br/>"
                        "Well: %s → %s<br/>"
                        "Rig: %s → %s"
                    )
                    % (
                        move.product_id.display_name,
                        old_well.display_name if old_well else "-",
                        move.well_id.display_name if move.well_id else "-",
                        old_rig.display_name if old_rig else "-",
                        move.rig_id.display_name if move.rig_id else "-",
                    ),
                    subtype_xmlid="mail.mt_note",
                )
        return res
