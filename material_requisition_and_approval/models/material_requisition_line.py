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


from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class MaterialRequisitionLine(models.Model):
    _name = "material.requisition.line"
    _description = "Material Requisition Line"
    _rec_name = "requisition_id"

    _order = "id desc"

    active = fields.Boolean(default=True)
    requisition_id = fields.Many2one("material.requisition", string="Reference")
    product_id = fields.Many2one("product.product", string="Product", required=True)
    # product_uom_category_id = fields.Many2one(
    #     related="product_id.uom_id.category_id", depends=["product_id"]
    # )

    requisition_action = fields.Selection(
        [("purchase", "Purchase"), ("transfer", "Transfer")],
        string="Requisition Action",
    )

    available_qty = fields.Float(
        string="Available Quantity", compute="_compute_available_qty", store=True
    )

    remarks = fields.Text(string="Remarks")

    rfq_id = fields.Many2one("purchase.order", string="Request for Quotation")
    rfq_line_id = fields.Many2one("purchase.order.line", string="Purchase Order Line")
    picking_id = fields.Many2one("stock.picking", string="Picking")
    purchase_dispatch_picking_ids = fields.Many2many(
        "stock.picking",
        "material_requisition_line_purchase_dispatch_rel",
        "line_id",
        "picking_id",
        string="Purchase Dispatch Pickings",
    )
    vendor_id = fields.Many2one("res.partner", string="Vendor")

    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        compute="_compute_uom_id",
        store=True,
        precompute=True,
        readonly=False,
        domain="[('id', 'in', product_id.uom_id.related_uom_ids)]",
    )

    is_dispatch = fields.Boolean(default=False)
    all_vendor_ids = fields.Many2many(
        "res.partner", compute="_compute_all_vendor_ids", store=False
    )
    stock_location_id = fields.Many2one(
        "stock.location", string="Source Stock Location"
    )

    all_stock_location_ids = fields.Many2many(
        "stock.location", compute="_compute_stock_location_ids", store=False
    )

    quantity = fields.Float(string="Quantity", default=1)

    qty_cancel = fields.Float(
        string="Cancelled Quantity",
        compute="_compute_qty_cancel",
        store=True,
        readonly=False,
    )

    qty_remaining = fields.Float(
        string="Remaining Quantity",
        compute="_compute_remaining_quantity",
        store=True,
        readonly=False,
    )

    qty_delivered = fields.Float(
        string="Delivered Quantity",
        compute="_compute_qty_delivered",
        store=True,
        readonly=False,
    )

    state = fields.Selection(
        [
            ("fulfilled", "Fulfilled"),
            ("partial_fulfilled", "Partially Fulfilled"),
            ("cancelled", "Cancelled"),
            ("draft", "Draft"),
        ],
        string="Status",
        compute="_compute_state",
        store=True,
        default="draft",
    )
    forecast_expected_date = fields.Datetime(
        string="Forecast Expected Date",
        compute="_compute_forecast_information",
        store=True,
    )
    forecast_availability = fields.Float(
        string="Forecast Availability",
        compute="_compute_forecast_information",
        store=True,
    )

    @api.depends("quantity", "qty_delivered", "qty_cancel")
    def _compute_state(self):
        for record in self:
            if record.qty_cancel == record.quantity:
                record.state = "cancelled"
            elif record.qty_delivered == record.quantity:
                record.state = "fulfilled"
            elif record.qty_delivered > 0 and record.qty_delivered < record.quantity:
                record.state = "partial_fulfilled"
            else:
                record.state = "draft"

    @api.depends("product_id", "uom_id", "quantity")
    def _compute_available_qty(self):
        for record in self:
            if not record.product_id:
                record.available_qty = 0.0
                continue

            quants = self.env["stock.quant"].search(
                [
                    ("product_id", "=", record.product_id.id),
                    ("location_id.usage", "=", "internal"),
                ]
            )

            total_qty = sum(quant.available_quantity for quant in quants)

            record.available_qty = record.product_id.uom_id._compute_quantity(
                total_qty, record.uom_id, rounding_method="HALF-UP"
            )

    @api.depends("quantity", "qty_delivered", "qty_cancel")
    def _compute_remaining_quantity(self):
        for line in self:
            line.qty_remaining = line.quantity - line.qty_delivered - line.qty_cancel

    @api.depends(
        "picking_id.state",
        "rfq_id.picking_ids.state",
        "purchase_dispatch_picking_ids",
        "purchase_dispatch_picking_ids.move_ids_without_package.state",
        "rfq_id.state",
        "requisition_action",
        "product_id",
    )
    def _compute_qty_delivered(self):
        for line in self:
            if line.requisition_action == "transfer" and line.picking_id:
                moves = line.picking_id.move_ids_without_package.filtered(
                    lambda m: m.product_id == line.product_id
                )
                line.qty_delivered = sum(
                    m.product_uom_qty for m in moves if m.state == "done"
                )

            elif line.requisition_action == "purchase" and line.rfq_id:
                if line.purchase_dispatch_picking_ids:
                    moves = line.purchase_dispatch_picking_ids.mapped(
                        "move_ids_without_package"
                    ).filtered(lambda m: m.product_id == line.product_id)
                    line.qty_delivered = sum(
                        m.product_uom_qty for m in moves if m.state == "done"
                    )
                else:
                    po_lines = line.rfq_id.order_line.filtered(
                        lambda li: li.product_id == line.product_id
                    )
                    line.qty_delivered = sum(po.qty_received for po in po_lines)

            else:
                line.qty_delivered = 0.0

    @api.depends(
        "picking_id.move_ids.state",
        "rfq_id.order_line.qty_received",
        "rfq_id.order_line.product_qty",
        "rfq_id.state",
        "requisition_action",
        "product_id",
        "rfq_id.picking_ids.state",
        "state"
    )
    def _compute_qty_cancel(self):
        for line in self:
            old_qty_cancel = line.qty_cancel
            qty_cancel = 0.0

            if line.requisition_action == "transfer" and line.picking_id:
                cancelled_moves = line.picking_id.move_ids_without_package.filtered(
                    lambda m: m.product_id == line.product_id and m.state == "cancel"
                )
                qty_cancel = sum(m.product_uom_qty for m in cancelled_moves)

            elif line.requisition_action == "purchase" and line.rfq_id:
                po_lines = line.rfq_id.order_line.filtered(
                    lambda li: li.product_id == line.product_id
                )

                if line.rfq_id.state == "cancel":
                    qty_cancel = sum(po.product_qty for po in po_lines)

                elif line.rfq_id.state == "done":
                    qty_cancel = sum(
                        max(0.0, po.product_qty - po.qty_received) for po in po_lines
                    )

                elif line.rfq_id.state == "purchase":
                    for picking in line.rfq_id.picking_ids.filtered(
                        lambda p: p.state == "cancel"
                    ):
                        cancelled_moves = picking.move_ids_without_package.filtered(
                            lambda m: m.product_id == line.product_id
                        )
                        qty_cancel += sum(m.product_uom_qty for m in cancelled_moves)

            line.qty_cancel = qty_cancel

            # Send notification if cancellation occurred
            if (qty_cancel > old_qty_cancel and line.requisition_id):
                line._notify_product_cancellation(qty_cancel - old_qty_cancel)

    def _notify_product_cancellation(self, cancelled_qty):
        """Send notification when product is cancelled"""
        message = ("Product Cancelled \n Product: %s\n Cancelled Quantity: %s %s") % (
            self.product_id.name,
            cancelled_qty,
            self.uom_id.name,
        )

        if self.requisition_action == "transfer" and self.picking_id:
            message += ("\n Transfer: %s") % self.picking_id.name
        elif self.requisition_action == "purchase" and self.rfq_id:
            message += ("\n Purchase Order: %s") % self.rfq_id.name

        odoo_bot = self.env.ref("base.user_root", raise_if_not_found=False)
        if not odoo_bot:
            odoo_bot = (
                self.env["res.users"]
                .sudo()
                .search([("login", "=", "__system__")], limit=1)
            )

        self.requisition_id.with_user(odoo_bot).message_post(
            body=message, author_id=odoo_bot.partner_id.id if odoo_bot else False
        )

        template = self.env.ref(
            "material_requisition_and_approval.email_template_material_requisition_cancellation",
            raise_if_not_found=False,
        )

        if template and self.requisition_id.requester_id.email:
            email_context = {
                "cancel_type": "Product Cancellation",
                "reason": "System detected cancellation",
                "cancelled_items": [
                    f"Product: {self.product_id.name} (Qty: {cancelled_qty} {self.uom_id.name})"
                ],
                'today': fields.Date.today(),
            }
            template.with_context(**email_context).send_mail(
                self.requisition_id.id, force_send=True
            )

    @api.constrains("quantity")
    def _check_quantity(self):
        for rule in self:
            if rule.quantity < 1:
                raise ValidationError(
                    "please select at least one quantity of a product"
                )

    @api.constrains("qty_remaining")
    def _check_remaining_quantity(self):
        for rule in self:
            if rule.qty_remaining < 0:
                raise ValidationError(
                    "please select at least one quantity of a product"
                )
            if rule.qty_remaining > rule.quantity:
                raise ValidationError(
                    "Quantity will not greater then Requested quantity"
                )

    @api.depends("product_id", "quantity", "requisition_id.location_id")
    def _compute_stock_location_ids(self):
        for record in self:
            valid_location_ids = []
            if record.product_id:
                dest_location_id = record.requisition_id.location_id.id
                quants = self.env["stock.quant"].search(
                    [
                        ("product_id", "=", record.product_id.id),
                        ("location_id.usage", "=", "internal"),
                        ("quantity", ">", 0),
                    ]
                )
                valid_location_ids = [
                    q.location_id.id for q in quants
                    if q.location_id.id != dest_location_id
                ]
            record.all_stock_location_ids = [(6, 0, valid_location_ids)]

    @api.depends("product_id")
    def _compute_all_vendor_ids(self):
        for record in self:
            if record.product_id and record.product_id.seller_ids:
                vendor_ids = record.product_id.seller_ids.mapped("partner_id").ids
                record.all_vendor_ids = [(6, 0, vendor_ids)]
            else:
                all_partners = self.env["res.partner"].search(
                    [("is_company", "=", True), ("supplier_rank", ">", 0)]
                )
                if not all_partners:
                    all_partners = self.env["res.partner"].search(
                        [("is_company", "=", True)]
                    )
                record.all_vendor_ids = [(6, 0, all_partners.ids)]

    @api.onchange("product_id")
    def _onchange_product_id_set_defaults(self):
        """Auto-select first vendor and first stock location when product changes."""
        if self.product_id:
            if self.product_id.seller_ids and not self.vendor_id:
                self.vendor_id = self.product_id.seller_ids[0].partner_id
            dest_location_id = self.requisition_id.location_id.id
            quants = self.env["stock.quant"].search(
                [
                    ("product_id", "=", self.product_id.id),
                    ("location_id.usage", "=", "internal"),
                    ("quantity", ">", 0),
                ]
            )
            valid_ids = [q.location_id.id for q in quants if q.location_id.id != dest_location_id]
            if valid_ids and not self.stock_location_id:
                self.stock_location_id = valid_ids[0]

    @api.depends("product_id")
    def _compute_uom_id(self):
        for line in self:
            if not line.uom_id or (line.product_id.uom_id.id != line.uom_id.id):
                line.uom_id = line.product_id.uom_id

    @api.depends("product_id", "quantity", "requisition_id.state", "requisition_id.location_id")
    def _compute_forecast_information(self):
        """Compute forecasted information from the requisition location warehouse."""
        _logger.info("@compute_forecast_information@")
        for line in self:
            line.forecast_availability = False
            line.forecast_expected_date = False

            # if not line.product_id or not line.product_id.type == 'product':
            #     line.forecast_availability = line.quantity
            #     _logger.info("forecast_availability: %s", line.forecast_availability)
            #     continue

            location = line.requisition_id.location_id
            warehouse = location.warehouse_id if location else False
            if not warehouse:
                continue

            virtual_available = line.product_id.with_context(
                warehouse=warehouse.id, to_date=fields.Datetime.now()
            ).virtual_available

            line.forecast_availability = virtual_available

            if virtual_available < line.quantity:
                incoming_moves = self.env["stock.move"].search(
                    [
                        ("product_id", "=", line.product_id.id),
                        (
                            "location_dest_id",
                            "child_of",
                            warehouse.view_location_id.id,
                        ),
                        (
                            "location_id",
                            "not in",
                            [location.id],
                        ),
                        ("state", "in", ["waiting", "confirmed", "assigned"]),
                        ("date", "!=", False),
                    ],
                    order="date",
                    limit=1,
                )

                if incoming_moves:
                    line.forecast_expected_date = incoming_moves[0].date


    @api.model
    def get_action_click_graph(self):
        return self._get_action(
            "material_requisition_and_approval.action_material_requisition_summary_dashboard"
        )

    def _get_action(self, action_xmlid):
        action = self.env["ir.actions.actions"]._for_xml_id(action_xmlid)
        action["view_mode"] = "list,form"
        return action

    @api.onchange('product_id', 'quantity', 'requisition_id.location_id')
    def _onchange_forecast_refresh(self):
        """Refresh forecast information when key fields change"""
        self._compute_forecast_information()

    def action_product_forecast_report(self):
        self.ensure_one()
        action = self.product_id.action_product_forecast_report()

        action["context"] = {
            "active_id": self.product_id.id,
            "active_model": "product.product",
            "move_to_match_ids": self.ids,
        }

        warehouse = self.requisition_id.location_id.warehouse_id

        if warehouse:
            action["context"]["warehouse_id"] = warehouse.id

        _logger.info("action_product_forecast_report: %s", action)

        return action

    def unlink(self):
        if self.env.context.get("force_unlink"):
            return super().unlink()

        self.filtered("active").write({"active": False})
        return True
