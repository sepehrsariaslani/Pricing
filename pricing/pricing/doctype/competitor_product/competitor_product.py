import frappe
from frappe.model.document import Document
from frappe.utils import flt, today, now, cint
import json
import requests
from datetime import datetime, timedelta

class CompetitorProduct(Document):
    def validate(self):
        """اعتبارسنجی داده‌های محصول رقیب"""
        self.calculate_price_differences()
        self.set_last_updated()
        self.update_price_history()
    
    def calculate_price_differences(self):
        """محاسبه اختلاف قیمت و موقعیت بازار"""
        if self.item_code and self.competitor_price:
            # دریافت قیمت فعلی ما
            our_price = self.get_our_item_price()
            self.our_price = our_price
            
            if our_price:
                # محاسبه اختلاف قیمت
                self.price_difference = flt(self.competitor_price) - flt(our_price)
                self.price_difference_percent = (self.price_difference / our_price) * 100
                
                # تعیین موقعیت بازار
                if self.price_difference_percent > 20:
                    self.market_position = "گران‌تر"
                elif self.price_difference_percent > 5:
                    self.market_position = "پریمیوم"
                elif self.price_difference_percent < -20:
                    self.market_position = "ارزان‌تر"
                else:
                    self.market_position = "مشابه"
    
    def get_our_item_price(self):
        """دریافت قیمت فروش فعلی کالای ما"""
        try:
            # ابتدا از Item Price بگیر
            item_price = frappe.get_value("Item Price", 
                {"item_code": self.item_code, "selling": 1}, 
                "price_list_rate")
            
            if item_price:
                return item_price
            
            # در صورت عدم وجود از نرخ استاندارد Item استفاده کن
            standard_rate = frappe.get_value("Item", self.item_code, "standard_rate")
            return standard_rate or 0
            
        except Exception:
            return 0
    
    def set_last_updated(self):
        """تنظیم تاریخ آخرین به‌روزرسانی"""
        self.last_updated = now()
    
    def update_price_history(self):
        """به‌روزرسانی تاریخچه تغییرات قیمت"""
        if not self.competitor_price:
            return
            
        try:
            # دریافت تاریخچه فعلی
            price_history = []
            if self.price_history:
                price_history = json.loads(self.price_history)
            
            # بررسی آخرین قیمت ثبت شده
            current_price = flt(self.competitor_price)
            today_date = today()
            
            # اگر تاریخچه خالی است یا قیمت تغییر کرده
            if not price_history or price_history[-1]['price'] != current_price:
                price_history.append({
                    'date': today_date,
                    'price': current_price,
                    'timestamp': now()
                })
                
                # نگهداری حداکثر 50 رکورد آخر
                if len(price_history) > 50:
                    price_history = price_history[-50:]
                
                self.price_history = json.dumps(price_history)
                
        except Exception as e:
            frappe.log_error(f"خطا در به‌روزرسانی تاریخچه قیمت: {str(e)}", "Competitor Product Price History")
    
    def get_price_trend(self, days=30):
        """تحلیل روند تغییرات قیمت در بازه زمانی مشخص"""
        if not self.price_history:
            return {"trend": "ناشناخته", "change_percent": 0, "data_points": 0}
        
        try:
            price_history = json.loads(self.price_history)
            if len(price_history) < 2:
                return {"trend": "داده ناکافی", "change_percent": 0, "data_points": len(price_history)}
            
            # فیلتر کردن داده‌های بازه زمانی مورد نظر
            cutoff_date = datetime.now() - timedelta(days=days)
            recent_data = []
            
            for entry in price_history:
                entry_date = datetime.strptime(entry['date'], '%Y-%m-%d')
                if entry_date >= cutoff_date:
                    recent_data.append(entry)
            
            if len(recent_data) < 2:
                return {"trend": "داده ناکافی", "change_percent": 0, "data_points": len(recent_data)}
            
            # محاسبه روند
            first_price = recent_data[0]['price']
            last_price = recent_data[-1]['price']
            change_percent = ((last_price - first_price) / first_price) * 100
            
            if change_percent > 5:
                trend = "صعودی"
            elif change_percent < -5:
                trend = "نزولی"
            else:
                trend = "ثابت"
            
            return {
                "trend": trend,
                "change_percent": change_percent,
                "data_points": len(recent_data),
                "first_price": first_price,
                "last_price": last_price
            }
            
        except Exception as e:
            frappe.log_error(f"خطا در تحلیل روند قیمت: {str(e)}", "Competitor Product Trend Analysis")
            return {"trend": "خطا", "change_percent": 0, "data_points": 0}
    
    def should_send_price_alert(self, threshold_percent=10):
        """بررسی نیاز به ارسال هشدار تغییر قیمت"""
        trend_data = self.get_price_trend(days=7)  # بررسی هفته اخیر
        
        if abs(trend_data.get('change_percent', 0)) >= threshold_percent:
            return True, trend_data
        
        return False, trend_data
    
    def crawl_product_data(self):
        """کرال اطلاعات محصول از وب‌سایت رقیب"""
        if not self.product_url:
            frappe.throw("آدرس محصول مشخص نشده است")
        
        try:
            # استفاده از کرالر موجود در Competitor Analysis
            competitor_analysis = frappe.get_doc("Competitor Analysis", self.competitor_analysis)
            
            if not competitor_analysis.website_url:
                frappe.throw("آدرس وب‌سایت رقیب در تحلیل رقیب مشخص نشده است")
            
            # import کرالر
            from .web_crawler import CompetitorWebCrawler
            
            crawler = CompetitorWebCrawler(competitor_analysis.name)
            
            # کرال اطلاعات محصول خاص
            product_data = crawler.crawl_single_product(self.product_url)
            
            if product_data:
                # به‌روزرسانی اطلاعات محصول
                if product_data.get('name'):
                    self.item_name = product_data['name']
                
                if product_data.get('price'):
                    self.competitor_price = flt(product_data['price'])
                
                if product_data.get('description'):
                    self.description = product_data['description']
                
                if product_data.get('image_url'):
                    self.image_url = product_data['image_url']
                
                if product_data.get('availability'):
                    availability_map = {
                        'in_stock': 'موجود',
                        'out_of_stock': 'ناموجود',
                        'limited': 'محدود',
                        'discontinued': 'متوقف شده'
                    }
                    self.availability = availability_map.get(product_data['availability'], 'ناشناخته')
                
                if product_data.get('stock_status'):
                    self.stock_status = product_data['stock_status']
                
                # اطلاعات SEO
                if product_data.get('seo_title'):
                    self.seo_title = product_data['seo_title']
                
                if product_data.get('seo_description'):
                    self.seo_description = product_data['seo_description']
                
                if product_data.get('meta_keywords'):
                    self.meta_keywords = product_data['meta_keywords']
                
                # تنظیم زمان آخرین کرال
                self.last_crawled = now()
                
                # ذخیره تغییرات
                self.save()
                
                return {"success": True, "message": "اطلاعات محصول با موفقیت به‌روزرسانی شد", "data": product_data}
            else:
                return {"success": False, "message": "امکان استخراج اطلاعات محصول وجود ندارد"}
                
        except Exception as e:
            frappe.log_error(f"خطا در کرال محصول {self.name}: {str(e)}", "Competitor Product Crawl")
            return {"success": False, "message": f"خطا در کرال محصول: {str(e)}"}
    
    def generate_comparison_report(self):
        """تولید گزارش مقایسه کامل محصول"""
        try:
            # اطلاعات پایه
            report_data = {
                "product_name": self.item_name,
                "competitor_analysis": self.competitor_analysis,
                "our_item_code": self.item_code,
                "product_url": self.product_url,
                "last_updated": self.last_updated
            }
            
            # مقایسه قیمت
            report_data["pricing"] = {
                "competitor_price": self.competitor_price,
                "our_price": self.our_price,
                "price_difference": self.price_difference,
                "price_difference_percent": self.price_difference_percent,
                "market_position": self.market_position
            }
            
            # تحلیل روند قیمت
            trend_7d = self.get_price_trend(days=7)
            trend_30d = self.get_price_trend(days=30)
            
            report_data["price_trends"] = {
                "weekly": trend_7d,
                "monthly": trend_30d
            }
            
            # وضعیت موجودی
            report_data["availability"] = {
                "status": self.availability,
                "stock_details": self.stock_status
            }
            
            # اطلاعات SEO
            report_data["seo_analysis"] = {
                "title": self.seo_title,
                "description": self.seo_description,
                "keywords": self.meta_keywords,
                "title_length": len(self.seo_title or ""),
                "description_length": len(self.seo_description or "")
            }
            
            # امتیاز کیفیت
            report_data["quality"] = {
                "rating": self.quality_rating,
                "features_comparison": self.features_comparison
            }
            
            # توصیه‌های استراتژیک
            recommendations = self.generate_strategic_recommendations()
            report_data["recommendations"] = recommendations
            
            return report_data
            
        except Exception as e:
            frappe.log_error(f"خطا در تولید گزارش مقایسه: {str(e)}", "Competitor Product Report")
            return {"error": f"خطا در تولید گزارش: {str(e)}"}
    
    def generate_strategic_recommendations(self):
        """تولید توصیه‌های استراتژیک بر اساس تحلیل محصول"""
        recommendations = []
        
        try:
            # توصیه‌های قیمت‌گذاری
            if self.market_position == "گران‌تر":
                recommendations.append({
                    "type": "قیمت‌گذاری",
                    "priority": "بالا",
                    "message": f"محصول رقیب {self.price_difference_percent:.1f}% گران‌تر از ما است. فرصت افزایش قیمت وجود دارد."
                })
            elif self.market_position == "ارزان‌تر":
                recommendations.append({
                    "type": "قیمت‌گذاری",
                    "priority": "بالا",
                    "message": f"محصول رقیب {abs(self.price_difference_percent):.1f}% ارزان‌تر از ما است. بررسی کاهش قیمت یا بهبود ارزش پیشنهادی ضروری است."
                })
            
            # توصیه‌های موجودی
            if self.availability == "ناموجود":
                recommendations.append({
                    "type": "موجودی",
                    "priority": "متوسط",
                    "message": "محصول رقیب ناموجود است. فرصت مناسب برای افزایش فروش و جذب مشتریان رقیب."
                })
            
            # توصیه‌های SEO
            if self.seo_title and len(self.seo_title) > 60:
                recommendations.append({
                    "type": "SEO",
                    "priority": "پایین",
                    "message": "عنوان SEO رقیب طولانی است. می‌توانیم با عنوان بهینه‌تر رتبه بهتری کسب کنیم."
                })
            
            # تحلیل روند قیمت
            trend_data = self.get_price_trend(days=30)
            if trend_data.get('trend') == 'صعودی' and trend_data.get('change_percent', 0) > 10:
                recommendations.append({
                    "type": "روند بازار",
                    "priority": "بالا",
                    "message": f"قیمت رقیب در ماه اخیر {trend_data['change_percent']:.1f}% افزایش یافته. ممکن است نشان‌دهنده افزایش تقاضا باشد."
                })
            
            return recommendations
            
        except Exception as e:
            frappe.log_error(f"خطا در تولید توصیه‌های استراتژیک: {str(e)}", "Strategic Recommendations")
            return [{"type": "خطا", "priority": "بالا", "message": "امکان تولید توصیه‌ها وجود ندارد"}]
