from odoo import api, fields, models, _


class ProjectInvoiceLineMixin(models.AbstractModel):
    _name = 'project.invoice.line.mixin'
    _description = 'Project Invoice Line (common logic)'
    _order = 'sequence, id'

    _parent_field = None   # name of the One2many on the header
    _log_fields = []       # fields logged to the chatter

    invoice_id = fields.Many2one('project.custom.invoice', required=True,
                                 ondelete='cascade', index=True)
    company_id = fields.Many2one(related='invoice_id.company_id', store=True)
    sequence = fields.Integer(default=10)
    line_no = fields.Integer(string='م', compute='_compute_line_no')
    product_id = fields.Many2one('product.product', string='البيان', required=True)
    price_unit = fields.Float(string='السعر', digits=(16, 3), compute='_compute_price_unit',
                              store=True, readonly=False)
    subtotal = fields.Float(string='الإجمالي', digits=(16, 3),
                            compute='_compute_subtotal', store=True)

    # -- hooks ----------------------------------------------------------
    def _get_price_qty(self):
        return 1.0

    def _get_line_amount(self):
        return self.price_unit

    # -- computes -------------------------------------------------------
    @api.depends('sequence', 'invoice_id')
    def _compute_line_no(self):
        for line in self:
            siblings = line.invoice_id[line._parent_field].sorted('sequence') \
                if line.invoice_id and line._parent_field else line
            idx = 0
            for i, sib in enumerate(siblings, 1):
                if sib.id == line.id:
                    idx = i
            line.line_no = idx or 1

    @api.depends('product_id', 'invoice_id.pricelist_id')
    def _compute_price_unit(self):
        for line in self:
            product = line.product_id
            if not product:
                line.price_unit = line.price_unit or 0.0
                continue
            price = product.lst_price
            pricelist = line.invoice_id.pricelist_id
            if pricelist:
                uom = getattr(line, 'uom_id', False) or product.uom_id
                price = pricelist._get_product_price(
                    product, line._get_price_qty() or 1.0, uom=uom,
                    date=line.invoice_id.invoice_date or fields.Date.context_today(line))
            line.price_unit = price

    @api.depends('price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line._get_line_amount()

    # -- chatter audit --------------------------------------------------
    def _fmt_value(self, fname, value):
        field = self._fields[fname]
        if field.type == 'many2one':
            return value.display_name or '-'
        if field.type == 'float':
            return '%.3f' % value
        return value or '-'

    def _line_summary(self):
        self.ensure_one()
        parts = ['%s: %s' % (self._fields[f].string, self._fmt_value(f, self[f]))
                 for f in self._log_fields]
        return '; '.join(parts)

    def _post_log(self, invoices, body_by_invoice):
        for invoice, bodies in body_by_invoice.items():
            invoice.sudo().message_post(
                body='<br/>'.join(bodies),
                author_id=self.env.user.partner_id.id,
                subtype_xmlid='mail.mt_note')

    @api.model_create_multi
    def create(self, vals_list):
        invoices = self.env['project.custom.invoice'].browse(
            [v['invoice_id'] for v in vals_list if v.get('invoice_id')])
        invoices._check_edit_rights()
        lines = super().create(vals_list)
        if not self.env.context.get('pi_creating'):
            logs = {}
            for line in lines:
                logs.setdefault(line.invoice_id, []).append(
                    '<b>%s</b> %s &mdash; %s' % (
                        _('Line added'), line._description, line._line_summary()))
            self._post_log(lines.invoice_id, logs)
        return lines

    def write(self, vals):
        self.invoice_id._check_edit_rights()
        tracked = [f for f in self._log_fields if f in vals]
        old = {line.id: {f: line[f] for f in tracked} for line in self} if tracked else {}
        res = super().write(vals)
        if tracked:
            logs = {}
            for line in self:
                changes = []
                for f in tracked:
                    before, after = old[line.id][f], line[f]
                    if before != after:
                        changes.append('%s: %s &rarr; %s' % (
                            line._fields[f].string, line._fmt_value(f, before),
                            line._fmt_value(f, after)))
                if changes:
                    logs.setdefault(line.invoice_id, []).append(
                        '<b>%s</b> %s (%s): %s' % (
                            _('Line modified'), line._description,
                            line.product_id.display_name or '-', '; '.join(changes)))
            self._post_log(self.invoice_id, logs)
        return res

    def unlink(self):
        self.invoice_id._check_edit_rights()
        logs = {}
        for line in self:
            logs.setdefault(line.invoice_id, []).append(
                '<b>%s</b> %s &mdash; %s' % (
                    _('Line removed'), line._description, line._line_summary()))
        self._post_log(self.invoice_id, logs)
        return super().unlink()


class UomMixin(models.AbstractModel):
    """Adds a UoM column auto-filled from the product (sections 1, 4, 5)."""
    _name = 'project.invoice.uom.mixin'
    _description = 'Project Invoice Line with UoM'

    uom_id = fields.Many2one('uom.uom', string='الوحدة', compute='_compute_uom_id',
                             store=True, readonly=False)

    @api.depends('product_id')
    def _compute_uom_id(self):
        for line in self:
            if line.product_id:
                line.uom_id = line.product_id.uom_id
            elif not line.uom_id:
                line.uom_id = False


# ----------------------------------------------------------------------
# Section 1: Materials
# ----------------------------------------------------------------------
class MaterialLine(models.Model):
    _name = 'project.invoice.material.line'
    _inherit = ['project.invoice.line.mixin', 'project.invoice.uom.mixin']
    _description = 'أولاً: المواد'
    _order = 'sequence, id'
    _parent_field = 'material_line_ids'
    _log_fields = ['product_id', 'uom_id', 'qty', 'price_unit']

    qty = fields.Float(string='عدد الوحدات', default=1.0, digits=(16, 3))
    price_unit = fields.Float(string='سعر الوحدة')

    def _get_price_qty(self):
        return self.qty

    def _get_line_amount(self):
        return self.qty * self.price_unit

    @api.depends('qty', 'price_unit')
    def _compute_subtotal(self):
        super()._compute_subtotal()


# ----------------------------------------------------------------------
# Section 2: Labor
# ----------------------------------------------------------------------
class LaborLine(models.Model):
    _name = 'project.invoice.labor.line'
    _inherit = 'project.invoice.line.mixin'
    _description = 'ثانياً: فريق العمل'
    _order = 'sequence, id'
    _parent_field = 'labor_line_ids'
    _log_fields = ['product_id', 'worker_days_qty', 'price_unit', 'overtime_hours',
                   'overtime_rate']

    worker_days_qty = fields.Float(string='عدد العاملين', default=1.0, digits=(16, 3))
    price_unit = fields.Float(string='السعر / اليوم')
    overtime_hours = fields.Float(string='ساعات الإضافية', default=0.0, digits=(16, 3))
    overtime_rate = fields.Float(string='تكلفة الساعة', default=0.0, digits=(16, 3))

    def _get_price_qty(self):
        return self.worker_days_qty

    def _get_line_amount(self):
        return (self.worker_days_qty * self.price_unit) + \
               (self.overtime_hours * self.overtime_rate)

    @api.depends('worker_days_qty', 'price_unit', 'overtime_hours', 'overtime_rate')
    def _compute_subtotal(self):
        super()._compute_subtotal()


# ----------------------------------------------------------------------
# Section 3: Transport
# ----------------------------------------------------------------------
class TransportLine(models.Model):
    _name = 'project.invoice.transport.line'
    _inherit = 'project.invoice.line.mixin'
    _description = 'ثالثاً: وسائل النقل'
    _order = 'sequence, id'
    _parent_field = 'transport_line_ids'
    _log_fields = ['product_id', 'days_qty', 'distance_label', 'price_unit',
                   'extra_distance_km', 'extra_km_price', 'base_extra_tier_fee']

    days_qty = fields.Float(string='عدد الأيام', default=1.0, digits=(16, 3))
    distance_label = fields.Char(string='المسافة كم')
    price_unit = fields.Float(string='السعر')
    extra_distance_km = fields.Float(string='مسافة الإضافية كم', default=0.0, digits=(16, 3))
    extra_km_price = fields.Float(string='سعر المسافة الإضافية', default=6.5, digits=(16, 3))
    base_extra_tier_fee = fields.Float(string='تكلفة الشريحة الأولى (100-300 كم)',
                                       default=926.0, digits=(16, 3))

    def _get_price_qty(self):
        return self.days_qty

    def _get_line_amount(self):
        base_amount = self.days_qty * self.price_unit
        km = self.extra_distance_km
        if km <= 0:
            extra_fee = 0.0
        elif km <= 300:
            extra_fee = self.base_extra_tier_fee
        else:
            extra_fee = self.base_extra_tier_fee + ((km - 300.0) * self.extra_km_price)
        return base_amount + extra_fee

    @api.depends('days_qty', 'price_unit', 'extra_distance_km', 'extra_km_price',
                 'base_extra_tier_fee')
    def _compute_subtotal(self):
        super()._compute_subtotal()


# ----------------------------------------------------------------------
# Section 4: Equipment
# ----------------------------------------------------------------------
class EquipmentLine(models.Model):
    _name = 'project.invoice.equipment.line'
    _inherit = ['project.invoice.line.mixin', 'project.invoice.uom.mixin']
    _description = 'رابعاً: المعدات وأدوات التشغيل'
    _order = 'sequence, id'
    _parent_field = 'equipment_line_ids'
    _log_fields = ['product_id', 'qty', 'uom_id', 'price_unit']

    qty = fields.Float(string='عدد الوحدات', default=1.0, digits=(16, 3))

    def _get_price_qty(self):
        return self.qty

    def _get_line_amount(self):
        return self.qty * self.price_unit

    @api.depends('qty', 'price_unit')
    def _compute_subtotal(self):
        super()._compute_subtotal()


# ----------------------------------------------------------------------
# Section 5: Catering
# ----------------------------------------------------------------------
class CateringLine(models.Model):
    _name = 'project.invoice.catering.line'
    _inherit = ['project.invoice.line.mixin', 'project.invoice.uom.mixin']
    _description = 'خامساً: الإعاشة'
    _order = 'sequence, id'
    _parent_field = 'catering_line_ids'
    _log_fields = ['product_id', 'qty', 'uom_id', 'price_unit']

    qty = fields.Float(string='عدد الوحدات', default=1.0, digits=(16, 3))

    def _get_price_qty(self):
        return self.qty

    def _get_line_amount(self):
        return self.qty * self.price_unit

    @api.depends('qty', 'price_unit')
    def _compute_subtotal(self):
        super()._compute_subtotal()
