// Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Raw Materials Report"] = {
    "filters": [
        {
            "fieldname": "auto_price_list",
            "label": __("Auto Price List"),
            "fieldtype": "Link",
            "options": "Auto Price List",
            "reqd": 1
        }
    ]
};
