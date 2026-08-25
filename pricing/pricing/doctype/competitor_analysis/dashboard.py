import frappe
from frappe.utils import flt, cint, today, now_datetime
import json
from datetime import datetime, timedelta

@frappe.whitelist()
def get_competitor_dashboard_data():
    """دریافت داده‌های داشبورد تحلیل رقبا"""
    try:
        dashboard_data = {
            "summary": get_competitors_summary(),
            "price_alerts": get_price_alerts(),
            "recent_crawls": get_recent_crawls(),
            "seo_metrics": get_seo_metrics(),
            "market_position": get_market_position_data(),
            "trending_products": get_trending_products(),
            "competitor_performance": get_competitor_performance()
        }
        
        return dashboard_data
        
    except Exception as e:
        frappe.log_error(f"خطا در دریافت داده‌های داشبورد: {str(e)}", "Dashboard Data Error")
        return {"error": str(e)}

def get_competitors_summary():
    """خلاصه کلی رقبا"""
    try:
        total_competitors = frappe.db.count("Competitor Analysis")
        active_competitors = frappe.db.count("Competitor Analysis", {"auto_crawl_enabled": 1})
        total_products = frappe.db.count("Competitor Product")
        
        # محاسبه میانگین قیمت‌ها
        avg_competitor_price = frappe.db.sql("""
            SELECT AVG(competitor_price) as avg_price
            FROM `tabCompetitor Product`
            WHERE competitor_price > 0
        """)[0][0] or 0
        
        avg_our_price = frappe.db.sql("""
            SELECT AVG(our_price) as avg_price
            FROM `tabCompetitor Product`
            WHERE our_price > 0
        """)[0][0] or 0
        
        price_advantage = 0
        if avg_competitor_price > 0 and avg_our_price > 0:
            price_advantage = ((avg_competitor_price - avg_our_price) / avg_our_price) * 100
        
        return {
            "total_competitors": total_competitors,
            "active_competitors": active_competitors,
            "total_products": total_products,
            "avg_competitor_price": avg_competitor_price,
            "avg_our_price": avg_our_price,
            "price_advantage_percent": price_advantage
        }
        
    except Exception as e:
        frappe.log_error(f"خطا در دریافت خلاصه رقبا: {str(e)}", "Competitors Summary Error")
        return {}

def get_price_alerts():
    """دریافت هشدارهای قیمت"""
    try:
        alerts = []
        
        # محصولاتی که تغییر قیمت قابل توجه داشته‌اند
        products = frappe.get_all("Competitor Product",
            filters={"price_history": ["!=", ""]},
            fields=["name", "item_name", "competitor_analysis", "competitor_price", "our_price", "price_history"]
        )
        
        for product in products:
            try:
                if product.price_history:
                    history = json.loads(product.price_history)
                    if len(history) >= 2:
                        latest = history[-1]
                        previous = history[-2]
                        change_percent = ((latest['price'] - previous['price']) / previous['price']) * 100
                        
                        if abs(change_percent) >= 10:  # تغییرات بالای 10 درصد
                            competitor_name = frappe.get_value("Competitor Analysis", 
                                product.competitor_analysis, "competitor_name")
                            
                            alerts.append({
                                "product_name": product.item_name,
                                "competitor_name": competitor_name,
                                "change_percent": change_percent,
                                "current_price": latest['price'],
                                "previous_price": previous['price'],
                                "date": latest['date'],
                                "alert_type": "صعودی" if change_percent > 0 else "نزولی"
                            })
            except:
                continue
        
        # مرتب‌سازی بر اساس درصد تغییر
        alerts.sort(key=lambda x: abs(x['change_percent']), reverse=True)
        
        return alerts[:10]  # حداکثر 10 هشدار
        
    except Exception as e:
        frappe.log_error(f"خطا در دریافت هشدارهای قیمت: {str(e)}", "Price Alerts Error")
        return []

def get_recent_crawls():
    """دریافت آخرین کرال‌ها"""
    try:
        crawls = frappe.get_all("Competitor Analysis",
            filters={"last_crawl_date": ["!=", ""]},
            fields=["competitor_name", "last_crawl_date", "website_url", "crawl_frequency"],
            order_by="last_crawl_date desc",
            limit=10
        )
        
        for crawl in crawls:
            # محاسبه زمان باقی‌مانده تا کرال بعدی
            if crawl.last_crawl_date and crawl.crawl_frequency:
                frequency_map = {"روزانه": 1, "هفتگی": 7, "ماهانه": 30}
                days_interval = frequency_map.get(crawl.crawl_frequency, 7)
                
                last_crawl = datetime.strptime(str(crawl.last_crawl_date), '%Y-%m-%d %H:%M:%S')
                next_crawl = last_crawl + timedelta(days=days_interval)
                now = datetime.now()
                
                if next_crawl > now:
                    days_remaining = (next_crawl - now).days
                    crawl.days_until_next = days_remaining
                else:
                    crawl.days_until_next = 0
                    crawl.overdue = True
        
        return crawls
        
    except Exception as e:
        frappe.log_error(f"خطا در دریافت آخرین کرال‌ها: {str(e)}", "Recent Crawls Error")
        return []

def get_seo_metrics():
    """دریافت متریک‌های SEO"""
    try:
        competitors = frappe.get_all("Competitor Analysis",
            fields=["competitor_name", "domain_authority", "page_authority", "backlinks_count", 
                   "organic_keywords", "monthly_traffic", "traffic_trend"]
        )
        
        # محاسبه میانگین‌ها
        total_da = sum(c.domain_authority or 0 for c in competitors)
        total_pa = sum(c.page_authority or 0 for c in competitors)
        total_backlinks = sum(c.backlinks_count or 0 for c in competitors)
        total_keywords = sum(c.organic_keywords or 0 for c in competitors)
        total_traffic = sum(c.monthly_traffic or 0 for c in competitors)
        
        count = len(competitors) or 1
        
        seo_summary = {
            "avg_domain_authority": total_da / count,
            "avg_page_authority": total_pa / count,
            "total_backlinks": total_backlinks,
            "total_keywords": total_keywords,
            "total_monthly_traffic": total_traffic,
            "competitors_count": count
        }
        
        # رتبه‌بندی رقبا بر اساس DA
        competitors.sort(key=lambda x: x.domain_authority or 0, reverse=True)
        seo_summary["top_competitors"] = competitors[:5]
        
        return seo_summary
        
    except Exception as e:
        frappe.log_error(f"خطا در دریافت متریک‌های SEO: {str(e)}", "SEO Metrics Error")
        return {}

def get_market_position_data():
    """دریافت داده‌های موقعیت بازار"""
    try:
        # تحلیل موقعیت محصولات
        positions = frappe.db.sql("""
            SELECT market_position, COUNT(*) as count
            FROM `tabCompetitor Product`
            WHERE market_position IS NOT NULL AND market_position != ''
            GROUP BY market_position
        """, as_dict=True)
        
        position_data = {pos['market_position']: pos['count'] for pos in positions}
        
        # محاسبه درصدها
        total = sum(position_data.values()) or 1
        position_percentages = {
            pos: (count / total) * 100 
            for pos, count in position_data.items()
        }
        
        return {
            "position_counts": position_data,
            "position_percentages": position_percentages,
            "total_products": total
        }
        
    except Exception as e:
        frappe.log_error(f"خطا در دریافت داده‌های موقعیت بازار: {str(e)}", "Market Position Error")
        return {}

def get_trending_products():
    """دریافت محصولات پرطرفدار"""
    try:
        products = frappe.get_all("Competitor Product",
            filters={"price_history": ["!=", ""]},
            fields=["name", "item_name", "competitor_analysis", "competitor_price", "price_history"]
        )
        
        trending = []
        
        for product in products:
            try:
                if product.price_history:
                    history = json.loads(product.price_history)
                    if len(history) >= 3:
                        # محاسبه روند قیمت
                        recent_prices = [h['price'] for h in history[-3:]]
                        trend_score = 0
                        
                        for i in range(1, len(recent_prices)):
                            if recent_prices[i] > recent_prices[i-1]:
                                trend_score += 1
                            elif recent_prices[i] < recent_prices[i-1]:
                                trend_score -= 1
                        
                        competitor_name = frappe.get_value("Competitor Analysis", 
                            product.competitor_analysis, "competitor_name")
                        
                        trending.append({
                            "product_name": product.item_name,
                            "competitor_name": competitor_name,
                            "current_price": recent_prices[-1],
                            "trend_score": trend_score,
                            "price_changes": len(history)
                        })
            except:
                continue
        
        # مرتب‌سازی بر اساس امتیاز روند
        trending.sort(key=lambda x: abs(x['trend_score']), reverse=True)
        
        return trending[:8]  # حداکثر 8 محصول
        
    except Exception as e:
        frappe.log_error(f"خطا در دریافت محصولات پرطرفدار: {str(e)}", "Trending Products Error")
        return []

def get_competitor_performance():
    """دریافت عملکرد رقبا"""
    try:
        competitors = frappe.get_all("Competitor Analysis",
            fields=["name", "competitor_name", "last_crawl_date", "domain_authority", "monthly_traffic"]
        )
        
        performance_data = []
        
        for competitor in competitors:
            # تعداد محصولات
            products_count = frappe.db.count("Competitor Product", 
                {"competitor_analysis": competitor.name})
            
            # میانگین قیمت محصولات
            avg_price = frappe.db.sql("""
                SELECT AVG(competitor_price) as avg_price
                FROM `tabCompetitor Product`
                WHERE competitor_analysis = %s AND competitor_price > 0
            """, competitor.name)[0][0] or 0
            
            # تعداد تغییرات قیمت اخیر
            recent_changes = frappe.db.sql("""
                SELECT COUNT(*) as changes
                FROM `tabCompetitor Product`
                WHERE competitor_analysis = %s 
                AND price_history IS NOT NULL 
                AND price_history != ''
            """, competitor.name)[0][0] or 0
            
            # محاسبه امتیاز عملکرد
            performance_score = 0
            if competitor.domain_authority:
                performance_score += competitor.domain_authority * 0.3
            if competitor.monthly_traffic:
                performance_score += min(competitor.monthly_traffic / 10000, 50) * 0.4
            if products_count:
                performance_score += min(products_count * 2, 20) * 0.3
            
            performance_data.append({
                "competitor_name": competitor.competitor_name,
                "products_count": products_count,
                "avg_price": avg_price,
                "recent_changes": recent_changes,
                "domain_authority": competitor.domain_authority or 0,
                "monthly_traffic": competitor.monthly_traffic or 0,
                "performance_score": performance_score,
                "last_crawl": competitor.last_crawl_date
            })
        
        # مرتب‌سازی بر اساس امتیاز عملکرد
        performance_data.sort(key=lambda x: x['performance_score'], reverse=True)
        
        return performance_data
        
    except Exception as e:
        frappe.log_error(f"خطا در دریافت عملکرد رقبا: {str(e)}", "Competitor Performance Error")
        return []

@frappe.whitelist()
def get_competitor_comparison_chart():
    """دریافت داده‌های نمودار مقایسه رقبا"""
    try:
        competitors = frappe.get_all("Competitor Analysis",
            fields=["competitor_name", "domain_authority", "monthly_traffic"],
            limit=10
        )
        
        chart_data = {
            "labels": [c.competitor_name for c in competitors],
            "datasets": [
                {
                    "name": "اعتبار دامنه",
                    "values": [c.domain_authority or 0 for c in competitors]
                },
                {
                    "name": "ترافیک ماهانه (هزار)",
                    "values": [(c.monthly_traffic or 0) / 1000 for c in competitors]
                }
            ]
        }
        
        return chart_data
        
    except Exception as e:
        frappe.log_error(f"خطا در دریافت نمودار مقایسه: {str(e)}", "Comparison Chart Error")
        return {}

@frappe.whitelist()
def get_price_trend_chart(competitor_name=None, days=30):
    """دریافت نمودار روند قیمت‌ها"""
    try:
        filters = {}
        if competitor_name:
            filters["competitor_analysis"] = competitor_name
        
        products = frappe.get_all("Competitor Product",
            filters=filters,
            fields=["item_name", "price_history"],
            limit=5
        )
        
        chart_data = {
            "labels": [],
            "datasets": []
        }
        
        # تهیه برچسب‌های تاریخ
        dates = []
        for i in range(days):
            date = (datetime.now() - timedelta(days=days-i-1)).strftime('%Y-%m-%d')
            dates.append(date)
        
        chart_data["labels"] = dates
        
        for product in products:
            if product.price_history:
                try:
                    history = json.loads(product.price_history)
                    price_data = [0] * days
                    
                    for entry in history:
                        entry_date = entry['date']
                        if entry_date in dates:
                            index = dates.index(entry_date)
                            price_data[index] = entry['price']
                    
                    chart_data["datasets"].append({
                        "name": product.item_name,
                        "values": price_data
                    })
                except:
                    continue
        
        return chart_data
        
    except Exception as e:
        frappe.log_error(f"خطا در دریافت نمودار روند قیمت: {str(e)}", "Price Trend Chart Error")
        return {}
