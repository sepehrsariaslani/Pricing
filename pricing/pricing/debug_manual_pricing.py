#!/usr/bin/env python3

import frappe

def debug_manual_pricing():
    """
    دیباگ مشکل manual pricing
    """
    try:
        print("🔍 شروع دیباگ manual pricing...")
        
        # پیدا کردن اولین Auto Price List
        price_lists = frappe.get_all('Auto Price List', 
                                fields=['name'],
                                limit=1)
        
        if not price_lists:
            print("❌ هیچ Auto Price List وجود ندارد")
            return
        
        price_list_name = price_lists[0].name
        print(f"📋 استفاده از Price List: {price_list_name}")
        
        # بارگذاری price list
        doc = frappe.get_doc('Auto Price List', price_list_name)
        
        # بررسی manual_material_prices
        print(f"🔍 تعداد manual_material_prices: {len(doc.manual_material_prices or [])}")
        if doc.manual_material_prices:
            for mp in doc.manual_material_prices:
                print(f"   - {mp.item_code}: {mp.manual_price:,.0f}")
        else:
            print("❌ هیچ manual_material_prices وجود ندارد")
            return
        
        # بررسی items
        print(f"🔍 تعداد items: {len(doc.items or [])}")
        if not doc.items:
            print("❌ هیچ آیتمی وجود ندارد")
            return
        
        # تست روی اولین آیتم
        first_item = doc.items[0]
        print(f"🧪 تست روی آیتم: {first_item.item_code}")
        print(f"   - هزینه فعلی: {first_item.raw_material_cost or 0:,.0f}")
        
        # تست فانکشن is_item_affected_by_manual_prices
        manual_price_map = {}
        for mp in doc.manual_material_prices:
            if mp.item_code and mp.manual_price:
                manual_price_map[mp.item_code] = mp.manual_price
        
        print(f"🔍 Manual price map: {manual_price_map}")
        
        is_affected = doc.is_item_affected_by_manual_prices(first_item.item_code, manual_price_map)
        print(f"🔍 آیا آیتم متأثر است؟ {is_affected}")
        
        if is_affected:
            # تست فانکشن calculate_item_cost_with_exploded_items
            print("🧮 محاسبه قیمت جدید...")
            new_cost = doc.calculate_item_cost_with_exploded_items(first_item.item_code)
            old_cost = first_item.raw_material_cost or 0
            
            print(f"📊 نتایج:")
            print(f"   - قیمت قدیمی: {old_cost:,.0f}")
            print(f"   - قیمت جدید: {new_cost:,.0f}")
            print(f"   - تفاوت: {new_cost - old_cost:,.0f}")
            print(f"   - آیا تفاوت > 0.01؟ {abs(new_cost - old_cost) > 0.01}")
        
        return {"success": True, "message": "Debug completed"}
        
    except Exception as e:
        print(f"❌ خطا: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}
