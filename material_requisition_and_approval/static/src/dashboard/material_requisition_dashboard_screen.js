/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState, useRef, onMounted } from "@odoo/owl";

class MaterialRequisitionDashboardScreen extends Component {
    static template = "material_requisition_and_approval.MaterialRequisitionDashboardScreen";

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.showTooltip = this.showTooltip.bind(this);
        this.moveTooltip = this.moveTooltip.bind(this);
        this.hideTooltip = this.hideTooltip.bind(this);
        this.getTooltipStyle = this.getTooltipStyle.bind(this);
        this.openPoint = this.openPoint.bind(this);
        this.openCard = this.openCard.bind(this);
        this.openMaterialRow = this.openMaterialRow.bind(this);
        this.openNewRequisition = this.openNewRequisition.bind(this);
        this.openSetup = this.openSetup.bind(this);
        this.openRequests = this.openRequests.bind(this);
        this.setCardChartType = this.setCardChartType.bind(this);
        this.state = useState({
            loading: true,
            summary: {},
            summaryDisplay: { total_requisitions: 0, open_requisitions: 0, pending_approvals: 0, active_departments: 0 },
            cards: [],
            materialRows: [],
            chartTypes: {},
            tooltip: {
                visible: false,
                text: "",
                x: 0,
                y: 0,
            },
        });

        onWillStart(async () => {
            await this.loadDashboard();
        });
    }

    async loadDashboard() {
        this.state.loading = true;
        const payload = await this.orm.call(
            "material.requisition.dashboard",
            "get_dashboard_screen_data",
            []
        );
        this.state.summary = payload.summary || {};
        this.state.cards = payload.cards || [];
        this.state.materialRows = payload.material_rows || [];
        this.state.loading = false;
        this._animateSummary();
    }

    _animateSummary() {
        const keys = ["total_requisitions", "open_requisitions", "pending_approvals", "active_departments"];
        const duration = 1500;
        const start = performance.now();
        const targets = {};
        for (const key of keys) {
            targets[key] = this.state.summary[key] || 0;
        }
        const tick = (now) => {
            const elapsed = now - start;
            const progress = Math.min(elapsed / duration, 1);
            const ease = 1 - Math.pow(1 - progress, 3);
            for (const key of keys) {
                this.state.summaryDisplay[key] = Math.round(targets[key] * ease);
            }
            if (progress < 1) {
                requestAnimationFrame(tick);
            }
        };
        requestAnimationFrame(tick);
    }

    getChartValues(card) {
        const values = card?.graph?.[0]?.values;
        if (!Array.isArray(values)) {
            return [];
        }
        const limit = card?.display_limit || 6;
        const points = values.map((point, index) => ({ ...point, index }));
        if (this.getChartKind(card) === "line") {
            return points.slice(0, limit);
        }
        return [...points]
            .sort((left, right) => (right.value || 0) - (left.value || 0))
            .slice(0, limit);
    }

    hasMoreValues(card) {
        const values = card?.graph?.[0]?.values;
        return Array.isArray(values) && values.length > (card?.display_limit || 6);
    }

    getMaxValue(card) {
        const values = this.getChartValues(card);
        return Math.max(...values.map((value) => value.value || 0), 1);
    }

    getBarHeight(value, maxValue) {
        const safeMax = maxValue || 1;
        const height = Math.max((value / safeMax) * 100, value ? 14 : 6);
        return `height:${Math.min(height, 100)}%`;
    }

    getChartKind(card) {
        return this.state.chartTypes[card?.id] || card?.chart_type || "bar";
    }

    getChartTypeOptions(card) {
        return [
            { type: "bar", label: "Bar" },
            { type: "line", label: "Line" },
            { type: "pie", label: "Pie" },
            { type: "doughnut", label: "Doughnut" },
            { type: "table", label: "Table" },
        ];
    }

    getChartButtonClass(card, chartType) {
        const activeClass = this.getChartKind(card) === chartType ? " mrdc_chart_type_btn_active" : "";
        return `mrdc_chart_type_btn${activeClass}`;
    }

    setCardChartType(card, chartType) {
        this.state.chartTypes[card.id] = chartType;
    }

    getCardPreview(card) {
        const topText = card?.top_label && card.top_label !== "No data"
            ? `${card.top_label} ${card.top_value || 0}`
            : "No data";
        return `${card?.primary_total || 0} · ${topText}`;
    }

    getChartSubtitle(card) {
        if (card?.description) {
            return card.description;
        }
        return "Distribution across material requisitions";
    }

    getSummaryItems() {
        return [
            {
                key: "total",
                label: "Total Requisitions",
                value: this.state.summaryDisplay.total_requisitions,
                icon: "fa-list-alt",
            },
            {
                key: "open",
                label: "Open Requisitions",
                value: this.state.summaryDisplay.open_requisitions,
                icon: "fa-clock-o",
            },
            {
                key: "pending",
                label: "Pending Approvals",
                value: this.state.summaryDisplay.pending_approvals,
                icon: "fa-check-square-o",
            },
            {
                key: "departments",
                label: "Active Departments",
                value: this.state.summaryDisplay.active_departments,
                icon: "fa-building-o",
            },
        ];
    }

    getShortLabel(label) {
        const value = label || "No data";
        return value.length > 14 ? `${value.slice(0, 13)}...` : value;
    }

    formatDate(value) {
        if (!value) {
            return "";
        }
        const date = new Date(`${value}T00:00:00`);
        if (Number.isNaN(date.getTime())) {
            return value;
        }
        return date.toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
            year: "numeric",
        });
    }

    getStatusClass(row) {
        const state = row?.state || "";
        if (["fulfilled"].includes(state)) {
            return "mrdc_status mrdc_status_success";
        }
        if (["rejected", "cancel"].includes(state)) {
            return "mrdc_status mrdc_status_error";
        }
        if (["submitted", "waiting_for_approval", "waiting_stock_check"].includes(state)) {
            return "mrdc_status mrdc_status_pending";
        }
        if (["in_dispatch_process"].includes(state)) {
            return "mrdc_status mrdc_status_progress";
        }
        return "mrdc_status";
    }

    getLinePoints(card) {
        const values = this.getChartValues(card);
        if (!values.length) {
            return [];
        }
        const maxValue = Math.max(...values.map((point) => point.value || 0), 1);
        const width = 320;
        const height = 180;
        const paddingX = 26;
        const paddingY = 24;
        const usableWidth = width - paddingX * 2;
        const usableHeight = height - paddingY * 2;

        return values.map((point, index) => {
            const x = values.length === 1
                ? width / 2
                : paddingX + (usableWidth * index) / (values.length - 1);
            const y = height - paddingY - (((point.value || 0) / maxValue) * usableHeight);
            return { ...point, x, y };
        });
    }

    getLinePathLength(card) {
        const points = this.getLinePoints(card);
        if (points.length < 2) return 1000;
        let length = 0;
        for (let i = 1; i < points.length; i++) {
            const dx = points[i].x - points[i - 1].x;
            const dy = points[i].y - points[i - 1].y;
            length += Math.hypot(dx, dy);
        }
        return Math.ceil(length * 1.1);
    }

    getLinePath(card) {
        const points = this.getLinePoints(card);
        if (!points.length) {
            return "";
        }
        if (points.length === 1) {
            return `M ${points[0].x} ${points[0].y}`;
        }
        if (points.length === 2) {
            return `M ${points[0].x} ${points[0].y} L ${points[1].x} ${points[1].y}`;
        }

        const controlPoint = (current, previous, next, reverse = false) => {
            const smoothing = 0.2;
            const start = previous || current;
            const end = next || current;
            const angle = Math.atan2(end.y - start.y, end.x - start.x) + (reverse ? Math.PI : 0);
            const length = Math.hypot(end.x - start.x, end.y - start.y) * smoothing;
            return {
                x: current.x + Math.cos(angle) * length,
                y: current.y + Math.sin(angle) * length,
            };
        };

        return points.reduce((path, point, index) => {
            if (index === 0) {
                return `M ${point.x} ${point.y}`;
            }
            const previous = points[index - 1];
            const previousPrevious = points[index - 2];
            const next = points[index + 1];
            const startControl = controlPoint(previous, previousPrevious, point);
            const endControl = controlPoint(point, previous, next, true);
            return `${path} C ${startControl.x} ${startControl.y}, ${endControl.x} ${endControl.y}, ${point.x} ${point.y}`;
        }, "");
    }

    getRingCenterValue(card) {
        if (this.getChartKind(card) === "doughnut") {
            return card.primary_total || 0;
        }
        return card.top_value || 0;
    }

    getCardClass(card) {
        return `mrdc_card mrdc_card_${card.operation_type || "generic"}`;
    }

    getPointTooltip(point) {
        return `${point.label}: ${point.value}`;
    }

    showTooltip(ev, point) {
        this.state.tooltip.visible = true;
        this.state.tooltip.text = this.getPointTooltip(point);
        this.state.tooltip.x = ev.clientX;
        this.state.tooltip.y = ev.clientY;
    }

    moveTooltip(ev) {
        if (!this.state.tooltip.visible) {
            return;
        }
        this.state.tooltip.x = ev.clientX;
        this.state.tooltip.y = ev.clientY;
    }

    hideTooltip() {
        this.state.tooltip.visible = false;
    }

    getTooltipStyle() {
        return `left:${this.state.tooltip.x + 14}px; top:${this.state.tooltip.y - 12}px;`;
    }

    polarToCartesian(centerX, centerY, radius, angleInDegrees) {
        const angleInRadians = ((angleInDegrees - 90) * Math.PI) / 180.0;
        return {
            x: centerX + radius * Math.cos(angleInRadians),
            y: centerY + radius * Math.sin(angleInRadians),
        };
    }

    describePieSlice(centerX, centerY, radius, startAngle, endAngle) {
        const start = this.polarToCartesian(centerX, centerY, radius, endAngle);
        const end = this.polarToCartesian(centerX, centerY, radius, startAngle);
        const largeArcFlag = endAngle - startAngle <= 180 ? "0" : "1";
        return [
            `M ${centerX} ${centerY}`,
            `L ${start.x} ${start.y}`,
            `A ${radius} ${radius} 0 ${largeArcFlag} 0 ${end.x} ${end.y}`,
            "Z",
        ].join(" ");
    }

    describeDonutSlice(centerX, centerY, outerRadius, innerRadius, startAngle, endAngle) {
        const startOuter = this.polarToCartesian(centerX, centerY, outerRadius, endAngle);
        const endOuter = this.polarToCartesian(centerX, centerY, outerRadius, startAngle);
        const startInner = this.polarToCartesian(centerX, centerY, innerRadius, endAngle);
        const endInner = this.polarToCartesian(centerX, centerY, innerRadius, startAngle);
        const largeArcFlag = endAngle - startAngle <= 180 ? "0" : "1";
        return [
            `M ${startOuter.x} ${startOuter.y}`,
            `A ${outerRadius} ${outerRadius} 0 ${largeArcFlag} 0 ${endOuter.x} ${endOuter.y}`,
            `L ${endInner.x} ${endInner.y}`,
            `A ${innerRadius} ${innerRadius} 0 ${largeArcFlag} 1 ${startInner.x} ${startInner.y}`,
            "Z",
        ].join(" ");
    }

    describeFullPie(centerX, centerY, radius) {
        return [
            `M ${centerX} ${centerY - radius}`,
            `A ${radius} ${radius} 0 1 0 ${centerX} ${centerY + radius}`,
            `A ${radius} ${radius} 0 1 0 ${centerX} ${centerY - radius}`,
            "Z",
        ].join(" ");
    }

    describeFullDonut(centerX, centerY, outerRadius, innerRadius) {
        return [
            `M ${centerX} ${centerY - outerRadius}`,
            `A ${outerRadius} ${outerRadius} 0 1 0 ${centerX} ${centerY + outerRadius}`,
            `A ${outerRadius} ${outerRadius} 0 1 0 ${centerX} ${centerY - outerRadius}`,
            `M ${centerX} ${centerY - innerRadius}`,
            `A ${innerRadius} ${innerRadius} 0 1 1 ${centerX} ${centerY + innerRadius}`,
            `A ${innerRadius} ${innerRadius} 0 1 1 ${centerX} ${centerY - innerRadius}`,
            "Z",
        ].join(" ");
    }

    getChartSegments(card) {
        const values = this.getChartValues(card);
        const total = values.reduce((sum, value) => sum + (value.value || 0), 0);
        if (!total) {
            return [];
        }

        const isDoughnut = this.getChartKind(card) === "doughnut";
        const center = 100;
        const outerRadius = 78;
        const innerRadius = isDoughnut ? 46 : 0;
        let currentAngle = 0;

        return values.map((point, index) => {
            const angle = ((point.value || 0) / total) * 360;
            const startAngle = currentAngle;
            const endAngle = currentAngle + angle;
            const labelAngle = startAngle + angle / 2;
            const labelRadius = isDoughnut ? (outerRadius + innerRadius) / 2 : outerRadius * 0.58;
            const labelPoint = this.polarToCartesian(center, center, labelRadius, labelAngle);
            currentAngle = endAngle;

            const isFullCircle = angle >= 359.999;
            const path = isFullCircle
                ? (
                    isDoughnut
                        ? this.describeFullDonut(center, center, outerRadius, innerRadius)
                        : this.describeFullPie(center, center, outerRadius)
                )
                : (
                    isDoughnut
                        ? this.describeDonutSlice(center, center, outerRadius, innerRadius, startAngle, endAngle)
                        : this.describePieSlice(center, center, outerRadius, startAngle, endAngle)
                );

            return {
                ...point,
                labelX: labelPoint.x,
                labelY: labelPoint.y,
                path,
            };
        });
    }

    async openPoint(card, valueIndex) {
        const action = await this.orm.call(
            "material.requisition.dashboard",
            "get_dashboard_point_action",
            [card.id, valueIndex]
        );
        if (action) {
            await this.actionService.doAction(action);
        }
    }

    async openCard(card) {
        const action = await this.orm.call(
            "material.requisition.dashboard",
            "get_dashboard_graph_action",
            [card.id]
        );
        if (action) {
            await this.actionService.doAction(action);
        }
    }

    async openMaterialRow(row) {
        const action = await this.orm.call(
            "material.requisition.dashboard",
            "get_dashboard_material_row_action",
            [row.id]
        );
        if (action) {
            await this.actionService.doAction(action);
        }
    }

    async openNewRequisition() {
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "New Requisition",
            res_model: "material.requisition",
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
            context: {},
        });
    }

    async openSetup() {
        await this.actionService.doAction("material_requisition_and_approval.action_material_requisition_dashboard_edit");
    }

    async openRequests() {
        await this.actionService.doAction("material_requisition_and_approval.action_my_requests");
    }
}

registry.category("actions").add(
    "material_requisition_dashboard_screen",
    MaterialRequisitionDashboardScreen
);
