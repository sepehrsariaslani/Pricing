// Copyright (c) 2025, Sepehr and contributors
// For license information, please see license.txt

frappe.query_reports["Production Prices"] = {
	"filters": [
		{
			"fieldname": "item_code",
			"label": __("کد محصول"),
			"fieldtype": "MultiSelectList",
			"get_data": function(txt) {
				return frappe.db.get_link_options('Item', txt, {}, null, 100); // Increase limit to 100
			}
		},
		{
			"fieldname": "item_group", 
			"label": __("گروه محصول"),
			"fieldtype": "MultiSelectList",
			"get_data": function(txt) {
				return frappe.db.get_link_options('Item Group', txt, {}, null, 50);
			}
		},
		{
			"fieldname": "workstation",
			"label": __("ایستگاه کاری"),
			"fieldtype": "MultiSelectList",
			"get_data": function(txt) {
				return frappe.db.get_link_options('Workstation', txt, {}, null, 50);
			}
		},
		{
			"fieldname": "bom",
			"label": __("BOM"),
			"fieldtype": "MultiSelectList",
			"get_data": function(txt) {
				return frappe.db.get_link_options('BOM', txt, {
					"is_active": 1,
					"is_default": 1
				}, null, 100);
			}
		},
		{
			"fieldname": "max_level",
			"label": __("حداکثر سطح BOM"),
			"fieldtype": "Int",
			"default": 3,
			"description": __("حداکثر سطح تو در تو برای BOM ها")
		},
		{
			"fieldname": "show_summary",
			"label": __("نمایش خلاصه"),
			"fieldtype": "Check",
			"default": 0,
			"description": __("نمایش خلاصه هزینه ها بر اساس بخش کاری")
		},
		{
			"fieldname": "show_comparison",
			"label": __("مقایسه گروهی"),
			"fieldtype": "Check",
			"default": 0,
			"description": __("مقایسه میانگین هزینه ها بین محصولات مختلف")
		}
	],
	
	"formatter": function (value, row, column, data, default_formatter) {
		// Add indentation for production items based on level
		if (column.fieldname === "production_item" && data && data.level) {
			let indent = "　".repeat(data.level); // Use full-width space for indentation
			value = indent + value;
		}
		
		// Format currency values
		if (column.fieldtype === "Currency" && value) {
			value = format_currency(value, frappe.defaults.get_default("currency"));
		}
		
		return default_formatter(value, row, column, data);
	},
	
	"onload": function(report) {
		// Fix filter width issues
		setTimeout(function() {
			// Make filter containers wider
			report.page.find('.filter-section .form-group').css({
				'min-width': '250px',
				'margin-right': '15px'
			});
			
			// Make MultiSelectList inputs wider
			report.page.find('[data-fieldtype="MultiSelectList"] .control-input').css({
				'min-width': '220px'
			});
			
			// Ensure filter area has enough space
			report.page.find('.filter-section').css({
				'flex-wrap': 'wrap',
				'gap': '10px'
			});
		}, 500);
		
		// Add custom buttons
		report.page.add_inner_button(__("انتخاب همه محصولات"), function() {
			frappe.db.get_list('Item', {
				fields: ['name'],
				filters: {
					'is_stock_item': 1
				},
				limit: 200 // Increase limit
			}).then(function(items) {
				let item_names = items.map(item => item.name);
				report.set_filter_value('item_code', item_names);
				report.refresh();
			});
		});
		
		report.page.add_inner_button(__("انتخاب محصولات فیلتر شده"), function() {
			// Show dialog to get search term
			frappe.prompt([
				{
					'fieldname': 'search_term',
					'label': __('جستجوی محصول'),
					'fieldtype': 'Data',
					'description': __('مثال: پیلو، صندلی، میز و ...')
				}
			], function(values) {
				let search_text = values.search_term;
				if (search_text && search_text.length > 0) {
					frappe.db.get_list('Item', {
						fields: ['name'],
						filters: {
							'is_stock_item': 1,
							'name': ['like', '%' + search_text + '%']
						},
						limit: 100
					}).then(function(items) {
						let item_names = items.map(item => item.name);
						if (item_names.length > 0) {
							report.set_filter_value('item_code', item_names);
							report.refresh();
							frappe.show_alert({
								message: __('انتخاب شد: {0} محصول برای "{1}"', [item_names.length, search_text]),
								indicator: 'green'
							});
						} else {
							frappe.show_alert({
								message: __('هیچ محصولی برای "{0}" یافت نشد', [search_text]),
								indicator: 'orange'
							});
						}
					});
				}
			}, __('انتخاب محصولات'), __('انتخاب'));
		});
		
		report.page.add_inner_button(__("پاک کردن فیلترها"), function() {
			report.clear_filters();
			report.refresh();
		});
		
		// Auto-load all products by default on first load
		if (!report.get_filter_value('item_code') && !report._initial_load_done) {
			report._initial_load_done = true;
			setTimeout(function() {
				frappe.db.get_list('Item', {
					fields: ['name'],
					filters: {
						'is_stock_item': 1
					},
					limit: 200
				}).then(function(items) {
					let item_names = items.map(item => item.name);
					report.set_filter_value('item_code', item_names);
					report.refresh();
				});
			}, 1000);
		}
	}
};
