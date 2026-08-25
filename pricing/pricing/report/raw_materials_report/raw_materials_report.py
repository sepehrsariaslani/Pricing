# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
    """
    گزارش مواد اولیه خام
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
            "label": _("کد ماده"),
            "fieldtype": "Link",
            "options": "Item",
            "width": 120
        },
        {
            "fieldname": "item_name",
            "label": _("نام ماده"),
            "fieldtype": "Data",
            "width": 200
        },
        {
            "fieldname": "uom",
            "label": _("واحد"),
            "fieldtype": "Link",
            "options": "UOM",
            "width": 80
        },
        {
            "fieldname": "rate",
            "label": _("قیمت واحد"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "status",
            "label": _("وضعیت قیمت"),
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "bom_count",
            "label": _("تعداد BOM"),
            "fieldtype": "Int",
            "width": 100
        },
        {
            "fieldname": "total_qty",
            "label": _("مقدار کل"),
            "fieldtype": "Float",
            "width": 100
        }
    ]

def get_data(filters):
    """
    دریافت داده‌های گزارش - رفتن به سطح آخر BOM و استخراج تمام مواد اولیه خام
    """
    if not filters or not filters.get("auto_price_list"):
        return []
    
    try:
        # دریافت سند Auto Price List
        doc = frappe.get_doc("Auto Price List", filters.get("auto_price_list"))
        
        if not doc.items:
            return []
        
        # جمع‌آوری تمام مواد اولیه از BOMهای موجود
        materials = {}
        processed_items_count = 0
        bom_found_count = 0
        
        for item in doc.items:
            if not item.item_code:
                continue
            
            processed_items_count += 1
            
            # پیدا کردن BOM فعال
            bom = frappe.db.get_value("BOM", {
                "item": item.item_code,
                "is_active": 1,
                "is_default": 1
            }, ["name"])
            
            if not bom:
                # سعی کن هر BOM فعالی را پیدا کن (حتی اگر default نباشد)
                bom = frappe.db.get_value("BOM", {
                    "item": item.item_code,
                    "is_active": 1
                }, ["name"], order_by="modified desc")
            
            if not bom:
                # اگر BOM نداشت، خود این آیتم یک ماده خام است
                
                # دریافت قیمت این آیتم
                latest_price = frappe.db.get_value("Item Price", {
                    "item_code": item.item_code,
                    "price_list": doc.price_list
                }, ["price_list_rate"], order_by="modified desc")
                
                if not latest_price:
                    latest_price = frappe.db.get_value("Item Price", {
                        "item_code": item.item_code
                    }, ["price_list_rate"], order_by="modified desc")
                
                # اضافه کردن به لیست مواد
                if item.item_code not in materials:
                    materials[item.item_code] = {
                        "item_code": item.item_code,
                        "item_name": item.item_name or "",
                        "uom": frappe.db.get_value("Item", item.item_code, "stock_uom") or "",
                        "rate": latest_price or 0,
                        "status": "دارای قیمت" if latest_price and latest_price > 0 else "بدون قیمت",
                        "bom_count": 1,
                        "total_qty": 1
                    }
                
                continue
            
            bom_found_count += 1
            
            # استفاده از روش بازگشتی برای دریافت تمام مواد اولیه از همه سطوح
            raw_materials = get_raw_materials_recursive(bom, set())
            
            # اضافه کردن مواد به دیکشنری نهایی
            for raw_mat in raw_materials:
                item_code = raw_mat.get("item_code")
                
                if item_code not in materials:
                    # دریافت آخرین قیمت
                    latest_price = frappe.db.get_value("Item Price", {
                        "item_code": item_code,
                        "price_list": doc.price_list
                    }, ["price_list_rate"], order_by="modified desc")
                    
                    if not latest_price:
                        latest_price = frappe.db.get_value("Item Price", {
                            "item_code": item_code
                        }, ["price_list_rate"], order_by="modified desc")
                    
                    # دریافت اطلاعات آیتم
                    item_info = frappe.db.get_value("Item", item_code, 
                        ["item_name", "stock_uom"], as_dict=1) or {}
                    
                    materials[item_code] = {
                        "item_code": item_code,
                        "item_name": raw_mat.get("item_name") or item_info.get("item_name", ""),
                        "uom": raw_mat.get("stock_uom") or raw_mat.get("uom") or item_info.get("stock_uom", ""),
                        "rate": latest_price or 0,
                        "status": "دارای قیمت" if latest_price and latest_price > 0 else "بدون قیمت",
                        "bom_count": 1,
                        "total_qty": raw_mat.get("qty", 0)
                    }
                else:
                    # اگر ماده قبلاً وجود داشت، تعداد BOM و مقدار را به‌روزرسانی کن
                    materials[item_code]["bom_count"] += 1
                    materials[item_code]["total_qty"] += raw_mat.get("qty", 0)
        
        # تبدیل به لیست و مرتب‌سازی
        data = list(materials.values())
        data.sort(key=lambda x: x["item_code"])
        
        return data
        
    except Exception as e:
        import traceback
        frappe.logger().error(f"خطا در گزارش مواد اولیه: {traceback.format_exc()}")
        return []

def get_raw_materials_recursive(bom_name, processed_boms):
    """
    دریافت مواد اولیه خام به صورت بازگشتی از BOM
    """
    if bom_name in processed_boms:
        return []
    
    processed_boms.add(bom_name)
    raw_materials = []
    
    try:
        # دریافت تمام items این BOM
        bom_items = frappe.get_all("BOM Item", {
            "parent": bom_name
        }, ["item_code", "item_name", "qty", "uom", "rate"])
        
        for bom_item in bom_items:
            item_code = bom_item.item_code
            
            # چک کردن آیا این item خودش BOM دارد
            sub_bom = frappe.db.get_value("BOM", {
                "item": item_code,
                "is_active": 1,
                "is_default": 1
            }, ["name"])
            
            if sub_bom:
                # اگر BOM دارد، به صورت بازگشتی مواد آن را بگیر
                sub_materials = get_raw_materials_recursive(sub_bom, processed_boms)
                # ضریب مقدار را اعمال کن
                for mat in sub_materials:
                    mat["qty"] = mat.get("qty", 0) * bom_item.qty
                raw_materials.extend(sub_materials)
            else:
                # اگر BOM ندارد، خودش ماده خام است
                raw_materials.append({
                    "item_code": item_code,
                    "item_name": bom_item.item_name,
                    "qty": bom_item.qty,
                    "uom": bom_item.uom,
                    "stock_uom": bom_item.uom,
                    "rate": bom_item.rate
                })
        
        return raw_materials
        
    except Exception as e:
        frappe.log_error(f"خطا در get_raw_materials_recursive برای {bom_name}: {str(e)}")
        return []
