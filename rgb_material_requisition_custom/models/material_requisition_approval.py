# -*- coding: utf-8 -*-
from odoo import fields, models


class MaterialRequisitionApproval(models.Model):
    _inherit = "material.requisition.approval"

    well_id = fields.Many2one(
        "rgb.well", related="requisition_id.well_id", store=True, readonly=False
    )
    rig_id = fields.Many2one(
        "rgb.rig",
        related="requisition_id.rig_id",
        store=True,
        readonly=False,
        domain="[('well_id', '=', well_id)]",
    )
