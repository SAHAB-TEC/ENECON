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


class ProductAvailabilityLookupWizard(models.TransientModel):
    _name = "product.availability.lookup.wizard"
    _description = "Check Product Availability in Other Locations"

    requisition_id = fields.Many2one("material.requisition", required=True)

    line_ids = fields.One2many(
        "product.availability.lookup.line", "wizard_id", string="Product Availability"
    )

    @api.model
    def default_get(self, fields):
        result = super().default_get(fields)
        if result.get("requisition_id"):
            requisition_id = self.env["material.requisition"].browse(
                result["requisition_id"]
            )
            requisition_lines = requisition_id.requested_product_ids
            data = []
            warehouse_loc = self.requisition_id.location_id.id
            for line in requisition_lines.filtered(lambda line: line.product_id and line.state != 'cancelled'):
                product = line.product_id
                if self.env.context.get("current_location"):
                    quants = self.env["stock.quant"].search(
                        [
                            ("product_id", "=", product.id),
                            ("location_id", "=", warehouse_loc),
                        ]
                    )
                else:
                    quants = self.env["stock.quant"].search(
                        [
                            ("product_id", "=", product.id),
                            ("location_id.usage", "=", "internal"),
                            ("location_id", "!=", warehouse_loc),
                        ]
                    )
                for quant in quants:
                    location_id = quant["location_id"][0]
                    available_qty = quant["quantity"]

                    if available_qty >= line.quantity:
                        data.append(
                            (
                                0,
                                0,
                                {
                                    "product_id": product.id,
                                    "requested_qty": line.quantity,
                                    "location_id": location_id,
                                    "available_qty": available_qty,
                                },
                            )
                        )
                        break
            result["line_ids"] = data
        return result
