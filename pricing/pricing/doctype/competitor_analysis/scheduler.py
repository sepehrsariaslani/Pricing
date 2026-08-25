import frappe
from frappe.utils import now_datetime, add_days, cint
from datetime import datetime, timedelta
import json
from .competitor_analysis import WEB_CRAWLER_AVAILABLE

def run_scheduled_competitor_crawls():
    """اجرای کرال‌های زمان‌بندی شده رقبا"""
    try:
        if not WEB_CRAWLER_AVAILABLE:
            return

        # دریافت تمام تحلیل‌های رقیب که کرال خودکار فعال دارند
        competitors = frappe.get_all("Competitor Analysis", 
            filters={
                "auto_crawl_enabled": 1,
                "website_url": ["!=", ""]
            },
            fields=["name", "competitor_name", "crawl_frequency", "last_crawl_date", "website_url"]
        )
        
        crawled_count = 0
        
        for competitor in competitors:
            if should_crawl_competitor(competitor):
                try:
                    # اجرای کرال در پس‌زمینه
                    frappe.enqueue(
                        "pricing.pricing.doctype.competitor_analysis.competitor_analysis.start_intelligent_crawl",
                        competitor_name=competitor.name,
                        queue="long",
                        timeout=3600,
                        job_name=f"competitor_crawl_{competitor.name}"
                    )
                    
                    crawled_count += 1
                    frappe.log_error(f"کرال زمان‌بندی شده برای {competitor.competitor_name} شروع شد", "Scheduled Crawl")
                    
                except Exception as e:
                    frappe.log_error(f"خطا در شروع کرال {competitor.competitor_name}: {str(e)}", "Scheduled Crawl Error")
        
        if crawled_count > 0:
            frappe.log_error(f"تعداد {crawled_count} کرال زمان‌بندی شده اجرا شد", "Scheduled Crawl Summary")
            
    except Exception as e:
        frappe.log_error(f"خطا در اجرای کرال‌های زمان‌بندی شده: {str(e)}", "Scheduled Crawl System Error")

def should_crawl_competitor(competitor):
    """بررسی اینکه آیا زمان کرال رقیب فرا رسیده یا نه"""
    if not competitor.last_crawl_date:
        return True
    
    last_crawl = datetime.strptime(str(competitor.last_crawl_date), '%Y-%m-%d %H:%M:%S')
    now = datetime.now()
    
    frequency_map = {
        "روزانه": 1,
        "هفتگی": 7,
        "ماهانه": 30
    }
    
    days_interval = frequency_map.get(competitor.crawl_frequency, 7)
    next_crawl_date = last_crawl + timedelta(days=days_interval)
    
    return now >= next_crawl_date

def check_competitor_price_alerts():
    """بررسی و ارسال هشدارهای تغییر قیمت رقبا"""
    try:
        # دریافت تمام محصولات رقبا که نظارت بر قیمت فعال دارند
        competitor_products = frappe.get_all("Competitor Product",
            filters={
                "auto_update_enabled": 1,
                "competitor_price": [">", 0]
            },
            fields=["name", "item_name", "competitor_analysis", "competitor_price", "price_history"]
        )
        
        alerts_sent = 0
        
        for product in competitor_products:
            try:
                product_doc = frappe.get_doc("Competitor Product", product.name)
                
                # بررسی نیاز به ارسال هشدار
                should_alert, trend_data = product_doc.should_send_price_alert(threshold_percent=10)
                
                if should_alert:
                    send_price_change_alert(product_doc, trend_data)
                    alerts_sent += 1
                    
            except Exception as e:
                frappe.log_error(f"خطا در بررسی هشدار قیمت محصول {product.name}: {str(e)}", "Price Alert Check Error")
        
        if alerts_sent > 0:
            frappe.log_error(f"تعداد {alerts_sent} هشدار تغییر قیمت ارسال شد", "Price Alert Summary")
            
    except Exception as e:
        frappe.log_error(f"خطا در بررسی هشدارهای قیمت: {str(e)}", "Price Alert System Error")

def send_price_change_alert(product_doc, trend_data):
    """ارسال هشدار تغییر قیمت"""
    try:
        # دریافت اطلاعات تحلیل رقیب
        competitor_analysis = frappe.get_doc("Competitor Analysis", product_doc.competitor_analysis)
        
        if not competitor_analysis.notification_email:
            return
        
        # تهیه محتوای ایمیل
        subject = f"هشدار تغییر قیمت: {product_doc.item_name}"
        
        message = f"""
        <div dir="rtl" style="font-family: Tahoma, Arial, sans-serif;">
            <h3>هشدار تغییر قیمت محصول رقیب</h3>
            
            <table border="1" cellpadding="10" cellspacing="0" style="border-collapse: collapse; width: 100%;">
                <tr>
                    <td><strong>نام محصول:</strong></td>
                    <td>{product_doc.item_name}</td>
                </tr>
                <tr>
                    <td><strong>رقیب:</strong></td>
                    <td>{competitor_analysis.competitor_name}</td>
                </tr>
                <tr>
                    <td><strong>قیمت فعلی رقیب:</strong></td>
                    <td>{product_doc.competitor_price:,.0f} ریال</td>
                </tr>
                <tr>
                    <td><strong>قیمت ما:</strong></td>
                    <td>{product_doc.our_price:,.0f} ریال</td>
                </tr>
                <tr>
                    <td><strong>روند تغییر (7 روز):</strong></td>
                    <td style="color: {'red' if trend_data.get('change_percent', 0) > 0 else 'green'}">
                        {trend_data.get('trend', 'نامشخص')} ({trend_data.get('change_percent', 0):.1f}%)
                    </td>
                </tr>
            </table>
            
            <p><strong>توصیه:</strong></p>
            <ul>
        """
        
        # افزودن توصیه‌ها
        recommendations = product_doc.generate_strategic_recommendations()
        for rec in recommendations[:3]:  # حداکثر 3 توصیه
            message += f"<li>{rec.get('message', '')}</li>"
        
        message += """
            </ul>
            
            <p>برای مشاهده جزئیات بیشتر به سیستم مراجعه کنید.</p>
        </div>
        """
        
        # ارسال ایمیل
        frappe.sendmail(
            recipients=[competitor_analysis.notification_email],
            subject=subject,
            message=message,
            delayed=False
        )
        
        # به‌روزرسانی تاریخ آخرین اطلاع‌رسانی
        competitor_analysis.last_notification_date = now_datetime()
        competitor_analysis.save()
        
    except Exception as e:
        frappe.log_error(f"خطا در ارسال هشدار قیمت: {str(e)}", "Price Alert Send Error")

def update_competitor_seo_metrics():
    """به‌روزرسانی متریک‌های SEO رقبا"""
    try:
        # دریافت رقبایی که تحلیل SEO فعال دارند
        competitors = frappe.get_all("Competitor Analysis",
            filters={
                "auto_crawl_enabled": 1,
                "crawl_seo_data": 1,
                "website_url": ["!=", ""]
            },
            fields=["name", "competitor_name", "website_url"]
        )
        
        updated_count = 0
        
        for competitor in competitors:
            try:
                # اجرای تحلیل SEO در پس‌زمینه
                frappe.enqueue(
                    "pricing.pricing.doctype.competitor_analysis.competitor_analysis.analyze_seo_performance",
                    competitor_name=competitor.name,
                    queue="default",
                    timeout=1800,
                    job_name=f"seo_analysis_{competitor.name}"
                )
                
                updated_count += 1
                
            except Exception as e:
                frappe.log_error(f"خطا در شروع تحلیل SEO {competitor.competitor_name}: {str(e)}", "SEO Analysis Error")
        
        if updated_count > 0:
            frappe.log_error(f"تعداد {updated_count} تحلیل SEO شروع شد", "SEO Analysis Summary")
            
    except Exception as e:
        frappe.log_error(f"خطا در به‌روزرسانی متریک‌های SEO: {str(e)}", "SEO Metrics System Error")

def generate_weekly_competitor_report():
    """تولید گزارش هفتگی رقبا"""
    try:
        # دریافت تمام تحلیل‌های رقیب فعال
        competitors = frappe.get_all("Competitor Analysis",
            filters={"docstatus": ["!=", 2]},
            fields=["name", "competitor_name", "website_url"]
        )
        
        if not competitors:
            return
        
        # تهیه گزارش کلی
        report_data = {
            "report_date": now_datetime(),
            "total_competitors": len(competitors),
            "competitors_summary": []
        }
        
        for competitor in competitors:
            try:
                competitor_doc = frappe.get_doc("Competitor Analysis", competitor.name)
                
                # دریافت آمار محصولات
                products_count = frappe.db.count("Competitor Product", 
                    filters={"competitor_analysis": competitor.name})
                
                # دریافت آخرین تغییرات قیمت
                recent_price_changes = get_recent_price_changes(competitor.name)
                
                competitor_summary = {
                    "name": competitor.competitor_name,
                    "website": competitor.website_url,
                    "products_count": products_count,
                    "recent_price_changes": recent_price_changes,
                    "last_crawl": competitor_doc.last_crawl_date
                }
                
                report_data["competitors_summary"].append(competitor_summary)
                
            except Exception as e:
                frappe.log_error(f"خطا در تهیه خلاصه رقیب {competitor.name}: {str(e)}", "Weekly Report Error")
        
        # ذخیره گزارش
        save_weekly_report(report_data)
        
    except Exception as e:
        frappe.log_error(f"خطا در تولید گزارش هفتگی: {str(e)}", "Weekly Report System Error")

def get_recent_price_changes(competitor_name):
    """دریافت تغییرات قیمت اخیر یک رقیب"""
    try:
        products = frappe.get_all("Competitor Product",
            filters={"competitor_analysis": competitor_name},
            fields=["name", "item_name", "price_history"]
        )
        
        changes = []
        for product in products:
            if product.price_history:
                try:
                    history = json.loads(product.price_history)
                    if len(history) >= 2:
                        latest = history[-1]
                        previous = history[-2]
                        change_percent = ((latest['price'] - previous['price']) / previous['price']) * 100
                        
                        if abs(change_percent) >= 5:  # تغییرات بالای 5 درصد
                            changes.append({
                                "product": product.item_name,
                                "change_percent": change_percent,
                                "current_price": latest['price']
                            })
                except:
                    continue
        
        return changes[:5]  # حداکثر 5 تغییر
        
    except Exception as e:
        frappe.log_error(f"خطا در دریافت تغییرات قیمت: {str(e)}", "Price Changes Error")
        return []

def save_weekly_report(report_data):
    """ذخیره گزارش هفتگی"""
    try:
        # ایجاد فایل گزارش
        from frappe.utils.file_manager import save_file
        
        report_content = json.dumps(report_data, ensure_ascii=False, indent=2)
        
        file_name = f"weekly_competitor_report_{datetime.now().strftime('%Y_%m_%d')}.json"
        
        save_file(
            fname=file_name,
            content=report_content,
            dt="Competitor Analysis",
            is_private=1
        )
        
        frappe.log_error(f"گزارش هفتگی ذخیره شد: {file_name}", "Weekly Report Saved")
        
    except Exception as e:
        frappe.log_error(f"خطا در ذخیره گزارش هفتگی: {str(e)}", "Weekly Report Save Error")
