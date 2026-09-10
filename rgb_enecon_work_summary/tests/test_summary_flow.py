from datetime import date

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestEneconSummaryFlow(TransactionCase):
    def test_summary_cycle(self):
        project = self.env["construction.project"].create({"name": "ENECON Summary Test"})
        material_tmpl = self.env["product.template"].create({"name": "ENECON Summary Material", "rgb_enecon_material": True})
        material = material_tmpl.product_variant_id
        job = self.env["hr.job"].create({"name": "ENECON Summary Engineer"})
        transport = self.env["rgb.enecon.transport.type"].create({"name": "ENECON Summary Truck"})
        entry1 = self.env["rgb.enecon.work.summary.entry"].create({
            "project_id": project.id,
            "date": date(2026, 9, 1),
            "notes_before_transport": "Before note",
            "notes_after_transport": "After note",
            "material_line_ids": [Command.create({"product_id": material.id, "quantity": 5.0, "uom_id": material.uom_id.id})],
            "workforce_line_ids": [Command.create({"job_id": job.id, "count": 2})],
            "transport_line_ids": [Command.create({"transport_type_id": transport.id, "quantity": 1})],
        })
        entry2 = self.env["rgb.enecon.work.summary.entry"].create({
            "project_id": project.id,
            "date": date(2026, 9, 2),
            "material_line_ids": [Command.create({"product_id": material.id, "quantity": 7.0, "uom_id": material.uom_id.id})],
            "workforce_line_ids": [Command.create({"job_id": job.id, "count": 3})],
            "transport_line_ids": [Command.create({"transport_type_id": transport.id, "quantity": 2})],
        })
        with self.assertRaises(AccessError):
            entry1.action_approve()
        self.env.user.write({"groups_id": [Command.link(self.env.ref("rgb_enecon_work_summary.group_rgb_enecon_work_summary_approver").id)]})
        entry1.action_approve()
        entry2.action_approve()
        with self.assertRaises(UserError):
            entry1.write({"notes_before_transport": "Locked Change"})
        with self.assertRaises(UserError):
            entry1.material_line_ids.write({"quantity": 9.0})
        wizard = self.env["rgb.enecon.work.summary.report.wizard"].create({
            "project_id": project.id,
            "date_from": date(2026, 9, 1),
            "date_to": date(2026, 9, 2),
            "approved_only": True,
        })
        values = self.env["report.rgb_enecon_work_summary.work_summary_document"]._get_report_values(wizard.ids)
        self.assertEqual(values["material_totals"], [12.0])
        self.assertEqual(values["workforce_totals"], [5])
        self.assertEqual(values["workforce_grand_total"], 5)
        self.assertEqual(values["transport_totals"], [3])
        action = self.env.ref("rgb_enecon_work_summary.action_report_rgb_enecon_work_summary")
        pdf, fmt = action.with_context(force_report_rendering=True)._render_qweb_pdf(action.report_name, res_ids=wizard.ids)
        self.assertEqual(fmt, "pdf")
        self.assertTrue(pdf.startswith(b"%PDF"))
        invalid = self.env["rgb.enecon.work.summary.report.wizard"].create({
            "project_id": project.id,
            "date_from": date(2026, 9, 3),
            "date_to": date(2026, 9, 1),
        })
        with self.assertRaises(ValidationError):
            invalid.action_print_report()
