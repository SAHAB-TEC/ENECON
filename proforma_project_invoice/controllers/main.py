import io

import xlsxwriter

from odoo import http
from odoo.http import request, content_disposition

NCOL = 9  # sheet is 9 columns wide (0..8); column 8 always holds the line total


def _d(value):
    return value.strftime('%d/%m/%Y') if value else ''


class ProjectInvoiceXlsx(http.Controller):

    @http.route('/proforma_invoice/xlsx/<int:invoice_id>', type='http', auth='user')
    def download_xlsx(self, invoice_id, **kw):
        invoice = request.env['project.custom.invoice'].browse(invoice_id).exists()
        if not invoice:
            return request.not_found()
        invoice.check_access('read')
        data = self._build_xlsx(invoice)
        filename = 'Invoice_%s.xlsx' % (invoice.name or invoice_id).replace('/', '_')
        return request.make_response(data, headers=[
            ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
            ('Content-Disposition', content_disposition(filename)),
        ])

    # ------------------------------------------------------------------
    def _build_xlsx(self, inv):
        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = wb.add_worksheet('Invoice')
        ws.right_to_left()
        ws.set_paper(9)
        ws.fit_to_pages(1, 0)
        ws.set_column(0, 0, 5)
        ws.set_column(1, 1, 38)
        ws.set_column(2, NCOL - 2, 15)
        ws.set_column(NCOL - 1, NCOL - 1, 16)

        base = {'font_name': 'Arial', 'font_size': 11, 'valign': 'vcenter'}

        def fmt(**kw):
            return wb.add_format({**base, **kw})

        F = {
            'title': fmt(bold=True, align='center', font_size=14),
            'sub': fmt(bold=True, align='center', font_size=12),
            'meta_r': fmt(bold=True, align='right'),
            'meta_l': fmt(bold=True, align='left'),
            'section': fmt(bold=True, align='right', font_size=12),
            'th': fmt(bold=True, align='center', border=1, bg_color='#F0F0F0', text_wrap=True),
            'txt': fmt(align='right', border=1),
            'cell': fmt(align='center', border=1),
            'qty': fmt(align='center', border=1, num_format='General'),
            'money': fmt(align='center', border=1, num_format='0.000'),
            'tot_l': fmt(bold=True, align='center', border=1),
            'tot_n': fmt(bold=True, align='center', border=1, num_format='0.000'),
            'tot_q': fmt(bold=True, align='center', border=1, num_format='General'),
            'note': fmt(align='right', text_wrap=True, border=1, bold=True),
            'grand_l': fmt(bold=True, align='center', border=2, font_size=12),
            'grand_n': fmt(bold=True, align='center', border=2, font_size=12,
                           num_format='0.000'),
            'sign': fmt(bold=True, align='left'),
        }

        row = 0
        ws.merge_range(row, 0, row, NCOL - 1, 'فاتورة رقم %s' % (inv.manual_invoice_number or ''), F['title'])
        row += 1
        ws.merge_range(row, 0, row, NCOL - 1, inv.project_title or '', F['sub'])
        row += 1
        ws.merge_range(row, 0, row, 4, 'الاخوة / %s' % (inv.partner_id.name or ''), F['meta_r'])
        ws.merge_range(row, 5, row, NCOL - 1, 'فترة العمل من %s الى %s' % (
            _d(inv.work_date_from), _d(inv.work_date_to)), F['meta_l'])
        row += 1
        ws.merge_range(row, 0, row, 4, 'الرقم الاشاري : %s' % (inv.reference_number or ''), F['meta_r'])
        ws.merge_range(row, 5, row, NCOL - 1, 'التاريخ : %s' % _d(inv.invoice_date), F['meta_l'])
        row += 2

        # (header, getter, kind)
        sections = [
            ('أولاً: المواد', inv.material_line_ids, [
                ('البيان', lambda l: l.product_id.display_name, 'txt'),
                ('الوحدة', lambda l: l.uom_id.name, 'cell'),
                ('عدد الوحدات', lambda l: l.qty, 'qty'),
                ('سعر الوحدة', lambda l: l.price_unit, 'money'),
            ], inv.total_materials, inv.notes_materials, None),
            ('ثانياً: فريق العمل', inv.labor_line_ids, [
                ('البيان', lambda l: l.product_id.display_name, 'txt'),
                ('عدد العاملين', lambda l: l.worker_days_qty, 'qty'),
                ('السعر / اليوم', lambda l: l.price_unit, 'money'),
                ('ساعات الإضافية', lambda l: l.overtime_hours, 'qty'),
                ('تكلفة الساعة', lambda l: l.overtime_rate, 'money'),
            ], inv.total_labor, inv.notes_labor, (1, inv.total_labor_qty)),
            ('ثالثاً: وسائل النقل', inv.transport_line_ids, [
                ('البيان', lambda l: l.product_id.display_name, 'txt'),
                ('عدد الأيام', lambda l: l.days_qty, 'qty'),
                ('المسافة كم', lambda l: l.distance_label or '', 'cell'),
                ('السعر', lambda l: l.price_unit, 'money'),
                ('مسافة الإضافية كم', lambda l: l.extra_distance_km, 'qty'),
                ('سعر المسافة الإضافية', lambda l: l.extra_km_price, 'money'),
                ('تكلفة الشريحة الأولى (100-300 كم)', lambda l: l.base_extra_tier_fee, 'money'),
            ], inv.total_transport, inv.notes_transport, None),
            ('رابعاً: المعدات وأدوات التشغيل', inv.equipment_line_ids, [
                ('البيان', lambda l: l.product_id.display_name, 'txt'),
                ('عدد الوحدات', lambda l: l.qty, 'qty'),
                ('الوحدة', lambda l: l.uom_id.name, 'cell'),
                ('السعر', lambda l: l.price_unit, 'money'),
            ], inv.total_equipment, inv.notes_equipment, None),
            ('خامساً: الإعاشة', inv.catering_line_ids, [
                ('البيان', lambda l: l.product_id.display_name, 'txt'),
                ('عدد الوحدات', lambda l: l.qty, 'qty'),
                ('الوحدة', lambda l: l.uom_id.name, 'cell'),
                ('السعر', lambda l: l.price_unit, 'money'),
            ], inv.total_catering, inv.notes_catering, None),
        ]

        for title, lines, cols, total, notes, qty_sum in sections:
            ws.merge_range(row, 0, row, NCOL - 1, title, F['section'])
            row += 1
            # header row: م | cols... | (blank filler) | الإجمالي
            ws.write(row, 0, 'م', F['th'])
            for i, (h, _g, _k) in enumerate(cols):
                ws.write(row, 1 + i, h, F['th'])
            for c in range(1 + len(cols), NCOL - 1):
                ws.write_blank(row, c, None, F['th'])
            ws.write(row, NCOL - 1, 'الإجمالي', F['th'])
            ws.set_row(row, 32)
            row += 1
            for n, line in enumerate(lines, 1):
                ws.write_number(row, 0, n, F['cell'])
                for i, (_h, getter, kind) in enumerate(cols):
                    val = getter(line)
                    if kind in ('qty', 'money'):
                        ws.write_number(row, 1 + i, val or 0.0, F[kind])
                    else:
                        ws.write(row, 1 + i, val or '', F[kind])
                for c in range(1 + len(cols), NCOL - 1):
                    ws.write_blank(row, c, None, F['cell'])
                ws.write_number(row, NCOL - 1, line.subtotal, F['money'])
                row += 1
            # footer
            ws.write_blank(row, 0, None, F['tot_l'])
            ws.write(row, 1, 'المجموع', F['tot_l'])
            for c in range(2, NCOL - 1):
                ws.write_blank(row, c, None, F['tot_l'])
            if qty_sum:
                ws.write_number(row, 1 + qty_sum[0], qty_sum[1], F['tot_q'])
            ws.write_number(row, NCOL - 1, total, F['tot_n'])
            row += 1
            if notes:
                ws.merge_range(row, 0, row, NCOL - 1, 'ملاحظات القسم: %s' % notes, F['note'])
                ws.set_row(row, max(18, 15 * (notes.count('\n') + 1)))
                row += 1
            row += 1

        ws.merge_range(row, 0, row, NCOL - 2, 'الاجمالى', F['grand_l'])
        ws.write_number(row, NCOL - 1, inv.grand_total, F['grand_n'])
        row += 3
        ws.merge_range(row, 5, row, NCOL - 1, inv.signatory_name or '', F['sign'])
        row += 1
        ws.merge_range(row, 5, row, NCOL - 1, inv.signatory_job_title or '', F['sign'])

        wb.close()
        return output.getvalue()
