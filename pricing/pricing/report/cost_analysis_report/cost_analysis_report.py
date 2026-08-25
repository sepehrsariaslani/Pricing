# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
    """
    گزارش تحلیل هزینه‌های تولید
    """
    columns = get_columns()
    data = get_data(filters)
    
    return columns, data

def get_columns():
    """
    تعریف ستون‌های گزارش
    """
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
            "fieldname": "raw_material_cost",
            "label": _("هزینه مواد اولیه"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "operation_cost",
            "label": _("هزینه عملیات"),
            "fieldtype": "Currency", 
            "width": 120
        },
        {
            "fieldname": "overhead_cost",
            "label": _("هزینه سربار"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "total_cost",
            "label": _("کل هزینه"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "selling_price",
            "label": _("قیمت فروش"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "profit",
            "label": _("سود"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "profit_percentage",
            "label": _("درصد سود"),
            "fieldtype": "Percent",
            "width": 100
        }
    ]

def get_data(filters):
    """
    دریافت داده‌های گزارش
    """
    if not filters or not filters.get("auto_price_list"):
        return []
    
    try:
        # دریافت سند Auto Price List
        doc = frappe.get_doc("Auto Price List", filters.get("auto_price_list"))
        
        if not doc.items:
            return []
        
        data = []
        
        for item in doc.items:
            raw_cost = flt(item.raw_material_cost or 0)
            op_cost = flt(item.operation_cost or 0) 
            oh_cost = flt(item.overhead_cost or 0)
            total_cost = raw_cost + op_cost + oh_cost
            selling_price = flt(item.selling_price or 0)
            profit = selling_price - total_cost
            profit_percentage = (profit / selling_price * 100) if selling_price > 0 else 0
            
            data.append({
                "item_code": item.item_code,
                "item_name": item.item_name or item.item_code,
                "raw_material_cost": raw_cost,
                "operation_cost": op_cost,
                "overhead_cost": oh_cost,
                "total_cost": total_cost,
                "selling_price": selling_price,
                "profit": profit,
                "profit_percentage": profit_percentage
            })
        
        return data
        
    except Exception as e:
        frappe.log_error(f"خطا در گزارش تحلیل هزینه: {str(e)}")
        return []
