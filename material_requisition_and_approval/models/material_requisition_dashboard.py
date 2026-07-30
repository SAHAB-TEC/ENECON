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

import json
import calendar
from datetime import timedelta, date
import logging
from markupsafe import escape
from odoo import models, fields, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class MaterialRequisitionDashboard(models.Model):
    _name = "material.requisition.dashboard"
    _description = "Material Requisition Dashboard"

    name = fields.Char("Name", required=True)
    operation_type = fields.Selection(
        [
            ("requisition_by_state", "Requisition by State"),
            ("top_requested_products", "Top Requested Products"), 
            ("requisition_by_department", "Requisition by Department"),
            ("requisition_by_request_type", "Requisition by Request Type"),
        ],
        required=True,
    )
    state_selections = fields.Selection(
        [("one", "One State"), ("more_than_one", "Many State")],
        string="State Selections",
        default="one",
    )
    state_id = fields.Many2one("material.requisition.state", string="State")
    state_ids = fields.Many2many("material.requisition.state", string="States")
    request_type_id = fields.Many2one("requisition.request.type",string="Request Type")
    graph_data = fields.Text("Graph Data", compute="_compute_graph_data")
    graph_summary_html = fields.Html(
        "Graph Summary",
        compute="_compute_graph_data",
        sanitize=False,
    )
    chart_type = fields.Selection(
        [("bar", "Bar"), ("line", "Line"), ("pie", "Pie"), ("doughnut", "Doughnut")],
        string="Default Chart Type",
        default="bar",
    )
    date_group_by = fields.Selection(
        [("day", "Day"), ("week", "Week"), ("month", "Month")],
        string="Time Grouping",
        default="day",
    )
    record_limit = fields.Integer("Visible Points", default=6)

    @api.constrains("operation_type", "state_selections", "state_id", "state_ids", "request_type", "record_limit")
    def _check_state_selections(self):
        for record in self:
            if record.operation_type == "requisition_by_state":
                if not record.state_selections:
                    raise ValidationError("Please select the state selection type")
                
                if record.state_selections == "one" and not record.state_id:
                    raise ValidationError("Please select a state for single state selection")
                    
                if record.state_selections == "more_than_one" and not record.state_ids:
                    raise ValidationError("Please select states for multiple state selection")
                    
            if record.operation_type == "requisition_by_request_type" and not record.request_type_id:
                raise ValidationError("Please select a request type")
            if record.record_limit < 1:
                raise ValidationError("Visible points must be at least 1.")
                
        
    def _get_record_limit(self):
        self.ensure_one()
        return max(self.record_limit or 6, 1)

    def _get_month_end(self, value_date):
        last_day = calendar.monthrange(value_date.year, value_date.month)[1]
        return value_date.replace(day=last_day)

    def _get_trend_values(self, domain, extra_domain=None):
        self.ensure_one()
        requisition_domain = list(domain or [])
        if extra_domain:
            requisition_domain += list(extra_domain)

        requisitions = self.env["material.requisition"].search(
            requisition_domain, order="requested_date asc"
        )
        grouped_counts = {}
        for req in requisitions:
            if not req.requested_date:
                continue

            requested_date = req.requested_date
            if self.date_group_by == "week":
                date_from = requested_date - timedelta(days=requested_date.weekday())
                date_to = date_from + timedelta(days=6)
                label = f"{date_from.strftime('%d %b')} - {date_to.strftime('%d %b')}"
            elif self.date_group_by == "month":
                date_from = requested_date.replace(day=1)
                date_to = self._get_month_end(requested_date)
                label = requested_date.strftime("%b %Y")
            else:
                date_from = requested_date
                date_to = requested_date
                label = requested_date.strftime("%d %b")

            key = (date_from, date_to, label)
            grouped_counts[key] = grouped_counts.get(key, 0) + 1

        palette = ["#2196F3", "#4CAF50", "#FF9800", "#9C27B0", "#00BCD4", "#F44336"]
        values = []
        for index, ((date_from, date_to, label), count) in enumerate(sorted(grouped_counts.items(), key=lambda item: item[0][0])):
            values.append(
                {
                    "label": label,
                    "value": count,
                    "color": palette[index % len(palette)],
                    "date_from": fields.Date.to_string(date_from),
                    "date_to": fields.Date.to_string(date_to),
                }
            )

        limit = self._get_record_limit()
        if len(values) > limit:
            values = values[-limit:]
        return values

    def _create_graph(rec, domain=[]):
        today = fields.Date.today()
        graph = []
        color_palette = [
            "#F44336",
            "#2196F3",
            "#4CAF50",
            "#FF9800",
            "#9C27B0",
            "#00BCD4",
            "#8E44AD",
            "#3498DB",
            "#E67E22",
            "#2ECC71",
            "#F1C40F",
            "#E74C3C",
            "#1ABC9C",
            "#2980B9",
            "#C0392B",
            "#F39C12",
            "#9B59B6",
            "#16A085",
        ]

        def add_values(data_map, label_key, id_key):
            values = [
                {
                    "label": data["name"],
                    "value": data["count"],
                    "color": color_palette[i % len(color_palette)],
                    id_key: item_id,
                }
                for i, (item_id, data) in enumerate(data_map.items())
            ]
            values = sorted(values, key=lambda item: item["value"], reverse=True)
            return values[: rec._get_record_limit()]

        if rec.operation_type == "requisition_by_state":
            if rec.state_selections == "one" and rec.state_id:
                req_domain = domain + [("state_id", "=", rec.state_id.id)]
                if rec.chart_type == "line":
                    values = rec._get_trend_values(req_domain)
                else:
                    requisitions = rec.env["material.requisition"].search(req_domain)
                    buckets = {"before": 0, "yesterday": 0, "today": 0}
                    for req in requisitions:
                        if not req.requested_date:
                            continue
                        delta = (today - req.requested_date).days
                        if delta > 1:
                            buckets["before"] += 1
                        elif delta == 1:
                            buckets["yesterday"] += 1
                        elif delta == 0:
                            buckets["today"] += 1

                    values = [
                        {
                            "label": "Before",
                            "type": "past",
                            "value": buckets["before"],
                            "color": "#5A9",
                        },
                        {
                            "label": "Yesterday",
                            "type": "past",
                            "value": buckets["yesterday"],
                            "color": "#F90",
                        },
                        {
                            "label": "Today",
                            "type": "present",
                            "value": buckets["today"],
                            "color": "#09F",
                        },
                    ]

                graph = [
                    {
                        "key": rec.state_id.name,
                        "state_id": rec.state_id.id,
                        "chart_type": rec.chart_type,
                        "values": values,
                    }
                ]
            elif rec.state_selections == "more_than_one" and rec.state_ids:
                values = [
                    {
                        "label": state.display_name,
                        "value": rec.env["material.requisition"].search_count(
                            [("state_id", "=", state.id)] + domain
                        ),
                        "color": color_palette[i % len(color_palette)],
                        "state_id": state.id,
                    }
                    for i, state in enumerate(rec.state_ids)
                ]
                values = sorted(values, key=lambda item: item["value"], reverse=True)[: rec._get_record_limit()]
                graph = [
                    {
                        "key": rec.name or "Requisition by State",
                        "chart_type": rec.chart_type,
                        "values": values,
                    }
                ]

        elif rec.operation_type == "top_requested_products":
            product_data = {}
            for line in rec.env["material.requisition.line"].search([] + domain):
                product = line.product_id
                if not product:
                    continue
                if product.id not in product_data:
                    product_data[product.id] = {"name": product.name, "count": 0}
                product_data[product.id]["count"] += 1

            graph = [
                {
                    "key": "Top Requested Products",
                    "chart_type": rec.chart_type,
                    "values": add_values(product_data, "name", "product_id"),
                }
            ]

        elif rec.operation_type == "requisition_by_department":
            department_data = {}
            for req in rec.env["material.requisition"].search([] + domain):
                dep = req.department_id
                if not dep:
                    continue
                if dep.id not in department_data:
                    department_data[dep.id] = {"name": dep.name, "count": 0}
                department_data[dep.id]["count"] += 1

            graph = [
                {
                    "key": "Requisition by Department",
                    "chart_type": rec.chart_type,
                    "values": add_values(department_data, "name", "department_id"),
                }
            ]
        elif  rec.operation_type == "requisition_by_request_type":
            if rec.request_type_id:
                req_domain = domain + [("request_type_id", "=", rec.request_type_id.id)]
                if rec.chart_type == "line":
                    values = rec._get_trend_values(req_domain)
                else:
                    requisitions = rec.env["material.requisition"].search(req_domain)
                    buckets = {"before": 0, "yesterday": 0, "today": 0}
                    for req in requisitions:
                        if not req.requested_date:
                            continue
                        delta = (today - req.requested_date).days
                        if delta > 1:
                            buckets["before"] += 1
                        elif delta == 1:
                            buckets["yesterday"] += 1
                        elif delta == 0:
                            buckets["today"] += 1

                    values = [
                        {
                            "label": "Before",
                            "type": "past",
                            "value": buckets["before"],
                            "color": "#5A9",
                        },
                        {
                            "label": "Yesterday",
                            "type": "past",
                            "value": buckets["yesterday"],
                            "color": "#F90",
                        },
                        {
                            "label": "Today",
                            "type": "present",
                            "value": buckets["today"],
                            "color": "#09F",
                        },
                    ]

                graph = [
                    {
                        "key": rec.request_type_id.name,
                        "request_type_id": rec.request_type_id.id,
                        "chart_type": rec.chart_type,
                        "values": values,
                    }
                ]

        return graph

    @api.depends("state_id", "state_ids", "state_selections", "operation_type", "request_type_id", "chart_type", "date_group_by", "record_limit")
    def _compute_graph_data(self):
        for rec in self:
            graph = rec._create_graph()
            rec.graph_data = json.dumps(graph)
            values = graph[0].get("values", []) if graph else []
            if values:
                rows = "".join(
                    f"""
                    <div class="mrd_fs_breakdown_row">
                        <span class="mrd_fs_breakdown_color" style="background:{escape(value.get('color') or '#2196f3')};"></span>
                        <span class="mrd_fs_breakdown_label">{escape(value.get('label') or 'Unknown')}</span>
                        <span class="mrd_fs_breakdown_value">{escape(str(value.get('value', 0)))}</span>
                    </div>
                    """
                    for value in values
                )
                rec.graph_summary_html = f"""
                    <div class="mrd_fs_breakdown">
                        {rows}
                    </div>
                """
            else:
                rec.graph_summary_html = """
                    <div class="mrd_fs_breakdown_empty">
                        No chart points available for this widget yet.
                    </div>
                """

    @api.model
    def compute_graph_data_with_dates(self, dashboard_id, start_date, end_date):
        dashboard = self.browse(dashboard_id).exists()
        if not dashboard:
            return json.dumps([])

        date_field = (
            "requisition_id.requested_date"
            if dashboard.operation_type == "top_requested_products"
            else "requested_date"
        )
        domain = []
        if start_date:
            domain.append((date_field, ">=", start_date))
        if end_date:
            domain.append((date_field, "<=", end_date))

        return json.dumps(dashboard._create_graph(domain=domain))

    @api.model
    def get_dashboard_screen_data(self):
        dashboards = self.search([], order="id")
        requisition_model = self.env["material.requisition"]
        requisition_line_model = self.env["material.requisition.line"]
        all_requisitions = requisition_model.search([])
        pending_states = [
            "submitted",
            "waiting_for_approval",
            "waiting_stock_check",
            "in_dispatch_process",
        ]

        operation_labels = {
            "requisition_by_state": "By State",
            "top_requested_products": "Top Products",
            "requisition_by_department": "By Department",
            "requisition_by_request_type": "Request Type",
        }
        operation_descriptions = {
            "requisition_by_state": "Track requisitions by workflow stage and compare movement over time.",
            "top_requested_products": "Spot high-demand items early and identify recurring pressure on stock.",
            "requisition_by_department": "Understand where demand is concentrated across business functions.",
            "requisition_by_request_type": "Monitor request categories and their recent operational rhythm.",
        }
        chart_labels = {
            "bar": "Comparative bars",
            "line": "Trend line",
            "pie": "Share of total",
            "doughnut": "Circular breakdown",
        }
        state_labels = dict(requisition_model._fields["state"].selection)

        cards = []
        for dashboard in dashboards:
            graph = dashboard._create_graph()
            series = graph[0] if graph else {}
            values = series.get("values", [])
            total_value = sum(value.get("value", 0) for value in values)
            top_value = max(values, key=lambda value: value.get("value", 0), default={})
            cards.append(
                {
                    "id": dashboard.id,
                    "name": dashboard.name,
                    "operation_type": dashboard.operation_type,
                    "operation_label": operation_labels.get(dashboard.operation_type, dashboard.operation_type),
                    "description": operation_descriptions.get(dashboard.operation_type, ""),
                    "chart_type": dashboard.chart_type,
                    "chart_label": chart_labels.get(dashboard.chart_type, dashboard.chart_type),
                    "display_limit": dashboard._get_record_limit(),
                    "graph": graph,
                    "primary_total": total_value,
                    "top_label": top_value.get("label") or "No data",
                    "top_value": top_value.get("value", 0),
                }
            )

        material_rows = []
        recent_lines = requisition_line_model.search(
            [("product_id", "!=", False), ("requisition_id", "!=", False)],
            order="id desc",
            limit=5,
        )
        for line in recent_lines:
            requisition = line.requisition_id
            status_label = (
                requisition.state_id.display_name
                or state_labels.get(requisition.state)
                or "Draft"
            )
            material_rows.append(
                {
                    "id": line.id,
                    "material": line.product_id.display_name,
                    "user": requisition.requester_id.name or requisition.employee_id.name or "",
                    "user_id": requisition.requester_id.id or 0,
                    "user_avatar": "/web/image/res.users/%d/avatar_128" % requisition.requester_id.id if requisition.requester_id else "",
                    "status": status_label,
                    "state": requisition.state or "draft",
                    "date": fields.Date.to_string(requisition.requested_date) if requisition.requested_date else "",
                    "quantity": line.quantity,
                }
            )

        return {
            "summary": {
                "total_requisitions": requisition_model.search_count([]),
                "open_requisitions": requisition_model.search_count(
                    [("state", "not in", ["fulfilled", "cancel", "rejected"])]
                ),
                "pending_approvals": requisition_model.search_count([("state", "in", pending_states)]),
                "active_departments": len(all_requisitions.mapped("department_id").ids),
            },
            "cards": cards,
            "material_rows": material_rows,
        }

    @api.model
    def get_dashboard_material_row_action(self, line_id):
        line = self.env["material.requisition.line"].browse(line_id).exists()
        if not line or not line.requisition_id:
            return False

        return {
            "type": "ir.actions.act_window",
            "name": line.requisition_id.display_name,
            "res_model": "material.requisition",
            "res_id": line.requisition_id.id,
            "view_mode": "form",
            "views": [[False, "form"]],
            "target": "current",
            "context": dict(self.env.context),
        }

    @api.model
    def get_dashboard_graph_action(self, dashboard_id):
        dashboard = self.browse(dashboard_id).exists()
        if not dashboard:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": "Dashboard Graph View",
            "res_model": "material.requisition.dashboard",
            "res_id": dashboard.id,
            "view_mode": "form",
            "views": [
                (
                    self.env.ref(
                        "material_requisition_and_approval.view_material_requisition_dashboard_graph_form"
                    ).id,
                    "form",
                )
            ],
            "target": "current",
            "context": dict(self.env.context),
        }

    @api.model
    def get_dashboard_point_action(self, dashboard_id, value_index):
        dashboard = self.browse(dashboard_id).exists()
        if not dashboard:
            return False

        graph = dashboard._create_graph()
        if not graph:
            return False
        series = graph[0]
        values = series.get("values", [])
        if value_index is None or value_index < 0 or value_index >= len(values):
            return False
        clicked_value = values[value_index]

        if series.get("state_id"):
            action = self.env["material.requisition"]._get_action(
                "material_requisition_and_approval.action_material_requisition_graph"
            )
            action["context"] = {
                **self.env.context,
                "state_id": series["state_id"],
                "search_default_state_id": [series["state_id"]],
            }
            if clicked_value.get("date_from") and clicked_value.get("date_to"):
                action["domain"] = [
                    ("requested_date", ">=", clicked_value["date_from"]),
                    ("requested_date", "<=", clicked_value["date_to"]),
                ]
            else:
                date_category = ["before", "yesterday", "today"][value_index] if value_index < 3 else False
                if date_category:
                    action["context"][f"search_default_{date_category}"] = True
                    filters = {
                        "before": ("requested_date", "<", fields.Date.today() - timedelta(days=1)),
                        "yesterday": ("requested_date", "=", fields.Date.today() - timedelta(days=1)),
                        "today": ("requested_date", "=", fields.Date.today()),
                    }
                    action["domain"] = [filters[date_category]]
            return action

        if series.get("request_type_id"):
            action = self.env["material.requisition"]._get_action(
                "material_requisition_and_approval.action_material_requisition_graph"
            )
            action["context"] = {
                **self.env.context,
                "request_type_id": series["request_type_id"],
                "search_default_request_type_id": [series["request_type_id"]],
            }
            if clicked_value.get("date_from") and clicked_value.get("date_to"):
                action["domain"] = [
                    ("requested_date", ">=", clicked_value["date_from"]),
                    ("requested_date", "<=", clicked_value["date_to"]),
                ]
            else:
                date_category = ["before", "yesterday", "today"][value_index] if value_index < 3 else False
                if date_category:
                    action["context"][f"search_default_{date_category}"] = True
                    filters = {
                        "before": ("requested_date", "<", fields.Date.today() - timedelta(days=1)),
                        "yesterday": ("requested_date", "=", fields.Date.today() - timedelta(days=1)),
                        "today": ("requested_date", "=", fields.Date.today()),
                    }
                    action["domain"] = [filters[date_category]]
            return action

        if clicked_value.get("state_id"):
            state_id = clicked_value["state_id"]
            action = self.env["material.requisition"]._get_action(
                "material_requisition_and_approval.action_material_requisition_graph"
            )
            action["context"] = {
                **self.env.context,
                "search_default_state_id": [state_id],
            }
            action["domain"] = [("state_id", "=", state_id)]
            return action

        if clicked_value.get("product_id"):
            action = self.env["material.requisition.line"]._get_action(
                "material_requisition_and_approval.action_material_requisition_summary_dashboard"
            )
            action["context"] = {
                **self.env.context,
                "search_default_product_id": [clicked_value["product_id"]],
            }
            action["domain"] = [("product_id", "=", clicked_value["product_id"])]
            return action

        if clicked_value.get("department_id"):
            action = self.env["material.requisition"]._get_action(
                "material_requisition_and_approval.action_material_requisition_graph"
            )
            action["context"] = {
                **self.env.context,
                "search_default_department_id": clicked_value["department_id"],
            }
            action["domain"] = [("department_id", "=", clicked_value["department_id"])]
            return action

        return False

    @api.model
    def web_search_read(
        self, domain, specification, offset=0, limit=None, order=None, count_limit=None
    ):
        _logger.info(f"@ filter domain is {domain} @")

        # Extract create_date conditions and build proper filtered domain
        create_date_domain = []
        write_date_domain = []
        non_create_date_conditions = []
        state_by_domain = []
        request_type_id_by_domain = []

        create_by_domain = []
        write_by_domain = []

        if domain:
            for item in domain:
                if (
                    isinstance(item, list)
                    and len(item) == 3
                    and item[0] == "create_date"
                ):
                    create_date_domain.append(item)
                elif (
                    isinstance(item, list)
                    and len(item) == 3
                    and item[0] == "create_uid"
                ):
                    create_by_domain.append(item)
                elif (
                    isinstance(item, list)
                    and len(item) == 3
                    and item[0] == "write_uid"
                ):
                    write_by_domain.append(item)
                elif (
                    isinstance(item, list)
                    and len(item) == 3
                    and item[0] == "write_date"
                ):
                    write_date_domain.append(item)
                elif (
                    isinstance(item, list)
                    and len(item) == 3
                    and item[0] == "state_id"
                ):
                    state_by_domain.append(item)
                elif (
                    isinstance(item, list)
                    and len(item) == 3
                    and item[0] == "request_type_id"
                ):
                    request_type_id_by_domain.append(item)
                elif item not in ["&", "|", "!"]:
                    non_create_date_conditions.append(item)

        # Build proper filtered domain - avoid orphaned logical operators
        filtered_domain = non_create_date_conditions

        _logger.info(
            f"@ filtered domain is {filtered_domain}, create_date_domain is {create_date_domain} @"
        )

        # Use the filtered domain for the actual search
        result = super().web_search_read(
            filtered_domain,
            specification,
            offset=offset,
            limit=limit,
            order=order,
            count_limit=count_limit,
        )

        # Apply date filtering to the graph data
        if create_date_domain:
            for record_dict in result.get("records", []):
                try:
                    dashboard_record = self.env[
                        "material.requisition.dashboard"
                    ].browse(record_dict.get("id"))

                    # Convert create_date conditions to requested_date conditions
                    requested_date_domain = []
                    for cond in create_date_domain:
                        if (
                            isinstance(cond, list)
                            and len(cond) == 3
                            and cond[0] == "create_date"
                        ):
                            if (
                                dashboard_record.operation_type
                                == "top_requested_products"
                            ):
                                requested_date_domain.append(
                                    ["requisition_id.requested_date", cond[1], cond[2]]
                                )
                            else:
                                requested_date_domain.append(
                                    ["requested_date", cond[1], cond[2]]
                                )

                    # Recompute graph data with the date filter
                    updated_graph_data = dashboard_record._create_graph(
                        domain=requested_date_domain
                    )
                    record_dict["graph_data"] = json.dumps(updated_graph_data)
                except Exception as e:
                    _logger.warning(
                        f"Failed to update graph_data for record {record_dict.get('id')}: {e}"
                    )
        
        # Apply date filtering to the graph data
        if create_by_domain:
            for record_dict in result.get("records", []):
                try:
                    dashboard_record = self.env[
                        "material.requisition.dashboard"
                    ].browse(record_dict.get("id"))

                 
                    requested_date_domain = []
                    for cond in create_by_domain:
                        if (
                            isinstance(cond, list)
                            and len(cond) == 3
                            and cond[0] == "create_uid"
                        ):
                            if (
                                dashboard_record.operation_type
                                == "top_requested_products"
                            ):
                                requested_date_domain.append(
                                    ["requisition_id.requester_id", cond[1], cond[2]]
                                )
                            else:
                                requested_date_domain.append(
                                    ["requester_id", cond[1], cond[2]]
                                )

                    updated_graph_data = dashboard_record._create_graph(
                        domain=requested_date_domain
                    )
                    record_dict["graph_data"] = json.dumps(updated_graph_data)
                except Exception as e:
                    _logger.warning(
                        f"Failed to update graph_data for record {record_dict.get('id')}: {e}"
                    )
        if write_by_domain:
            for record_dict in result.get("records", []):
                try:
                    dashboard_record = self.env[
                        "material.requisition.dashboard"
                    ].browse(record_dict.get("id"))

                 
                    requested_date_domain = []
                    for cond in write_by_domain:
                        if (
                            isinstance(cond, list)
                            and len(cond) == 3
                            and cond[0] == "write_uid"
                        ):
                            if (
                                dashboard_record.operation_type
                                == "top_requested_products"
                            ):
                                requested_date_domain.append(
                                    ["write_uid", cond[1], cond[2]],
                                )
                            else:
                                requested_date_domain.append(
                                    ["write_uid", cond[1], cond[2]]
                                )

                    updated_graph_data = dashboard_record._create_graph(
                        domain=requested_date_domain
                    )
                    record_dict["graph_data"] = json.dumps(updated_graph_data)
                except Exception as e:
                    _logger.warning(
                        f"Failed to update graph_data for record {record_dict.get('id')}: {e}"
                    )

        if write_date_domain:
            for record_dict in result.get("records", []):
                try:
                    dashboard_record = self.env[
                        "material.requisition.dashboard"
                    ].browse(record_dict.get("id"))

                 
                    requested_date_domain = []
                    for cond in write_date_domain:
                        if (
                            isinstance(cond, list)
                            and len(cond) == 3
                            and cond[0] == "write_date"
                        ):
                            if (
                                dashboard_record.operation_type
                                == "top_requested_products"
                            ):
                                requested_date_domain.append(
                                    ["write_date", cond[1], cond[2]],
                                )
                            else:
                                requested_date_domain.append(
                                    ["write_date", cond[1], cond[2]]
                                )

                    updated_graph_data = dashboard_record._create_graph(
                        domain=requested_date_domain
                    )
                    record_dict["graph_data"] = json.dumps(updated_graph_data)
                except Exception as e:
                    _logger.warning(
                        f"Failed to update graph_data for record {record_dict.get('id')}: {e}"
                    )

        
        if state_by_domain:
            for record_dict in result.get("records", []):
                try:
                    dashboard_record = self.env[
                        "material.requisition.dashboard"
                    ].browse(record_dict.get("id"))

                 
                    requested_date_domain = []
                    for cond in state_by_domain:
                        if (
                            isinstance(cond, list)
                            and len(cond) == 3
                            and cond[0] == "state_id"
                        ):
                            if (
                                dashboard_record.operation_type
                                == "top_requested_products"
                            ):
                                requested_date_domain.append(
                                    ["state_id", cond[1], cond[2]],
                                )
                            else:
                                requested_date_domain.append(
                                    ["state_id", cond[1], cond[2]]
                                )

                    updated_graph_data = dashboard_record._create_graph(
                        domain=requested_date_domain
                    )
                    record_dict["graph_data"] = json.dumps(updated_graph_data)
                except Exception as e:
                    _logger.warning(
                        f"Failed to update graph_data for record {record_dict.get('id')}: {e}"
                    )

        if request_type_id_by_domain:
            for record_dict in result.get("records", []):
                try:
                    dashboard_record = self.env[
                        "material.requisition.dashboard"
                    ].browse(record_dict.get("id"))

                
                    requested_date_domain = []
                    for cond in request_type_id_by_domain:
                        if (
                            isinstance(cond, list)
                            and len(cond) == 3
                            and cond[0] == "request_type_id"
                        ):
                            if (
                                dashboard_record.operation_type
                                == "top_requested_products"
                            ):
                                requested_date_domain.append(
                                    ["request_type_id", cond[1], cond[2]],
                                )
                            else:
                                requested_date_domain.append(
                                    ["request_type_id", cond[1], cond[2]]
                                )

                    updated_graph_data = dashboard_record._create_graph(
                        domain=requested_date_domain
                    )
                    record_dict["graph_data"] = json.dumps(updated_graph_data)
                except Exception as e:
                    _logger.warning(
                        f"Failed to update graph_data for record {record_dict.get('id')}: {e}"
                    )


        return result

    @api.model
    def web_read_group(self, domain, fields, groupby, limit=None, offset=0, orderby=False, lazy=True):
        if groupby:
            new_groupby = []
            for group in groupby:
                if group == "state_id": 
                    new_groupby.append("state_id")
                elif group == "create_date":
                    new_groupby.append("create_date")
                elif group == "write_date":
                    new_groupby.append("write_date")
                if group == "request_type_id":
                    new_groupby.append("request_type_id")
                else:
                    new_groupby.append(group)
            

        try:
            groups = self.env['material.requisition'].read_group(
                domain, fields, new_groupby,
                limit=limit, offset=offset,
                orderby=orderby, lazy=lazy
            )

            if not groups:
                length = 0
            elif limit and len(groups) == limit:
                length = limit + self.env['material.requisition'].search_count(domain)
            else:
                length = len(groups) + offset
            

            return {
                'groups': groups or [], # Ensure groups is always iterable
                'length': length
            }
            
        except Exception as e:
            groups = self.read_group(
                domain, fields, groupby,
                limit=limit, offset=offset,
                orderby=orderby, lazy=lazy
            )
            if not groups:
                length = 0
            elif limit and len(groups) == limit:
                length = limit + self.search_count(domain)
            else:
                length = len(groups) + offset
            
            return {
                'groups': groups,
                'length': 0
            }    
    
    @api.model
    def custom_filtered_records(self, period):
        today = date.today()
        domain = []

        if period == "today":
            domain = [("create_date", ">=", today.strftime("%Y-%m-%d 00:00:00"))]
        elif period == "last_7":
            domain = [
                (
                    "create_date",
                    ">=",
                    (today - timedelta(days=7)).strftime("%Y-%m-%d 00:00:00"),
                )
            ]
        elif period == "this_month":
            first_day = today.replace(day=1)
            domain = [("create_date", ">=", first_day.strftime("%Y-%m-%d 00:00:00"))]

        return {"domain": domain}

    def action_open_dashboard_form(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "material.requisition.dashboard",
            "res_id": self.id,
            "view_mode": "form",
            "view_id": self.env.ref(
                "material_requisition_and_approval.view_material_requisition_dashboard_graph_form"
            ).id,
            "target": "current",
        }

    def action_open_requisitions(self):
        return {
            "name": f"Requisitions - {self.state_id.name}",
            "type": "ir.actions.act_window",
            "res_model": "material.requisition",
            "view_mode": "list,form",
            "domain": [("state_id", "=", self.state_id.id)],
            "target": "current",
        }
