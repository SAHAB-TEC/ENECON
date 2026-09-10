/** @odoo-module **/
/* Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>) */
/* See LICENSE file for full copyright and licensing details. */
/* License URL : <https://store.webkul.com/license.html/> */


import { registry } from "@web/core/registry";
import { statusBarField, StatusBarField } from "@web/views/fields/statusbar/statusbar_field";
import { _t } from "@web/core/l10n/translation";

export class StraightLineRibbonWidget extends StatusBarField {
    static template = "material_requisition_and_approval.Ribbon";

    adjustVisibleItems(){
        // we don't need to adjust visibility so override this funtion
    }

}



export const straightRibbonWidget = {
    ...statusBarField,
    component: StraightLineRibbonWidget,
    supportedTypes: ["many2one"],
};


registry.category("fields").add("straight_ribbon", straightRibbonWidget);
