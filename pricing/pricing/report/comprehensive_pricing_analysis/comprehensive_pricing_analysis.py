# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, cint
import math

def execute(filters=None):
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data

def get_columns(filters):
    columns = [
        {
            "label": "کد کالا",
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 120
        },
        {
            "label": "نام کالا",
            "fieldname": "item_name",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": "گروه کالا",
            "fieldname": "item_group",
            "fieldtype": "Link",
            "options": "Item Group",
            "width": 120
        }
    ]
    
    # اضافه کردن ستون‌های لیست قیمت‌های انتخاب شده
    if filters.get("price_lists"):
        if isinstance(filters.get("price_lists"), list):
            price_lists = filters.get("price_lists")
        else:
            price_lists = filters.get("price_lists").split(",")
        for price_list in price_lists:
            price_list = price_list.strip()
            columns.extend([
                {
                    "label": f"قیمت - {price_list}",
                    "fieldname": f"price_{price_list.replace(' ', '_')}",
                    "fieldtype": "Currency",
                    "width": 120
                },
                {
                    "label": f"سود - {price_list}",
                    "fieldname": f"profit_{price_list.replace(' ', '_')}",
                    "fieldtype": "Currency",
                    "width": 100
                },
                {
                    "label": f"درصد سود - {price_list}",
                    "fieldname": f"profit_pct_{price_list.replace(' ', '_')}",
                    "fieldtype": "Percent",
                    "width": 100
                }
            ])
    
    # اضافه کردن ستون‌های هزینه
    columns.extend([
        {
            "label": "هزینه مواد اولیه",
            "fieldname": "raw_material_cost",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": "هزینه برق",
            "fieldname": "electricity_cost",
            "fieldtype": "Currency",
            "width": 100
        },
        {
            "label": "هزینه مصرفی",
            "fieldname": "consumable_cost",
            "fieldtype": "Currency",
            "width": 100
        },
        {
            "label": "هزینه اجاره",
            "fieldname": "rent_cost",
            "fieldtype": "Currency",
            "width": 100
        },
        {
            "label": "هزینه نیروی کار",
            "fieldname": "labor_cost",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": "هزینه عملیات",
            "fieldname": "operation_cost",
            "fieldtype": "Currency",
            "width": 100
        },
        {
            "label": "هزینه سربار",
            "fieldname": "overhead_cost",
            "fieldtype": "Currency",
            "width": 100
        },
        {
            "label": "مجموع هزینه",
            "fieldname": "total_cost",
            "fieldtype": "Currency",
            "width": 120
        }
    ])
    
    # اضافه کردن ستون قیمت قسطی اگر فعال باشد
    if filters.get("enable_installment"):
        columns.extend([
            {
                "label": "قیمت با بهره",
                "fieldname": "installment_price",
                "fieldtype": "Currency",
                "width": 120
            },
            {
                "label": "پیش پرداخت",
                "fieldname": "down_payment",
                "fieldtype": "Currency",
                "width": 100
            },
            {
                "label": "قسط ماهانه",
                "fieldname": "monthly_payment",
                "fieldtype": "Currency",
                "width": 100
            },
            {
                "label": "مجموع بهره",
                "fieldname": "total_interest",
                "fieldtype": "Currency",
                "width": 100
            }
        ])
    
    return columns

def get_data(filters):
    conditions = get_conditions(filters)
    
    # دریافت کالاها
    items_query = f"""
        SELECT 
            i.item_code,
            i.item_name,
            i.item_group,
            i.standard_rate
        FROM `tabItem` i
        WHERE i.disabled = 0
        {conditions}
        ORDER BY i.item_code
    """
    
    items = frappe.db.sql(items_query, filters, as_dict=1)
    
    data = []
    for item in items:
        row = {
            "item_code": item.item_code,
            "item_name": item.item_name,
            "item_group": item.item_group
        }
        
        # محاسبه هزینه‌ها از BOM
        cost_data = get_item_costs(item.item_code)
        row.update(cost_data)
        
        # دریافت قیمت‌ها از لیست‌های قیمت انتخاب شده
        if filters.get("price_lists"):
            if isinstance(filters.get("price_lists"), list):
                price_lists = filters.get("price_lists")
            else:
                price_lists = filters.get("price_lists").split(",")
            for price_list in price_lists:
                price_list = price_list.strip()
                price = get_item_price(item.item_code, price_list)
                
                field_suffix = price_list.replace(' ', '_')
                row[f"price_{field_suffix}"] = price
                
                # اعمال رند کردن قیمت
                if filters.get("price_rounding_amount") and price > 0:
                    rounding_amount = flt(filters.get("price_rounding_amount"))
                    if rounding_amount > 0:
                        price = math.ceil(price / rounding_amount) * rounding_amount
                        row[f"price_{field_suffix}"] = price
                
                # محاسبه سود
                if price and row.get("total_cost"):
                    profit = price - row["total_cost"]
                    profit_pct = (profit / row["total_cost"]) * 100 if row["total_cost"] > 0 else 0
                    row[f"profit_{field_suffix}"] = profit
                    row[f"profit_pct_{field_suffix}"] = profit_pct
        
        # محاسبه قیمت قسطی
        if filters.get("enable_installment"):
            installment_data = calculate_installment_price(
                row.get("total_cost", 0),
                filters
            )
            row.update(installment_data)
        
        data.append(row)
    
    return data

def get_conditions(filters):
    conditions = ""
    
    if filters.get("item_group"):
        conditions += " AND i.item_group = %(item_group)s"
    
    if filters.get("brand"):
        conditions += " AND i.brand = %(brand)s"
    
    if filters.get("item_code"):
        conditions += " AND i.item_code = %(item_code)s"
    
    return conditions

def get_item_costs(item_code):
    """محاسبه هزینه‌های کالا از BOM"""
    
    # دریافت BOM فعال
    bom = frappe.db.get_value("BOM", {
        "item": item_code,
        "is_active": 1,
        "is_default": 1
    }, ["name", "raw_material_cost", "operating_cost"], as_dict=1)
    
    if not bom:
        return {
            "raw_material_cost": 0,
            "electricity_cost": 0,
            "consumable_cost": 0,
            "rent_cost": 0,
            "labor_cost": 0,
            "operation_cost": 0,
            "overhead_cost": 0,
            "total_cost": 0
        }
    
    # محاسبه هزینه مواد اولیه
    raw_material_cost = flt(bom.raw_material_cost)
    
    # محاسبه هزینه عملیات
    operation_cost = flt(bom.operating_cost)
    
    # محاسبه سایر هزینه‌ها (می‌توان از تنظیمات یا جداول مخصوص دریافت کرد)
    electricity_cost = raw_material_cost * 0.05  # 5% از مواد اولیه
    consumable_cost = raw_material_cost * 0.03   # 3% از مواد اولیه
    rent_cost = raw_material_cost * 0.02         # 2% از مواد اولیه
    labor_cost = operation_cost * 0.6            # 60% از هزینه عملیات
    overhead_cost = (raw_material_cost + operation_cost) * 0.1  # 10% سربار
    
    total_cost = (raw_material_cost + electricity_cost + consumable_cost + 
                 rent_cost + labor_cost + operation_cost + overhead_cost)
    
    return {
        "raw_material_cost": raw_material_cost,
        "electricity_cost": electricity_cost,
        "consumable_cost": consumable_cost,
        "rent_cost": rent_cost,
        "labor_cost": labor_cost,
        "operation_cost": operation_cost,
        "overhead_cost": overhead_cost,
        "total_cost": total_cost
    }

def get_item_price(item_code, price_list):
    """دریافت قیمت کالا از لیست قیمت"""
    price = frappe.db.get_value("Item Price", {
        "item_code": item_code,
        "price_list": price_list
    }, "price_list_rate")
    
    return flt(price) if price else 0

def calculate_installment_price(base_cost, filters):
    """محاسبه قیمت قسطی با بهره"""
    
    if not filters.get("enable_installment"):
        return {}
    
    # محاسبه قیمت فروش با حاشیه سود
    profit_margin = flt(filters.get("profit_margin", 20))  # 20% پیش‌فرض
    selling_price = base_cost * (1 + profit_margin / 100)
    
    # پارامترهای قسط
    down_payment_pct = flt(filters.get("down_payment_percentage", 20))
    months = cint(filters.get("number_of_months", 12))
    monthly_rate = flt(filters.get("monthly_interest_rate", 2)) / 100
    
    # محاسبه پیش پرداخت
    down_payment = selling_price * (down_payment_pct / 100)
    financed_amount = selling_price - down_payment
    
    if months <= 0 or monthly_rate <= 0:
        return {
            "installment_price": selling_price,
            "down_payment": down_payment,
            "monthly_payment": financed_amount / months if months > 0 else 0,
            "total_interest": 0
        }
    
    # محاسبه قسط ماهانه با بهره مرکب
    monthly_payment = financed_amount * (monthly_rate * (1 + monthly_rate)**months) / ((1 + monthly_rate)**months - 1)
    total_payments = monthly_payment * months
    total_amount = down_payment + total_payments
    total_interest = total_amount - selling_price
    
    return {
        "installment_price": total_amount,
        "down_payment": down_payment,
        "monthly_payment": monthly_payment,
        "total_interest": total_interest
    }
