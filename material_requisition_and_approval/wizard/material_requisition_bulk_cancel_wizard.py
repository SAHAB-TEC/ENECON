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


class MaterialRequisitionBulkCancelWizard(models.TransientModel):
    _name = 'material.requisition.bulk.cancel.wizard'
    _description = 'Material Requisition Bulk Cancel Wizard'

    requisition_ids = fields.Many2many('material.requisition', 'mr_bulk_cancel_rel', 'wizard_id', 'requisition_id', string='Requisitions to Cancel')
    reason = fields.Text(string='Cancellation Reason', required=True)
    send_notification = fields.Boolean(string='Send Email Notifications', default=True)
    cancel_related_documents = fields.Boolean(string='Cancel Related Documents', default=True)
    summary_html = fields.Html(string='Summary', compute='_compute_summary_html')
    
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_ids'):
            requisitions = self.env['material.requisition'].browse(self.env.context.get('active_ids'))
            # Filter only cancellable requisitions
            cancellable = requisitions.filtered(lambda r: r.state in ['draft', 'submitted', 'waiting_for_approval'])
            res['requisition_ids'] = [(6, 0, cancellable.ids)]
        return res
    
    @api.depends('requisition_ids')
    def _compute_summary_html(self):
        for wizard in self:
            if not wizard.requisition_ids:
                wizard.summary_html = False
                continue
                
            html = "<div class='alert alert-info'>"
            html += f"<h5>Bulk Cancellation Summary</h5>"
            html += f"<p><strong>Total Requisitions:</strong> {len(wizard.requisition_ids)}</p>"
            
            # Group by state
            states = {}
            for req in wizard.requisition_ids:
                state_label = dict(req._fields['state'].selection)[req.state]
                states[state_label] = states.get(state_label, 0) + 1
            
            html += "<p><strong>By Status:</strong></p><ul>"
            for state, count in states.items():
                html += f"<li>{state}: {count}</li>"
            html += "</ul>"
            
            # Count related documents
            total_pickings = sum(len(req.requested_product_ids.mapped('picking_id').filtered(lambda p: p)) for req in wizard.requisition_ids)
            total_pos = sum(len(req.requested_product_ids.mapped('rfq_id').filtered(lambda p: p)) for req in wizard.requisition_ids)
            
            if total_pickings or total_pos:
                html += "<p><strong>Related Documents:</strong></p><ul>"
                if total_pickings:
                    html += f"<li>Internal Transfers: {total_pickings}</li>"
                if total_pos:
                    html += f"<li>Purchase Orders: {total_pos}</li>"
                html += "</ul>"
            
            html += "</div>"
            wizard.summary_html = html
    
    def action_bulk_cancel(self):
        self.ensure_one()
        
        if not self.requisition_ids:
            raise UserError(_("No requisitions selected for cancellation."))
        
        cancelled_count = 0
        failed_requisitions = []
        
        for requisition in self.requisition_ids:
            try:
                # Check if requisition can be cancelled
                if requisition.state not in ['draft', 'submitted', 'waiting_for_approval']:
                    failed_requisitions.append(f"{requisition.name}: Invalid state ({requisition.state})")
                    continue
                
                # Check for completed documents
                completed_pickings = requisition.requested_product_ids.mapped('picking_id').filtered(lambda p: p.state == 'done')
                completed_pos = requisition.requested_product_ids.mapped('rfq_id').filtered(lambda p: p.state in ['done', 'purchase'])
                
                if completed_pickings or completed_pos:
                    failed_requisitions.append(f"{requisition.name}: Has completed documents")
                    continue
                
                # Cancel the requisition
                requisition._set_state_by_code('cancel')
                
                # Cancel related documents if requested
                if self.cancel_related_documents:
                    pickings = requisition.requested_product_ids.mapped('picking_id').filtered(
                        lambda p: p.state not in ['done', 'cancel']
                    )
                    for picking in pickings:
                        picking.action_cancel()
                    
                    pos = requisition.requested_product_ids.mapped('rfq_id').filtered(
                        lambda p: p.state not in ['done', 'cancel', 'purchase']
                    )
                    for po in pos:
                        po.button_cancel()
                
                # Log cancellation
                requisition.message_post(
                    body=_("<b>Bulk Cancellation</b><br/>Reason: %s") % self.reason
                )
                
                # Send notification if requested
                if self.send_notification:
                    self._send_individual_notification(requisition)
                
                cancelled_count += 1
                
            except Exception as e:
                failed_requisitions.append(f"{requisition.name}: {str(e)}")
        
        # Show results
        message = f"Successfully cancelled {cancelled_count} requisition(s)."
        if failed_requisitions:
            message += f"\n\nFailed to cancel {len(failed_requisitions)} requisition(s):\n"
            message += "\n".join(failed_requisitions)
        
        if failed_requisitions:
            raise UserError(message)
        else:
            return {'type': 'ir.actions.act_window_close'}
    def _send_individual_notification(self, requisition):
        """Send cancellation notification for individual requisition"""
        template = self.env.ref(
            'material_requisition_and_approval.email_template_material_requisition_cancellation',
            raise_if_not_found=False
        )
        
        if not template:
            return
        
        email_context = {
            'cancel_type': 'Full Cancellation (Bulk)',
            'reason': self.reason,
            'cancelled_items': [f"Requisition: {requisition.name}"],
        }
        
        if requisition.requester_id.email:
            template.with_context(**email_context).send_mail(
                requisition.id, force_send=True
            )