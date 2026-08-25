import frappe
from frappe.model.document import Document

class MaterialSubstitution(Document):
    def validate(self):
        """اعتبارسنجی و محاسبه خودکار قیمت‌ها"""
        self.calculate_prices()
    
    def calculate_prices(self):
        """محاسبه خودکار قیمت کالای اصلی و جایگزین"""
        try:
            # محاسبه قیمت کالای اصلی
            if self.original_item:
                self.original_item_price = self.get_item_price(self.original_item)
            
            # محاسبه قیمت کالای جایگزین
            if self.substitute_item:
                self.substitute_item_price = self.get_item_price(self.substitute_item)
            
            # محاسبه تفاوت قیمت و درصد صرفه‌جویی
            if self.original_item_price and self.substitute_item_price:
                self.price_difference = self.original_item_price - self.substitute_item_price
                
                if self.original_item_price > 0:
                    self.cost_savings_percentage = (self.price_difference / self.original_item_price) * 100
                else:
                    self.cost_savings_percentage = 0
                    
        except Exception as e:
            frappe.logger().error(f"خطا در محاسبه قیمت جایگزینی مواد: {str(e)}")
    
    def get_item_price(self, item_code):
        """دریافت قیمت کالا از منابع مختلف"""
        try:
            # 1. ابتدا از Item Price فروش بگیر
            selling_price = frappe.db.get_value("Item Price", {
                "item_code": item_code,
                "selling": 1
            }, "price_list_rate")
            
            if selling_price and selling_price > 0:
                frappe.logger().info(f"💰 قیمت فروش {item_code}: {selling_price}")
                return selling_price
            
            # 2. از Item Price خرید بگیر
            buying_price = frappe.db.get_value("Item Price", {
                "item_code": item_code,
                "buying": 1
            }, "price_list_rate")
            
            if buying_price and buying_price > 0:
                frappe.logger().info(f"🛒 قیمت خرید {item_code}: {buying_price}")
                return buying_price
            
            # 3. از BOM محاسبه کن
            bom_cost = self.get_bom_cost(item_code)
            if bom_cost and bom_cost > 0:
                frappe.logger().info(f"🔧 هزینه BOM {item_code}: {bom_cost}")
                return bom_cost
            
            # 4. از Standard Rate کالا استفاده کن
            standard_rate = frappe.db.get_value("Item", item_code, "standard_rate")
            if standard_rate and standard_rate > 0:
                frappe.logger().info(f"📊 نرخ استاندارد {item_code}: {standard_rate}")
                return standard_rate
            
            # 5. از Valuation Rate استفاده کن
            valuation_rate = frappe.db.get_value("Item", item_code, "valuation_rate")
            if valuation_rate and valuation_rate > 0:
                frappe.logger().info(f"💎 نرخ ارزش‌گذاری {item_code}: {valuation_rate}")
                return valuation_rate
            
            # 6. از آخرین Purchase Receipt بگیر
            last_purchase_rate = self.get_last_purchase_rate(item_code)
            if last_purchase_rate and last_purchase_rate > 0:
                frappe.logger().info(f"📦 آخرین قیمت خرید {item_code}: {last_purchase_rate}")
                return last_purchase_rate
            
            # 7. از Stock Ledger Entry بگیر
            stock_rate = self.get_stock_rate(item_code)
            if stock_rate and stock_rate > 0:
                frappe.logger().info(f"📋 نرخ موجودی {item_code}: {stock_rate}")
                return stock_rate
            
            frappe.logger().warning(f"⚠️ هیچ قیمتی برای {item_code} یافت نشد")
            return 0
            
        except Exception as e:
            frappe.logger().error(f"خطا در دریافت قیمت {item_code}: {str(e)}")
            return 0
    
    def get_bom_cost(self, item_code):
        """محاسبه هزینه از BOM فعال"""
        try:
            bom = frappe.db.get_value("BOM", {
                "item": item_code,
                "is_active": 1,
                "is_default": 1
            }, "total_cost")
            
            return bom or 0
            
        except Exception as e:
            frappe.logger().error(f"خطا در دریافت BOM cost برای {item_code}: {str(e)}")
            return 0

    def get_last_purchase_rate(self, item_code):
        """دریافت آخرین قیمت خرید از Purchase Receipt"""
        try:
            last_purchase = frappe.db.sql("""
                SELECT pri.rate
                FROM `tabPurchase Receipt Item` pri
                INNER JOIN `tabPurchase Receipt` pr ON pri.parent = pr.name
                WHERE pri.item_code = %s 
                AND pr.docstatus = 1
                AND pri.rate > 0
                ORDER BY pr.posting_date DESC, pr.creation DESC
                LIMIT 1
            """, (item_code,))
            
            if last_purchase:
                return last_purchase[0][0]
            return 0
            
        except Exception as e:
            frappe.logger().error(f"خطا در دریافت آخرین قیمت خرید {item_code}: {str(e)}")
            return 0

    def get_stock_rate(self, item_code):
        """دریافت نرخ از Stock Ledger Entry"""
        try:
            stock_rate = frappe.db.sql("""
                SELECT incoming_rate
                FROM `tabStock Ledger Entry`
                WHERE item_code = %s 
                AND incoming_rate > 0
                ORDER BY posting_date DESC, creation DESC
                LIMIT 1
            """, (item_code,))
            
            if stock_rate:
                return stock_rate[0][0]
            return 0
            
        except Exception as e:
            frappe.logger().error(f"خطا در دریافت نرخ موجودی {item_code}: {str(e)}")
            return 0

@frappe.whitelist()
def get_item_price_for_substitution(item_code):
    """تابع عمومی برای دریافت قیمت کالا از JavaScript"""
    try:
        # ایجاد یک نمونه موقت برای استفاده از متدها
        temp_doc = MaterialSubstitution()
        price = temp_doc.get_item_price(item_code)
        return price
    except Exception as e:
        frappe.logger().error(f"خطا در دریافت قیمت برای {item_code}: {str(e)}")
        return 0
