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

from odoo import models, fields


class ProductAvailabilityLookupLine(models.TransientModel):
    _name = "product.availability.lookup.line"
    _description = "Line Showing Product Availability"

    wizard_id = fields.Many2one("product.availability.lookup.wizard")
    product_id = fields.Many2one("product.product", string="Product")
    requested_qty = fields.Float(string="Requested Qty")
    location_id = fields.Many2one("stock.location", string="Location")
    available_qty = fields.Float(string="Available Qty")
