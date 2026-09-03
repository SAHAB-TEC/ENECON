from collections import defaultdict

from odoo import fields, models
from odoo.exceptions import ValidationError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    material_requisition_id = fields.Many2one(
        "material.requisition", copy=False
    )
    material_requisition_receipt_id = fields.Many2one(
        "stock.picking", copy=False
    )

    def _action_done(self, *args, **kwargs):
        result = super()._action_done(*args, **kwargs)
        self.filtered(
            lambda picking: picking.state == "done"
        )._create_material_requisition_dispatches()
        return result

    def _create_material_requisition_dispatches(self):
        incoming_pickings = self.filtered(
            lambda picking: (
                picking.picking_type_id.code == "incoming" and picking.purchase_id
            )
        )
        for picking in incoming_pickings:
            requisition_lines = self.env["material.requisition.line"].search(
                [
                    ("requisition_action", "=", "purchase"),
                    ("rfq_id", "=", picking.purchase_id.id),
                    ("state", "!=", "cancelled"),
                ]
            )
            if not requisition_lines:
                continue

            moves = picking.move_ids_without_package.filtered(
                lambda move: (
                    move.state == "done"
                    and move.product_id
                )
            )
            lines_by_requisition = defaultdict(list)
            for line, quantity in self._get_material_requisition_dispatch_quantities(
                requisition_lines, moves
            ):
                requisition = line.requisition_id
                if not requisition:
                    continue
                requisition._ensure_destination_location(rule=requisition.approval_rule_id)
                if (
                    not requisition.location_id
                    or picking.location_dest_id == requisition.location_id
                ):
                    continue
                lines_by_requisition[requisition.id].append((line, quantity))

            for requisition_id, dispatch_lines in lines_by_requisition.items():
                requisition = self.env["material.requisition"].browse(requisition_id)
                existing = self.search(
                    [
                        ("material_requisition_receipt_id", "=", picking.id),
                        ("material_requisition_id", "=", requisition.id),
                        ("state", "!=", "cancel"),
                    ],
                    limit=1,
                )
                if existing:
                    continue

                dispatch_picking = self.create(
                    {
                        "picking_type_id": self.env.ref("stock.picking_type_internal").id,
                        "partner_id": requisition._get_delivery_partner().id or False,
                        "location_id": picking.location_dest_id.id,
                        "location_dest_id": requisition.location_id.id,
                        "origin": "%s - %s" % (requisition.name, picking.name),
                        "material_requisition_id": requisition.id,
                        "material_requisition_receipt_id": picking.id,
                        "move_ids": [
                            (
                                0,
                                0,
                                {
                                    "name": line.product_id.display_name,
                                    "product_id": line.product_id.id,
                                    "product_uom_qty": quantity,
                                    "product_uom": line.product_id.uom_id.id,
                                    "location_id": picking.location_dest_id.id,
                                    "location_dest_id": requisition.location_id.id,
                                },
                            )
                            for line, quantity in dispatch_lines
                        ],
                    }
                )
                dispatch_picking.action_confirm()
                dispatch_picking.action_assign()
                for line, quantity in dispatch_lines:
                    line.purchase_dispatch_picking_ids = [(4, dispatch_picking.id)]
                    if not line.picking_id:
                        line.picking_id = dispatch_picking.id

    def _get_material_requisition_dispatch_quantities(self, requisition_lines, moves):
        quantities_by_line = defaultdict(float)
        for move in moves:
            done_quantity = self._get_material_requisition_move_done_quantity(move)
            if done_quantity <= 0:
                continue
            matching_lines = requisition_lines.filtered(
                lambda line: (
                    line.rfq_line_id and line.rfq_line_id == move.purchase_line_id
                )
            )
            if not matching_lines:
                matching_lines = requisition_lines.filtered(
                    lambda line: (
                        not line.rfq_line_id and line.product_id == move.product_id
                )
            )
            remaining_quantity = move.product_uom._compute_quantity(
                done_quantity,
                move.product_id.uom_id,
                rounding_method="HALF-UP",
            )
            for line in matching_lines:
                if remaining_quantity <= 0:
                    break
                dispatched_moves = line.purchase_dispatch_picking_ids.mapped(
                    "move_ids_without_package"
                ).filtered(
                    lambda dispatch_move: dispatch_move.state != "cancel"
                    and dispatch_move.product_id == line.product_id
                )
                dispatched_quantity = sum(dispatched_moves.mapped("product_uom_qty"))
                line_uom = line.uom_id or line.product_id.uom_id
                requested_quantity = line_uom._compute_quantity(
                    line.quantity,
                    move.product_id.uom_id,
                    rounding_method="HALF-UP",
                )
                line_quantity = max(requested_quantity - dispatched_quantity, 0.0)
                quantity = min(remaining_quantity, line_quantity)
                if quantity <= 0:
                    continue
                quantities_by_line[line.id] += quantity
                remaining_quantity -= quantity

        return [
            (self.env["material.requisition.line"].browse(line_id), quantity)
            for line_id, quantity in quantities_by_line.items()
            if quantity > 0
        ]

    def _get_material_requisition_move_done_quantity(self, move):
        if "quantity" in move._fields:
            return move.quantity
        if "quantity_done" in move._fields:
            return move.quantity_done
        move_lines = move.move_line_ids
        if "quantity" in move_lines._fields:
            return sum(move_lines.mapped("quantity"))
        if "qty_done" in move_lines._fields:
            return sum(move_lines.mapped("qty_done"))
        return move.product_uom_qty
