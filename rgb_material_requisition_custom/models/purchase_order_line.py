# -*- coding: utf-8 -*-
from odoo import models


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    def _prepare_stock_move_vals(self, picking, price_unit, product_uom_qty, product_uom):
        vals = super()._prepare_stock_move_vals(
            picking, price_unit, product_uom_qty, product_uom
        )
        vals.update(self.order_id._get_well_rig_vals())
        requisition = self.order_id._get_material_requisition()
        if requisition and requisition.location_id:
            vals["location_dest_id"] = requisition.location_id.id
            vals["location_final_id"] = requisition.location_id.id
        return vals
