# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_contractor = fields.Boolean(
        string='Is Contractor',
        help='When checked, this partner appears in contractor lists for purchase contracts.',
    )

    @api.model
    def _rgb_partner_needs_auto_ref(self, vals):
        """Assign auto ref to main partners without a manual ref."""
        if vals.get('ref'):
            return False
        # Child contacts / addresses do not get their own reference.
        if vals.get('parent_id'):
            return False
        partner_type = vals.get('type', 'contact')
        if partner_type in ('invoice', 'delivery', 'other', 'private'):
            return False
        return True

    @api.model
    def _rgb_next_partner_ref(self):
        return self.env['ir.sequence'].next_by_code('rgb.partner.ref') or False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if self._rgb_partner_needs_auto_ref(vals):
                ref = self._rgb_next_partner_ref()
                if ref:
                    vals['ref'] = ref
        return super().create(vals_list)
