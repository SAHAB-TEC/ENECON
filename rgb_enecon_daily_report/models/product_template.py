from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    rgb_enecon_material = fields.Boolean(
        string='ENECON Material',
        help='Allow this product to be selected as a material in ENECON daily reports.',
    )
    rgb_enecon_equipment = fields.Boolean(
        string='ENECON Equipment',
        help='Allow this product to be selected as equipment in ENECON daily reports.',
    )
