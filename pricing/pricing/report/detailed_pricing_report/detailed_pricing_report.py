# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)
	return columns, data

def get_columns():
	return [
		{
			"label": _("کد کالا"),
			"fieldname": "item_code",
			"fieldtype": "Link",
			"options": "Item",
			"width": 120
		},
		{
			"label": _("نام کالا"),
			"fieldname": "item_name",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"label": _("گروه کالا"),
			"fieldname": "item_group",
			"fieldtype": "Link",
			"options": "Item Group",
			"width": 120
		},
		{
			"label": _("هزینه مواد اولیه"),
			"fieldname": "raw_material_cost",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": _("هزینه برق"),
			"fieldname": "electricity_cost",
			"fieldtype": "Currency",
			"width": 100
		},
		{
			"label": _("هزینه مصرفی"),
			"fieldname": "consumable_cost",
			"fieldtype": "Currency",
			"width": 100
		},
		{
			"label": _("هزینه اجاره"),
			"fieldname": "rent_cost",
			"fieldtype": "Currency",
			"width": 100
		},
		{
			"label": _("هزینه کارگر"),
			"fieldname": "labor_cost",
			"fieldtype": "Currency",
			"width": 100
		},
		{
			"label": _("هزینه عملیات"),
			"fieldname": "operation_cost",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": _("هزینه سربار"),
			"fieldname": "overhead_cost",
			"fieldtype": "Currency",
			"width": 100
		},
		{
			"label": _("بهای تمام شده"),
			"fieldname": "total_cost",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": _("قیمت فروش پایه"),
			"fieldname": "selling_price",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": _("قیمت با افزایش"),
			"fieldname": "final_price_with_markup",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": _("قیمت کل قسطی"),
			"fieldname": "total_installment_amount",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": _("قیمت نهایی انتخابی"),
			"fieldname": "final_selected_price",
			"fieldtype": "Currency",
			"width": 130
		},
		{
			"label": _("مبلغ سود"),
			"fieldname": "profit_amount",
			"fieldtype": "Currency",
			"width": 100
		},
		{
			"label": _("درصد سود"),
			"fieldname": "profit_percentage",
			"fieldtype": "Percent",
			"width": 100
		},
		{
			"label": _("قیمت فعلی بازار"),
			"fieldname": "current_market_price",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": _("وضعیت سود/ضرر"),
			"fieldname": "profit_loss_status",
			"fieldtype": "Data",
			"width": 120
		}
	]

def get_data(filters):
	conditions = ""
	values = {}
	
	if filters.get("price_list"):
		# دریافت آیتم‌های لیست قیمت انتخاب شده
		price_list_items = frappe.db.sql("""
			SELECT DISTINCT ip.item_code
			FROM `tabItem Price` ip
			WHERE ip.price_list = %(price_list)s
		""", {"price_list": filters.get("price_list")}, as_dict=1)
		
		if not price_list_items:
			return []
		
		item_codes = [item.item_code for item in price_list_items]
		conditions += " AND apli.item_code IN %(item_codes)s"
		values["item_codes"] = item_codes
	
	if filters.get("auto_price_list"):
		conditions += " AND apl.name = %(auto_price_list)s"
		values["auto_price_list"] = filters.get("auto_price_list")
	
	if filters.get("item_group"):
		conditions += " AND apli.item_group = %(item_group)s"
		values["item_group"] = filters.get("item_group")
	
	if filters.get("from_date"):
		conditions += " AND apl.valid_from >= %(from_date)s"
		values["from_date"] = filters.get("from_date")
	
	if filters.get("to_date"):
		conditions += " AND apl.valid_until <= %(to_date)s"
		values["to_date"] = filters.get("to_date")
	
	data = frappe.db.sql(f"""
		SELECT 
			apli.item_code,
			apli.item_name,
			apli.item_group,
			apli.raw_material_cost,
			apli.electricity_cost,
			apli.consumable_cost,
			apli.rent_cost,
			apli.labor_cost,
			apli.operation_cost,
			apli.overhead_cost,
			apli.total_cost,
			apli.selling_price,
			apli.final_price_with_markup,
			apli.total_installment_amount,
			apli.final_selected_price,
			apli.profit_amount,
			CASE 
				WHEN apli.total_cost > 0 THEN (apli.profit_amount / apli.total_cost) * 100
				ELSE 0
			END as profit_percentage,
			apli.current_market_price,
			apli.profit_loss_status,
			apl.name as auto_price_list_name,
			apl.price_list,
			apl.selected_price_type
		FROM `tabAuto Price List Item` apli
		INNER JOIN `tabAuto Price List` apl ON apli.parent = apl.name
		WHERE apl.docstatus = 1 {conditions}
		ORDER BY apl.modified DESC, apli.item_code
	""", values, as_dict=1)
	
	return data

def get_report_summary(data):
	if not data:
		return []
	
	total_items = len(data)
	total_cost = sum(flt(row.get("total_cost", 0)) for row in data)
	total_selling = sum(flt(row.get("final_selected_price", 0)) for row in data)
	total_profit = total_selling - total_cost
	avg_profit_margin = (total_profit / total_cost * 100) if total_cost > 0 else 0
	
	profitable_items = len([row for row in data if row.get("profit_loss_status") == "سودآور"])
	loss_items = len([row for row in data if row.get("profit_loss_status") == "ضررآور"])
	
	return [
		{
			"value": total_items,
			"label": "تعداد کل کالاها",
			"datatype": "Int"
		},
		{
			"value": total_cost,
			"label": "مجموع بهای تمام شده",
			"datatype": "Currency"
		},
		{
			"value": total_selling,
			"label": "مجموع قیمت فروش",
			"datatype": "Currency"
		},
		{
			"value": total_profit,
			"label": "مجموع سود",
			"datatype": "Currency"
		},
		{
			"value": avg_profit_margin,
			"label": "میانگین حاشیه سود (%)",
			"datatype": "Percent"
		},
		{
			"value": profitable_items,
			"label": "کالاهای سودآور",
			"datatype": "Int"
		},
		{
			"value": loss_items,
			"label": "کالاهای ضررآور",
			"datatype": "Int"
		}
	]
