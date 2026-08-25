# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, cint, today, getdate
import math

@frappe.whitelist()
def get_item_price_details(item_code, price_list=None, qty=1):
    """
    دریافت جزئیات قیمت یک کالا
    شامل قیمت نقدی، قسطی، با تخفیف و غیره
    """
    if not item_code:
        return {"error": "کد کالا وارد نشده است"}
    
    qty = flt(qty) or 1
    
    # دریافت اطلاعات کالا
    item = frappe.db.get_value("Item", item_code, 
        ["item_name", "item_group", "brand", "standard_rate", "valuation_rate"],
        as_dict=True
    )
    
    if not item:
        return {"error": "کالا یافت نشد"}
    
    # دریافت آخرین Auto Price List فعال
    latest_apl = get_latest_auto_price_list(price_list)
    
    # دریافت قیمت از Auto Price List Item
    apl_item = None
    if latest_apl:
        apl_item = frappe.db.get_value("Auto Price List Item",
            {"parent": latest_apl.name, "item_code": item_code},
            ["total_cost", "selling_price", "profit_amount", "final_price_with_markup",
             "down_payment_amount", "monthly_payment", "total_interest", "total_installment_amount",
             "commission_amount", "net_profit_after_commission"],
            as_dict=True
        )
    
    # محاسبه قیمت‌ها
    result = {
        "item_code": item_code,
        "item_name": item.item_name,
        "item_group": item.item_group,
        "brand": item.brand,
        "qty": qty,
        "prices": {}
    }
    
    if apl_item:
        # قیمت‌های محاسبه شده از Auto Price List
        unit_cost = flt(apl_item.total_cost)
        unit_selling_price = flt(apl_item.selling_price)
        unit_profit = flt(apl_item.profit_amount)
        
        result["prices"]["unit_cost"] = unit_cost
        result["prices"]["total_cost"] = unit_cost * qty
        result["prices"]["unit_selling_price"] = unit_selling_price
        result["prices"]["total_selling_price"] = unit_selling_price * qty
        result["prices"]["unit_profit"] = unit_profit
        result["prices"]["total_profit"] = unit_profit * qty
        result["prices"]["profit_percentage"] = (unit_profit / unit_cost * 100) if unit_cost > 0 else 0
        
        # قیمت با افزایش (برای امکان تخفیف)
        if apl_item.final_price_with_markup:
            result["prices"]["unit_price_with_markup"] = flt(apl_item.final_price_with_markup)
            result["prices"]["total_price_with_markup"] = flt(apl_item.final_price_with_markup) * qty
        
        # جزئیات قسط
        if apl_item.monthly_payment:
            result["installment"] = {
                "down_payment": flt(apl_item.down_payment_amount) * qty,
                "monthly_payment": flt(apl_item.monthly_payment) * qty,
                "total_interest": flt(apl_item.total_interest) * qty,
                "total_amount": flt(apl_item.total_installment_amount) * qty,
                "number_of_months": latest_apl.number_of_months if latest_apl else 0,
                "monthly_interest_rate": latest_apl.monthly_interest_rate if latest_apl else 0
            }
        
        # کمیسیون
        if apl_item.commission_amount:
            result["commission"] = {
                "amount": flt(apl_item.commission_amount) * qty,
                "net_profit": flt(apl_item.net_profit_after_commission) * qty
            }
        
        # تنظیمات از APL
        if latest_apl:
            result["settings"] = {
                "price_list": latest_apl.price_list,
                "profit_margin": latest_apl.profit_margin,
                "target_discount_percentage": latest_apl.target_discount_percentage,
                "required_markup_percentage": latest_apl.required_markup_percentage,
                "enable_installment": latest_apl.enable_installment,
                "number_of_months": latest_apl.number_of_months,
                "monthly_interest_rate": latest_apl.monthly_interest_rate,
                "down_payment_percentage": latest_apl.down_payment_percentage
            }
    else:
        # استفاده از قیمت استاندارد کالا
        unit_price = flt(item.standard_rate) or flt(item.valuation_rate) or 0
        result["prices"]["unit_selling_price"] = unit_price
        result["prices"]["total_selling_price"] = unit_price * qty
        result["warning"] = "این کالا در لیست قیمت خودکار نیست"
    
    return result

@frappe.whitelist()
def get_multiple_items_prices(items):
    """
    دریافت قیمت چندین کالا به صورت همزمان
    items: لیست از دیکشنری‌ها با item_code و qty
    """
    import json
    if isinstance(items, str):
        items = json.loads(items)
    
    results = []
    totals = {
        "total_cost": 0,
        "total_selling_price": 0,
        "total_profit": 0,
        "total_with_markup": 0,
        "total_installment": 0,
        "total_commission": 0
    }
    
    for item in items:
        item_code = item.get("item_code")
        qty = flt(item.get("qty", 1))
        
        if item_code:
            price_details = get_item_price_details(item_code, qty=qty)
            if "error" not in price_details:
                results.append(price_details)
                
                # جمع کل‌ها
                prices = price_details.get("prices", {})
                totals["total_cost"] += prices.get("total_cost", 0)
                totals["total_selling_price"] += prices.get("total_selling_price", 0)
                totals["total_profit"] += prices.get("total_profit", 0)
                totals["total_with_markup"] += prices.get("total_price_with_markup", 0)
                
                if price_details.get("installment"):
                    totals["total_installment"] += price_details["installment"].get("total_amount", 0)
                
                if price_details.get("commission"):
                    totals["total_commission"] += price_details["commission"].get("amount", 0)
    
    return {
        "items": results,
        "totals": totals
    }

@frappe.whitelist()
def search_items(search_term, limit=20):
    """
    جستجوی کالاها برای autocomplete
    """
    if not search_term:
        return []
    
    items = frappe.db.sql("""
        SELECT 
            item_code, 
            item_name, 
            item_group, 
            brand,
            standard_rate
        FROM `tabItem`
        WHERE disabled = 0
          AND (
              item_code LIKE %(search)s
              OR item_name LIKE %(search)s
              OR barcode LIKE %(search)s
          )
        LIMIT %(limit)s
    """, {
        "search": f"%{search_term}%",
        "limit": cint(limit)
    }, as_dict=True)
    
    return items

@frappe.whitelist()
def get_price_lists():
    """دریافت لیست‌های قیمت موجود"""
    return frappe.get_all("Price List", 
        filters={"enabled": 1},
        fields=["name", "price_list_name", "currency"],
        order_by="name"
    )

@frappe.whitelist()
def get_auto_price_lists():
    """دریافت لیست‌های قیمت خودکار"""
    return frappe.get_all("Auto Price List",
        filters={"docstatus": 1},
        fields=["name", "price_list", "valid_from", "valid_until", "profit_margin"],
        order_by="valid_from desc"
    )

def get_latest_auto_price_list(price_list=None):
    """دریافت آخرین Auto Price List فعال"""
    filters = {
        "docstatus": 1,
        "valid_from": ["<=", today()],
        "valid_until": [">=", today()]
    }
    
    if price_list:
        filters["price_list"] = price_list
    
    apl = frappe.db.get_value("Auto Price List", filters,
        ["name", "price_list", "profit_margin", "commission_percentage",
         "target_discount_percentage", "required_markup_percentage",
         "enable_installment", "number_of_months", "monthly_interest_rate",
         "down_payment_percentage", "enable_deferred_payment",
         "deferred_payment_months", "deferred_payment_interest_rate"],
        as_dict=True,
        order_by="valid_from desc"
    )
    
    return apl

@frappe.whitelist()
def calculate_custom_price(base_price, profit_margin=0, discount_percentage=0, 
                           enable_installment=False, number_of_months=0, 
                           monthly_interest_rate=0, down_payment_percentage=0, qty=1):
    """
    محاسبه قیمت سفارشی با پارامترهای دلخواه
    """
    base_price = flt(base_price)
    profit_margin = flt(profit_margin)
    discount_percentage = flt(discount_percentage)
    qty = flt(qty) or 1
    
    # محاسبه قیمت با سود
    selling_price = base_price * (1 + profit_margin / 100)
    profit_amount = selling_price - base_price
    
    # محاسبه قیمت با افزایش (برای تخفیف)
    price_with_markup = selling_price
    discount_amount = 0
    if discount_percentage > 0:
        markup_percentage = (discount_percentage / (100 - discount_percentage)) * 100
        price_with_markup = selling_price * (1 + markup_percentage / 100)
        discount_amount = price_with_markup * discount_percentage / 100
    
    result = {
        "unit_cost": base_price,
        "unit_selling_price": selling_price,
        "unit_profit": profit_amount,
        "unit_price_with_markup": price_with_markup,
        "unit_discount_amount": discount_amount,
        "profit_percentage": (profit_amount / base_price * 100) if base_price > 0 else 0,
        "markup_percentage": (discount_percentage / (100 - discount_percentage)) * 100 if discount_percentage < 100 else 0,
        "total_cost": base_price * qty,
        "total_selling_price": selling_price * qty,
        "total_price_with_markup": price_with_markup * qty
    }
    
    # محاسبه قسط
    if enable_installment and number_of_months > 0:
        monthly_rate = flt(monthly_interest_rate) / 100
        months = cint(number_of_months)
        down_pct = flt(down_payment_percentage) / 100
        
        total_price = price_with_markup * qty
        down_payment = total_price * down_pct
        financed_amount = total_price - down_payment
        
        if monthly_rate > 0:
            # فرمول بهره مرکب
            monthly_payment = financed_amount * (monthly_rate * (1 + monthly_rate)**months) / ((1 + monthly_rate)**months - 1)
            total_installment = down_payment + (monthly_payment * months)
            total_interest = total_installment - total_price
        else:
            monthly_payment = financed_amount / months
            total_installment = total_price
            total_interest = 0
        
        result["installment"] = {
            "down_payment": down_payment,
            "monthly_payment": monthly_payment,
            "number_of_months": months,
            "total_interest": total_interest,
            "total_amount": total_installment,
            "interest_percentage": ((1 + monthly_rate) ** months - 1) * 100
        }
    
    return result

@frappe.whitelist()
def create_quotation_from_items(items, customer=None, price_type="selling_price"):
    """
    ایجاد پیش‌فاکتور از آیتم‌های انتخاب شده
    """
    import json
    if isinstance(items, str):
        items = json.loads(items)
    
    # ایجاد Quotation
    quotation = frappe.new_doc("Quotation")
    quotation.quotation_to = "Customer" if customer else "Lead"
    if customer:
        quotation.party_name = customer
    
    for item in items:
        item_code = item.get("item_code")
        qty = flt(item.get("qty", 1))
        
        # دریافت قیمت
        price_details = get_item_price_details(item_code, qty=1)
        if "error" not in price_details:
            prices = price_details.get("prices", {})
            
            # انتخاب نوع قیمت
            if price_type == "selling_price":
                rate = prices.get("unit_selling_price", 0)
            elif price_type == "with_markup":
                rate = prices.get("unit_price_with_markup", 0)
            elif price_type == "installment":
                installment = price_details.get("installment", {})
                rate = installment.get("total_amount", 0) / qty if qty > 0 else 0
            else:
                rate = prices.get("unit_selling_price", 0)
            
            quotation.append("items", {
                "item_code": item_code,
                "qty": qty,
                "rate": rate
            })
    
    quotation.insert()
    
    return {
        "success": True,
        "quotation": quotation.name,
        "message": f"پیش‌فاکتور {quotation.name} ایجاد شد"
    }

