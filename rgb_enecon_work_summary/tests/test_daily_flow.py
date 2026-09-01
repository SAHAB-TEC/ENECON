from datetime import date

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase


class TestEneconDailyFlow(TransactionCase):
    def test_daily_cycle(self):
        partner = self.env["res.partner"].create({"name": "ENECON Test Customer"})
        project = self.env["construction.project"].create({"name": "ENECON Daily Test", "partner_id": partner.id, "city": "Cairo"})
        material_tmpl = self.env["product.template"].create({"name": "ENECON Test Material", "rgb_enecon_material": True})
        equipment_tmpl = self.env["product.template"].create({"name": "ENECON Test Equipment", "rgb_enecon_equipment": True})
        material = material_tmpl.product_variant_id
        equipment = equipment_tmpl.product_variant_id
        stock_before = material.qty_available
        report = self.env["rgb.enecon.daily.report"].create({
            "project_id": project.id,
            "date": date(2026, 9, 1),
            "stage_name": "Surface Preparation",
            "tank_name": "Tank 02",
            "work_type": "Coating",
            "work_hours": 8.0,
            "overtime_hours": 1.5,
            "work_description": "Functional test work",
            "material_line_ids": [Command.create({"product_id": material.id, "quantity": 5.0, "uom_id": material.uom_id.id})],
            "equipment_line_ids": [Command.create({"product_id": equipment.id, "quantity": 1.0, "uom_id": equipment.uom_id.id})],
            "transport_line_ids": [Command.create({"name": "Manual Test Vehicle", "quantity": 1.0})],
        })
        self.assertEqual(report.customer_id, partner)
        self.assertEqual(report.location, "Cairo")
        self.assertNotEqual(report.name, "New")
        with self.assertRaises(AccessError):
            report.action_approve()
        self.env.user.write({"groups_id": [Command.link(self.env.ref("rgb_enecon_daily_report.group_rgb_enecon_daily_report_approver").id)]})
        report.action_approve()
        self.assertEqual(report.state, "approved")
        self.assertEqual(material.qty_available, stock_before)
        with self.assertRaises(UserError):
            report.write({"tank_name": "Locked Change"})
        with self.assertRaises(UserError):
            report.material_line_ids.write({"quantity": 9.0})
        action = self.env.ref("rgb_enecon_daily_report.action_report_rgb_enecon_daily_report")
        pdf, fmt = action.with_context(force_report_rendering=True)._render_qweb_pdf(action.report_name, res_ids=report.ids)
        self.assertEqual(fmt, "pdf")
        self.assertTrue(pdf.startswith(b"%PDF"))
