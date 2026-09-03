/** @odoo-module **/
/* Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>) */
/* See LICENSE file for full copyright and licensing details. */
/* License URL : <https://store.webkul.com/license.html/> */


import { cookie } from "@web/core/browser/cookie";
import { getCustomColor } from "@web/core/colors/colors";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { onMounted, onPatched, onWillUnmount } from "@odoo/owl";

import { JournalDashboardGraphField } from "@web/views/fields/journal_dashboard_graph/journal_dashboard_graph_field";


export class StateTypeDashboardGraphField extends JournalDashboardGraphField {

    static props = {
        ...JournalDashboardGraphField.props,
        hideAxes: { type: Boolean, optional: true },
        showTooltip: { type: Boolean, optional: true },
        showLegend: { type: Boolean, optional: true },
        readonly: { type: Boolean, optional: true },
    };

    setup() {
        super.setup();
        this.actionService = useService("action");
        this.orm = useService("orm");
        this.resizeObserver = null;
        this.dateRangeHandler = null;

        onMounted(() => {
            const host = this.__owl__?.bdom?.el || this.el || null;
            const root = host?.closest?.(".mrd_fullscreen_form") || document;
            const startInput = root.querySelector?.(".mrd_fs_date_input_start");
            const endInput = root.querySelector?.(".mrd_fs_date_input_end");
            const resId = this.props.record?._config?.resId;

            if (startInput && endInput && resId) {
                const handleChange = async () => {
                    const start = startInput?.value;
                    const end = endInput?.value;

                    if (start && end && resId) {
                        try {
                            const result = await this.orm.call(
                                "material.requisition.dashboard",
                                "compute_graph_data_with_dates",
                                [parseInt(resId, 10), start, end]
                            );
                            this.data = JSON.parse(result);
                            this.render(true);
                            this.scheduleHeightSync();
                        } catch (error) {
                            console.error("Error:", error);
                        }
                    }
                };
                this.dateRangeHandler = handleChange;

                startInput.addEventListener("change", handleChange);
                endInput.addEventListener("change", handleChange);
            }

            this.widenDialogIfNeeded();
            this.observeChartContainer();
            this.scheduleHeightSync();
        });

        onPatched(() => {
            this.widenDialogIfNeeded();
            this.observeChartContainer();
            this.scheduleHeightSync();
        });

        onWillUnmount(() => {
            const host = this.__owl__?.bdom?.el || this.el || null;
            const root = host?.closest?.(".mrd_fullscreen_form") || document;
            const startInput = root.querySelector?.(".mrd_fs_date_input_start");
            const endInput = root.querySelector?.(".mrd_fs_date_input_end");
            if (this.dateRangeHandler) {
                startInput?.removeEventListener("change", this.dateRangeHandler);
                endInput?.removeEventListener("change", this.dateRangeHandler);
            }
            this.resizeObserver?.disconnect();
            this.resizeObserver = null;
        });

    }

    getHostElement() {
        return this.__owl__?.bdom?.el || this.el || null;
    }

    getChartElements() {
        const host = this.getHostElement();
        const fullscreenShell = host?.closest?.(".mrd_fs_chart_shell") || null;
        const cardShell = host?.closest?.(".mrd_card_chart") || null;
        const shell = fullscreenShell || cardShell || host;
        const graph = host?.querySelector?.(".o_dashboard_graph") || shell?.querySelector?.(".o_dashboard_graph") || null;
        const canvas = host?.querySelector?.("canvas") || shell?.querySelector?.("canvas") || null;
        const widget = host?.closest?.(".o_field_widget") || null;

        return { fullscreenShell, cardShell, shell, graph, canvas, widget };
    }

    widenDialogIfNeeded() {
        const host = this.getHostElement();
        const dialog = host?.closest?.(".modal-dialog") || null;
        const content = host?.closest?.(".modal-content") || null;
        if (!dialog) {
            return;
        }

        dialog.style.width = "min(96vw, 1680px)";
        dialog.style.maxWidth = "min(96vw, 1680px)";

        if (content) {
            content.style.minHeight = "80vh";
        }
    }

    getTargetHeight() {
        const { fullscreenShell, cardShell, shell } = this.getChartElements();
        if (fullscreenShell) {
            const measuredHeight = fullscreenShell.clientHeight || shell?.clientHeight || 0;
            return Math.max(480, Math.min(measuredHeight || Math.round(window.innerHeight * 0.62), 720));
        }
        if (cardShell) {
            return Math.max(220, Math.min(cardShell.clientHeight || 220, 320));
        }
        return 320;
    }

    syncCanvasHeight() {
        const { shell, graph, canvas, widget } = this.getChartElements();
        if (!shell || !canvas) {
            return;
        }

        const targetHeight = this.getTargetHeight();
        shell.style.minHeight = `${targetHeight}px`;
        shell.style.height = `${targetHeight}px`;
        shell.style.maxHeight = `${targetHeight}px`;
        if (widget) {
            widget.style.height = "100%";
            widget.style.minHeight = "0";
        }
        if (graph) {
            graph.style.height = `${targetHeight}px`;
            graph.style.maxHeight = `${targetHeight}px`;
            graph.style.minHeight = `${targetHeight}px`;
            graph.style.overflow = "hidden";
        }

        canvas.style.height = `${targetHeight}px`;
        canvas.style.maxHeight = `${targetHeight}px`;
        canvas.style.minHeight = `${targetHeight}px`;
        canvas.style.width = "100%";
    }

    scheduleHeightSync() {
        requestAnimationFrame(() => {
            this.syncCanvasHeight();
            if (this.chart?.resize) {
                this.chart.resize();
            }
        });
    }

    observeChartContainer() {
        const { shell } = this.getChartElements();
        if (!shell || typeof ResizeObserver === "undefined") {
            return;
        }
        if (this.resizeObserver) {
            this.resizeObserver.disconnect();
        }
        this.resizeObserver = new ResizeObserver(() => {
            this.scheduleHeightSync();
        });
        this.resizeObserver.observe(shell);
    }


    getBarChartConfig() {
        const series = this.data?.[0];
        const values = Array.isArray(series?.values) ? series.values : [];
        if (!series) {
            return {
                type: "doughnut",
                data: { labels: [], datasets: [] },
                options: {},
            };
        }

        const chartType = series.chart_type || "bar";
        const data = [];
        const labels = [];
        const backgroundColor = [];

        values.forEach((pt) => {
            labels.push(pt.label);
            data.push(pt.value);

            if (pt.color) {
                backgroundColor.push(pt.color);
            }
            else {
                backgroundColor.push(getCustomColor(cookie.get("color_scheme"), "#cccccc", "#3C3E4B"));
            }
        });

        return {
            type: chartType,
            data: {
                labels,
                datasets: [
                    {
                        label: series.key,
                        data,
                        backgroundColor: chartType === "line" ? backgroundColor.map((color) => `${color}33`) : backgroundColor,
                        borderColor: chartType === "line" ? backgroundColor : undefined,
                        pointBackgroundColor: chartType === "line" ? backgroundColor : undefined,
                        pointBorderColor: chartType === "line" ? "#ffffff" : undefined,
                        pointBorderWidth: chartType === "line" ? 2 : undefined,
                        pointRadius: chartType === "line" ? 4 : undefined,
                        pointHoverRadius: chartType === "line" ? 5 : undefined,
                        borderWidth: chartType === "line" ? 3 : 1,
                        fill: false,
                        hoverOffset: chartType === "pie" || chartType === "doughnut" ? 0 : undefined,
                    },
                ],
            },
            options: {
                animation: false,
                plugins: {
                    legend: { display: this.props.showLegend },
                    tooltip: {
                        intersect: false,
                        position: "nearest",
                        caretSize: 0,
                        enabled: this.props.showTooltip,
                    },
                },
                scales: {
                    x: { display: !this.props.hideAxes },
                    y: { display: !this.props.hideAxes },
                },
                maintainAspectRatio: false,
                elements: {
                    line: { tension: 0.000001 },
                    arc: {
                        hoverOffset: 0,
                        offset: 0,
                    },
                },


                state_id: series.state_id,
                state_ids: Array.isArray(series.state_ids) ? series.state_ids : [],
                request_type_id: series.request_type_id,
                key: series.key,


                onClick: async (e) => {
                    const chart = e.chart;
                    const valueIndex = chart.tooltip?.dataPoints?.[0]?.dataIndex;
                    const dashboardId = this.props.record?._config?.resId;
                    if (dashboardId === undefined || valueIndex === undefined) {
                        return;
                    }
                    const action = await this.orm.call(
                        "material.requisition.dashboard",
                        "get_dashboard_point_action",
                        [parseInt(dashboardId, 10), valueIndex]
                    );
                    if (action) {
                        await this.actionService.doAction(action);
                    }
                },
            },
        };

    }

}

export const stateTypeDashboardGraphField = {
    component: StateTypeDashboardGraphField,
    supportedTypes: ["text"],
    extractProps: ({ attrs }) => ({
        graphType: attrs.graph_type || "bar",
        hideAxes: attrs.hide_axes === "true",
        showTooltip: attrs.show_tooltip !== "false",
        showLegend: attrs.show_legend == "true"
    }),
};


registry.category("fields").add("state_type_dashboard_graph", stateTypeDashboardGraphField);
