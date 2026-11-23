from markupsafe import Markup

from odoo import _, api, fields, models

AUDITED_FIELDS = [
    'is_section', 'item_code', 'description', 'wtg_pct', 'value_per_item',
    'prev_period_pct', 'this_period_pct', 'overall_pct', 'prev_period_amount',
]


class ProgressPaymentScheduleLine(models.Model):
    _name = 'progress.payment.schedule.line'
    _description = 'Progress Payment Schedule Line'
    _order = 'sequence, id'

    schedule_id = fields.Many2one(
        'progress.payment.schedule', string='Schedule', required=True,
        ondelete='cascade', index=True)
    sequence = fields.Integer(default=10)
    is_section = fields.Boolean(string='Is Section Header', default=False)
    item_code = fields.Char(string='ITEM')
    description = fields.Char(string='DESCRIPTION OF WORKS')
    wtg_pct = fields.Float(string='WTG% of total value', digits=(16, 2))
    value_per_item = fields.Float(string='VALUE PER ITEM', digits=(16, 3))
    prev_period_pct = fields.Float(string='PREVIOUS PERIOD %', digits=(16, 2))
    this_period_pct = fields.Float(string='THIS PERIOD PROGRESS %', digits=(16, 2))

    # Manual input columns (do not drive any other column)
    overall_pct = fields.Float(string='OVERALL PROGRESS %', digits=(16, 2))
    prev_period_amount = fields.Float(string='Previous Period (LYD)', digits=(16, 3))

    # Computed columns
    this_period_amount = fields.Float(
        string='This Period (LYD)', digits=(16, 3),
        compute='_compute_line_values', store=True)
    cumulative_amount = fields.Float(
        string='Cummulative (LYD)', digits=(16, 3),
        compute='_compute_line_values', store=True)

    @api.depends('value_per_item', 'this_period_pct', 'prev_period_amount', 'is_section')
    def _compute_line_values(self):
        for line in self:
            if line.is_section:
                line.this_period_amount = 0.0
                line.cumulative_amount = 0.0
                continue
            this_amount = line.value_per_item * (line.this_period_pct / 100.0)
            line.this_period_amount = this_amount
            line.cumulative_amount = line.prev_period_amount + this_amount

    @api.onchange('is_section')
    def _onchange_is_section(self):
        if self.is_section:
            self.wtg_pct = 0.0
            self.value_per_item = 0.0
            self.prev_period_pct = 0.0
            self.this_period_pct = 0.0
            self.overall_pct = 0.0
            self.prev_period_amount = 0.0

    # ------------------------------------------------------------------
    # Audit trail on the parent document's chatter
    # ------------------------------------------------------------------
    @staticmethod
    def _fmt(value):
        if isinstance(value, bool):
            return _('Yes') if value else _('No')
        if isinstance(value, float):
            return '%.3f' % value
        return value or '-'

    def _line_label(self):
        self.ensure_one()
        return ' '.join(filter(None, [self.item_code, self.description])) or _('(empty line)')

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines:
            line.schedule_id.message_post(body=Markup(
                _("Work item added: <b>%(label)s</b> (value: %(value)s)")
            ) % {
                'label': line._line_label(),
                'value': '%.3f' % line.value_per_item,
            })
        return lines

    def write(self, vals):
        tracked = [f for f in AUDITED_FIELDS if f in vals]
        old = {}
        if tracked:
            for line in self:
                old[line.id] = {f: line[f] for f in tracked}
        res = super().write(vals)
        for line in self:
            if not tracked or line.id not in old:
                continue
            changes = []
            for fname in tracked:
                before, after = old[line.id][fname], line[fname]
                if before != after:
                    changes.append(Markup("<li>%s: %s &rarr; %s</li>") % (
                        self._fields[fname].string, self._fmt(before), self._fmt(after)))
            if changes:
                line.schedule_id.message_post(body=Markup(
                    "<p>%s <b>%s</b></p><ul>%s</ul>") % (
                        _("Work item updated:"), line._line_label(),
                        Markup('').join(changes)))
        return res

    def unlink(self):
        for line in self:
            line.schedule_id.message_post(body=Markup(
                _("Work item removed: <b>%(label)s</b> (value: %(value)s)")
            ) % {
                'label': line._line_label(),
                'value': '%.3f' % line.value_per_item,
            })
        return super().unlink()
