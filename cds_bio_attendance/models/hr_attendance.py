import csv
from datetime import datetime, timedelta
import base64

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
TIME_FORMAT = "%H:%M:%S"
DATE_FORMAT = "%Y-%m-%d"


class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    @api.model
    def _cron_send_notification(self):
        print("iam in crone method notification")
        atts = self.search([('state', '!=', 'right')])
        atts.send_notification()

    def send_notification(self):
        for att in self:
            att_date = datetime.strftime(datetime.strptime(att.check_in.strftime(DATETIME_FORMAT), DATETIME_FORMAT), DATE_FORMAT)
            if att.state == 'right':
                continue
            employee = att.employee_id
            partners = self.env['res.partner']
            if employee.address_id:
                mail_content = "  Hello  " + employee.name + ",<br>Your Attendance in " + att_date + "  Need To Be Fixed " + ". Please Check  it <br> Regards"
                main_content = {
                    'subject': _('Wrong Attendance Notification'),
                    'author_id': self.env.user.partner_id.id,
                    'body_html': mail_content,
                    'email_to': self.env.user.partner_id.email,
                    'recipient_ids': [(4, employee.address_id.id)],

                }
                print('i have sent to employee')
                self.env['mail.mail'].sudo().create(main_content).send()

            for user in self.env['res.users'].search([]):
                if user.has_group('cds_bio_attendance.group_wrong_attendance_notify'):
                    partners += user.partner_id
            print('not partners is', [p.name for p in partners])
            mail_content = _(
                'Dear Sir, <br> Attendance of Employee:%s  In  date :%s Need to be fixed Please Check.<br> '
                'Regards<br>') % (
                               employee.name, att_date)
            main_content = {
                'subject': _('Wrong Attendance Of :%s  at %s') % (employee.name, att_date),
                'author_id': self.env.user.partner_id.id,
                'body_html': mail_content,
                'recipient_ids': [(4, pid) for pid in partners.ids],
            }
            self.env['mail.mail'].sudo().create(main_content).send()

    def fix_register(self):
        self.write({'state': 'right'})

    state = fields.Selection(
        selection=[('fixin', 'Fix In'), ('fixout', 'Fix Out'), ('right', 'Right'), ('fixed', 'Auto Fixed Out'),
                   ('fixed_in', 'Auto Fixed In')],
        default='right',
        help='The user did not register an input '
             'or an output in the correct order, '
             'then the system proposed one or more regiters to fix the problem '
             'but you must review the created register due '
             'because of hour could be not correct')
