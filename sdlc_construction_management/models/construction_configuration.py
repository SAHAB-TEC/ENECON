from odoo import models, fields, api, _


class ConstructionWorkType(models.Model):
    _name = 'construction.work.type'
    _description = 'Construction Work Type'
    _order = 'name'

    name = fields.Char(string='Work Type', required=True)
    code = fields.Char(string='Code')
    description = fields.Text(string='Description')
    sub_type_ids = fields.One2many('construction.work.sub.type', 'work_type_id', string='Sub Types')
    active = fields.Boolean(string='Active', default=True)


class ConstructionWorkSubType(models.Model):
    _name = 'construction.work.sub.type'
    _description = 'Construction Work Sub Type'
    _order = 'name'

    name = fields.Char(string='Work Sub Type', required=True)
    code = fields.Char(string='Code')
    work_type_id = fields.Many2one('construction.work.type', string='Work Type', required=True, ondelete='cascade')
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)
