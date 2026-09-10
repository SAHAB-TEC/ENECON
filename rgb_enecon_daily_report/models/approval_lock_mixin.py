from odoo import api, models, _
from odoo.exceptions import UserError


class EneconApprovalLockMixin(models.AbstractModel):
    _name = "rgb.enecon.approval.lock.mixin"
    _description = "ENECON Approved Parent Lock Mixin"

    _parent_lock_field = False

    def _check_parent_lock(self):
        field_name = self._parent_lock_field
        if field_name and self.filtered(lambda line: getattr(line, field_name).state == "approved"):
            raise UserError(_("Approved records are locked and their detail lines cannot be modified."))

    @api.model_create_multi
    def create(self, vals_list):
        field_name = self._parent_lock_field
        if field_name:
            parent_ids = [vals.get(field_name) for vals in vals_list if vals.get(field_name)]
            if parent_ids:
                parent_model = self._fields[field_name].comodel_name
                parents = self.env[parent_model].browse(parent_ids)
                if parents.filtered(lambda parent: parent.state == "approved"):
                    raise UserError(_("Approved records are locked and new detail lines cannot be added."))
        return super().create(vals_list)
    def write(self, vals):
        self._check_parent_lock()
        return super().write(vals)

    def unlink(self):
        self._check_parent_lock()
        return super().unlink()
