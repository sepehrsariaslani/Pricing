// Copyright (c) 2024, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.query_reports["Unified Pricing Report"] = {
    "filters": [
        {
            "fieldname": "auto_price_list",
            "fieldtype": "Link",
            "label": __("لیست قیمت خودکار"),
            "options": "Auto Price List",
            "width": 150
        },
        {
            "fieldname": "item_group",
            "fieldtype": "Link",
            "label": __("گروه کالا"),
            "options": "Item Group",
            "width": 120
        },
        {
            "fieldname": "brand",
            "fieldtype": "Link",
            "label": __("برند"),
            "options": "Brand",
            "width": 120
        },
        {
            "fieldname": "from_date",
            "fieldtype": "Date",
            "label": __("از تاریخ"),
            "width": 100
        },
        {
            "fieldname": "to_date",
            "fieldtype": "Date",
            "label": __("تا تاریخ"),
            "width": 100
        },
        {
            "fieldname": "compare_with_price_list",
            "fieldtype": "Link",
            "label": __("مقایسه با لیست قیمت"),
            "options": "Price List",
            "width": 150
        },
        {
            "fieldname": "min_profit_percentage",
            "fieldtype": "Percent",
            "label": __("حداقل درصد سود"),
            "width": 100
        },
        {
            "fieldname": "max_profit_percentage",
            "fieldtype": "Percent",
            "label": __("حداکثر درصد سود"),
            "width": 100
        },
        {
            "default": 1,
            "fieldname": "show_cost_details",
            "fieldtype": "Check",
            "label": __("نمایش جزئیات هزینه")
        },
        {
            "default": 0,
            "fieldname": "show_markup_details",
            "fieldtype": "Check",
            "label": __("نمایش جزئیات افزایش قیمت")
        },
        {
            "default": 0,
            "fieldname": "show_commission_details",
            "fieldtype": "Check",
            "label": __("نمایش جزئیات کمیسیون")
        },
        {
            "default": 0,
            "fieldname": "show_installment_details",
            "fieldtype": "Check",
            "label": __("نمایش جزئیات قسط")
        },
        {
            "default": "profit_distribution",
            "fieldname": "chart_type",
            "fieldtype": "Select",
            "label": __("نوع نمودار"),
            "options": "\nprofit_distribution\ncost_breakdown\ntop_profitable"
        }
    ],
    
    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        
        // رنگ‌بندی بر اساس سودآوری
        if (column.fieldname == "profit_percentage") {
            if (data.profit_percentage < 0) {
                value = "<span style='color: red; font-weight: bold;'>" + value + "</span>";
            } else if (data.profit_percentage < 10) {
                value = "<span style='color: orange;'>" + value + "</span>";
            } else if (data.profit_percentage >= 30) {
                value = "<span style='color: green; font-weight: bold;'>" + value + "</span>";
            }
        }
        
        if (column.fieldname == "profit_loss_status") {
            if (value == "سودآور") {
                value = "<span style='color: green; font-weight: bold;'>✓ " + value + "</span>";
            } else if (value == "ضررآور") {
                value = "<span style='color: red; font-weight: bold;'>✗ " + value + "</span>";
            }
        }
        
        if (column.fieldname == "profit_amount") {
            if (data.profit_amount < 0) {
                value = "<span style='color: red;'>" + value + "</span>";
            } else if (data.profit_amount > 0) {
                value = "<span style='color: green;'>" + value + "</span>";
            }
        }
        
        return value;
    },
    
    "onload": function(report) {
        report.page.add_inner_button(__("خروجی اکسل"), function() {
            report.export_report("xlsx");
        });
        
        report.page.add_inner_button(__("چاپ"), function() {
            report.print_report();
        });
    }
};

