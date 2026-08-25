#!/usr/bin/env python3
"""
تست سیستم تحلیل رقبا
"""

import frappe
import json
from frappe.utils import now_datetime

def test_competitor_analysis_system():
    """تست کامل سیستم تحلیل رقبا"""
    print("🚀 شروع تست سیستم تحلیل رقبا...")
    
    try:
        # تست 1: ایجاد تحلیل رقیب جدید
        print("\n📋 تست 1: ایجاد تحلیل رقیب...")
        competitor = create_test_competitor()
        print(f"✅ تحلیل رقیب '{competitor.competitor_name}' با موفقیت ایجاد شد")
        
        # تست 2: ایجاد محصول رقیب
        print("\n📦 تست 2: ایجاد محصول رقیب...")
        product = create_test_product(competitor.name)
        print(f"✅ محصول رقیب '{product.item_name}' با موفقیت ایجاد شد")
        
        # تست 3: تست محاسبات قیمت
        print("\n💰 تست 3: تست محاسبات قیمت...")
        test_price_calculations(product)
        print("✅ محاسبات قیمت با موفقیت انجام شد")
        
        # تست 4: تست تاریخچه قیمت
        print("\n📊 تست 4: تست تاریخچه قیمت...")
        test_price_history(product)
        print("✅ تاریخچه قیمت با موفقیت به‌روزرسانی شد")
        
        # تست 5: تست گزارش مقایسه
        print("\n📈 تست 5: تست گزارش مقایسه...")
        report = test_comparison_report(product)
        print("✅ گزارش مقایسه با موفقیت تولید شد")
        
        # تست 6: تست داشبورد
        print("\n📊 تست 6: تست داشبورد...")
        dashboard_data = test_dashboard()
        print("✅ داده‌های داشبورد با موفقیت دریافت شد")
        
        print("\n🎉 تمام تست‌ها با موفقیت انجام شد!")
        return True
        
    except Exception as e:
        print(f"\n❌ خطا در تست سیستم: {str(e)}")
        return False
    
    finally:
        # پاک‌سازی داده‌های تست
        cleanup_test_data()

def create_test_competitor():
    """ایجاد رقیب تست"""
    competitor = frappe.new_doc("Competitor Analysis")
    competitor.competitor_name = "رقیب تستی"
    competitor.website_url = "https://example.com"
    competitor.auto_crawl_enabled = 1
    competitor.crawl_frequency = "هفتگی"
    competitor.crawl_products = 1
    competitor.crawl_prices = 1
    competitor.crawl_seo_data = 1
    competitor.enable_price_monitoring = 1
    competitor.price_change_threshold = 10
    competitor.notification_email = "test@example.com"
    competitor.save()
    return competitor

def create_test_product(competitor_name):
    """ایجاد محصول تست"""
    product = frappe.new_doc("Competitor Product")
    product.competitor_analysis = competitor_name
    product.item_name = "محصول تستی"
    product.competitor_price = 1000000
    product.our_price = 900000
    product.category = "دسته تست"
    product.availability = "موجود"
    product.auto_update_enabled = 1
    product.crawl_frequency = "هفتگی"
    product.save()
    return product

def test_price_calculations(product):
    """تست محاسبات قیمت"""
    # بارگذاری مجدد برای اطمینان از محاسبات
    product.reload()
    
    # بررسی محاسبات
    expected_difference = product.competitor_price - product.our_price
    expected_percent = (expected_difference / product.our_price) * 100
    
    assert product.price_difference == expected_difference, "اختلاف قیمت اشتباه محاسبه شده"
    assert abs(product.price_difference_percent - expected_percent) < 0.01, "درصد اختلاف قیمت اشتباه محاسبه شده"
    assert product.market_position in ["ارزان‌تر", "مشابه", "گران‌تر", "پریمیوم"], "موقعیت بازار نامعتبر"

def test_price_history(product):
    """تست تاریخچه قیمت"""
    # تغییر قیمت
    product.competitor_price = 1100000
    product.save()
    
    # بررسی تاریخچه
    assert product.price_history, "تاریخچه قیمت ایجاد نشده"
    
    history = json.loads(product.price_history)
    assert len(history) > 0, "تاریخچه قیمت خالی است"
    assert history[-1]['price'] == 1100000, "آخرین قیمت در تاریخچه اشتباه است"

def test_comparison_report(product):
    """تست گزارش مقایسه"""
    report = product.generate_comparison_report()
    
    assert 'pricing' in report, "بخش قیمت‌گذاری در گزارش موجود نیست"
    assert 'recommendations' in report, "توصیه‌ها در گزارش موجود نیست"
    assert report['pricing']['competitor_price'] == product.competitor_price, "قیمت رقیب در گزارش اشتباه است"
    
    return report

def test_dashboard():
    """تست داشبورد"""
    from pricing.pricing.doctype.competitor_analysis.dashboard import get_competitor_dashboard_data
    
    dashboard_data = get_competitor_dashboard_data()
    
    assert 'summary' in dashboard_data, "خلاصه در داشبورد موجود نیست"
    assert 'price_alerts' in dashboard_data, "هشدارهای قیمت در داشبورد موجود نیست"
    
    return dashboard_data

def cleanup_test_data():
    """پاک‌سازی داده‌های تست"""
    try:
        # حذف محصولات تست
        test_products = frappe.get_all("Competitor Product", 
            filters={"item_name": ["like", "%تست%"]})
        for product in test_products:
            frappe.delete_doc("Competitor Product", product.name, force=True)
        
        # حذف رقبای تست
        test_competitors = frappe.get_all("Competitor Analysis", 
            filters={"competitor_name": ["like", "%تست%"]})
        for competitor in test_competitors:
            frappe.delete_doc("Competitor Analysis", competitor.name, force=True)
        
        frappe.db.commit()
        print("🧹 داده‌های تست پاک شد")
        
    except Exception as e:
        print(f"⚠️ خطا در پاک‌سازی: {str(e)}")

if __name__ == "__main__":
    # اجرای تست
    success = test_competitor_analysis_system()
    exit(0 if success else 1)
