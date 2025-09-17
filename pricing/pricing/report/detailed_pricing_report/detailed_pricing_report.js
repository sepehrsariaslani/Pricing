// Copyright (c) 2024, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.query_reports["Detailed Pricing Report"] = {
	"filters": [
		{
			"fieldname": "price_list",
			"label": __("لیست قیمت"),
			"fieldtype": "Link",
			"options": "Price List",
			"reqd": 0
		},
		{
			"fieldname": "auto_price_list",
			"label": __("لیست قیمت خودکار"),
			"fieldtype": "Link",
			"options": "Auto Price List",
			"reqd": 0
		},
		{
			"fieldname": "item_group",
			"label": __("گروه کالا"),
			"fieldtype": "Link",
			"options": "Item Group"
		},
		{
			"fieldname": "from_date",
			"label": __("از تاریخ"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1)
		},
		{
			"fieldname": "to_date",
			"label": __("تا تاریخ"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today()
		}
	],
	
	"formatter": function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		
		if (column.fieldname == "profit_loss_status") {
			if (value === "ضررآور") {
				value = `<span style="color: red; font-weight: bold;">${value}</span>`;
			} else if (value === "سودآور") {
				value = `<span style="color: green; font-weight: bold;">${value}</span>`;
			}
		}
		
		if (column.fieldname == "profit_percentage") {
			if (data && data.profit_percentage < 0) {
				value = `<span style="color: red;">${value}</span>`;
			} else if (data && data.profit_percentage > 30) {
				value = `<span style="color: green; font-weight: bold;">${value}</span>`;
			}
		}
		
		return value;
	}
};
