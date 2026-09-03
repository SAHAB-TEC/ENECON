# -*- coding: utf-8 -*-
from odoo import fields, models


class MaterialRequisitionLine(models.Model):
    _inherit = "material.requisition.line"

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
    project_id = fields.Many2one(
        "project.project",
        related="requisition_id.project_id",
        store=True,
        readonly=False,
        string="Project",
    )
    analytic_account_id = fields.Many2one(
        "account.analytic.account",
        related="requisition_id.analytic_account_id",
        store=True,
        readonly=False,
        string="Analytic Account",
    )
