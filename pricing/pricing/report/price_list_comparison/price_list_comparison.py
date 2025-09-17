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
			"label": _("هزینه خدمات و پیمانکاری"),
			"fieldname": "operation_cost",
			"fieldtype": "Currency",
			"width": 140
		},
		{
			"label": _("بهای تمام شده"),
			"fieldname": "total_cost",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": _("قیمت لیست اول"),
			"fieldname": "price_list_1_rate",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": _("قیمت لیست دوم"),
			"fieldname": "price_list_2_rate",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": _("تفاوت قیمت"),
			"fieldname": "price_difference",
			"fieldtype": "Currency",
			"width": 100
		},
		{
			"label": _("درصد تغییر"),
			"fieldname": "price_change_percentage",
			"fieldtype": "Percent",
			"width": 100
		},
		{
			"label": _("سود لیست اول"),
			"fieldname": "profit_list_1",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": _("سود لیست دوم"),
			"fieldname": "profit_list_2",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": _("وضعیت لیست اول"),
			"fieldname": "status_list_1",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": _("وضعیت لیست دوم"),
			"fieldname": "status_list_2",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": _("توصیه"),
			"fieldname": "recommendation",
			"fieldtype": "Data",
			"width": 150
		}
	]

def get_data(filters):
	if not filters.get("price_list_1") or not filters.get("price_list_2"):
		frappe.throw(_("لطفاً هر دو لیست قیمت را انتخاب کنید"))
	
	# دریافت آیتم‌های مشترک در هر دو لیست قیمت
	common_items_query = """
		SELECT DISTINCT 
			ip1.item_code,
			i.item_name,
			i.item_group,
			ip1.price_list_rate as price_list_1_rate,
			ip2.price_list_rate as price_list_2_rate
		FROM `tabItem Price` ip1
		INNER JOIN `tabItem Price` ip2 ON ip1.item_code = ip2.item_code
		INNER JOIN `tabItem` i ON ip1.item_code = i.item_code
		WHERE ip1.price_list = %(price_list_1)s
		AND ip2.price_list = %(price_list_2)s
		AND i.disabled = 0
	"""
	
	conditions = ""
	values = {
		"price_list_1": filters.get("price_list_1"),
		"price_list_2": filters.get("price_list_2")
	}
	
	if filters.get("item_group"):
		conditions += " AND i.item_group = %(item_group)s"
		values["item_group"] = filters.get("item_group")
	
	if filters.get("item_code"):
		conditions += " AND ip1.item_code = %(item_code)s"
		values["item_code"] = filters.get("item_code")
	
	common_items_query += conditions + " ORDER BY i.item_name"
	
	items_data = frappe.db.sql(common_items_query, values, as_dict=1)
	
	if not items_data:
		return []
	
	# دریافت اطلاعات هزینه از آخرین Auto Price List
	item_codes = [item.item_code for item in items_data]
	
	cost_data = {}
	if item_codes:
		cost_query = """
			SELECT 
				apli.item_code,
				apli.raw_material_cost,
				apli.rent_cost,
				apli.labor_cost,
				apli.operation_cost,
				apli.total_cost
			FROM `tabAuto Price List Item` apli
			INNER JOIN `tabAuto Price List` apl ON apli.parent = apl.name
			WHERE apli.item_code IN %(item_codes)s
			AND apl.docstatus = 1
			ORDER BY apl.modified DESC
		"""
		
		cost_results = frappe.db.sql(cost_query, {"item_codes": item_codes}, as_dict=1)
		
		# گروه‌بندی بر اساس item_code و گرفتن آخرین رکورد
		for cost in cost_results:
			if cost.item_code not in cost_data:
				cost_data[cost.item_code] = cost
	
	# ترکیب داده‌ها و محاسبه متریک‌ها
	final_data = []
	for item in items_data:
		item_code = item.item_code
		cost_info = cost_data.get(item_code, {})
		
		price_1 = flt(item.price_list_1_rate)
		price_2 = flt(item.price_list_2_rate)
		total_cost = flt(cost_info.get("total_cost", 0))
		
		# محاسبه تفاوت قیمت
		price_difference = price_2 - price_1
		price_change_percentage = (price_difference / price_1 * 100) if price_1 > 0 else 0
		
		# محاسبه سود
		profit_list_1 = price_1 - total_cost if total_cost > 0 else 0
		profit_list_2 = price_2 - total_cost if total_cost > 0 else 0
		
		# تعیین وضعیت
		status_list_1 = "سودآور" if profit_list_1 >= 0 else "ضررآور"
		status_list_2 = "سودآور" if profit_list_2 >= 0 else "ضررآور"
		
		# توصیه
		recommendation = ""
		if profit_list_1 < 0 and profit_list_2 < 0:
			recommendation = "هر دو قیمت ضررآور - بازنگری لازم"
		elif profit_list_1 < 0 and profit_list_2 >= 0:
			recommendation = "لیست دوم بهتر"
		elif profit_list_1 >= 0 and profit_list_2 < 0:
			recommendation = "لیست اول بهتر"
		elif price_change_percentage > 20:
			recommendation = "افزایش قیمت زیاد"
		elif price_change_percentage < -20:
			recommendation = "کاهش قیمت زیاد"
		else:
			recommendation = "قیمت‌گذاری مناسب"
		
		row = {
			"item_code": item_code,
			"item_name": item.item_name,
			"item_group": item.item_group,
			"raw_material_cost": cost_info.get("raw_material_cost", 0),
			"rent_cost": cost_info.get("rent_cost", 0),
			"labor_cost": cost_info.get("labor_cost", 0),
			"operation_cost": cost_info.get("operation_cost", 0),
			"total_cost": total_cost,
			"price_list_1_rate": price_1,
			"price_list_2_rate": price_2,
			"price_difference": price_difference,
			"price_change_percentage": price_change_percentage,
			"profit_list_1": profit_list_1,
			"profit_list_2": profit_list_2,
			"status_list_1": status_list_1,
			"status_list_2": status_list_2,
			"recommendation": recommendation
		}
		
		final_data.append(row)
	
	return final_data

def get_report_summary(data):
	if not data:
		return []
	
	total_items = len(data)
	
	# آمار لیست اول
	profitable_list_1 = len([row for row in data if row.get("status_list_1") == "سودآور"])
	loss_list_1 = len([row for row in data if row.get("status_list_1") == "ضررآور"])
	avg_profit_1 = sum(flt(row.get("profit_list_1", 0)) for row in data) / total_items if total_items > 0 else 0
	
	# آمار لیست دوم
	profitable_list_2 = len([row for row in data if row.get("status_list_2") == "سودآور"])
	loss_list_2 = len([row for row in data if row.get("status_list_2") == "ضررآور"])
	avg_profit_2 = sum(flt(row.get("profit_list_2", 0)) for row in data) / total_items if total_items > 0 else 0
	
	# تغییرات قیمت
	avg_price_change = sum(flt(row.get("price_change_percentage", 0)) for row in data) / total_items if total_items > 0 else 0
	price_increases = len([row for row in data if flt(row.get("price_change_percentage", 0)) > 0])
	price_decreases = len([row for row in data if flt(row.get("price_change_percentage", 0)) < 0])
	
	return [
		{
			"value": total_items,
			"label": "تعداد کل کالاها",
			"datatype": "Int"
		},
		{
			"value": profitable_list_1,
			"label": "کالاهای سودآور لیست اول",
			"datatype": "Int"
		},
		{
			"value": profitable_list_2,
			"label": "کالاهای سودآور لیست دوم",
			"datatype": "Int"
		},
		{
			"value": avg_profit_1,
			"label": "میانگین سود لیست اول",
			"datatype": "Currency"
		},
		{
			"value": avg_profit_2,
			"label": "میانگین سود لیست دوم",
			"datatype": "Currency"
		},
		{
			"value": avg_price_change,
			"label": "میانگین تغییر قیمت (%)",
			"datatype": "Percent"
		},
		{
			"value": price_increases,
			"label": "کالاهای گران شده",
			"datatype": "Int"
		},
		{
			"value": price_decreases,
			"label": "کالاهای ارزان شده",
			"datatype": "Int"
		}
	]
