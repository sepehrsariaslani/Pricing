// Copyright (c) 2024, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.query_reports["Price List Comparison"] = {
	"filters": [
		{
			"fieldname": "price_list_1",
			"label": __("لیست قیمت اول"),
			"fieldtype": "Link",
			"options": "Price List",
			"reqd": 1
		},
		{
			"fieldname": "price_list_2",
			"label": __("لیست قیمت دوم"),
			"fieldtype": "Link",
			"options": "Price List",
			"reqd": 1
		},
		{
			"fieldname": "item_group",
			"label": __("گروه کالا"),
			"fieldtype": "Link",
			"options": "Item Group"
		},
		{
			"fieldname": "item_code",
			"label": __("کد کالا"),
			"fieldtype": "Link",
			"options": "Item"
		}
	],
	
	"formatter": function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		
		// رنگ‌آمیزی وضعیت سود/ضرر
		if (column.fieldname == "status_list_1" || column.fieldname == "status_list_2") {
			if (value === "ضررآور") {
				value = `<span style="color: red; font-weight: bold;">${value}</span>`;
			} else if (value === "سودآور") {
				value = `<span style="color: green; font-weight: bold;">${value}</span>`;
			}
		}
		
		// رنگ‌آمیزی تفاوت قیمت
		if (column.fieldname == "price_difference") {
			if (data && data.price_difference > 0) {
				value = `<span style="color: green;">+${value}</span>`;
			} else if (data && data.price_difference < 0) {
				value = `<span style="color: red;">${value}</span>`;
			}
		}
		
		// رنگ‌آمیزی درصد تغییر
		if (column.fieldname == "price_change_percentage") {
			if (data && data.price_change_percentage > 20) {
				value = `<span style="color: orange; font-weight: bold;">+${value}</span>`;
			} else if (data && data.price_change_percentage < -20) {
				value = `<span style="color: red; font-weight: bold;">${value}</span>`;
			} else if (data && data.price_change_percentage > 0) {
				value = `<span style="color: green;">+${value}</span>`;
			} else if (data && data.price_change_percentage < 0) {
				value = `<span style="color: red;">${value}</span>`;
			}
		}
		
		// رنگ‌آمیزی سود
		if (column.fieldname == "profit_list_1" || column.fieldname == "profit_list_2") {
			if (data && parseFloat(value.replace(/[^\d.-]/g, '')) < 0) {
				value = `<span style="color: red;">${value}</span>`;
			} else if (data && parseFloat(value.replace(/[^\d.-]/g, '')) > 0) {
				value = `<span style="color: green;">${value}</span>`;
			}
		}
		
		// رنگ‌آمیزی توصیه‌ها
		if (column.fieldname == "recommendation") {
			if (value && value.includes("ضررآور")) {
				value = `<span style="color: red; font-weight: bold;">${value}</span>`;
			} else if (value && value.includes("بهتر")) {
				value = `<span style="color: blue; font-weight: bold;">${value}</span>`;
			} else if (value && value.includes("زیاد")) {
				value = `<span style="color: orange; font-weight: bold;">${value}</span>`;
			} else if (value && value.includes("مناسب")) {
				value = `<span style="color: green;">${value}</span>`;
			}
		}
		
		return value;
	},
	
	"onload": function(report) {
		// اضافه کردن دکمه‌های اضافی
		report.page.add_inner_button(__("صادرات به Excel"), function() {
			frappe.utils.csv_to_excel(frappe.query_report.get_data_for_csv(), __("مقایسه لیست قیمت"));
		});
		
		report.page.add_inner_button(__("چاپ گزارش"), function() {
			frappe.query_report.print_report();
		});
	}
};
