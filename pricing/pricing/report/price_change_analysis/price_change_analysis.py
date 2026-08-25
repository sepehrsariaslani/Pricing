# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, cstr


def execute(filters=None):
    """
    گزارش تحلیل تغییرات قیمت
    نمایش قیمت تمام شده قبل و بعد از تغییرات با محصولات جایگزین
    """
    columns = get_columns()
    data = get_data(filters)
    
    return columns, data


def get_columns():
    """تعریف ستون‌های گزارش"""
    return [
        {
            "fieldname": "item_code",
            "label": _("کد کالا"),
            "fieldtype": "Link",
            "options": "Item",
            "width": 120
        },
        {
            "fieldname": "item_name",
            "label": _("نام کالا"),
            "fieldtype": "Data",
            "width": 200
        },
        {
            "fieldname": "item_group",
            "label": _("گروه کالا"),
            "fieldtype": "Link",
            "options": "Item Group",
            "width": 120
        },
        {
            "fieldname": "uom",
            "label": _("واحد"),
            "fieldtype": "Link",
            "options": "UOM",
            "width": 80
        },
        {
            "fieldname": "previous_total_cost",
            "label": _("بهای تمام شده قبلی"),
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "fieldname": "current_total_cost",
            "label": _("بهای تمام شده فعلی"),
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "fieldname": "cost_change",
            "label": _("تغییر هزینه"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "cost_change_percent",
            "label": _("درصد تغییر"),
            "fieldtype": "Percent",
            "width": 100
        },
        {
            "fieldname": "previous_selling_price",
            "label": _("قیمت فروش قبلی"),
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "fieldname": "current_selling_price",
            "label": _("قیمت فروش فعلی"),
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "fieldname": "price_change",
            "label": _("تغییر قیمت فروش"),
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "fieldname": "substitute_items",
            "label": _("محصولات جایگزین"),
            "fieldtype": "Data",
            "width": 200
        },
        {
            "fieldname": "substitute_avg_price",
            "label": _("متوسط قیمت جایگزین"),
            "fieldtype": "Currency",
            "width": 140
        },
        {
            "fieldname": "competitive_status",
            "label": _("وضعیت رقابتی"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "change_reason",
            "label": _("دلیل تغییر"),
            "fieldtype": "Data",
            "width": 150
        }
    ]


def get_data(filters):
    """دریافت داده‌های گزارش"""
    conditions = get_conditions(filters)
    
    # دریافت داده‌های اصلی از Auto Price List
    data = frappe.db.sql(f"""
        SELECT 
            apl.name as auto_price_list,
            apli.item_code,
            apli.item_name,
            i.item_group,
            i.stock_uom as uom,
            apli.total_cost as current_total_cost,
            apli.final_selected_price as current_selling_price,
            apli.raw_material_cost,
            apli.operation_cost,
            apli.overhead_cost,
            apli.electricity_cost,
            apli.rent_cost,
            apli.labor_cost,
            apli.consumable_cost,
            apli.subcontracting_cost
        FROM `tabAuto Price List` apl
        INNER JOIN `tabAuto Price List Item` apli ON apl.name = apli.parent
        INNER JOIN `tabItem` i ON apli.item_code = i.name
        WHERE apl.docstatus = 1 {conditions}
        ORDER BY apli.item_code
    """, as_dict=True)
    
    result = []
    
    for row in data:
        # دریافت قیمت‌های قبلی از Item Price
        previous_data = get_previous_pricing_data(row.item_code)
        
        # محاسبه تغییرات
        cost_change = flt(row.current_total_cost) - flt(previous_data.get('previous_total_cost', 0))
        cost_change_percent = 0
        if previous_data.get('previous_total_cost'):
            cost_change_percent = (cost_change / flt(previous_data['previous_total_cost'])) * 100
        
        price_change = flt(row.current_selling_price) - flt(previous_data.get('previous_selling_price', 0))
        
        # دریافت محصولات جایگزین
        substitute_data = get_substitute_items(row.item_code, row.item_group)
        
        # تعیین وضعیت رقابتی
        competitive_status = determine_competitive_status(
            row.current_selling_price, 
            substitute_data.get('avg_price', 0)
        )
        
        # تعیین دلیل تغییر
        change_reason = determine_change_reason(row, previous_data)
        
        result.append({
            'item_code': row.item_code,
            'item_name': row.item_name,
            'item_group': row.item_group,
            'uom': row.uom,
            'previous_total_cost': previous_data.get('previous_total_cost', 0),
            'current_total_cost': row.current_total_cost,
            'cost_change': cost_change,
            'cost_change_percent': cost_change_percent,
            'previous_selling_price': previous_data.get('previous_selling_price', 0),
            'current_selling_price': row.current_selling_price,
            'price_change': price_change,
            'substitute_items': substitute_data.get('items_list', ''),
            'substitute_avg_price': substitute_data.get('avg_price', 0),
            'competitive_status': competitive_status,
            'change_reason': change_reason
        })
    
    return result


def get_conditions(filters):
    """ایجاد شرایط فیلتر"""
    conditions = ""
    
    if filters.get("auto_price_list"):
        conditions += f" AND apl.name = '{filters['auto_price_list']}'"
    
    if filters.get("item_code"):
        conditions += f" AND apli.item_code = '{filters['item_code']}'"
    
    if filters.get("item_group"):
        conditions += f" AND i.item_group = '{filters['item_group']}'"
    
    if filters.get("from_date"):
        conditions += f" AND apl.creation >= '{filters['from_date']}'"
    
    if filters.get("to_date"):
        conditions += f" AND apl.creation <= '{filters['to_date']}'"
    
    return conditions


def get_previous_pricing_data(item_code):
    """دریافت داده‌های قیمت‌گذاری قبلی از Item Price"""
    try:
        # دریافت آخرین قیمت از Item Price
        previous_price = frappe.db.sql("""
            SELECT 
                price_list_rate as previous_selling_price,
                total_cost as previous_total_cost,
                raw_material_cost,
                operation_cost,
                overhead_cost
            FROM `tabItem Price`
            WHERE item_code = %s
            ORDER BY modified DESC
            LIMIT 1
        """, (item_code,), as_dict=True)
        
        if previous_price:
            return previous_price[0]
        
        # اگر در Item Price نبود، از Item master بگیر
        item_data = frappe.db.get_value("Item", item_code, 
                                       ["standard_rate"], as_dict=True)
        
        return {
            'previous_selling_price': item_data.get('standard_rate', 0) if item_data else 0,
            'previous_total_cost': 0
        }
        
    except Exception as e:
        frappe.logger().error(f"خطا در دریافت داده‌های قبلی {item_code}: {str(e)}")
        return {'previous_selling_price': 0, 'previous_total_cost': 0}


def get_substitute_items(item_code, item_group):
    """دریافت محصولات جایگزین و متوسط قیمت آنها"""
    try:
        # جستجو برای آیتم‌های مشابه در همان گروه
        substitutes = frappe.db.sql("""
            SELECT 
                i.item_code,
                i.item_name,
                COALESCE(ip.price_list_rate, i.standard_rate, 0) as price
            FROM `tabItem` i
            LEFT JOIN `tabItem Price` ip ON i.item_code = ip.item_code
            WHERE i.item_group = %s 
            AND i.item_code != %s
            AND i.disabled = 0
            AND (ip.price_list_rate > 0 OR i.standard_rate > 0)
            ORDER BY price
            LIMIT 5
        """, (item_group, item_code), as_dict=True)
        
        if not substitutes:
            return {'items_list': '', 'avg_price': 0}
        
        # محاسبه متوسط قیمت
        total_price = sum(flt(sub.price) for sub in substitutes)
        avg_price = total_price / len(substitutes) if substitutes else 0
        
        # ایجاد لیست نام‌ها
        items_list = ', '.join([sub.item_code for sub in substitutes[:3]])
        if len(substitutes) > 3:
            items_list += f" و {len(substitutes) - 3} مورد دیگر"
        
        return {
            'items_list': items_list,
            'avg_price': avg_price
        }
        
    except Exception as e:
        frappe.logger().error(f"خطا در دریافت محصولات جایگزین {item_code}: {str(e)}")
        return {'items_list': '', 'avg_price': 0}


def determine_competitive_status(current_price, substitute_avg_price):
    """تعیین وضعیت رقابتی"""
    if not substitute_avg_price:
        return "بدون رقیب"
    
    price_diff_percent = ((flt(current_price) - flt(substitute_avg_price)) / flt(substitute_avg_price)) * 100
    
    if price_diff_percent <= -10:
        return "بسیار رقابتی"
    elif price_diff_percent <= -5:
        return "رقابتی"
    elif price_diff_percent <= 5:
        return "متعادل"
    elif price_diff_percent <= 15:
        return "گران"
    else:
        return "بسیار گران"


def determine_change_reason(current_data, previous_data):
    """تعیین دلیل اصلی تغییر قیمت"""
    reasons = []
    
    # بررسی تغییر مواد اولیه
    prev_material = flt(previous_data.get('raw_material_cost', 0))
    curr_material = flt(current_data.get('raw_material_cost', 0))
    if abs(curr_material - prev_material) > 100:  # تغییر بیش از 100 واحد
        if curr_material > prev_material:
            reasons.append("افزایش مواد اولیه")
        else:
            reasons.append("کاهش مواد اولیه")
    
    # بررسی تغییر هزینه‌های عملیاتی
    prev_operation = flt(previous_data.get('operation_cost', 0))
    curr_operation = flt(current_data.get('operation_cost', 0))
    if abs(curr_operation - prev_operation) > 50:
        if curr_operation > prev_operation:
            reasons.append("افزایش هزینه عملیات")
        else:
            reasons.append("کاهش هزینه عملیات")
    
    # بررسی تغییر سربار
    prev_overhead = flt(previous_data.get('overhead_cost', 0))
    curr_overhead = flt(current_data.get('overhead_cost', 0))
    if abs(curr_overhead - prev_overhead) > 50:
        if curr_overhead > prev_overhead:
            reasons.append("افزایش سربار")
        else:
            reasons.append("کاهش سربار")
    
    if not reasons:
        return "تغییر جزئی"
    
    return " + ".join(reasons[:2])  # حداکثر 2 دلیل اصلی
