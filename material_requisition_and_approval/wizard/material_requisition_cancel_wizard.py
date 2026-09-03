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

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class MaterialRequisitionCancelWizard(models.TransientModel):
    _name = 'material.requisition.cancel.wizard'
    _description = 'Material Requisition Cancel Wizard'

    requisition_id = fields.Many2one('material.requisition', string='Requisition', required=True)
    cancel_type = fields.Selection([
        ('full', 'Cancel Entire Request'),
        ('lines', 'Cancel Selected Lines')
    ], string='Cancellation Type', default='full', required=True)
    line_ids = fields.Many2many('material.requisition.line', 'mr_cancel_line_rel', 'wizard_id', 'line_id', string='Lines to Cancel')
    cancel_related_documents = fields.Boolean(string='Cancel Related Documents', default=True,
                                             help='Cancel related internal transfers and purchase orders')
    reason = fields.Text(string='Cancellation Reason', required=True)
    send_notification = fields.Boolean(string='Send Email Notification', default=True,
                                      help='Send cancellation notification to requester and approvers')
    impact_summary = fields.Html(string='Impact Summary', compute='_compute_impact_summary')
    has_related_documents = fields.Boolean(compute='_compute_has_related_documents')
    related_pickings_count = fields.Integer(compute='_compute_related_documents_count')
    related_pos_count = fields.Integer(compute='_compute_related_documents_count')
    
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'material.requisition' and self.env.context.get('active_id'):
            res['requisition_id'] = self.env.context.get('active_id')
        return res
    
    @api.depends('requisition_id', 'cancel_type', 'line_ids')
    def _compute_impact_summary(self):
        for wizard in self:
            if not wizard.requisition_id:
                wizard.impact_summary = False
                continue
                
            html = "<div class='alert alert-warning'><h5>Cancellation Impact:</h5><ul>"
            
            if wizard.cancel_type == 'full':
                lines = wizard.requisition_id.requested_product_ids
                html += f"<li><strong>Total Lines:</strong> {len(lines)} will be cancelled</li>"
            else:
                html += f"<li><strong>Selected Lines:</strong> {len(wizard.line_ids)} will be cancelled</li>"
            
            # Count related documents
            if wizard.cancel_type == 'full':
                lines_to_check = wizard.requisition_id.requested_product_ids
            else:
                lines_to_check = wizard.line_ids
                
            pickings = lines_to_check.mapped('picking_id').filtered(lambda p: p.state not in ['done', 'cancel'])
            pos = lines_to_check.mapped('rfq_id').filtered(lambda p: p.state not in ['done', 'cancel', 'purchase'])
            
            if pickings:
                html += f"<li><strong>Internal Transfers:</strong> {len(pickings)} will be cancelled</li>"
            if pos:
                html += f"<li><strong>Purchase Orders:</strong> {len(pos)} will be cancelled</li>"
                
            html += "</ul></div>"
            wizard.impact_summary = html
    
    @api.depends('requisition_id')
    def _compute_has_related_documents(self):
        for wizard in self:
            if not wizard.requisition_id:
                wizard.has_related_documents = False
                continue
            
            lines = wizard.requisition_id.requested_product_ids
            has_pickings = any(line.picking_id for line in lines)
            has_pos = any(line.rfq_id for line in lines)
            wizard.has_related_documents = has_pickings or has_pos
    
    @api.depends('requisition_id')
    def _compute_related_documents_count(self):
        for wizard in self:
            if not wizard.requisition_id:
                wizard.related_pickings_count = 0
                wizard.related_pos_count = 0
                continue
                
            lines = wizard.requisition_id.requested_product_ids
            wizard.related_pickings_count = len(lines.mapped('picking_id').filtered(lambda p: p))
            wizard.related_pos_count = len(lines.mapped('rfq_id').filtered(lambda p: p))
    
    @api.onchange('requisition_id', 'cancel_type')
    def _onchange_requisition_id(self):
        if self.requisition_id and self.cancel_type == 'lines':
            # Only show lines that can be cancelled
            cancellable_lines = self.requisition_id.requested_product_ids.filtered(
                lambda l: not (l.picking_id and l.picking_id.state == 'done') and 
                         not (l.rfq_id and l.rfq_id.state in ['done', 'purchase']) and not l.state == 'cancelled'
            )
            self.line_ids = [(6, 0, cancellable_lines.ids)]
            return {'domain': {'line_ids': [('id', 'in', cancellable_lines.ids)]}}
    
    @api.constrains('line_ids', 'cancel_type')
    def _check_line_selection(self):
        for wizard in self:
            if wizard.cancel_type == 'lines' and not wizard.line_ids:
                raise ValidationError(_("Please select at least one line to cancel."))
    
    def action_preview_cancellation(self):
        """Show preview of what will be cancelled before actual cancellation"""
        self.ensure_one()
        
        if self.cancel_type == 'lines' and not self.line_ids:
            raise UserError(_("Please select at least one line to cancel."))
            
        # Validate cancellation is possible
        self._validate_cancellation()
        
        return {
            'name': 'Confirm Cancellation',
            'type': 'ir.actions.act_window',
            'res_model': 'material.requisition.cancel.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('material_requisition_and_approval.view_material_requisition_cancel_confirm_form').id,
            'target': 'new',
        }
    
    def _validate_cancellation(self):
        """Validate if cancellation is possible"""
        if self.cancel_type == 'full':
            lines_to_check = self.requisition_id.requested_product_ids
        else:
            lines_to_check = self.line_ids
            
        blocked_lines = []
        for line in lines_to_check:
            if line.picking_id and line.picking_id.state == 'done':
                blocked_lines.append(f"• {line.product_id.name}: Transfer already completed")
            if line.rfq_id and line.rfq_id.state in ['done', 'purchase']:
                blocked_lines.append(f"• {line.product_id.name}: Purchase order already processed")
        
        if blocked_lines:
            error_msg = _("Cannot cancel the following lines:\n%s") % '\n'.join(blocked_lines)
            if self.cancel_type == 'full':
                error_msg += _("\n\nPlease use 'Cancel Selected Lines' option instead.")
            raise UserError(error_msg)
    
    def action_cancel(self):
        self.ensure_one()
        
        # Final validation
        self._validate_cancellation()
        
        cancelled_items = []
        
        if self.cancel_type == 'full':
            self._cancel_full_requisition(cancelled_items)
        else:
            self._cancel_selected_lines(cancelled_items)
        

        return {'type': 'ir.actions.act_window_close'}
    
    def _cancel_full_requisition(self, cancelled_items):
        """Cancel the entire requisition"""
        pickings = self.requisition_id.requested_product_ids.mapped('picking_id')
        purchase_orders = self.requisition_id.requested_product_ids.mapped('rfq_id')
        
        self.requisition_id._set_state_by_code('cancel')
        
        if self.cancel_related_documents:
            for picking in pickings.filtered(lambda p: p.state not in ['done', 'cancel']):
                picking.action_cancel()
                cancelled_items.append(f"Internal Transfer: {picking.name}")
            
            for po in purchase_orders.filtered(lambda p: p.state not in ['done', 'cancel', 'purchase']):
                po.button_cancel()
                cancelled_items.append(f"Purchase Order: {po.name}")
        
        
        self._send_full_cancellation_notification(cancelled_items)
        
    
        message = _("Requisition Cancelled \n Reason: %s") % self.reason
        if cancelled_items:
            message += _("Related documents cancelled:\n• %s") % '• '.join(cancelled_items)
        
        self.requisition_id.message_post(body=message)
    
    def _cancel_selected_lines(self, cancelled_items):
        """Cancel selected lines only"""
        for line in self.line_ids:
            line.qty_cancel = line.quantity
            cancelled_items.append(f"Product: {line.product_id.name} (Qty: {line.quantity})")
            
            if self.cancel_related_documents:
                if line.picking_id and line.picking_id.state not in ['done', 'cancel']:
                    line.picking_id.action_cancel()
                    cancelled_items.append(f"Internal Transfer: {line.picking_id.name}")
                
                if line.rfq_id and line.rfq_id.state not in ['done', 'cancel', 'purchase']:
                    line.rfq_id.button_cancel()
                    cancelled_items.append(f"Purchase Order: {line.rfq_id.name}")
        
        # if all(line.qty_cancel == line.quantity for line in self.requisition_id.requested_product_ids):
        #     self.requisition_id._set_state_by_code('cancel')
        # else:
        #     self.requisition_id._set_state_by_code('partial_fulfillment')
        
    
        message = _("""Lines Cancelled 
                    Reason: %s
                    Cancelled items:• %s""") % (
            self.reason, '\n• '.join(cancelled_items)
        )
        self._send_cancellation_notification(cancelled_items)
        self.requisition_id.message_post(body=message)
    
    def _send_cancellation_notification(self, cancelled_items):
        """Send email notification about cancellation"""
        template = self.env.ref(
            'material_requisition_and_approval.email_template_material_requisition_cancellation',
            raise_if_not_found=False
        )
        
        if not template:
            return
        
   
        email_context = {
            'cancelled_items': cancelled_items,
            'cancel_type': dict(self._fields['cancel_type'].selection)[self.cancel_type],
            'reason': self.reason,
             'today': fields.Date.today(),
        }
        
    
        if self.requisition_id.requester_id.email:
            template.with_context(**email_context).send_mail(
                self.requisition_id.id, force_send=True
            )
        
   
    def _send_full_cancellation_notification(self, cancelled_items):
        """Send email notification for full requisition cancellation"""
        template = self.env.ref(
            'material_requisition_and_approval.email_template_material_requisition_cancellation',
            raise_if_not_found=False
        )
        
        if not template:
            return
        
        # Get recipients
        recipients = []
        if self.requisition_id.requester_id:
            recipients.append(self.requisition_id.requester_id)
        if self.requisition_id.department_manager_id.user_id:
            recipients.append(self.requisition_id.department_manager_id.user_id)
        
        valid_recipients = [user for user in recipients if user and user.email]
        
        if valid_recipients:
            recipient_emails = [user.email for user in valid_recipients]
            recipient_names = [user.name for user in valid_recipients]
            
            # Email context
            email_context = {
                'email_to': ','.join(recipient_emails),
                'cancelled_items': cancelled_items,
                'reason': self.reason,
                'today': fields.Date.today(),
            }

            
            
            template.with_context(**email_context).send_mail(
                self.requisition_id.id, force_send=True
            )
            
            self.requisition_id.message_post(
                body=f"Cancellation notification sent to: {', '.join(recipient_names)}",
                message_type="notification"
            )