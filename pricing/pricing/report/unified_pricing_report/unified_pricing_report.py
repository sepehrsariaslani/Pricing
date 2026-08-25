# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, cint
import math

def execute(filters=None):
    """
    گزارش جامع قیمت‌گذاری
    این گزارش ترکیبی از تمام گزارش‌های قیمت‌گذاری است
    """
    if not filters:
        filters = {}
    
    columns = get_columns(filters)
    data = get_data(filters)
    summary = get_report_summary(data, filters)
    chart = get_chart_data(data, filters)
    
    return columns, data, None, chart, summary

def get_columns(filters):
    """تعریف ستون‌های گزارش بر اساس تنظیمات"""
    columns = [
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
            "width": 180
        },
        {
            "label": _("گروه کالا"),
            "fieldname": "item_group",
            "fieldtype": "Link",
            "options": "Item Group",
            "width": 120
        }
    ]
    
    # ستون‌های هزینه
    if filters.get("show_cost_details"):
        columns.extend([
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
                "label": _("هزینه پیمانکاری"),
                "fieldname": "subcontracting_cost",
                "fieldtype": "Currency",
                "width": 110
            },
            {
                "label": _("هزینه عملیات"),
                "fieldname": "operation_cost",
                "fieldtype": "Currency",
                "width": 110
            },
            {
                "label": _("هزینه سربار"),
                "fieldname": "overhead_cost",
                "fieldtype": "Currency",
                "width": 100
            }
        ])
    
    # ستون‌های اصلی
    columns.extend([
        {
            "label": _("بهای تمام شده"),
            "fieldname": "total_cost",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("قیمت فروش"),
            "fieldname": "selling_price",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("مبلغ سود"),
            "fieldname": "profit_amount",
            "fieldtype": "Currency",
            "width": 110
        },
        {
            "label": _("درصد سود"),
            "fieldname": "profit_percentage",
            "fieldtype": "Percent",
            "width": 90
        }
    ])
    
    # ستون‌های تخفیف و افزایش قیمت
    if filters.get("show_markup_details"):
        columns.extend([
            {
                "label": _("قیمت با افزایش"),
                "fieldname": "final_price_with_markup",
                "fieldtype": "Currency",
                "width": 120
            },
            {
                "label": _("مبلغ تخفیف"),
                "fieldname": "discount_amount",
                "fieldtype": "Currency",
                "width": 100
            }
        ])
    
    # ستون‌های کمیسیون
    if filters.get("show_commission_details"):
        columns.extend([
            {
                "label": _("کمیسیون"),
                "fieldname": "commission_amount",
                "fieldtype": "Currency",
                "width": 100
            },
            {
                "label": _("سود بعد کمیسیون"),
                "fieldname": "net_profit_after_commission",
                "fieldtype": "Currency",
                "width": 120
            }
        ])
    
    # ستون‌های قسطی
    if filters.get("show_installment_details"):
        columns.extend([
            {
                "label": _("پیش پرداخت"),
                "fieldname": "down_payment_amount",
                "fieldtype": "Currency",
                "width": 100
            },
            {
                "label": _("قسط ماهانه"),
                "fieldname": "monthly_payment",
                "fieldtype": "Currency",
                "width": 100
            },
            {
                "label": _("مجموع بهره"),
                "fieldname": "total_interest",
                "fieldtype": "Currency",
                "width": 100
            },
            {
                "label": _("قیمت قسطی"),
                "fieldname": "total_installment_amount",
                "fieldtype": "Currency",
                "width": 110
            }
        ])
    
    # ستون‌های مقایسه با بازار
    if filters.get("compare_with_price_list"):
        columns.extend([
            {
                "label": _("قیمت فعلی بازار"),
                "fieldname": "current_market_price",
                "fieldtype": "Currency",
                "width": 120
            },
            {
                "label": _("اختلاف قیمت"),
                "fieldname": "price_variance",
                "fieldtype": "Currency",
                "width": 110
            },
            {
                "label": _("وضعیت سود/ضرر"),
                "fieldname": "profit_loss_status",
                "fieldtype": "Data",
                "width": 100
            }
        ])
    
    return columns

def get_data(filters):
    """دریافت داده‌های گزارش"""
    conditions = []
    values = {}
    
    if filters.get("auto_price_list"):
        conditions.append("apl.name = %(auto_price_list)s")
        values["auto_price_list"] = filters.get("auto_price_list")
    
    if filters.get("item_group"):
        conditions.append("apli.item_group = %(item_group)s")
        values["item_group"] = filters.get("item_group")
    
    if filters.get("brand"):
        conditions.append("apli.brand = %(brand)s")
        values["brand"] = filters.get("brand")
    
    if filters.get("from_date"):
        conditions.append("apl.valid_from >= %(from_date)s")
        values["from_date"] = filters.get("from_date")
    
    if filters.get("to_date"):
        conditions.append("apl.valid_until <= %(to_date)s")
        values["to_date"] = filters.get("to_date")
    
    if filters.get("min_profit_percentage"):
        conditions.append("""
            CASE 
                WHEN apli.total_cost > 0 THEN (apli.profit_amount / apli.total_cost) * 100
                ELSE 0
            END >= %(min_profit_percentage)s
        """)
        values["min_profit_percentage"] = filters.get("min_profit_percentage")
    
    if filters.get("max_profit_percentage"):
        conditions.append("""
            CASE 
                WHEN apli.total_cost > 0 THEN (apli.profit_amount / apli.total_cost) * 100
                ELSE 0
            END <= %(max_profit_percentage)s
        """)
        values["max_profit_percentage"] = filters.get("max_profit_percentage")
    
    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)
    
    query = f"""
        SELECT 
            apl.name as auto_price_list,
            apli.item_code,
            apli.item_name,
            apli.item_group,
            apli.brand,
            apli.raw_material_cost,
            apli.electricity_cost,
            apli.consumable_cost,
            apli.rent_cost,
            apli.labor_cost,
            apli.subcontracting_cost,
            apli.operation_cost,
            apli.overhead_cost,
            apli.total_cost,
            apli.selling_price,
            apli.profit_amount,
            apli.commission_amount,
            apli.net_profit_after_commission,
            apli.final_price_with_markup,
            apli.required_markup_amount,
            apli.down_payment_amount,
            apli.monthly_payment,
            apli.total_interest,
            apli.total_installment_amount,
            apli.current_market_price,
            apli.profit_loss_status,
            apl.profit_margin,
            apl.commission_percentage,
            apl.target_discount_percentage,
            apl.required_markup_percentage,
            apl.compare_with_price_list
        FROM `tabAuto Price List` apl
        LEFT JOIN `tabAuto Price List Item` apli ON apl.name = apli.parent
        {where_clause}
        ORDER BY apl.name, apli.total_cost DESC
    """
    
    data = frappe.db.sql(query, values, as_dict=1)
    
    # پردازش اضافی داده‌ها
    compare_price_list = filters.get("compare_with_price_list")
    
    for row in data:
        # محاسبه درصد سود
        if row.total_cost and row.total_cost > 0:
            row.profit_percentage = (flt(row.profit_amount) / flt(row.total_cost)) * 100
        else:
            row.profit_percentage = 0
        
        # محاسبه مبلغ تخفیف
        if row.final_price_with_markup and row.selling_price:
            row.discount_amount = flt(row.final_price_with_markup) - flt(row.selling_price)
        else:
            row.discount_amount = 0
        
        # مقایسه با لیست قیمت انتخابی
        if compare_price_list:
            current_price = frappe.db.get_value("Item Price", {
                "item_code": row.item_code,
                "price_list": compare_price_list
            }, "price_list_rate") or 0
            row.current_market_price = current_price
            
            # محاسبه اختلاف قیمت
            row.price_variance = flt(current_price) - flt(row.total_cost)
            
            # تعیین وضعیت سود/ضرر
            if row.price_variance > 0:
                row.profit_loss_status = "سودآور"
            elif row.price_variance < 0:
                row.profit_loss_status = "ضررآور"
            else:
                row.profit_loss_status = "سر به سر"
    
    return data

def get_report_summary(data, filters):
    """محاسبه خلاصه گزارش"""
    if not data:
        return []
    
    total_items = len(data)
    total_cost = sum(flt(row.get("total_cost", 0)) for row in data)
    total_selling = sum(flt(row.get("selling_price", 0)) for row in data)
    total_profit = sum(flt(row.get("profit_amount", 0)) for row in data)
    total_commission = sum(flt(row.get("commission_amount", 0)) for row in data)
    
    avg_profit_margin = (total_profit / total_cost * 100) if total_cost > 0 else 0
    
    # تعداد کالاهای سودآور و ضررآور
    profitable_items = len([row for row in data if flt(row.get("profit_amount", 0)) > 0])
    loss_items = len([row for row in data if flt(row.get("profit_amount", 0)) < 0])
    
    summary = [
        {
            "value": total_items,
            "label": _("تعداد کل کالاها"),
            "datatype": "Int"
        },
        {
            "value": total_cost,
            "label": _("مجموع بهای تمام شده"),
            "datatype": "Currency"
        },
        {
            "value": total_selling,
            "label": _("مجموع قیمت فروش"),
            "datatype": "Currency"
        },
        {
            "value": total_profit,
            "label": _("مجموع سود"),
            "datatype": "Currency"
        },
        {
            "value": avg_profit_margin,
            "label": _("میانگین حاشیه سود (%)"),
            "datatype": "Percent"
        },
        {
            "value": profitable_items,
            "label": _("کالاهای سودآور"),
            "datatype": "Int",
            "indicator": "green"
        },
        {
            "value": loss_items,
            "label": _("کالاهای ضررآور"),
            "datatype": "Int",
            "indicator": "red"
        }
    ]
    
    if total_commission > 0:
        summary.append({
            "value": total_commission,
            "label": _("مجموع کمیسیون"),
            "datatype": "Currency"
        })
    
    return summary

def get_chart_data(data, filters):
    """ایجاد نمودار برای گزارش"""
    if not data:
        return None
    
    chart_type = filters.get("chart_type", "profit_distribution")
    
    if chart_type == "profit_distribution":
        # نمودار توزیع سود
        return get_profit_distribution_chart(data)
    elif chart_type == "cost_breakdown":
        # نمودار ترکیب هزینه‌ها
        return get_cost_breakdown_chart(data)
    elif chart_type == "top_profitable":
        # نمودار پرسودترین کالاها
        return get_top_profitable_chart(data)
    else:
        return get_profit_distribution_chart(data)

def get_profit_distribution_chart(data):
    """نمودار توزیع حاشیه سود"""
    margin_ranges = {
        "0-10%": 0, 
        "10-20%": 0, 
        "20-30%": 0, 
        "30-50%": 0, 
        "50%+": 0,
        "ضررآور": 0
    }
    
    for row in data:
        margin = flt(row.get("profit_percentage", 0))
        if margin < 0:
            margin_ranges["ضررآور"] += 1
        elif margin < 10:
            margin_ranges["0-10%"] += 1
        elif margin < 20:
            margin_ranges["10-20%"] += 1
        elif margin < 30:
            margin_ranges["20-30%"] += 1
        elif margin < 50:
            margin_ranges["30-50%"] += 1
        else:
            margin_ranges["50%+"] += 1
    
    return {
        "data": {
            "labels": list(margin_ranges.keys()),
            "datasets": [
                {
                    "name": _("تعداد کالا"),
                    "values": list(margin_ranges.values())
                }
            ]
        },
        "type": "bar",
        "colors": ["#ff6666", "#ff9999", "#ffcc99", "#99ff99", "#66ff66", "#333333"]
    }

def get_cost_breakdown_chart(data):
    """نمودار ترکیب هزینه‌ها"""
    total_raw_material = sum(flt(row.get("raw_material_cost", 0)) for row in data)
    total_operation = sum(flt(row.get("operation_cost", 0)) for row in data)
    total_overhead = sum(flt(row.get("overhead_cost", 0)) for row in data)
    
    return {
        "data": {
            "labels": [_("مواد اولیه"), _("عملیات"), _("سربار")],
            "datasets": [
                {
                    "name": _("هزینه‌ها"),
                    "values": [total_raw_material, total_operation, total_overhead]
                }
            ]
        },
        "type": "pie",
        "colors": ["#3498db", "#e74c3c", "#f1c40f"]
    }

def get_top_profitable_chart(data):
    """نمودار پرسودترین کالاها"""
    # مرتب‌سازی بر اساس سود
    sorted_data = sorted(data, key=lambda x: flt(x.get("profit_amount", 0)), reverse=True)[:10]
    
    return {
        "data": {
            "labels": [row.get("item_name", row.get("item_code", "")) for row in sorted_data],
            "datasets": [
                {
                    "name": _("مبلغ سود"),
                    "values": [flt(row.get("profit_amount", 0)) for row in sorted_data]
                }
            ]
        },
        "type": "bar",
        "colors": ["#2ecc71"]
    }

