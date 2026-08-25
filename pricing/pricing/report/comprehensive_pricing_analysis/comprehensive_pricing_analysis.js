// Copyright (c) 2024, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.query_reports["Comprehensive Pricing Analysis"] = {
	"filters": [
		{
			"fieldname": "price_lists",
			"label": __("لیست‌های قیمت"),
			"fieldtype": "MultiSelectList",
			"get_data": function(txt) {
				return frappe.db.get_link_options('Price List', txt);
			},
			"reqd": 1
		},
		{
			"fieldname": "price_rounding_amount",
			"label": __("مبلغ رند کردن قیمت"),
			"fieldtype": "Currency",
			"default": 0,
			"description": "قیمت‌ها به این مبلغ به سمت بالا رند می‌شوند"
		},
		{
			"fieldname": "item_group",
			"label": __("گروه کالا"),
			"fieldtype": "Link",
			"options": "Item Group"
		},
		{
			"fieldname": "brand",
			"label": __("برند"),
			"fieldtype": "Link",
			"options": "Brand"
		},
		{
			"fieldname": "item_code",
			"label": __("کد کالا"),
			"fieldtype": "Link",
			"options": "Item"
		},
		{
			"fieldname": "enable_installment",
			"label": __("فعال‌سازی قسط"),
			"fieldtype": "Check",
			"default": 0
		},
		{
			"fieldname": "down_payment_percentage",
			"label": __("درصد پیش پرداخت"),
			"fieldtype": "Float",
			"default": 20,
			"depends_on": "eval:doc.enable_installment"
		},
		{
			"fieldname": "number_of_months",
			"label": __("تعداد ماه"),
			"fieldtype": "Int",
			"default": 12,
			"depends_on": "eval:doc.enable_installment"
		},
		{
			"fieldname": "monthly_interest_rate",
			"label": __("نرخ بهره ماهانه (درصد)"),
			"fieldtype": "Float",
			"default": 2,
			"depends_on": "eval:doc.enable_installment"
		},
		{
			"fieldname": "profit_margin",
			"label": __("حاشیه سود (درصد)"),
			"fieldtype": "Float",
			"default": 20,
			"depends_on": "eval:doc.enable_installment"
		},
		{
			"fieldname": "installment_base_price_list",
			"label": __("لیست قیمت مبنای قسط"),
			"fieldtype": "Link",
			"options": "Price List",
			"depends_on": "eval:doc.enable_installment",
			"description": "لیست قیمتی که برای محاسبه قسط استفاده شود"
		}
	],
	
	"formatter": function(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		
		if (!value || value === "0" || value === "0.00") {
			return value;
		}
		
		// رنگ‌آمیزی درصد سود
		if (column.fieldname && column.fieldname.includes("profit_pct_")) {
			let numValue = parseFloat(value.toString().replace(/[^\d.-]/g, ''));
			if (!isNaN(numValue)) {
				if (numValue < 0) {
					value = `<span style="color: red; font-weight: bold;">${value}</span>`;
				} else if (numValue > 30) {
					value = `<span style="color: green; font-weight: bold;">${value}</span>`;
				} else if (numValue > 15) {
					value = `<span style="color: blue;">${value}</span>`;
				}
			}
		}
		
		// رنگ‌آمیزی سود
		if (column.fieldname && column.fieldname.includes("profit_") && !column.fieldname.includes("profit_pct_")) {
			let numValue = parseFloat(value.toString().replace(/[^\d.-]/g, ''));
			if (!isNaN(numValue)) {
				if (numValue < 0) {
					value = `<span style="color: red;">${value}</span>`;
				} else if (numValue > 0) {
					value = `<span style="color: green;">${value}</span>`;
				}
			}
		}
		
		// رنگ‌آمیزی قیمت قسطی
		if (column.fieldname == "installment_price") {
			value = `<span style="color: purple; font-weight: bold;">${value}</span>`;
		}
		
		// رنگ‌آمیزی بهره
		if (column.fieldname == "total_interest") {
			let numValue = parseFloat(value.toString().replace(/[^\d.-]/g, ''));
			if (!isNaN(numValue) && numValue > 0) {
				value = `<span style="color: orange;">${value}</span>`;
			}
		}
		
		return value;
	},
	
	"onload": function(report) {
		// اضافه کردن دکمه‌های اضافی
		report.page.add_inner_button(__("صادرات به Excel"), function() {
			let data = frappe.query_report.data || [];
			let columns = frappe.query_report.columns || [];
			
			if (data.length === 0) {
				frappe.msgprint(__("هیچ داده‌ای برای صادرات وجود ندارد"));
				return;
			}
			
			// تبدیل داده‌ها به فرمت CSV
			let csv_data = [];
			let headers = columns.map(col => col.label || col.fieldname);
			csv_data.push(headers);
			
			data.forEach(row => {
				let row_data = columns.map(col => row[col.fieldname] || '');
				csv_data.push(row_data);
			});
			
			frappe.tools.downloadify(csv_data, null, "تحلیل_جامع_قیمت‌گذاری");
		});
		
		report.page.add_inner_button(__("چاپ گزارش"), function() {
			if (!frappe.query_report.data || frappe.query_report.data.length === 0) {
				frappe.msgprint(__("هیچ داده‌ای برای چاپ وجود ندارد"));
				return;
			}
			window.print();
		});
		
		// اضافه کردن دکمه تنظیمات سریع
		report.page.add_inner_button(__("تنظیمات سریع"), function() {
			let d = new frappe.ui.Dialog({
				title: 'تنظیمات سریع گزارش',
				fields: [
					{
						label: 'نوع تحلیل',
						fieldname: 'analysis_type',
						fieldtype: 'Select',
						options: [
							'',
							'تحلیل سودآوری',
							'مقایسه قیمت‌ها',
							'تحلیل قسطی'
						]
					},
					{
						label: 'رند کردن قیمت',
						fieldname: 'quick_rounding',
						fieldtype: 'Currency',
						description: 'مبلغ رند کردن قیمت (مثال: 1000)'
					}
				],
				primary_action_label: 'اعمال',
				primary_action(values) {
					if (values.analysis_type === 'تحلیل قسطی') {
						frappe.query_report.set_filter_value('enable_installment', 1);
					}
					if (values.quick_rounding) {
						frappe.query_report.set_filter_value('price_rounding_amount', values.quick_rounding);
					}
					frappe.query_report.refresh();
					d.hide();
				}
			});
			d.show();
		});
		
		// راهنمای استفاده
		report.page.add_inner_button(__("راهنما"), function() {
			frappe.msgprint({
				title: 'راهنمای استفاده از گزارش',
				message: `
					<div style="text-align: right; direction: rtl;">
						<h4>نحوه استفاده:</h4>
						<ul>
							<li><strong>لیست‌های قیمت:</strong> نام لیست‌های قیمت را با کاما جدا کنید</li>
							<li><strong>تحلیل قسطی:</strong> برای فعال‌سازی محاسبات قسط، گزینه "فعال‌سازی قسط" را انتخاب کنید</li>
							<li><strong>فیلترها:</strong> از فیلترهای گروه کالا و برند برای محدود کردن نتایج استفاده کنید</li>
						</ul>
						<h4>رنگ‌بندی:</h4>
						<ul>
							<li><span style="color: green;">سبز:</span> سود بالا (بیش از 30%)</li>
							<li><span style="color: blue;">آبی:</span> سود متوسط (15-30%)</li>
							<li><span style="color: red;">قرمز:</span> ضرر یا سود کم</li>
							<li><span style="color: purple;">بنفش:</span> قیمت قسطی</li>
							<li><span style="color: orange;">نارنجی:</span> بهره</li>
						</ul>
					</div>
				`,
				indicator: 'blue'
			});
		});
	}
};
