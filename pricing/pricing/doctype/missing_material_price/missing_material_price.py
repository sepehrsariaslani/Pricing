import frappe
from frappe.model.document import Document

class MissingMaterialPrice(Document):
    def validate(self):
        """اعتبارسنجی و محاسبه خودکار قیمت‌ها"""
        self.calculate_current_price()
        self.calculate_suggested_price()
        self.calculate_bom_usage()
        self.find_affected_items()
    
    def calculate_current_price(self):
        """محاسبه قیمت فعلی از سیستم"""
        if not self.item_code:
            return
        
        try:
            # استفاده از همان الگوریتم قیمت‌گیری بهبود یافته
            price_info = self.get_comprehensive_price(self.item_code)
            self.current_price = price_info.get('price', 0)
            self.price_source = price_info.get('source', 'قیمت یافت نشد')
            
        except Exception as e:
            frappe.logger().error(f"خطا در محاسبه قیمت فعلی {self.item_code}: {str(e)}")
            self.current_price = 0
            self.price_source = f"خطا: {str(e)}"
    
    def calculate_suggested_price(self):
        """محاسبه قیمت پیشنهادی بر اساس تحلیل"""
        if not self.item_code:
            return
        
        try:
            # قیمت پیشنهادی بر اساس میانگین قیمت مواد مشابه
            similar_items_avg = self.get_similar_items_average_price()
            if similar_items_avg > 0:
                self.suggested_price = similar_items_avg
                return
            
            # اگر مواد مشابه نبود، از valuation rate استفاده کن
            valuation_rate = frappe.db.get_value("Item", self.item_code, "valuation_rate")
            if valuation_rate and valuation_rate > 0:
                self.suggested_price = valuation_rate * 1.2  # 20% markup
                return
            
            self.suggested_price = 0
            
        except Exception as e:
            frappe.logger().error(f"خطا در محاسبه قیمت پیشنهادی {self.item_code}: {str(e)}")
            self.suggested_price = 0
    
    def calculate_bom_usage(self):
        """محاسبه تعداد BOMهای استفاده‌کننده"""
        if not self.item_code:
            return
        
        try:
            count = frappe.db.count("BOM Item", {
                "item_code": self.item_code,
                "parenttype": "BOM"
            })
            self.bom_usage_count = count
            
        except Exception as e:
            frappe.logger().error(f"خطا در محاسبه تعداد BOM {self.item_code}: {str(e)}")
            self.bom_usage_count = 0
    
    def find_affected_items(self):
        """یافتن محصولات تأثیرپذیر"""
        if not self.item_code:
            return
        
        try:
            affected_items = frappe.db.sql("""
                SELECT DISTINCT b.item
                FROM `tabBOM` b
                INNER JOIN `tabBOM Item` bi ON bi.parent = b.name
                WHERE bi.item_code = %s
                AND b.is_active = 1
                ORDER BY b.item
                LIMIT 10
            """, (self.item_code,))
            
            if affected_items:
                items_list = [item[0] for item in affected_items]
                self.affected_items = ", ".join(items_list)
                if len(affected_items) == 10:
                    self.affected_items += "..."
            else:
                self.affected_items = "هیچ محصولی یافت نشد"
                
        except Exception as e:
            frappe.logger().error(f"خطا در یافتن محصولات تأثیرپذیر {self.item_code}: {str(e)}")
            self.affected_items = f"خطا: {str(e)}"
    
    def get_comprehensive_price(self, item_code):
        """دریافت جامع قیمت با منبع"""
        try:
            # 1. Item Price فروش
            selling_price = frappe.db.get_value("Item Price", {
                "item_code": item_code,
                "selling": 1
            }, "price_list_rate")
            
            if selling_price and selling_price > 0:
                return {"price": selling_price, "source": "قیمت فروش"}
            
            # 2. Item Price خرید
            buying_price = frappe.db.get_value("Item Price", {
                "item_code": item_code,
                "buying": 1
            }, "price_list_rate")
            
            if buying_price and buying_price > 0:
                return {"price": buying_price, "source": "قیمت خرید"}
            
            # 3. Standard Rate
            standard_rate = frappe.db.get_value("Item", item_code, "standard_rate")
            if standard_rate and standard_rate > 0:
                return {"price": standard_rate, "source": "نرخ استاندارد"}
            
            # 4. Valuation Rate
            valuation_rate = frappe.db.get_value("Item", item_code, "valuation_rate")
            if valuation_rate and valuation_rate > 0:
                return {"price": valuation_rate, "source": "نرخ ارزش‌گذاری"}
            
            # 5. آخرین Purchase Receipt
            last_purchase = frappe.db.sql("""
                SELECT pri.rate
                FROM `tabPurchase Receipt Item` pri
                INNER JOIN `tabPurchase Receipt` pr ON pri.parent = pr.name
                WHERE pri.item_code = %s 
                AND pr.docstatus = 1
                AND pri.rate > 0
                ORDER BY pr.posting_date DESC
                LIMIT 1
            """, (item_code,))
            
            if last_purchase:
                return {"price": last_purchase[0][0], "source": "آخرین خرید"}
            
            return {"price": 0, "source": "قیمت یافت نشد"}
            
        except Exception as e:
            return {"price": 0, "source": f"خطا: {str(e)}"}
    
    def get_similar_items_average_price(self):
        """محاسبه میانگین قیمت مواد مشابه"""
        try:
            if not self.item_code:
                return 0
            
            # گرفتن item group
            item_group = frappe.db.get_value("Item", self.item_code, "item_group")
            if not item_group:
                return 0
            
            # میانگین قیمت مواد همان گروه
            avg_price = frappe.db.sql("""
                SELECT AVG(ip.price_list_rate)
                FROM `tabItem Price` ip
                INNER JOIN `tabItem` i ON i.name = ip.item_code
                WHERE i.item_group = %s
                AND ip.price_list_rate > 0
                AND ip.item_code != %s
            """, (item_group, self.item_code))
            
            if avg_price and avg_price[0][0]:
                return avg_price[0][0]
            
            return 0
            
        except Exception as e:
            frappe.logger().error(f"خطا در محاسبه میانگین قیمت مواد مشابه: {str(e)}")
            return 0
