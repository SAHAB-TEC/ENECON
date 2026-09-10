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


class FulfillmentWizard(models.TransientModel):
    _name = "material.requisition.fulfillment.wizard"
    _description = "Wizard for Line Fulfillment"

    requisition_id = fields.Many2one("material.requisition", required=True)
    line_ids = fields.Many2many(
        "material.requisition.line",
        "wizard_requisition_line_rel",
        string="Requisition Lines",
    )
    action_type = fields.Selection(
        [("internal_transfer", "Internal Transfer"), ("rfq", "Purchase Order")],
        required=True,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get(
            "active_model"
        ) == "material.requisition" and self.env.context.get("active_id"):
            requisition_id = self.env.context.get("active_id")
            res["requisition_id"] = requisition_id

            requisition = self.env["material.requisition"].browse(requisition_id)

            action_type = self.env.context.get("default_action_type")
            if action_type == "internal_transfer":
                lines = requisition.requested_product_ids.filtered(
                    lambda li: not li.picking_id and not li.rfq_id and li.state != 'cancelled'
                )
            elif action_type == "rfq":
                lines = requisition.requested_product_ids.filtered(
                    lambda li: not li.picking_id and not li.rfq_id and li.state != 'cancelled'
                )
            else:
                lines = self.env["material.requisition.line"]

            if lines:
                res["line_ids"] = [(6, 0, lines.ids)]

        return res

    def action_fulfill(self):
        if not self.line_ids:
            raise ValidationError("Please select at least one line to fulfill.")

        self._validate_quantities()

        total_lines = len(self.requisition_id.requested_product_ids)
        fulfilled_lines = len(self.line_ids)

        if self.action_type == "internal_transfer":
            self._create_internal_transfers()
            self._update_requisition_state_transfer(fulfilled_lines, total_lines)
        elif self.action_type == "rfq":
            self._create_rfqs()
            self._update_requisition_state_rfq(fulfilled_lines, total_lines)

        action_name = "Internal Transfer" if self.action_type == "internal_transfer" else "Purchase Order"
        self.requisition_id.message_post(
            body=f"{action_name} created successfully for {len(self.line_ids)} line(s)",
            message_type="notification"
        )
    
    def _validate_quantities(self):
        """Validate quantities before processing"""
        for line in self.line_ids:
            if line.qty_remaining <= 0:
                raise ValidationError(f"Quantity must be greater than 0 for product {line.product_id.name}")
            if line.qty_remaining > line.quantity:
                raise ValidationError(f"Selected quantity ({line.qty_remaining}) cannot exceed requested quantity ({line.quantity}) for product {line.product_id.name}")
    
    def _update_requisition_state_transfer(self, fulfilled_lines, total_lines):
        """Update requisition state for internal transfers"""
        active_lines = self.requisition_id.requested_product_ids.filtered(
            lambda li: li.state != 'cancelled'
        )
        processed_lines = active_lines.filtered(
            lambda li: li.picking_id or li.rfq_id
        )
        if len(processed_lines) < len(active_lines):
            self.requisition_id.state_id = self.env.ref(
                "material_requisition_and_approval.partial_internal_transfer"
            )
        else:
            self.requisition_id.state_id = self.env.ref(
                "material_requisition_and_approval.internal_transfer_created"
            )
    
    def _update_requisition_state_rfq(self, fulfilled_lines, total_lines):
        """Update requisition state for RFQs"""
        active_lines = self.requisition_id.requested_product_ids.filtered(
            lambda li: li.state != 'cancelled'
        )
        processed_lines = active_lines.filtered(
            lambda li: li.picking_id or li.rfq_id
        )
        if len(processed_lines) < len(active_lines):
            self.requisition_id.state_id = self.env.ref(
                "material_requisition_and_approval.partial_rfq_created"
            )
        else:
            self.requisition_id.state_id = self.env.ref(
                "material_requisition_and_approval.rfq_created"
            )

    def _create_internal_transfers(self):
        stock_picking = self.env["stock.picking"]
        rule = self.requisition_id.approval_rule_id
        self.requisition_id._ensure_destination_location(rule=rule)

        for line_wizard in self.line_ids:
            product = line_wizard.product_id
            employee_location = self.requisition_id.location_id
            source_location = line_wizard.stock_location_id

            if not employee_location:
                raise ValidationError(
                    "Destination location must be set on the requisition."
                )

            if not source_location:
                available = line_wizard.all_stock_location_ids
                if not available:
                    raise ValidationError(
                        f"Product '{product.name}' has no stock in any location. "
                        f"Use 'Fulfill by Purchase Order' to procure it."
                    )
                raise ValidationError(
                    f"Product '{product.name}': please select a source location. "
                    f"Available locations with stock: {', '.join(available.mapped('complete_name'))}"
                )

            if source_location.usage != "internal":
                raise ValidationError(
                    "Source location must be an internal stock location."
                )

            if line_wizard.qty_remaining > line_wizard.quantity:
                raise ValidationError(
                    f"Product '{product.name}': transfer quantity ({line_wizard.qty_remaining}) "
                    f"cannot exceed requested quantity ({line_wizard.quantity})."
                )

            if line_wizard.qty_remaining < 1:
                raise ValidationError(
                    f"Product '{product.name}': transfer quantity must be at least 1 "
                    f"(current value: {line_wizard.qty_remaining})."
                )

            picking = stock_picking.create(
                {
                    "partner_id": self.requisition_id._get_delivery_partner().id or False,
                    "location_id": source_location.id,
                    "location_dest_id": employee_location.id,
                    "picking_type_id": self.env.ref("stock.picking_type_internal").id,
                    "origin": self.requisition_id.name,
                    "move_ids": [
                        (
                            0,
                            0,
                            {
                                "name": product.name,
                                "product_id": product.id,
                                "product_uom_qty": line_wizard.qty_remaining,
                                "product_uom": product.uom_id.id,
                                "location_id": source_location.id,
                                "location_dest_id": employee_location.id,
                            },
                        )
                    ],
                }
            )

            if rule and rule.auto_create_dispatch:
                picking.action_confirm()
                picking.action_assign()
                if picking.state == 'assigned':
                    picking.button_validate()
                else:
                    raise ValidationError(
                        f"Product '{product.name}': insufficient stock at '{source_location.complete_name}' "
                        f"to auto-complete the transfer. Disable 'Auto Create Dispatch' on the approval "
                        f"rule or replenish the location first."
                    )
            elif rule and rule.require_stock_manager_dispatch:
                picking.action_confirm()
                picking.action_assign()

            line_wizard.picking_id = picking.id
            line_wizard.requisition_action = "transfer"

    def _create_rfqs(self):
        """Create RFQs grouped by vendor"""
        rfq_lines_by_vendor = {}
        created_orders = []
        self.requisition_id._ensure_destination_location(
            rule=self.requisition_id.approval_rule_id
        )

        for line in self.line_ids:
            vendor = line.vendor_id
            if not vendor:
                raise ValidationError(f"Please select a vendor for product {line.product_id.name}")
            rfq_lines_by_vendor.setdefault(vendor.id, []).append(line)

        date_planned = fields.Datetime.to_datetime(
            self.requisition_id.required_date
        ) or fields.Datetime.now()

        for vendor_id, lines in rfq_lines_by_vendor.items():
            vendor = self.env['res.partner'].browse(vendor_id)
            try:
                order_vals = {
                    "partner_id": vendor_id,
                    "origin": self.requisition_id.name,
                }
                if "requisition_id" in self.env["purchase.order"]._fields:
                    order_vals["requisition_id"] = False
                order = self.env["purchase.order"].with_context(
                    default_requisition_id=False
                ).create(order_vals)
                created_orders.append(order)

                for line in lines:
                    product = line.product_id
                    order_line = self.env["purchase.order.line"].create({
                        "order_id": order.id,
                        "product_id": product.id,
                        "product_qty": line.qty_remaining,
                        "product_uom": product.uom_po_id.id or product.uom_id.id,
                        "price_unit": product.standard_price or 0.0,
                        "name": f"[{product.default_code}] {product.name}" if product.default_code else product.name,
                        "date_planned": date_planned,
                    })
                    line.rfq_id = order.id
                    line.rfq_line_id = order_line.id
                    line.requisition_action = "purchase"

            except Exception as e:
                raise ValidationError(f"Failed to create RFQ for vendor {vendor.name}: {str(e)}")

        _logger.info(f"Created {len(created_orders)} RFQs for requisition {self.requisition_id.name}")

