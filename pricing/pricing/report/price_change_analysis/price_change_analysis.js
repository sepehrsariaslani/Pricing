// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Price Change Analysis"] = {
	"filters": [
		{
			"fieldname": "auto_price_list",
			"label": __("Auto Price List"),
			"fieldtype": "Link",
			"options": "Auto Price List",
			"width": "80px"
		},
		{
			"fieldname": "item_code",
			"label": __("Item Code"),
			"fieldtype": "Link",
			"options": "Item",
			"width": "80px"
		},
		{
			"fieldname": "item_group",
			"label": __("Item Group"),
			"fieldtype": "Link",
			"options": "Item Group",
			"width": "80px"
		},
		{
			"fieldname": "from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			"width": "80px"
		},
		{
			"fieldname": "to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"width": "80px"
		}
	],
	
	"formatter": function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		
		if (column.fieldname == "cost_change" && data && data.cost_change) {
			if (data.cost_change > 0) {
				value = "<span style='color:red'>" + value + "</span>";
			} else if (data.cost_change < 0) {
				value = "<span style='color:green'>" + value + "</span>";
			}
		}
		
		if (column.fieldname == "cost_change_percent" && data && data.cost_change_percent) {
			if (data.cost_change_percent > 10) {
				value = "<span style='color:red; font-weight:bold'>" + value + "</span>";
			} else if (data.cost_change_percent < -10) {
				value = "<span style='color:green; font-weight:bold'>" + value + "</span>";
			}
		}
		
		if (column.fieldname == "competitive_status" && data && data.competitive_status) {
			if (data.competitive_status == "بسیار رقابتی") {
				value = "<span style='color:green; font-weight:bold'>" + value + "</span>";
			} else if (data.competitive_status == "رقابتی") {
				value = "<span style='color:green'>" + value + "</span>";
			} else if (data.competitive_status == "گران" || data.competitive_status == "بسیار گران") {
				value = "<span style='color:red'>" + value + "</span>";
			}
		}
		
		return value;
	},
	
	"onload": function(report) {
		// Add custom buttons
		report.page.add_inner_button(__("Export to Excel"), function() {
			frappe.utils.csvDownload(report.data, report.columns, __("Price Change Analysis"));
		});
		
		report.page.add_inner_button(__("Print Summary"), function() {
			let summary_data = report.get_summary_data();
			frappe.utils.print_table(summary_data, __("Price Change Summary"));
		});
	},
	
	get_summary_data: function() {
		// Calculate summary statistics
		let data = this.data || [];
		let total_items = data.length;
		let items_with_increase = data.filter(d => d.cost_change > 0).length;
		let items_with_decrease = data.filter(d => d.cost_change < 0).length;
		let avg_cost_change = data.reduce((sum, d) => sum + (d.cost_change || 0), 0) / total_items;
		
		return [
			{label: __("Total Items"), value: total_items},
			{label: __("Items with Cost Increase"), value: items_with_increase},
			{label: __("Items with Cost Decrease"), value: items_with_decrease},
			{label: __("Average Cost Change"), value: avg_cost_change.toFixed(2)}
		];
	}
};
