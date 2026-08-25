import frappe
from frappe import _
from frappe.utils import flt

@frappe.whitelist()
def get_price_comparison_data(doc):
    """
    دریافت داده‌های مقایسه قیمت با لیست قیمت مقایسه
    """
    if isinstance(doc, str):
        doc = frappe.get_doc("Auto Price List", doc)
    
    if not doc.compare_with_price_list:
        frappe.throw(_("لطفاً لیست قیمت مقایسه را انتخاب کنید"))
    
    if not doc.items:
        frappe.throw(_("هیچ محصولی برای مقایسه وجود ندارد"))
    
    comparison_data = {
        "compare_list_name": doc.compare_with_price_list,
        "items": []
    }
    
    for item in doc.items:
        if not item.item_code:
            continue
        
        # دریافت قیمت از لیست قیمت مقایسه
        old_price = frappe.db.get_value("Item Price", {
            "item_code": item.item_code,
            "price_list": doc.compare_with_price_list
        }, "price_list_rate") or 0
        
        # قیمت جدید محاسبه شده
        new_price = flt(item.final_selected_price or item.selling_price or item.total_cost or 0)
        
        # محاسبه تفاوت و درصد تغییر
        price_difference = new_price - old_price
        price_change_percentage = 0
        if old_price > 0:
            price_change_percentage = (price_difference / old_price) * 100
        
        comparison_data["items"].append({
            "item_code": item.item_code,
            "item_name": item.item_name,
            "old_price": old_price,
            "new_price": new_price,
            "price_difference": price_difference,
            "price_change_percentage": price_change_percentage
        })
    
    return comparison_data

@frappe.whitelist()
def update_item_prices_with_details_fixed(doc):
    """
    متد اصلاح شده برای محاسبه داینامیک قیمت‌ها
    """
    import frappe
    from frappe.utils import flt
    
    if isinstance(doc, str):
        doc = frappe.get_doc("Auto Price List", doc)
    
    try:
        frappe.logger().info("🚀 شروع محاسبه داینامیک قیمت‌ها")
        
        if not doc.items:
            return {
                "success": False,
                "message": "هیچ آیتمی برای محاسبه وجود ندارد"
            }
        
        updated_count = 0
        batch_size = 10
        
        # ابتدا محاسبه بهای تمام شده اگر لازم است
        for i in range(0, len(doc.items), batch_size):
            batch = doc.items[i:i+batch_size]
            
            for item in batch:
                if not item.item_code:
                    continue
                
                # اگر total_cost صفر است، ابتدا محاسبه کن
                if not item.total_cost or item.total_cost == 0:
                    # محاسبه هزینه مواد اولیه
                    if not item.raw_material_cost:
                        item.raw_material_cost = doc.calculate_item_cost_with_exploded_items(item.item_code)
                    
                    # محاسبه هزینه‌های عملیاتی
                    doc.calculate_operation_cost(item)
                    
                    # محاسبه هزینه سربار
                    doc.calculate_overhead_cost(item)
                    
                    # محاسبه total_cost
                    item.total_cost = (
                        flt(item.raw_material_cost or 0) +
                        flt(item.operation_cost or 0) +
                        flt(item.overhead_cost or 0)
                    )
                
                # حالا محاسبه قیمت نهایی بر اساس استراتژی
                base_price = flt(item.total_cost)
                
                # اعمال حاشیه سود
                profit_margin = flt(doc.profit_margin_percentage or 30)
                price_with_profit = base_price * (1 + profit_margin / 100)
                
                # اعمال رند کردن
                rounding_method = doc.rounding_method or 'nearest_thousand'
                final_price = apply_rounding(price_with_profit, rounding_method)
                
                # به‌روزرسانی فیلدها
                item.selling_price = final_price
                item.final_selected_price = final_price
                item.profit_amount = final_price - base_price
                
                if base_price > 0:
                    item.profit_percentage = ((final_price - base_price) / base_price) * 100
                else:
                    item.profit_percentage = 0
                
                # به‌روزرسانی سایر فیلدهای محاسباتی
                item.base_cost_amount = base_price
                item.profit_added_amount = item.profit_amount
                
                # مقایسه با قیمت بازار اگر وجود دارد
                if doc.compare_with_price_list and item.item_code:
                    market_price = frappe.db.get_value("Item Price", {
                        "item_code": item.item_code,
                        "price_list": doc.compare_with_price_list
                    }, "price_list_rate") or 0
                    
                    item.current_market_price = market_price
                    if market_price > 0:
                        item.profit_loss_amount = final_price - market_price
                        if final_price > market_price:
                            item.profit_loss_status = "سود"
                        elif final_price < market_price:
                            item.profit_loss_status = "ضرر"
                        else:
                            item.profit_loss_status = "برابر"
                
                updated_count += 1
                
                # ذخیره مستقیم در دیتابیس
                frappe.db.sql("""
                    UPDATE `tabAuto Price List Item`
                    SET 
                        selling_price = %(selling_price)s,
                        final_selected_price = %(final_selected_price)s,
                        profit_amount = %(profit_amount)s,
                        profit_percentage = %(profit_percentage)s,
                        base_cost_amount = %(base_cost_amount)s,
                        profit_added_amount = %(profit_added_amount)s,
                        current_market_price = %(current_market_price)s,
                        profit_loss_status = %(profit_loss_status)s,
                        profit_loss_amount = %(profit_loss_amount)s,
                        modified = NOW()
                    WHERE name = %(name)s
                """, {
                    "selling_price": item.selling_price,
                    "final_selected_price": item.final_selected_price,
                    "profit_amount": item.profit_amount,
                    "profit_percentage": item.profit_percentage,
                    "base_cost_amount": item.base_cost_amount,
                    "profit_added_amount": item.profit_added_amount,
                    "current_market_price": item.current_market_price or 0,
                    "profit_loss_status": item.profit_loss_status or "",
                    "profit_loss_amount": item.profit_loss_amount or 0,
                    "name": item.name
                })
            
            # Commit after each batch
            frappe.db.commit()
        
        frappe.logger().info(f"✅ محاسبه داینامیک برای {updated_count} آیتم انجام شد")
        
        return {
            "success": True,
            "message": f"✅ قیمت‌ها برای {updated_count} محصول با موفقیت محاسبه شد",
            "updated_count": updated_count
        }
        
    except Exception as e:
        frappe.logger().error(f"❌ خطا در محاسبه داینامیک: {str(e)}")
        frappe.db.rollback()
        return {
            "success": False,
            "message": f"خطا در محاسبه: {str(e)}"
        }

def apply_rounding(price, method):
    """
    اعمال رند کردن بر اساس روش انتخابی
    """
    if method == 'nearest_thousand':
        return round(price / 1000) * 1000
    elif method == 'nearest_ten_thousand':
        return round(price / 10000) * 10000
    elif method == 'nearest_hundred_thousand':
        return round(price / 100000) * 100000
    elif method == 'nearest_million':
        return round(price / 1000000) * 1000000
    elif method == 'ceil_thousand':
        import math
        return math.ceil(price / 1000) * 1000
    elif method == 'floor_thousand':
        import math
        return math.floor(price / 1000) * 1000
    else:
        return round(price)
