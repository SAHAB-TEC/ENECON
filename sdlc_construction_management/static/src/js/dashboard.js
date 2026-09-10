/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, onMounted, onWillUnmount, useState, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";

class ConstructionDashboard extends Component {
    static template = "construction_management.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.charts = {};

        // Canvas refs
        this.projectTimelineRef = useRef("projectTimelineCanvas");
        this.projectStatusRef = useRef("projectStatusCanvas");
        this.projectStageRef = useRef("projectStageCanvas");
        this.spStatusRef = useRef("spStatusCanvas");
        this.spTimelineRef = useRef("spTimelineCanvas");
        this.mreqChartRef = useRef("mreqChartCanvas");
        this.poChartRef = useRef("poChartCanvas");

        this.state = useState({
            // KPIs
            projectCount: 0, subProjectCount: 0, mreqCount: 0,
            phaseCount: 0, workOrderCount: 0, budgetCount: 0,
            // Project status
            projectDraft: 0, projectInProgress: 0, projectCompleted: 0,
            projectStages: [],
            // Sub project status
            spPlanning: 0, spProcurement: 0, spConstruction: 0, spHandover: 0,
            // MREQ status
            mreqDraft: 0, mreqApproval: 0, mreqInProgress: 0,
            mreqReady: 0, mreqDone: 0,
            // PO & IT counts
            poCount: 0, itCount: 0,
            itDraft: 0, itInProgress: 0, itDone: 0, itForward: 0,
            // Data arrays
            projects: [], subProjects: [], workOrders: [],
            // Filters
            projectOptions: [], subProjectOptions: [],
            selectedProjectId: false, selectedSubProjectId: false,
        });

        onWillStart(async () => {
            await loadJS("/web/static/lib/Chart/Chart.js");
            await this.loadProjectOptions();
            await this.loadSubProjectOptions();
            await this.fetchDashboardData();
        });

        onMounted(() => this.renderCharts());
        onWillUnmount(() => this.destroyCharts());
    }

    // ── Shared chart defaults ──

    _tooltipStyle() {
        return {
            backgroundColor: 'rgba(44, 62, 80, 0.95)',
            titleFont: { size: 12, weight: '600', family: "'Inter', 'Segoe UI', sans-serif" },
            bodyFont: { size: 11, family: "'Inter', 'Segoe UI', sans-serif" },
            footerFont: { size: 11, weight: '600', family: "'Inter', 'Segoe UI', sans-serif" },
            padding: 12,
            cornerRadius: 10,
            borderColor: 'rgba(255,255,255,0.1)',
            borderWidth: 1,
            displayColors: true,
            boxPadding: 4,
        };
    }

    _legendStyle(position = 'bottom') {
        return {
            position,
            labels: {
                usePointStyle: true,
                pointStyle: 'circle',
                padding: 14,
                font: { size: 11, family: "'Inter', 'Segoe UI', sans-serif", weight: '500' },
                color: '#636e72',
            }
        };
    }

    _gridStyle() {
        return { color: 'rgba(0,0,0,0.04)', drawBorder: false };
    }

    // ── Domain helpers ──

    getProjectDomain() {
        return this.state.selectedProjectId ? [["id", "=", this.state.selectedProjectId]] : [];
    }

    getSubProjectDomain() {
        const d = [];
        if (this.state.selectedProjectId) d.push(["project_id", "=", this.state.selectedProjectId]);
        if (this.state.selectedSubProjectId) d.push(["id", "=", this.state.selectedSubProjectId]);
        return d;
    }

    getDomain() {
        const d = [];
        if (this.state.selectedProjectId) d.push(["project_id", "=", this.state.selectedProjectId]);
        if (this.state.selectedSubProjectId) d.push(["sub_project_id", "=", this.state.selectedSubProjectId]);
        return d;
    }

    // ── Filter options ──

    async loadProjectOptions() {
        this.state.projectOptions = await this.orm.searchRead(
            "construction.project", [], ["name"], { order: "name asc" }
        );
    }

    async loadSubProjectOptions() {
        const domain = this.state.selectedProjectId
            ? [["project_id", "=", this.state.selectedProjectId]] : [];
        this.state.subProjectOptions = await this.orm.searchRead(
            "construction.sub.project", domain, ["name"], { order: "name asc" }
        );
    }

    // ── Data fetching ──

    async fetchDashboardData() {
        const pd = this.getProjectDomain();
        const spd = this.getSubProjectDomain();
        const d = this.getDomain();

        try {
            const stages = await this.orm.searchRead(
                "construction.project.stage",
                [],
                ["name", "sequence"],
                { order: "sequence, id" }
            );
            const stageCountPromises = stages.map((stage) =>
                this.orm.searchCount("construction.project", [...pd, ["stage_id", "=", stage.id]])
            );
            stageCountPromises.push(
                this.orm.searchCount("construction.project", [...pd, ["stage_id", "=", false]])
            );

            const r = await Promise.all([
                // KPIs [0-5]
                this.orm.searchCount("construction.project", pd),
                this.orm.searchCount("construction.sub.project", spd),
                this.orm.searchCount("construction.material.requisition", d),
                this.orm.searchCount("construction.phase", d),
                this.orm.searchCount("construction.work.order", d),
                this.orm.searchCount("construction.budget", d),
                // Project status [6-8]
                this.orm.searchCount("construction.project", [...pd, ["state", "=", "draft"]]),
                this.orm.searchCount("construction.project", [...pd, ["state", "=", "in_progress"]]),
                this.orm.searchCount("construction.project", [...pd, ["state", "=", "completed"]]),
                // Sub project status [9-12]
                this.orm.searchCount("construction.sub.project", [...spd, ["state", "=", "planning"]]),
                this.orm.searchCount("construction.sub.project", [...spd, ["state", "=", "procurement"]]),
                this.orm.searchCount("construction.sub.project", [...spd, ["state", "=", "construction"]]),
                this.orm.searchCount("construction.sub.project", [...spd, ["state", "=", "handover"]]),
                // MREQ status [13-17]
                this.orm.searchCount("construction.material.requisition", [...d, ["state", "=", "draft"]]),
                this.orm.searchCount("construction.material.requisition", [...d, ["state", "=", "under_approval"]]),
                this.orm.searchCount("construction.material.requisition", [...d, ["state", "=", "in_progress"]]),
                this.orm.searchCount("construction.material.requisition", [...d, ["state", "=", "ready"]]),
                this.orm.searchCount("construction.material.requisition", [...d, ["state", "=", "done"]]),
                // PO & IT [18-23]
                this.orm.searchCount("purchase.order", []),
                this.orm.searchCount("stock.picking", [["picking_type_code", "=", "internal"]]),
                this.orm.searchCount("stock.picking", [["picking_type_code", "=", "internal"], ["state", "=", "draft"]]),
                this.orm.searchCount("stock.picking", [["picking_type_code", "=", "internal"], ["state", "in", ["confirmed", "assigned"]]]),
                this.orm.searchCount("stock.picking", [["picking_type_code", "=", "internal"], ["state", "=", "done"]]),
                this.orm.searchCount("stock.picking", [["picking_type_code", "=", "outgoing"]]),
                // Data arrays [24-26]
                this.orm.searchRead("construction.project", pd,
                    ["name", "date_start", "date_end", "state"], { limit: 10, order: "id desc" }),
                this.orm.searchRead("construction.sub.project", spd,
                    ["name", "reference", "date_start", "date_end", "state", "project_id"],
                    { limit: 10, order: "id desc" }),
                this.orm.searchRead("construction.work.order", d,
                    ["name", "material_total", "equipment_total", "labour_total", "overhead_total"],
                    { limit: 10, order: "id asc" }),
                ...stageCountPromises,
            ]);

            const stageCounts = r.slice(27);
            const projectStages = stages.map((stage, index) => ({
                id: stage.id,
                name: stage.name,
                count: stageCounts[index] || 0,
            }));
            const noStageCount = stageCounts[stages.length] || 0;
            if (noStageCount) {
                projectStages.push({ id: false, name: "No Stage", count: noStageCount });
            }

            Object.assign(this.state, {
                projectCount: r[0], subProjectCount: r[1], mreqCount: r[2],
                phaseCount: r[3], workOrderCount: r[4], budgetCount: r[5],
                projectDraft: r[6], projectInProgress: r[7], projectCompleted: r[8],
                spPlanning: r[9], spProcurement: r[10], spConstruction: r[11], spHandover: r[12],
                mreqDraft: r[13], mreqApproval: r[14], mreqInProgress: r[15],
                mreqReady: r[16], mreqDone: r[17],
                poCount: r[18], itCount: r[19],
                itDraft: r[20], itInProgress: r[21], itDone: r[22], itForward: r[23],
                projects: r[24], subProjects: r[25], workOrders: r[26],
                projectStages,
            });
        } catch (e) {
            console.error("Dashboard fetch error:", e);
        }
    }

    // ── Chart lifecycle ──

    destroyCharts() {
        Object.values(this.charts).forEach(c => c.destroy());
        this.charts = {};
    }

    renderCharts() {
        this.destroyCharts();
        this._renderProjectTimeline();
        this._renderProjectStatus();
        this._renderProjectStage();
        this._renderSpStatus();
        this._renderSpTimeline();
        this._renderMreqChart();
        this._renderPoChart();
    }

    // ── Chart: Project Timeline (Gantt-like) ──

    _renderProjectTimeline() {
        const el = this.projectTimelineRef.el;
        if (!el) return;
        const projects = this.state.projects.filter(p => p.date_start && p.date_end);
        if (!projects.length) return;

        const colors = [
            ['#55efc4', '#00b894'], ['#ff7675', '#d63031'], ['#74b9ff', '#0984e3'],
            ['#fdcb6e', '#e17055'], ['#a29bfe', '#6c5ce7'], ['#fab1a0', '#e17055'],
            ['#81ecec', '#00cec9'], ['#ffeaa7', '#fdcb6e'], ['#dfe6e9', '#b2bec3'],
            ['#00b894', '#00cec9']
        ];
        const minDate = new Date(Math.min(...projects.map(p => new Date(p.date_start))));

        const data = projects.map(p => {
            const s = (new Date(p.date_start) - minDate) / 86400000;
            const e = (new Date(p.date_end) - minDate) / 86400000;
            return [s, e];
        });

        const bgColors = projects.map((_, i) => {
            const [c1, c2] = colors[i % colors.length];
            const gradient = el.getContext('2d').createLinearGradient(0, 0, el.width, 0);
            gradient.addColorStop(0, c1);
            gradient.addColorStop(1, c2);
            return gradient;
        });

        this.charts.projectTimeline = new Chart(el, {
            type: 'bar',
            data: {
                labels: projects.map(p => p.name),
                datasets: [{
                    data: data,
                    backgroundColor: bgColors,
                    borderRadius: 6,
                    barThickness: 24,
                    borderSkipped: false,
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 800, easing: 'easeOutQuart' },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            generateLabels: (chart) => chart.data.labels.map((l, i) => ({
                                text: l,
                                fillStyle: colors[i % colors.length][0],
                                strokeStyle: 'transparent',
                                pointStyle: 'circle',
                            })),
                            usePointStyle: true, padding: 14, font: { size: 10, weight: '500' }
                        }
                    },
                    tooltip: {
                        ...this._tooltipStyle(),
                        callbacks: {
                            label: (ctx) => {
                                const [s, e] = ctx.raw;
                                return ` Duration: ${Math.round(e - s)} days`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            callback: (value) => {
                                const date = new Date(minDate.getTime() + value * 86400000);
                                const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                                                 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
                                const yr = String(date.getFullYear()).slice(-2);
                                return `${months[date.getMonth()]} '${yr}`;
                            },
                            maxTicksLimit: 12,
                            font: { size: 10 },
                            color: '#95a5a6',
                        },
                        grid: this._gridStyle()
                    },
                    y: { display: false }
                }
            },
            plugins: [{
                id: 'barLabels',
                afterDatasetsDraw(chart) {
                    const ctx2 = chart.ctx;
                    const meta = chart.getDatasetMeta(0);
                    meta.data.forEach((bar, i) => {
                        const [s, e] = chart.data.datasets[0].data[i];
                        const days = Math.round(e - s);
                        const xS = chart.scales.x.getPixelForValue(s);
                        const xE = chart.scales.x.getPixelForValue(e);
                        if (xE - xS > 50) {
                            ctx2.save();
                            ctx2.fillStyle = '#fff';
                            ctx2.font = 'bold 10px Inter, Segoe UI, sans-serif';
                            ctx2.textAlign = 'center';
                            ctx2.textBaseline = 'middle';
                            ctx2.shadowColor = 'rgba(0,0,0,0.2)';
                            ctx2.shadowBlur = 2;
                            ctx2.fillText(`${days}d`, (xS + xE) / 2, bar.y);
                            ctx2.restore();
                        }
                    });
                }
            }]
        });
    }

    // ── Chart: Project Status (Donut) ──

    _renderProjectStatus() {
        const el = this.projectStatusRef.el;
        if (!el) return;
        const data = [this.state.projectDraft, this.state.projectInProgress, this.state.projectCompleted];
        const ctx = el.getContext('2d');

        const grad1 = ctx.createLinearGradient(0, 0, 0, 300);
        grad1.addColorStop(0, '#b2bec3'); grad1.addColorStop(1, '#95a5a6');
        const grad2 = ctx.createLinearGradient(0, 0, 0, 300);
        grad2.addColorStop(0, '#74b9ff'); grad2.addColorStop(1, '#0984e3');
        const grad3 = ctx.createLinearGradient(0, 0, 0, 300);
        grad3.addColorStop(0, '#55efc4'); grad3.addColorStop(1, '#00b894');

        this.charts.projectStatus = new Chart(el, {
            type: 'doughnut',
            data: {
                labels: ['Draft', 'In Progress', 'Completed'],
                datasets: [{
                    data: data.some(v => v > 0) ? data : [1, 0, 0],
                    backgroundColor: [grad1, grad2, grad3],
                    borderWidth: 0,
                    hoverOffset: 6,
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false, cutout: '68%',
                animation: { animateRotate: true, duration: 1000, easing: 'easeOutQuart' },
                plugins: {
                    legend: {
                        ...this._legendStyle(),
                        labels: {
                            ...this._legendStyle().labels,
                            generateLabels: (chart) => {
                                const ds = chart.data.datasets[0];
                                return chart.data.labels.map((label, i) => ({
                                    text: `${label}  (${ds.data[i]})`,
                                    fillStyle: ['#b2bec3', '#74b9ff', '#55efc4'][i],
                                    strokeStyle: 'transparent',
                                    pointStyle: 'circle',
                                    hidden: false,
                                }));
                            }
                        }
                    },
                    tooltip: {
                        ...this._tooltipStyle(),
                        callbacks: {
                            label: (ctx) => {
                                const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                                const pct = total > 0 ? ((ctx.parsed / total) * 100).toFixed(1) : 0;
                                return ` ${ctx.label}: ${ctx.parsed} (${pct}%)`;
                            }
                        }
                    }
                }
            },
            plugins: [{
                id: 'centerText',
                afterDraw(chart) {
                    const { ctx: c, chartArea } = chart;
                    const total = chart.data.datasets[0].data.reduce((a, b) => a + b, 0);
                    const cx = (chartArea.left + chartArea.right) / 2;
                    const cy = (chartArea.top + chartArea.bottom) / 2;
                    c.save();
                    c.fillStyle = '#2c3e50';
                    c.font = "bold 22px 'Inter', 'Segoe UI', sans-serif";
                    c.textAlign = 'center';
                    c.textBaseline = 'middle';
                    c.fillText(total, cx, cy - 8);
                    c.fillStyle = '#95a5a6';
                    c.font = "500 11px 'Inter', 'Segoe UI', sans-serif";
                    c.fillText('Total', cx, cy + 12);
                    c.restore();
                }
            }]
        });
    }

    // ── Chart: Project Stage (Donut) ──

    _renderProjectStage() {
        const el = this.projectStageRef.el;
        if (!el) return;

        const stages = this.state.projectStages.length
            ? this.state.projectStages
            : [{ name: "No Data", count: 0 }];
        const data = stages.map((stage) => stage.count);
        const labels = stages.map((stage) => stage.name);
        const ctx = el.getContext("2d");

        const palette = [
            ["#b2bec3", "#95a5a6"],
            ["#74b9ff", "#0984e3"],
            ["#55efc4", "#00b894"],
            ["#fdcb6e", "#e17055"],
            ["#a29bfe", "#6c5ce7"],
            ["#fab1a0", "#e17055"],
        ];
        const baseColors = labels.map((_, i) => palette[i % palette.length][0]);
        const gradients = labels.map((_, i) => {
            const [start, end] = palette[i % palette.length];
            const gradient = ctx.createLinearGradient(0, 0, 0, 300);
            gradient.addColorStop(0, start);
            gradient.addColorStop(1, end);
            return gradient;
        });

        this.charts.projectStage = new Chart(el, {
            type: "doughnut",
            data: {
                labels,
                datasets: [{
                    data: data.some((value) => value > 0) ? data : [1],
                    backgroundColor: data.some((value) => value > 0) ? gradients : ["#dfe6e9"],
                    borderWidth: 0,
                    hoverOffset: 6,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: "68%",
                animation: { animateRotate: true, duration: 1000, easing: "easeOutQuart" },
                plugins: {
                    legend: {
                        ...this._legendStyle(),
                        labels: {
                            ...this._legendStyle().labels,
                            generateLabels: (chart) => {
                                const ds = chart.data.datasets[0];
                                return chart.data.labels.map((label, i) => ({
                                    text: `${label}  (${ds.data[i]})`,
                                    fillStyle: baseColors[i],
                                    strokeStyle: "transparent",
                                    pointStyle: "circle",
                                    hidden: false,
                                }));
                            },
                        },
                    },
                    tooltip: {
                        ...this._tooltipStyle(),
                        callbacks: {
                            label: (ctx) => {
                                const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                                const pct = total > 0 ? ((ctx.parsed / total) * 100).toFixed(1) : 0;
                                return ` ${ctx.label}: ${ctx.parsed} (${pct}%)`;
                            },
                        },
                    },
                },
            },
            plugins: [{
                id: "projectStageCenterText",
                afterDraw(chart) {
                    const { ctx: c, chartArea } = chart;
                    const total = chart.data.datasets[0].data.reduce((a, b) => a + b, 0);
                    const cx = (chartArea.left + chartArea.right) / 2;
                    const cy = (chartArea.top + chartArea.bottom) / 2;
                    c.save();
                    c.fillStyle = "#2c3e50";
                    c.font = "bold 22px 'Inter', 'Segoe UI', sans-serif";
                    c.textAlign = "center";
                    c.textBaseline = "middle";
                    c.fillText(total, cx, cy - 8);
                    c.fillStyle = "#95a5a6";
                    c.font = "500 11px 'Inter', 'Segoe UI', sans-serif";
                    c.fillText("Total", cx, cy + 12);
                    c.restore();
                },
            }],
        });
    }

    // ── Chart: Sub Project Status (Bar) ──

    _renderSpStatus() {
        const el = this.spStatusRef.el;
        if (!el) return;
        const ctx = el.getContext('2d');

        const colors = [
            { start: '#55efc4', end: '#00b894' },
            { start: '#ff7675', end: '#d63031' },
            { start: '#74b9ff', end: '#0984e3' },
        ];
        const bgColors = colors.map(c => {
            const g = ctx.createLinearGradient(0, 0, 0, 220);
            g.addColorStop(0, c.start); g.addColorStop(1, c.end);
            return g;
        });

        this.charts.spStatus = new Chart(el, {
            type: 'bar',
            data: {
                labels: ['Planning', 'Procurement', 'Construction'],
                datasets: [{
                    label: 'Sub Project Status',
                    data: [this.state.spPlanning, this.state.spProcurement, this.state.spConstruction],
                    backgroundColor: bgColors,
                    borderRadius: 8, barThickness: 36, borderSkipped: false,
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                animation: { duration: 800, easing: 'easeOutQuart' },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            generateLabels: (chart) => chart.data.labels.map((l, i) => ({
                                text: l, fillStyle: colors[i].start,
                                strokeStyle: 'transparent', pointStyle: 'circle',
                            })),
                            usePointStyle: true, padding: 12, font: { size: 10, weight: '500' }
                        }
                    },
                    tooltip: this._tooltipStyle(),
                },
                scales: {
                    y: { beginAtZero: true, ticks: { stepSize: 1, color: '#95a5a6', font: { size: 10 } }, grid: this._gridStyle() },
                    x: { grid: { display: false }, ticks: { color: '#636e72', font: { size: 10, weight: '500' } } }
                }
            }
        });
    }

    // ── Chart: Sub Project Timeline (Gantt-like) ──

    _renderSpTimeline() {
        const el = this.spTimelineRef.el;
        if (!el) return;
        const sps = this.state.subProjects.filter(s => s.date_start && s.date_end);
        if (!sps.length) return;

        const colors = [
            ['#ff7675', '#d63031'], ['#00cec9', '#00b894'], ['#fdcb6e', '#e17055'],
            ['#6c5ce7', '#a29bfe'], ['#e17055', '#d63031'], ['#00b894', '#55efc4'],
            ['#74b9ff', '#0984e3'], ['#a29bfe', '#6c5ce7'], ['#fab1a0', '#e17055'],
            ['#81ecec', '#00cec9']
        ];
        const minDate = new Date(Math.min(...sps.map(s => new Date(s.date_start))));

        const data = sps.map(s => {
            const st = (new Date(s.date_start) - minDate) / 86400000;
            const en = (new Date(s.date_end) - minDate) / 86400000;
            return [st, en];
        });

        const bgColors = sps.map((_, i) => {
            const [c1, c2] = colors[i % colors.length];
            const gradient = el.getContext('2d').createLinearGradient(0, 0, el.width, 0);
            gradient.addColorStop(0, c1);
            gradient.addColorStop(1, c2);
            return gradient;
        });

        this.charts.spTimeline = new Chart(el, {
            type: 'bar',
            data: {
                labels: sps.map(s => s.name),
                datasets: [{
                    data: data,
                    backgroundColor: bgColors,
                    borderRadius: 6, barThickness: 22, borderSkipped: false,
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true, maintainAspectRatio: false,
                animation: { duration: 800, easing: 'easeOutQuart' },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            generateLabels: (chart) => chart.data.labels.map((l, i) => ({
                                text: l,
                                fillStyle: colors[i % colors.length][0],
                                strokeStyle: 'transparent', pointStyle: 'circle',
                            })),
                            usePointStyle: true, padding: 10, font: { size: 10, weight: '500' }
                        }
                    },
                    tooltip: {
                        ...this._tooltipStyle(),
                        callbacks: {
                            label: (ctx) => {
                                const [s, e] = ctx.raw;
                                return ` Duration: ${Math.round(e - s)} days`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            callback: (value) => {
                                const date = new Date(minDate.getTime() + value * 86400000);
                                const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                                                 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
                                return `${months[date.getMonth()]} '${String(date.getFullYear()).slice(-2)}`;
                            },
                            maxTicksLimit: 10,
                            font: { size: 10 },
                            color: '#95a5a6',
                        },
                        grid: this._gridStyle()
                    },
                    y: { display: false }
                }
            },
            plugins: [{
                id: 'spBarLabels',
                afterDatasetsDraw(chart) {
                    const ctx2 = chart.ctx;
                    const meta = chart.getDatasetMeta(0);
                    meta.data.forEach((bar, i) => {
                        const [s, e] = chart.data.datasets[0].data[i];
                        const days = Math.round(e - s);
                        const xS = chart.scales.x.getPixelForValue(s);
                        const xE = chart.scales.x.getPixelForValue(e);
                        if (xE - xS > 50) {
                            ctx2.save();
                            ctx2.fillStyle = '#fff';
                            ctx2.font = 'bold 10px Inter, Segoe UI, sans-serif';
                            ctx2.textAlign = 'center';
                            ctx2.textBaseline = 'middle';
                            ctx2.shadowColor = 'rgba(0,0,0,0.2)';
                            ctx2.shadowBlur = 2;
                            ctx2.fillText(`${days}d`, (xS + xE) / 2, bar.y);
                            ctx2.restore();
                        }
                    });
                }
            }]
        });
    }

    // ── Chart: Material Requisition (Donut) ──

    _renderMreqChart() {
        const el = this.mreqChartRef.el;
        if (!el) return;
        const data = [
            this.state.mreqDraft, this.state.mreqApproval,
            this.state.mreqInProgress, this.state.mreqReady, this.state.mreqDone
        ];
        const ctx = el.getContext('2d');
        const baseColors = ['#b2bec3', '#fdcb6e', '#74b9ff', '#55efc4', '#00b894'];
        const endColors  = ['#95a5a6', '#e17055', '#0984e3', '#00cec9', '#00835a'];

        const gradients = baseColors.map((c, i) => {
            const g = ctx.createLinearGradient(0, 0, 0, 230);
            g.addColorStop(0, c); g.addColorStop(1, endColors[i]);
            return g;
        });

        this.charts.mreqChart = new Chart(el, {
            type: 'doughnut',
            data: {
                labels: ['Draft', 'Waiting Approval', 'In Progress', 'Ready', 'Done'],
                datasets: [{
                    data: data.some(v => v > 0) ? data : [1, 0, 0, 0, 0],
                    backgroundColor: gradients,
                    borderWidth: 0,
                    hoverOffset: 6,
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false, cutout: '62%',
                animation: { animateRotate: true, duration: 1000, easing: 'easeOutQuart' },
                plugins: {
                    legend: {
                        ...this._legendStyle(),
                        labels: {
                            ...this._legendStyle().labels,
                            padding: 10,
                            font: { size: 10, weight: '500' },
                            generateLabels: (chart) => {
                                const ds = chart.data.datasets[0];
                                return chart.data.labels.map((label, i) => ({
                                    text: `${label}  (${ds.data[i]})`,
                                    fillStyle: baseColors[i],
                                    strokeStyle: 'transparent',
                                    pointStyle: 'circle',
                                    hidden: false,
                                }));
                            }
                        }
                    },
                    tooltip: {
                        ...this._tooltipStyle(),
                        callbacks: {
                            label: (ctx) => {
                                const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                                const pct = total > 0 ? ((ctx.parsed / total) * 100).toFixed(1) : 0;
                                return ` ${ctx.label}: ${ctx.parsed} (${pct}%)`;
                            }
                        }
                    }
                }
            },
            plugins: [{
                id: 'mreqCenterText',
                afterDraw(chart) {
                    const { ctx: c, chartArea } = chart;
                    const total = chart.data.datasets[0].data.reduce((a, b) => a + b, 0);
                    const cx = (chartArea.left + chartArea.right) / 2;
                    const cy = (chartArea.top + chartArea.bottom) / 2;
                    c.save();
                    c.fillStyle = '#2c3e50';
                    c.font = "bold 20px 'Inter', 'Segoe UI', sans-serif";
                    c.textAlign = 'center';
                    c.textBaseline = 'middle';
                    c.fillText(total, cx, cy - 7);
                    c.fillStyle = '#95a5a6';
                    c.font = "500 10px 'Inter', 'Segoe UI', sans-serif";
                    c.fillText('Total', cx, cy + 11);
                    c.restore();
                }
            }]
        });
    }

    // ── Chart: Purchase Orders (Bar) ──

    _renderPoChart() {
        const el = this.poChartRef.el;
        if (!el) return;
        const wos = this.state.workOrders;
        if (!wos.length) return;
        const ctx = el.getContext('2d');

        const colorDefs = [
            { label: 'Material',  start: '#e84393', end: '#d63384' },
            { label: 'Equipment', start: '#00cec9', end: '#00a8a8' },
            { label: 'Labour',    start: '#6c5ce7', end: '#5a4bd1' },
            { label: 'Overhead',  start: '#b2bec3', end: '#95a5a6' },
        ];

        const datasets = colorDefs.map((c, idx) => {
            const keys = ['material_total', 'equipment_total', 'labour_total', 'overhead_total'];
            const g = ctx.createLinearGradient(0, 0, 0, 320);
            g.addColorStop(0, c.start); g.addColorStop(1, c.end);
            return {
                label: c.label,
                data: wos.map(w => w[keys[idx]] || 0),
                backgroundColor: g,
                borderColor: c.end,
                borderWidth: 0,
                borderRadius: 6,
                borderSkipped: false,
            };
        });

        this.charts.poChart = new Chart(el, {
            type: 'bar',
            data: {
                labels: wos.map(w => w.name),
                datasets: datasets,
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                animation: { duration: 800, easing: 'easeOutQuart' },
                plugins: {
                    title: {
                        display: true,
                        text: 'Purchase Order Amount by Work Order',
                        font: { size: 13, weight: '700', family: "'Inter', 'Segoe UI', sans-serif" },
                        padding: { bottom: 20 },
                        color: '#2c3e50',
                    },
                    legend: {
                        position: 'bottom',
                        labels: {
                            usePointStyle: true, pointStyle: 'rectRounded', padding: 16,
                            font: { size: 11, weight: '500', family: "'Inter', 'Segoe UI', sans-serif" },
                            color: '#636e72',
                        }
                    },
                    tooltip: {
                        ...this._tooltipStyle(),
                        callbacks: {
                            label: function(ctx) {
                                const value = ctx.parsed.y || 0;
                                return ' ' + ctx.dataset.label + ': ' + value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                            },
                            footer: function(items) {
                                const total = items.reduce((sum, item) => sum + (item.parsed.y || 0), 0);
                                return 'Total: ' + total.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: this._gridStyle(),
                        title: { display: true, text: 'Amount', font: { size: 11, weight: '600' }, color: '#95a5a6' },
                        ticks: {
                            callback: function(value) { return value.toLocaleString(); },
                            font: { size: 10 },
                            color: '#95a5a6',
                        }
                    },
                    x: {
                        grid: { display: false },
                        title: { display: true, text: 'Work Orders', font: { size: 11, weight: '600' }, color: '#95a5a6' },
                        ticks: { font: { size: 10, weight: '500' }, color: '#636e72', maxRotation: 45 }
                    }
                }
            }
        });
    }

    // ── Filter handlers ──

    async onProjectFilterChange(ev) {
        this.state.selectedProjectId = parseInt(ev.target.value) || false;
        this.state.selectedSubProjectId = false;
        await this.loadSubProjectOptions();
        await this.fetchDashboardData();
        await new Promise(r => setTimeout(r, 50));
        this.renderCharts();
    }

    async onSubProjectFilterChange(ev) {
        this.state.selectedSubProjectId = parseInt(ev.target.value) || false;
        await this.fetchDashboardData();
        await new Promise(r => setTimeout(r, 50));
        this.renderCharts();
    }

    // ── Navigation handlers ──

    openView(model, name, domain = [], viewMode = "list,form") {
        const views =
            viewMode === "kanban,list,form"
                ? [[false, "kanban"], [false, "list"], [false, "form"]]
                : [[false, "list"], [false, "form"]];
        this.action.doAction({
            type: "ir.actions.act_window", name, res_model: model,
            view_mode: viewMode, views, domain,
        });
    }

    onProjectsClick() {
        this.action.doAction("sdlc_construction_management.action_construction_project");
    }
    onSubProjectsClick() { this.openView("construction.sub.project", "Sub Projects"); }
    onMreqClick() { this.openView("construction.material.requisition", "Material Requisitions"); }
    onPhasesClick() { this.openView("construction.phase", "Phases / WBS"); }
    onWorkOrdersClick() { this.openView("construction.work.order", "Work Orders"); }
    onBudgetsClick() { this.openView("construction.budget", "Budgets"); }

    onSpPlanningClick() { this.openView("construction.sub.project", "Sub Projects", [["state", "=", "planning"]]); }
    onSpProcurementClick() { this.openView("construction.sub.project", "Sub Projects", [["state", "=", "procurement"]]); }
    onSpConstructionClick() { this.openView("construction.sub.project", "Sub Projects", [["state", "=", "construction"]]); }

    onMreqDraftClick() { this.openView("construction.material.requisition", "Material Requisitions", [["state", "=", "draft"]]); }
    onMreqApprovalClick() { this.openView("construction.material.requisition", "Material Requisitions", [["state", "=", "under_approval"]]); }
    onMreqInProgressClick() { this.openView("construction.material.requisition", "Material Requisitions", [["state", "=", "in_progress"]]); }
    onMreqReadyClick() { this.openView("construction.material.requisition", "Material Requisitions", [["state", "=", "ready"]]); }
    onMreqDoneClick() { this.openView("construction.material.requisition", "Material Requisitions", [["state", "=", "done"]]); }
    onPoClick() { this.openView("purchase.order", "Purchase Orders"); }
    onItClick() { this.openView("stock.picking", "Internal Transfers", [["picking_type_code", "=", "internal"]]); }

    onItDraftClick() { this.openView("stock.picking", "Internal Transfers", [["picking_type_code", "=", "internal"], ["state", "=", "draft"]]); }
    onItInProgressClick() { this.openView("stock.picking", "Internal Transfers", [["picking_type_code", "=", "internal"], ["state", "in", ["confirmed", "assigned"]]]); }
    onItDoneClick() { this.openView("stock.picking", "Internal Transfers", [["picking_type_code", "=", "internal"], ["state", "=", "done"]]); }
    onItForwardClick() { this.openView("stock.picking", "Forward Transfers", [["picking_type_code", "=", "outgoing"]]); }
}

registry.category("actions").add("construction_dashboard", ConstructionDashboard);
