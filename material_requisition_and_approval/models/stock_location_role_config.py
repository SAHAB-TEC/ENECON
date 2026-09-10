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


class StockLocationRoleConfig(models.Model):
    _name = "stock.location.role.config"
    _description = "Stock Location Role Configuration"
    _rec_name = "location_id"

    location_id = fields.Many2one(
        "stock.location",
        string="Location",
        required=True,
        domain=[("usage", "=", "internal")],
    )
    store_checker_ids = fields.Many2many(
        "res.users",
        relation="stock_location_role_config_store_checker_rel",
        column1="config_id",
        column2="user_id",
        string="Store Checkers",
        required=True,
    )
    stock_manager_ids = fields.Many2many(
        "res.users",
        relation="stock_location_role_config_stock_manager_rel",
        column1="config_id",
        column2="user_id",
        string="Stock Managers",
        required=True,
    )
    replenishment_user_id = fields.Many2one(
        "res.users", string="Replenishment User"
    )
    remarks_required = fields.Boolean(string="Remarks Required")

    _sql_constraints = [
        ("location_id_unique", "UNIQUE(location_id)", "A role configuration already exists for this location.")
    ]

    def _assign_groups(self):
        store_checker_group = self.env.ref("material_requisition_and_approval.group_store_checker")
        stock_manager_group = self.env.ref("stock.group_stock_manager")
        for user in self.store_checker_ids:
            if store_checker_group not in user.groups_id:
                user.groups_id = [(4, store_checker_group.id)]
        for user in self.stock_manager_ids:
            if stock_manager_group not in user.groups_id:
                user.groups_id = [(4, stock_manager_group.id)]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._assign_groups()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._assign_groups()
        return res
