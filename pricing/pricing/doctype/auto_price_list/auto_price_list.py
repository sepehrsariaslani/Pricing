import frappe
from frappe.model.document import Document
from frappe.utils import flt, cint, get_datetime, add_days, today, getdate
import math
import json
from datetime import datetime, timedelta
from collections import defaultdict
from .ai import PricingAI
try:
    import numpy_financial as npf
except ImportError:
    npf = None
try:
    import requests
except ImportError:
    requests = None

# Advanced AI/ML Libraries
try:
    import pandas as pd
    import numpy as np
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.linear_model import LinearRegression, Ridge
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_absolute_error, r2_score
    ML_AVAILABLE = True
except ImportError:
    pd = None
    np = None
    ML_AVAILABLE = False

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False

try:
    from scipy import stats
    from scipy.optimize import minimize
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

try:
    from statsmodels.tsa.seasonal import seasonal_decompose
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False

class AutoPriceList(Document):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._overhead_cache = None
        self._market_data_cache = {}
        self._bom_cache = {}
        self._workstation_cache = {}
        self._pricing_ai = None
    
    @property
    def pricing_ai(self):
        """Get PricingAI instance (lazy loading)"""
        if self._pricing_ai is None:
            self._pricing_ai = PricingAI(self)
        return self._pricing_ai
    
    def get_item_price(self, item_code, price_list=None):
        """
        دریافت قیمت کالا از جدول قیمت‌ها
        این تابع قیمت یک کالا را از جدول Item Price دریافت می‌کند
        اگر لیست قیمت مشخص نشده باشد، از لیست قیمت فعلی استفاده می‌کند
        در صورت عدم وجود قیمت، قیمت استاندارد کالا را برمی‌گرداند
        """
        target_price_list = price_list or self.compare_with_price_list or self.price_list
        
        # Try to get price from Item Price table
        item_price = frappe.db.get_value("Item Price", {
            "item_code": item_code,
            "price_list": target_price_list
        }, "price_list_rate")
        
        if item_price:
            return flt(item_price)
        
        # Fallback to standard rate from Item master
        standard_rate = frappe.db.get_value("Item", item_code, "standard_rate")
        return flt(standard_rate) if standard_rate else 0
    def validate(self):
        """
        اعتبارسنجی سند
        این تابع قبل از ذخیره سند اجرا می‌شود و صحت داده‌ها را بررسی می‌کند
        تاریخ‌های شروع و پایان را کنترل کرده و قیمت‌ها را محاسبه می‌کند
        """
        self.validate_dates()
        self.calculate_total_interest_percentages()
        # Remove automatic calculation to prevent database locks

    def validate_dates(self):
        """
        اعتبارسنجی تاریخ‌ها
        این تابع بررسی می‌کند که تاریخ شروع از تاریخ پایان کوچکتر باشد
        در صورت نادرست بودن تاریخ‌ها، خطا نمایش می‌دهد
        """
        if self.valid_from and self.valid_until and self.valid_from > self.valid_until:
            frappe.throw(frappe._("Valid From date cannot be later than Valid Until date"))
    
    def calculate_total_interest_percentages(self):
        """محاسبه درصد کل بهره برای قسطی و تأخیری"""
        # محاسبه درصد کل بهره قسطی
        if self.enable_installment and self.monthly_interest_rate and self.number_of_months:
            self.installment_total_interest_percentage = self.monthly_interest_rate * self.number_of_months
        else:
            self.installment_total_interest_percentage = 0
            
        # محاسبه درصد کل بهره تأخیری  
        if self.enable_deferred_payment and self.deferred_payment_interest_rate and self.deferred_payment_months:
            self.deferred_payment_total_interest_percentage = self.deferred_payment_interest_rate * self.deferred_payment_months
        else:
            self.deferred_payment_total_interest_percentage = 0
    @frappe.whitelist()
    def fetch_items(self):
        """
        دریافت کالاها بر اساس فیلترهای تعریف شده
        این تابع کالاهای مناسب را از جدول Item دریافت می‌کند
        منابع داده: Item, Item Group, Brand, Warehouse
        هدف اصلی: انتخاب کالاهای مناسب برای محاسبه قیمت
        """
        filters = {}
        if self.item_group:
            filters['item_group'] = self.item_group
        if self.brand:
            filters['brand'] = self.brand
        
        # اضافه کردن فیلتر نام کالا
        if self.item_name_filter:
            filters['item_name'] = ['like', f'%{self.item_name_filter}%']
        
        items = frappe.get_all('Item', filters=filters, fields=['item_code', 'item_name', 'item_group', 'brand'])
        
        for item in items:
            if not any(existing_item.item_code == item.item_code for existing_item in self.items):
                self.append('items', {
                    'item_code': item.item_code,
                    'item_name': item.item_name,
                    'item_group': item.item_group,
                    'brand': item.brand
                })

    def get_cached_workstation_costs(self):
        """
        دریافت هزینه‌های workstation از cache برای بهبود عملکرد
        """
        if not hasattr(self, '_workstation_cache'):
            self._workstation_cache = {}
            
            workstations = frappe.get_all("Workstation", 
                fields=["name", "hour_rate_electricity", "hour_rate_consumable", 
                       "hour_rate_rent", "hour_rate_labour"])
            
            for ws in workstations:
                self._workstation_cache[ws.name] = ws
                
        return self._workstation_cache

    def calculate_subcontracting_cost(self, operation):
        """
        محاسبه هزینه پیمانکاری برای یک عملیات
        این تابع کارهای پیمانکاری مثل رنگ‌کاری، جوشکاری و غیره را شناسایی می‌کند
        """
        subcontracting_cost = 0
        
        try:
            # کلمات کلیدی برای شناسایی کارهای پیمانکاری
            subcontracting_keywords = [
                'رنگ', 'پوشش', 'آبکاری', 'جوشکاری', 'برش', 'تراش', 
                'سوراخکاری', 'خم', 'پرس', 'مونتاژ خارجی', 'پیمانکاری',
                'painting', 'coating', 'welding', 'cutting', 'machining',
                'drilling', 'bending', 'pressing', 'subcontract'
            ]
            
            operation_name = operation.operation.lower() if operation.operation else ""
            operation_desc = operation.description.lower() if operation.description else ""
            
            # بررسی اینکه آیا این عملیات پیمانکاری است یا نه
            is_subcontracting = any(keyword in operation_name or keyword in operation_desc 
                                  for keyword in subcontracting_keywords)
            
            if is_subcontracting:
                # اگر operating_cost موجود است، از آن استفاده کن
                if hasattr(operation, 'operating_cost') and operation.operating_cost:
                    subcontracting_cost = flt(operation.operating_cost)
                # در غیر این صورت از hour_rate و time محاسبه کن
                elif hasattr(operation, 'hour_rate') and hasattr(operation, 'time_in_mins'):
                    if operation.hour_rate and operation.time_in_mins:
                        time_in_hours = flt(operation.time_in_mins) / 60
                        subcontracting_cost = flt(operation.hour_rate) * time_in_hours
                
                # اگر هیچ قیمتی تعریف نشده، از قیمت پیش‌فرض استفاده کن
                if not subcontracting_cost:
                    # جستجو برای آیتم خدمات مرتبط
                    service_item = self.find_related_service_item(operation_name, operation_desc)
                    if service_item:
                        subcontracting_cost = flt(service_item.get('standard_rate', 0))
                
                frappe.logger().info(f"عملیات پیمانکاری شناسایی شد: {operation.operation} - هزینه: {subcontracting_cost}")
            
        except Exception as e:
            frappe.logger().error(f"خطا در محاسبه هزینه پیمانکاری: {str(e)}")
            subcontracting_cost = 0
        
        return subcontracting_cost

    def find_related_service_item(self, operation_name, operation_desc):
        """
        جستجو برای آیتم خدمات مرتبط با عملیات پیمانکاری
        مثلاً برای "رنگ مشکی صندلی" آیتم "خدمات رنگ مشکی صندلی" را پیدا می‌کند
        """
        try:
            # کلمات کلیدی برای جستجو
            search_terms = []
            
            # اضافه کردن کلمات از نام عملیات
            if operation_name:
                search_terms.extend(operation_name.split())
            
            # اضافه کردن کلمات از توضیحات
            if operation_desc:
                search_terms.extend(operation_desc.split())
            
            # حذف کلمات کوتاه و غیرضروری
            search_terms = [term for term in search_terms if len(term) > 2]
            
            if search_terms:
                # جستجو در آیتم‌های خدماتی
                service_items = frappe.get_all("Item",
                    filters={
                        "is_service_item": 1,
                        "disabled": 0
                    },
                    fields=["name", "item_name", "standard_rate"],
                    limit=10
                )
                
                # پیدا کردن بهترین تطبیق
                for item in service_items:
                    item_name_lower = item.item_name.lower() if item.item_name else ""
                    
                    # بررسی تطبیق کلمات کلیدی
                    matches = sum(1 for term in search_terms if term in item_name_lower)
                    
                    if matches >= 2:  # حداقل 2 کلمه تطبیق داشته باشد
                        frappe.logger().info(f"آیتم خدمات مرتبط پیدا شد: {item.item_name} - قیمت: {item.standard_rate}")
                        return item
            
        except Exception as e:
            frappe.logger().error(f"خطا در جستجوی آیتم خدمات: {str(e)}")
        
        return None

    def _batch_load_boms(self, item_codes):
        """Load all BOMs in batch to avoid repeated queries"""
        if not hasattr(self, '_bom_cache'):
            self._bom_cache = {}
            
        # Get all BOMs for items
        boms = frappe.get_all("BOM", 
            filters={
                "item": ["in", item_codes],
                "is_active": 1,
                "is_default": 1
            },
            fields=["name", "item", "raw_material_cost", "operating_cost", "total_cost"]
        )
        
        for bom in boms:
            self._bom_cache[bom.item] = bom
            
        return self._bom_cache
    
    def _get_cached_overhead_costs(self):
        """Get overhead costs with caching"""
        if not hasattr(self, '_overhead_cache'):
            try:
                self._overhead_cache = self.get_overhead_costs()
                if not self._overhead_cache:
                    self._overhead_cache = {'total_overhead': 0}
            except Exception as e:
                frappe.logger().error(f"Error getting overhead costs: {str(e)}")
                self._overhead_cache = {'total_overhead': 0}
        return self._overhead_cache
    
    def calculate_price_based_on_steps_fast(self, item, total_cost):
        """Fast version of stepwise pricing calculation"""
        current_price = flt(total_cost)
        calculation_steps = [f"هزینه پایه: {current_price:,.0f} ریال"]
        
        # Apply only essential steps for speed
        if self.profit_margin:
            profit_amount = current_price * (self.profit_margin / 100)
            current_price += profit_amount
            calculation_steps.append(f"سود {self.profit_margin}%: +{profit_amount:,.0f} = {current_price:,.0f} ریال")
        
        if self.commission_percentage:
            commission_amount = current_price * (self.commission_percentage / 100)
            calculation_steps.append(f"کمیسیون {self.commission_percentage}%: {commission_amount:,.0f} ریال")
        
        if self.price_rounding_amount and self.price_rounding_amount > 0:
            rounded_price = math.ceil(current_price / self.price_rounding_amount) * self.price_rounding_amount
            calculation_steps.append(f"رند کردن: {current_price:,.0f} → {rounded_price:,.0f} ریال")
            current_price = rounded_price
        
        calculation_steps.append(f"قیمت نهایی: {current_price:,.0f} ریال")
        return current_price, calculation_steps

    @frappe.whitelist()
    def calculate_item_prices_internal(self):
        """
        محاسبه قیمت برای تمام کالاها - نسخه بهینه‌شده
        """
        if not self.items:
            return
        
        # Pre-load all required data in batch to avoid repeated queries
        item_codes = [item.item_code for item in self.items if item.item_code]
        if not item_codes:
            return
            
        # Batch load all BOMs
        bom_data = self._batch_load_boms(item_codes)
        
        # Batch load overhead costs once
        overhead_costs = self._get_cached_overhead_costs()
        
        # Calculate prices for each item with cached data
        for item in self.items:
            if not item.item_code:
                continue
            
            # بررسی اینکه آیا کالا یک Product Bundle است
            if self.is_product_bundle(item.item_code):
                self.calculate_bundle_price(item)
                continue
            
            # Use cached BOM data instead of individual queries
            bom_info = bom_data.get(item.item_code)
            
            if bom_info:
                # Get BOM document for detailed calculations
                bom = frappe.get_doc("BOM", bom_info.name)
                
                # Use cached BOM costs
                item.raw_material_cost = flt(bom_info.raw_material_cost) or 0
                item.operation_cost = flt(bom_info.operating_cost) or 0
                item.subcontracting_cost = 0  # Initialize subcontracting cost
                
                # Only do detailed calculation if basic costs are zero
                if not item.raw_material_cost:
                    item.raw_material_cost = self.calculate_raw_material_cost_with_substitutions(bom)
                
                # Initialize operation costs
                item.electricity_cost = 0
                item.consumable_cost = 0
                item.rent_cost = 0
                item.labor_cost = 0
                
                # Use cached overhead costs instead of calculating each time
                if overhead_costs and isinstance(overhead_costs, dict):
                    item.overhead_cost = overhead_costs.get('total_overhead', 0)
                else:
                    item.overhead_cost = 0
                
                # Skip detailed operation calculations for speed
                # Only calculate if operation_cost is zero
                if not item.operation_cost:
                    workstation_cache = self.get_cached_workstation_costs()
                    if hasattr(bom, 'operations'):
                        for operation in bom.operations[:3]:  # Limit to first 3 operations for speed
                            # Calculate subcontracting costs
                            item.subcontracting_cost += self.calculate_subcontracting_cost(operation)
                            if operation.workstation and operation.time_in_mins:
                                # Get workstation details from cache
                                workstation_data = workstation_cache.get(operation.workstation, {})
                                
                                # Convert operation time from minutes to hours
                                operation_time_in_hours = operation.time_in_mins / 60
                                
                                # Calculate costs based on operation time and hourly rates
                                item.electricity_cost += workstation_data.get('hour_rate_electricity', 0) * operation_time_in_hours
                                item.consumable_cost += workstation_data.get('hour_rate_consumable', 0) * operation_time_in_hours
                                item.rent_cost += workstation_data.get('hour_rate_rent', 0) * operation_time_in_hours
                                item.labor_cost += workstation_data.get('hour_rate_labour', 0) * operation_time_in_hours
                
                # Calculate total operation cost
                item.operation_cost = (
                    item.electricity_cost +
                    item.consumable_cost +
                    item.rent_cost +
                    item.labor_cost +
                    item.subcontracting_cost
                )
            
            # Calculate overhead cost safely
            try:
                if overhead_costs and isinstance(overhead_costs, dict):
                    item.overhead_cost = overhead_costs.get('total_overhead', 0)
                else:
                    item.overhead_cost = 0
            except Exception as e:
                frappe.logger().error(f"Error setting overhead cost: {str(e)}")
                item.overhead_cost = 0
            
            # Calculate total cost
            total_cost = (
                (item.raw_material_cost or 0) +
                (item.operation_cost or 0) +
                (item.overhead_cost or 0)
            )
            
            # Update base item prices
            item.total_cost = total_cost
            
            # Use step-by-step pricing calculation based on pricing_steps table
            if self.pricing_steps:
                # Use the detailed step-by-step calculation
                self.calculate_step_by_step_pricing(item)
                # Also generate detailed calculation steps for display
                final_price, calculation_steps = self.calculate_price_based_on_steps(item, total_cost)
                item.step_by_step_calculation = "\n".join(calculation_steps)
            else:
                # Simple profit margin calculation
                final_price = total_cost * (1 + (self.profit_margin or 0) / 100)
                item.final_selected_price = final_price
                item.step_by_step_calculation = f"هزینه پایه: {total_cost:,.0f}\nسود {self.profit_margin or 0}%: {final_price:,.0f} ریال"
            
            # Skip market comparison for speed - can be done separately if needed
        
        # Skip heavy calculations for performance
        frappe.logger().info(f"محاسبه قیمت برای {len(self.items)} کالا تکمیل شد")

    def get_cached_overhead_cost(self):
        """
        محاسبه هزینه سربار با cache برای بهبود performance
        این تابع یک بار محاسبه کرده و نتیجه را cache می‌کند
        """
        if self._overhead_cache is not None:
            return self._overhead_cache
        
        # Get total overhead costs from GL entries
        overhead_accounts = frappe.get_all("Account",
            filters={
                "account_type": "Expense Account",
                "is_group": 0
            },
            pluck="name"
        )
        
        if not overhead_accounts:
            self._overhead_cache = 0
            return 0
        
        # Get total overhead amount with optimized query
        total_overhead = frappe.db.sql("""
            SELECT SUM(debit) as total
            FROM `tabGL Entry`
            WHERE account IN %(accounts)s
            AND posting_date BETWEEN %(from_date)s AND %(to_date)s
        """, {
            "accounts": tuple(overhead_accounts),
            "from_date": self.valid_from,
            "to_date": self.valid_until or "2099-12-31"
        }, as_dict=1)
        
        total_overhead = total_overhead[0].total if total_overhead else 0
        self._overhead_cache = flt(total_overhead)
        return self._overhead_cache
    
    def calculate_overhead_cost(self, item):
        """
        محاسبه هزینه سربار برای یک کالا با استفاده از cache
        """
        total_overhead = self.get_cached_overhead_cost()
        total_items = len(self.items)
        
        if total_items:
            item.overhead_cost = total_overhead / total_items
        else:
            item.overhead_cost = 0
    
    def calculate_raw_material_cost_with_substitutions(self, bom):
        """
        محاسبه هزینه مواد اولیه با در نظر گیری جایگزینی مواد
        این تابع ابتدا هزینه را از خود BOM دریافت می‌کند
        اگر صفر باشد، از اجزای BOM محاسبه کرده و جایگزینی مواد را اعمال می‌کند
        داده‌ها از BOM و جدول جایگزینی مواد آمده و هدف بهینه‌سازی هزینه‌هاست
        """
        # First try to get from BOM's raw_material_cost
        if bom.raw_material_cost and bom.raw_material_cost > 0:
            return bom.raw_material_cost
        
        # If zero, calculate from BOM items with substitutions
        total_cost = 0
        
        # Create substitution mapping
        substitution_map = {}
        if self.material_substitutions:
            for sub in self.material_substitutions:
                substitution_map[sub.original_item] = sub.substitute_item
        
        # Calculate cost for each BOM item (NO manual prices here - they are handled separately)
        for bom_item in bom.items:
            item_code = bom_item.item_code
            
            # Priority: Substitution > Original Price (manual prices handled elsewhere)
            if item_code in substitution_map:
                substitute_item = substitution_map[item_code]
                # Get the price of substitute item
                item_price = self.get_item_price(substitute_item)
            else:
                # Use original item price
                item_price = self.get_item_price(item_code)
            
            # Calculate cost based on quantity
            item_cost = item_price * bom_item.qty
            total_cost += item_cost
        
        return total_cost
    
    
    def calculate_item_cost(self, item_code):
        """
        محاسبه هزینه یک آیتم خاص با در نظر گیری قیمت‌های دستی جدید
        این تابع برای به‌روزرسانی قیمت‌ها هنگام تغییر قیمت مواد اولیه استفاده می‌شود
        """
        # استفاده از روش جدید exploded items
        return self.calculate_item_cost_with_exploded_items(item_code)
    
    def calculate_final_price_for_item(self, item):
        """
        محاسبه قیمت نهایی برای یک آیتم با اعمال pricing steps
        """
        try:
            # شروع با هزینه مواد اولیه
            current_price = flt(item.raw_material_cost or 0)
            
            if current_price <= 0:
                return 0
            
            frappe.logger().info(f"      🧮 شروع محاسبه قیمت نهایی برای {item.item_code}")
            frappe.logger().info(f"         هزینه مواد اولیه: {current_price:,.0f}")
            
            # اعمال pricing steps به ترتیب
            if self.pricing_steps:
                for step in self.pricing_steps:
                    step_type = step.step_type
                    percentage = flt(step.percentage or 0)
                    
                    if percentage == 0:
                        continue
                    
                    old_price = current_price
                    
                    if step_type == "سود":
                        # اضافه کردن سود
                        current_price = current_price * (1 + percentage / 100)
                        frappe.logger().info(f"         سود {percentage}%: {old_price:,.0f} → {current_price:,.0f}")
                        
                    elif step_type == "افزایش قیمت":
                        # افزایش قیمت
                        current_price = current_price * (1 + percentage / 100)
                        frappe.logger().info(f"         افزایش قیمت {percentage}%: {old_price:,.0f} → {current_price:,.0f}")
                        
                    elif step_type == "کمیسیون":
                        # کسر کمیسیون
                        current_price = current_price * (1 - percentage / 100)
                        frappe.logger().info(f"         کمیسیون {percentage}%: {old_price:,.0f} → {current_price:,.0f}")
                        
                    elif step_type == "بهره تأخیری/قسطی":
                        # اضافه کردن بهره
                        current_price = current_price * (1 + percentage / 100)
                        frappe.logger().info(f"         بهره {percentage}%: {old_price:,.0f} → {current_price:,.0f}")
                        
                    elif step_type == "رند کردن":
                        # رند کردن قیمت
                        if percentage > 0:
                            round_to = int(percentage)
                            current_price = math.ceil(current_price / round_to) * round_to
                            frappe.logger().info(f"         رند کردن به {round_to}: {old_price:,.0f} → {current_price:,.0f}")
                        
                    elif step_type == "تخفیف":
                        # کسر تخفیف
                        current_price = current_price * (1 - percentage / 100)
                        frappe.logger().info(f"         تخفیف {percentage}%: {old_price:,.0f} → {current_price:,.0f}")
            
            frappe.logger().info(f"         قیمت نهایی: {current_price:,.0f}")
            return current_price
            
        except Exception as e:
            frappe.logger().error(f"خطا در محاسبه قیمت نهایی: {str(e)}")
            return flt(item.raw_material_cost or 0)
    
    def is_item_affected_by_manual_prices(self, item_code, manual_price_map):
        """
        بررسی اینکه آیا یک آیتم تحت تأثیر قیمت‌های دستی مواد اولیه است یا نه
        """
        try:
            frappe.logger().info(f"      🔍 بررسی تأثیر قیمت‌های دستی برای {item_code}")
            print(f"      🔍 بررسی تأثیر قیمت‌های دستی برای {item_code}")
            
            # پیدا کردن BOM فعال
            bom_name = frappe.db.get_value("BOM", {
                "item": item_code,
                "is_active": 1,
                "is_default": 1
            }, "name")
            
            if not bom_name:
                frappe.logger().info(f"      ❌ BOM فعال برای {item_code} پیدا نشد")
                print(f"      ❌ BOM فعال برای {item_code} پیدا نشد")
                return False
            
            frappe.logger().info(f"      ✅ BOM پیدا شد: {bom_name}")
            print(f"      ✅ BOM پیدا شد: {bom_name}")
            
            # ابتدا بررسی exploded items
            exploded_items = frappe.get_all("BOM Explosion Item", 
                filters={"parent": bom_name},
                fields=["item_code"]
            )
            
            frappe.logger().info(f"      📋 تعداد exploded items: {len(exploded_items)}")
            print(f"      📋 تعداد exploded items: {len(exploded_items)}")
            print(f"      🔍 قیمت‌های دستی موجود: {list(manual_price_map.keys())}")
            
            # بررسی اینکه آیا هیچ یک از مواد اولیه در لیست قیمت‌های دستی هست یا نه
            affected_materials = []
            all_materials = []
            
            if exploded_items:
                # استفاده از exploded items
                print(f"      🔍 بررسی exploded items...")
                for exploded_item in exploded_items:
                    all_materials.append(exploded_item.item_code)
                    print(f"        🔍 بررسی ماده: {exploded_item.item_code}")
                    if exploded_item.item_code in manual_price_map:
                        affected_materials.append(exploded_item.item_code)
                        print(f"         ✅ ماده متأثر در exploded: {exploded_item.item_code}")
            else:
                # اگر exploded items نداشت، از BOM items استفاده کن
                print(f"      📋 exploded items خالی است، بررسی BOM items")
                bom = frappe.get_doc("BOM", bom_name)
                for bom_item in bom.items:
                    all_materials.append(bom_item.item_code)
                    print(f"        🔍 بررسی ماده BOM: {bom_item.item_code}")
                    if bom_item.item_code in manual_price_map:
                        affected_materials.append(bom_item.item_code)
                        print(f"         ✅ ماده متأثر در BOM: {bom_item.item_code}")
            
            print(f"      📋 تمام مواد موجود: {all_materials}")
            print(f"      🎯 مواد متأثر: {affected_materials}")
            
            if affected_materials:
                frappe.logger().info(f"      ✅ مواد متأثر پیدا شد: {affected_materials}")
                print(f"      ✅ مواد متأثر پیدا شد: {affected_materials}")
                return True
            else:
                frappe.logger().info(f"      ❌ هیچ ماده متأثری پیدا نشد")
                print(f"      ❌ هیچ ماده متأثری پیدا نشد")
                print(f"      🔍 دلیل: مواد موجود {all_materials} با قیمت‌های دستی {list(manual_price_map.keys())} مطابقت ندارند")
                return False
            
        except Exception as e:
            frappe.logger().error(f"      ❌ خطا در بررسی تأثیر: {str(e)}")
            print(f"      ❌ خطا در بررسی تأثیر: {str(e)}")
            import traceback
            print(f"      🔍 جزئیات خطا: {traceback.format_exc()}")
            return False
    
    def calculate_final_price_from_cost(self, cost):
        """
        محاسبه قیمت نهایی از روی هزینه با اعمال pricing steps
        """
        from frappe.utils import flt
        
        current_price = flt(cost)
        
        if not self.pricing_steps:
            # اگر pricing steps تعریف نشده، فقط سود اضافه کن
            if self.profit_margin:
                profit_amount = current_price * (self.profit_margin / 100)
                return current_price + profit_amount
            return current_price
        
        # مرتب‌سازی مراحل بر اساس ترتیب
        pricing_steps = sorted(self.pricing_steps, key=lambda x: x.step_order or 0)
        
        for step in pricing_steps:
            if step.step_type == "سود" and self.profit_margin:
                profit_amount = current_price * (self.profit_margin / 100)
                current_price += profit_amount
                
            elif step.step_type == "افزایش قیمت" and self.required_markup_percentage:
                markup_amount = current_price * (self.required_markup_percentage / 100)
                current_price += markup_amount
                
            elif step.step_type == "کمیسیون" and self.commission_percentage:
                # کسر کمیسیون - قیمت باید بالاتر باشد تا بعد از کسر کمیسیون سود مطلوب حاصل شود
                commission_factor = 1 / (1 - (self.commission_percentage / 100))
                current_price *= commission_factor
                
            elif step.step_type == "بهره تأخیری" and self.enable_installment and self.monthly_interest_rate and self.number_of_months:
                # اضافه کردن بهره
                total_interest = current_price * (self.monthly_interest_rate / 100) * self.number_of_months
                current_price += total_interest
                
            elif step.step_type == "رند کردن" and self.price_rounding_amount:
                # رند کردن قیمت
                import math
                rounding_amount = self.price_rounding_amount
                current_price = math.ceil(current_price / rounding_amount) * rounding_amount
                
            elif step.step_type == "تخفیف" and hasattr(self, 'target_discount_percentage') and self.target_discount_percentage:
                # اگر تخفیف باشد، قیمت را بالا ببر تا بعد از تخفیف قیمت مطلوب حاصل شود
                discount_factor = 1 / (1 - (self.target_discount_percentage / 100))
                current_price *= discount_factor
        
        return flt(current_price)
    
    def calculate_item_cost_with_exploded_items(self, item_code):
        """
        محاسبه هزینه آیتم با استفاده از exploded items و قیمت‌های دستی
        """
        try:
            print(f"🔍 شروع محاسبه هزینه برای {item_code}")
            
            # پیدا کردن BOM فعال
            bom_name = frappe.db.get_value("BOM", {
                "item": item_code,
                "is_active": 1,
                "is_default": 1
            }, "name")
            
            if not bom_name:
                print(f"      ❌ BOM فعال برای {item_code} پیدا نشد")
                return 0
            
            print(f"      ✅ BOM پیدا شد: {bom_name}")
            
            # ایجاد mapping قیمت‌های دستی
            manual_price_map = {}
            if self.manual_material_prices:
                for manual_price in self.manual_material_prices:
                    if manual_price.item_code and manual_price.manual_price:
                        manual_price_map[manual_price.item_code] = manual_price.manual_price
            
            print(f"      📋 قیمت‌های دستی: {manual_price_map}")
            
            # محاسبه هزینه از exploded items
            total_cost = 0
            
            exploded_items = frappe.get_all("BOM Explosion Item", 
                filters={"parent": bom_name},
                fields=["item_code", "qty_consumed_per_unit", "rate", "amount"]
            )
            
            print(f"      📋 تعداد exploded items: {len(exploded_items)}")
            print(f"      🔍 قیمت‌های دستی در محاسبه: {manual_price_map}")
            
            if len(exploded_items) == 0:
                print(f"      ⚠️ هیچ exploded item پیدا نشد، تلاش برای استفاده از BOM items...")
                # fallback به BOM items
                bom = frappe.get_doc("BOM", bom_name)
                print(f"      📋 تعداد BOM items: {len(bom.items)}")
                
                for bom_item in bom.items:
                    item_code_exp = bom_item.item_code
                    qty = bom_item.qty or 0
                    
                    print(f"        🔍 بررسی BOM item: {item_code_exp}")
                    
                    # اولویت: قیمت دستی > قیمت BOM
                    if item_code_exp in manual_price_map:
                        item_price = manual_price_map[item_code_exp]
                        item_cost = item_price * qty
                        print(f"        💰 قیمت دستی {item_code_exp}: {item_price:,.0f} × {qty} = {item_cost:,.0f}")
                    else:
                        item_price = self.get_item_price(item_code_exp)
                        item_cost = item_price * qty
                        print(f"        📊 قیمت عادی {item_code_exp}: {item_price:,.0f} × {qty} = {item_cost:,.0f}")
                    
                    total_cost += item_cost
                
                print(f"      💰 مجموع هزینه از BOM items: {total_cost:,.0f}")
                return total_cost
            
            for exploded_item in exploded_items:
                item_code_exp = exploded_item.item_code
                qty = exploded_item.qty_consumed_per_unit or 0
                
                print(f"        🔍 بررسی exploded item: {item_code_exp}")
                
                # اولویت: قیمت دستی > قیمت BOM
                if item_code_exp in manual_price_map:
                    item_price = manual_price_map[item_code_exp]
                    item_cost = item_price * qty
                    print(f"        💰 قیمت دستی {item_code_exp}: {item_price:,.0f} × {qty} = {item_cost:,.0f}")
                elif exploded_item.amount:
                    item_cost = exploded_item.amount
                    print(f"        📊 قیمت BOM {item_code_exp}: {item_cost:,.0f}")
                elif exploded_item.rate:
                    item_cost = exploded_item.rate * qty
                    print(f"        📈 محاسبه از rate {item_code_exp}: {exploded_item.rate:,.0f} × {qty} = {item_cost:,.0f}")
                else:
                    # fallback به قیمت فعلی آیتم
                    item_price = self.get_item_price(item_code_exp)
                    item_cost = item_price * qty
                    print(f"        🔄 قیمت فعلی {item_code_exp}: {item_price:,.0f} × {qty} = {item_cost:,.0f}")
                
                total_cost += item_cost
            
            print(f"      📈 هزینه کل محاسبه شده: {total_cost:,.0f}")
            return total_cost
            
        except Exception as e:
            print(f"      ❌ خطا در محاسبه هزینه: {str(e)}")
            import traceback
            print(f"      🔍 جزئیات خطا: {traceback.format_exc()}")
            return 0
    
    def calculate_raw_material_from_exploded_items(self, bom):
        """
        محاسبه هزینه مواد اولیه از جدول اجزای منفجر شده BOM
        این تابع زمانی استفاده می‌شود که BOM هزینه صفر داشته باشد
        از جدول BOM Exploded Item اطلاعات دریافت کرده و جایگزینی مواد را اعمال می‌کند
        هدف محاسبه دقیق هزینه مواد اولیه و عملیات است
        """
        total_raw_material_cost = 0
        
        # Create substitution mapping
        substitution_map = {}
        if self.material_substitutions:
            for sub in self.material_substitutions:
                substitution_map[sub.original_item] = sub.substitute_item
        
        try:
            # Try to get exploded items from BOM (newer ERPNext versions)
            exploded_items = frappe.get_all("BOM Explosion Item", 
                filters={"parent": bom.name},
                fields=["item_code", "qty", "rate", "amount"]
            )
            
            for exploded_item in exploded_items:
                item_code = exploded_item.item_code
                
                # Priority: Substitution > Original Price (NO manual prices here)
                if item_code in substitution_map:
                    substitute_item = substitution_map[item_code]
                    # Get the price of substitute item
                    item_price = self.get_item_price(substitute_item)
                    item_cost = item_price * exploded_item.qty
                    frappe.logger().info(f"Applied substitute price for {item_code} -> {substitute_item}: {item_price} x {exploded_item.qty} = {item_cost}")
                else:
                    # Use the amount from exploded item or calculate from rate
                    if exploded_item.amount:
                        item_cost = exploded_item.amount
                    elif exploded_item.rate:
                        item_cost = exploded_item.rate * exploded_item.qty
                    else:
                        # Fallback to getting current price
                        item_price = self.get_item_price(item_code)
                        item_cost = item_price * exploded_item.qty
                    frappe.logger().info(f"Applied BOM price for {item_code}: {item_cost}")
                
                total_raw_material_cost += item_cost
                
        except Exception:
            # Fallback to BOM items if BOM Exploded Item doesn't exist
            for bom_item in bom.items:
                item_code = bom_item.item_code
                
                # Check if there's a substitution for this item
                if item_code in substitution_map:
                    substitute_item = substitution_map[item_code]
                    # Get the price of substitute item
                    item_price = self.get_item_price(substitute_item)
                else:
                    # Use original item price
                    item_price = self.get_item_price(item_code)
                
                # Calculate cost based on quantity
                item_cost = item_price * bom_item.qty
                total_raw_material_cost += item_cost
        
        return total_raw_material_cost
    
    def calculate_installment_payment(self, selling_price):
        """
        محاسبه جزئیات پرداخت قسطی با استفاده از فرمول بهره مرکب
        این تابع مبلغ پیش پرداخت، قسط ماهانه، مجموع بهره را محاسبه می‌کند
        از کتابخانه numpy_financial برای محاسبات مالی دقیق استفاده می‌کنح
        هدف ارائه گزینه پرداخت قسطی به مشتریان است
        """
        if not self.enable_installment or not self.number_of_months:
            return {
                'down_payment_amount': 0,
                'monthly_payment': 0,
                'total_amount': selling_price,
                'total_interest': 0
            }
        
        # Calculate down payment
        down_payment_percentage = flt(self.down_payment_percentage or 0)
        down_payment_amount = selling_price * (down_payment_percentage / 100)
        
        # Amount to be financed
        financed_amount = selling_price - down_payment_amount
        
        if financed_amount <= 0:
            return {
                'down_payment_amount': down_payment_amount,
                'monthly_payment': 0,
                'total_amount': selling_price,
                'total_interest': 0
            }
        
        # Monthly interest rate
        monthly_rate = flt(self.monthly_interest_rate or 0) / 100
        number_of_months = int(self.number_of_months or 0)
        
        if monthly_rate == 0 or number_of_months == 0:
            # No interest calculation
            monthly_payment = financed_amount / number_of_months if number_of_months > 0 else 0
            total_amount = selling_price
            total_interest = 0
        else:
            # Use numpy_financial if available, otherwise use manual calculation
            if npf:
                # Using numpy_financial PMT function
                monthly_payment = -npf.pmt(monthly_rate, number_of_months, financed_amount)
            else:
                # Manual compound interest calculation
                if monthly_rate > 0:
                    monthly_payment = financed_amount * (monthly_rate * (1 + monthly_rate)**number_of_months) / ((1 + monthly_rate)**number_of_months - 1)
                else:
                    monthly_payment = financed_amount / number_of_months
            
            total_installment_payments = monthly_payment * number_of_months
            total_amount = down_payment_amount + total_installment_payments
            total_interest = total_amount - selling_price
        
        return {
            'down_payment_amount': down_payment_amount,
            'monthly_payment': monthly_payment,
            'total_amount': total_amount,
            'total_interest': total_interest
        }
    
    def is_product_bundle(self, item_code):
        """
        بررسی اینکه آیا کالا یک Product Bundle است
        این تابع وجود Product Bundle را برای کالا بررسی می‌کند
        منابع داده: جدول Product Bundle
        هدف اصلی: تشخیص بسته‌های محصول برای قیمت‌گذاری متفاوت
        """
        return frappe.db.exists("Product Bundle", {"new_item_code": item_code, "disabled": 0})
    
    def calculate_bundle_price(self, item):
        """
        محاسبه قیمت بسته محصول بر اساس مجموع قیمت آیتم‌های داخل آن
        این تابع قیمت بسته را برابر با مجموع قیمت‌های کالاهای داخل بسته محاسبه می‌کند
        منابع داده: Product Bundle، Product Bundle Item، Item Price
        هدف اصلی: قیمت‌گذاری دقیق بسته‌های محصول
        """
        bundle_items = frappe.get_all("Product Bundle Item", 
            filters={"parent": item.item_code},
            fields=["item_code", "qty"]
        )
        
        if not bundle_items:
            # اگر بسته آیتمی ندارد، قیمت صفر تنظیم می‌شود
            item.total_cost = 0
            item.selling_price = 0
            item.profit_amount = 0
            item.final_selected_price = 0
            return
        
        total_bundle_cost = 0
        total_bundle_selling_price = 0
        
        for bundle_item in bundle_items:
            # دریافت قیمت هر آیتم از لیست قیمت فعلی
            item_price = self.get_item_price(bundle_item.item_code)
            
            # اگر قیمت موجود نیست، از قیمت استاندارد استفاده می‌کنیم
            if not item_price:
                item_price = frappe.db.get_value("Item", bundle_item.item_code, "standard_rate") or 0
            
            # محاسبه هزینه و قیمت فروش برای این آیتم
            item_cost = self.calculate_item_cost_for_bundle(bundle_item.item_code)
            
            # اضافه کردن به مجموع بسته
            total_bundle_cost += item_cost * bundle_item.qty
            total_bundle_selling_price += item_price * bundle_item.qty
        
        # تنظیم قیمت‌های بسته
        item.total_cost = total_bundle_cost
        item.selling_price = total_bundle_selling_price
        item.profit_amount = total_bundle_selling_price - total_bundle_cost
        
        # محاسبه کمیسیون و تخفیف
        commission_calculations = self.calculate_commission_and_discount(total_bundle_selling_price, total_bundle_cost)
        item.commission_amount = commission_calculations.get('commission_amount', 0)
        item.net_profit_after_commission = commission_calculations.get('net_profit_after_commission', 0)
        item.final_price_with_markup = commission_calculations.get('final_price_with_markup', 0)
        item.required_markup_amount = commission_calculations.get('required_markup_amount', 0)
        
        # محاسبه جزئیات قسط
        installment_details = self.calculate_installment_payment(total_bundle_selling_price)
        item.down_payment_amount = installment_details.get('down_payment_amount', 0)
        item.monthly_payment = installment_details.get('monthly_payment', 0)
        item.total_installment_amount = installment_details.get('total_amount', 0)
        item.total_interest = installment_details.get('total_interest', 0)
        
        # محاسبه قیمت نهایی با جزئیات کامل
        pricing_breakdown = self.get_detailed_pricing_breakdown(item)
        final_price = pricing_breakdown['final_price']
        
        # اعمال رند کردن قیمت
        price_before_rounding = final_price
        if self.price_rounding_amount and self.price_rounding_amount > 0:
            final_price = self.round_price_up(final_price, self.price_rounding_amount)
        
        item.final_selected_price = final_price
        
        # ایجاد جزئیات محاسبه قیمت
        breakdown_parts = []
        breakdown_parts.append(f"💰 قیمت تمام شده: {frappe.utils.fmt_money(item.total_cost, currency='IRR')}")
        
        if item.profit_amount > 0:
            profit_percentage = (item.profit_amount / item.total_cost) * 100 if item.total_cost > 0 else 0
            breakdown_parts.append(f"📈 سود ({profit_percentage:.1f}%): +{frappe.utils.fmt_money(item.profit_amount, currency='IRR')}")
        
        if item.commission_amount > 0:
            breakdown_parts.append(f"💼 کمیسیون: +{frappe.utils.fmt_money(item.commission_amount, currency='IRR')}")
        
        if installment_details.get('total_interest', 0) > 0:
            breakdown_parts.append(f"💳 بهره قسط: +{frappe.utils.fmt_money(installment_details['total_interest'], currency='IRR')}")
        
        if self.target_discount_percentage and self.target_discount_percentage > 0:
            discount_amount = (item.selling_price * self.target_discount_percentage) / 100
            breakdown_parts.append(f"🎯 تخفیف ({self.target_discount_percentage}%): -{frappe.utils.fmt_money(discount_amount, currency='IRR')}")
        
        if self.price_rounding_amount and self.price_rounding_amount > 0 and final_price != price_before_rounding:
            rounding_amount = final_price - price_before_rounding
            breakdown_parts.append(f"🔄 رند ({frappe.utils.fmt_money(self.price_rounding_amount, currency='IRR')}): +{frappe.utils.fmt_money(rounding_amount, currency='IRR')}")
        
        breakdown_parts.append(f"✅ قیمت نهایی: {frappe.utils.fmt_money(final_price, currency='IRR')}")
        
        item.price_calculation_breakdown = "\n".join(breakdown_parts)
        
        # محاسبه مراحل قیمت‌گذاری ترکیبی
        self.calculate_step_by_step_pricing(item)
        
        # ذخیره جزئیات قیمت‌گذاری برای نمایش
        try:
            item.pricing_breakdown = frappe.as_json(pricing_breakdown)
        except Exception as e:
            frappe.logger().error(f"Error saving pricing breakdown: {e}")
            item.pricing_breakdown = "{}"
        
        # مقایسه با قیمت بازار
        if self.compare_with_price_list:
            current_market_price = self.get_item_price(item.item_code, self.compare_with_price_list)
            item.current_market_price = current_market_price
            
            if current_market_price > 0:
                profit_loss = current_market_price - item.total_cost
                item.profit_loss_amount = profit_loss
                
                if profit_loss >= 0:
                    item.profit_loss_status = "سودآور"
                else:
                    item.profit_loss_status = "ضررآور"
            else:
                item.profit_loss_status = "قیمت بازار موجود نیست"
    
    def calculate_item_cost_for_bundle(self, item_code):
        """
        محاسبه هزینه یک آیتم برای استفاده در بسته محصول
        این تابع هزینه تولید یک آیتم را محاسبه می‌کند
        منابع داده: BOM، Item
        هدف اصلی: محاسبه دقیق هزینه آیتم‌های داخل بسته
        """
        # بررسی وجود BOM
        bom = frappe.db.get_value("BOM", {
            "item": item_code,
            "is_active": 1,
            "is_default": 1
        }, ["name", "total_cost"], as_dict=1)
        
        if bom and bom.total_cost:
            return flt(bom.total_cost)
        
        # اگر BOM وجود ندارد، از قیمت استاندارد استفاده می‌کنیم
        standard_rate = frappe.db.get_value("Item", item_code, "standard_rate")
        return flt(standard_rate) if standard_rate else 0
    
    def calculate_price_based_on_steps(self, item, total_cost):
        """
        محاسبه قیمت بر اساس مراحل تعریف شده در pricing_steps
        هر مرحله روی نتیجه مرحله قبلی اعمال می‌شود - کاملاً داینامیک
        """
        from frappe.utils import flt
        
        # شروع با هزینه کل
        current_price = flt(total_cost)
        
        # مقداردهی اولیه فیلدها
        self._initialize_item_fields(item, current_price)
        
        # ذخیره مراحل برای گزارش step-by-step
        calculation_steps = []
        calculation_steps.append(f"۱. هزینه کل تولید: {current_price:,.0f} ریال")
        step_counter = 2
        
        # مرتب‌سازی مراحل بر اساس ترتیب
        pricing_steps = sorted(self.pricing_steps, key=lambda x: x.step_order)
        
        # اعمال مراحل به ترتیب تعریف شده - کاملاً داینامیک
        frappe.logger().info(f"شروع اجرای {len(pricing_steps)} مرحله برای آیتم {item.item_code}")
        
        for step in pricing_steps:
            previous_price = current_price
            frappe.logger().info(f"مرحله {step_counter}: {step.step_type} - قیمت فعلی: {current_price:,.0f}")
            
            step_result = self._apply_pricing_step(step, current_price, item)
            
            # همیشه مرحله را در گزارش نمایش بده، حتی اگر نتیجه‌ای نداشته باشد
            if step_result:
                frappe.logger().info(f"نتیجه مرحله {step.step_type}: {step_result}")
                # بررسی صحت قیمت جدید
                new_price = step_result['new_price']
                if new_price is None or new_price <= 0:
                    # در صورت خطا، قیمت قبلی را حفظ کن و ادامه بده
                    calculation_steps.append(f"{step_counter}. {step.step_type}: خطا در محاسبه - قیمت قبلی حفظ شد ({current_price:,.0f} ریال)")
                    frappe.logger().error(f"خطا در مرحله {step.step_type}: قیمت نامعتبر {new_price}")
                else:
                    current_price = new_price
                    if step_result['description']:
                        # نمایش دقیق قیمت قبل و بعد
                        price_change = current_price - previous_price
                        if price_change != 0:
                            calculation_steps.append(f"{step_counter}. {step.step_type}: {previous_price:,.0f} → {current_price:,.0f} ریال (تغییر: {price_change:+,.0f})")
                        else:
                            calculation_steps.append(f"{step_counter}. {step.step_type}: بدون تغییر ({current_price:,.0f} ریال)")
                    else:
                        calculation_steps.append(f"{step_counter}. {step.step_type}: بدون تغییر ({current_price:,.0f} ریال)")
                
                # اضافه کردن توضیحات اضافی اگر وجود دارد
                if step_result.get('additional_info'):
                    for info in step_result['additional_info']:
                        calculation_steps.append(f"   {info}")
            else:
                # اگر step_result وجود ندارد، باز هم مرحله را نمایش بده
                calculation_steps.append(f"{step_counter}. {step.step_type}: مرحله اجرا نشد ({current_price:,.0f} ریال)")
                frappe.logger().warning(f"مرحله {step.step_type} نتیجه‌ای برنگرداند")
            
            step_counter += 1
        
        frappe.logger().info(f"پایان اجرای مراحل - قیمت نهایی: {current_price:,.0f}")
        
        # تنظیم قیمت نهایی و گزارش
        item.final_selected_price = current_price
        calculation_steps.append(f"\n🎯 قیمت نهایی: {current_price:,.0f} ریال")
        item.step_by_step_calculation = "\n".join(calculation_steps)
        
        return current_price, calculation_steps
    
    def _initialize_item_fields(self, item, initial_price):
        """مقداردهی اولیه فیلدهای آیتم"""
        item.selling_price = initial_price
        item.profit_amount = 0
        item.commission_amount = 0
        item.net_profit_after_commission = 0
        item.final_price_with_markup = 0
        item.required_markup_amount = 0
        item.down_payment_amount = 0
        item.monthly_payment = 0
        item.total_installment_amount = 0
        item.total_interest = 0
    
    def _apply_pricing_step(self, step, current_price, item):
        """اعمال یک مرحله قیمت‌گذاری و بازگشت نتیجه"""
        step_type = step.step_type
        
        try:
            if step_type == "سود":
                return self._apply_profit_step(current_price, item)
            elif step_type == "افزایش قیمت":
                return self._apply_markup_step(current_price, item)
            elif step_type == "کمیسیون":
                return self._apply_commission_step(current_price, item)
            elif step_type == "بهره تأخیری":
                return self._apply_interest_step(current_price, item)
            elif step_type == "بهره قسطی":
                return self._apply_interest_step(current_price, item)  # استفاده از همان تابع بهره
            elif step_type == "تخفیف":
                return self._apply_discount_step(current_price, item)
            elif step_type == "رند کردن":
                return self._apply_rounding_step(current_price, item)
            
            # اگر نوع مرحله شناخته شده نیست
            return {
                'new_price': current_price,
                'description': f"{step_type}: نوع مرحله شناخته شده نیست"
            }
        except Exception as e:
            # در صورت خطا، قیمت را حفظ کن
            return {
                'new_price': current_price,
                'description': f"{step_type}: خطا در اجرا - {str(e)}"
            }
    
    def _apply_profit_step(self, current_price, item):
        """اعمال مرحله سود"""
        from frappe.utils import flt
        
        if not self.profit_margin:
            return {
                'new_price': current_price,
                'description': f"سود: تنظیم نشده (0 ریال)"
            }
        
        profit_amount = current_price * (flt(self.profit_margin) / 100)
        new_price = current_price + profit_amount
        
        # به‌روزرسانی فیلدهای آیتم
        item.selling_price = new_price
        item.profit_amount = profit_amount
        
        return {
            'new_price': new_price,
            'description': f"اضافه کردن سود ({self.profit_margin}%): +{profit_amount:,.0f} ریال = {new_price:,.0f} ریال"
        }
    
    def _apply_markup_step(self, current_price, item):
        """اعمال مرحله افزایش قیمت - اجباری برای امکان تخفیف"""
        from frappe.utils import flt
        
        # تعیین درصد افزایش
        markup_percentage = self.required_markup_percentage or 0
        
        # اگر تخفیف تعریف شده، حتماً افزایش قیمت لازم است
        if self.target_discount_percentage and flt(self.target_discount_percentage) > 0:
            if not markup_percentage:
                # محاسبه خودکار درصد افزایش لازم برای امکان تخفیف
                discount = flt(self.target_discount_percentage)
                markup_percentage = (discount / (100 - discount)) * 100
                self.required_markup_percentage = markup_percentage
        
        # اگر هیچ افزایشی تعریف نشده، مرحله را رد کن
        if not markup_percentage or markup_percentage <= 0:
            return {
                'new_price': current_price,
                'description': f"افزایش قیمت: تنظیم نشده (0 ریال)"
            }
        
        markup_amount = current_price * (flt(markup_percentage) / 100)
        new_price = current_price + markup_amount
        
        # به‌روزرسانی فیلدهای آیتم
        item.required_markup_amount = markup_amount
        
        return {
            'new_price': new_price,
            'description': f"افزایش برای امکان تخفیف ({markup_percentage:.1f}%): +{markup_amount:,.0f} ریال = {new_price:,.0f} ریال"
        }
    
    def _apply_commission_step(self, current_price, item):
        """اعمال مرحله کمیسیون - اجباری اگر تعریف شده"""
        from frappe.utils import flt
        
        # بررسی وجود درصد کمیسیون
        if not self.commission_percentage or flt(self.commission_percentage) <= 0:
            return {
                'new_price': current_price,
                'description': f"کمیسیون: تنظیم نشده (0 ریال)"
            }
        
        # بررسی وجود سود برای محاسبه کمیسیون
        if not item.profit_amount or flt(item.profit_amount) <= 0:
            return {
                'new_price': current_price,
                'description': f"کمیسیون: سودی برای محاسبه وجود ندارد (0 ریال)"
            }
        
        commission_amount = item.profit_amount * (flt(self.commission_percentage) / 100)
        net_profit = item.profit_amount - commission_amount
        
        # به‌روزرسانی فیلدهای آیتم
        item.commission_amount = commission_amount
        item.net_profit_after_commission = net_profit
        
        return {
            'new_price': current_price,  # قیمت تغییر نمی‌کند، فقط سود خالص کم می‌شود
            'description': f"کسر کمیسیون ({self.commission_percentage}%): -{commission_amount:,.0f} ریال",
            'additional_info': [f"سود خالص بعد از کمیسیون: {net_profit:,.0f} ریال"]
        }
    
    def _apply_interest_step(self, current_price, item):
        """اعمال مرحله بهره تأخیری - اجباری بر اساس تنظیمات"""
        from frappe.utils import flt
        
        # بررسی بهره تأخیری اولویت اول
        if (self.enable_deferred_payment and 
            self.deferred_payment_interest_rate and 
            flt(self.deferred_payment_interest_rate) > 0 and
            self.deferred_payment_months and 
            flt(self.deferred_payment_months) > 0):
            
            monthly_rate = flt(self.deferred_payment_interest_rate) / 100
            months = flt(self.deferred_payment_months)
            
            total_with_interest = current_price * ((1 + monthly_rate) ** months)
            interest_amount = total_with_interest - current_price
            
            # به‌روزرسانی فیلدهای آیتم
            item.total_interest = interest_amount
            
            return {
                'new_price': total_with_interest,
                'description': f"اضافه کردن بهره تأخیری ({self.deferred_payment_interest_rate}% ماهانه، {months} ماه): +{interest_amount:,.0f} ریال = {total_with_interest:,.0f} ریال"
            }
        
        # بررسی بهره قسطی به عنوان جایگزین
        elif (self.enable_installment and 
            self.monthly_interest_rate and 
            flt(self.monthly_interest_rate) > 0 and
            self.number_of_months and 
            flt(self.number_of_months) > 0):
            
            monthly_rate = flt(self.monthly_interest_rate) / 100
            months = flt(self.number_of_months)
            
            total_with_interest = current_price * ((1 + monthly_rate) ** months)
            interest_amount = total_with_interest - current_price
            
            # به‌روزرسانی فیلدهای آیتم
            item.total_interest = interest_amount
            
            # محاسبه جزئیات قسط
            if self.down_payment_percentage and flt(self.down_payment_percentage) > 0:
                down_payment = total_with_interest * (flt(self.down_payment_percentage) / 100)
                remaining_amount = total_with_interest - down_payment
                monthly_payment = remaining_amount / months
                
                item.down_payment_amount = down_payment
                item.monthly_payment = monthly_payment
                item.total_installment_amount = total_with_interest
            
            # بررسی صحت نتیجه محاسبه
            if total_with_interest <= 0 or interest_amount < 0:
                return {
                    'new_price': current_price,
                    'description': f"بهره قسطی: خطا در محاسبه - قیمت حفظ شد ({current_price:,.0f} ریال)"
                }
            
            return {
                'new_price': total_with_interest,
                'description': f"اضافه کردن بهره قسطی ({self.monthly_interest_rate}% ماهانه، {months} ماه): +{interest_amount:,.0f} ریال = {total_with_interest:,.0f} ریال"
            }
        
        # اگر هیچ نوع بهره‌ای فعال نیست
        return {
            'new_price': current_price,
            'description': f"بهره: فعال نیست (0 ریال)"
        }
    
    def _apply_installment_step(self, current_price, item):
        """اعمال مرحله بهره قسطی (مشابه بهره تأخیری)"""
        return self._apply_interest_step(current_price, item)
    
    def _apply_discount_step(self, current_price, item):
        """اعمال مرحله تخفیف"""
        from frappe.utils import flt
        
        if not self.target_discount_percentage:
            return {
                'new_price': current_price,
                'description': f"تخفیف: تنظیم نشده (0 ریال)"
            }
        
        discount_amount = current_price * (flt(self.target_discount_percentage) / 100)
        new_price = current_price - discount_amount
        
        return {
            'new_price': new_price,
            'description': f"کسر تخفیف ({self.target_discount_percentage}%): -{discount_amount:,.0f} ریال = {new_price:,.0f} ریال"
        }
    
    def _apply_rounding_step(self, current_price, item):
        """اعمال مرحله رند کردن"""
        from frappe.utils import flt
        import math
        
        if not self.price_rounding_amount or self.price_rounding_amount <= 0:
            return {
                'new_price': current_price,
                'description': f"رند کردن: تنظیم نشده (0 ریال)"
            }
        
        rounding_amount = flt(self.price_rounding_amount)
        rounded_price = math.ceil(current_price / rounding_amount) * rounding_amount
        rounding_adjustment = rounded_price - current_price
        
        return {
            'new_price': rounded_price,
            'description': f"رند کردن به {rounding_amount:,.0f} ریال: +{rounding_adjustment:,.0f} ریال = {rounded_price:,.0f} ریال"
        }
    
    def get_selected_price(self, item):
        """
        تابع انتخاب قیمت نهایی بر اساس گزینه انتخابی کاربر
        این تابع قیمت مناسب را بر اساس نوع قیمت انتخاب شده برمی‌گرداند
        منابع داده: فیلدهای محاسبه شده در آیتم
        هدف اصلی: تعیین قیمت نهایی برای فروش
        """
        # بررسی مراحل قیمت‌گذاری بر اساس ترتیب تعریف شده
        pricing_steps = sorted(self.pricing_steps, key=lambda x: x.step_order)
        
        # شروع با قیمت فروش پایه
        final_price = flt(item.selling_price)
        
        # اعمال مراحل قیمت‌گذاری به ترتیب
        for step in pricing_steps:
            if step.step_type == "سود":
                # قیمت پایه با سود (همان selling_price)
                final_price = flt(item.selling_price)
            elif step.step_type == "بهره تأخیری":
                # اگر پرداخت قسطی فعال باشد، از قیمت قسطی استفاده کن
                if self.enable_installment and item.total_installment_amount:
                    final_price = flt(item.total_installment_amount)
            elif step.step_type == "تخفیف":
                # اگر مارکآپ برای تخفیف محاسبه شده باشد
                if item.final_price_with_markup:
                    final_price = flt(item.final_price_with_markup)
            elif step.step_type == "افزایش قیمت":
                # اعمال افزایش مستقیم قیمت
                if self.direct_markup_percentage:
                    markup_amount = final_price * (flt(self.direct_markup_percentage) / 100)
                    final_price += markup_amount
            elif step.step_type == "رند کردن":
                # رند کردن در مرحله بعد انجام می‌شود
                pass
        
        return final_price
    
    def calculate_detailed_breakdown(self, item, final_price):
        """
        محاسبه تفکیک دقیق مبالغ اضافه شده در هر مرحله قیمت‌گذاری
        این تابع فقط فیلدهای اضافی را تنظیم می‌کند چون محاسبات اصلی در calculate_price_based_on_steps انجام شده
        """
        from frappe.utils import flt
        
        # مبلغ پایه (هزینه کل)
        item.base_cost_amount = flt(item.total_cost)
        
        # مبلغ سود اضافه شده - محاسبه دقیق بر اساس مراحل
        # سود واقعی = قیمت بعد از سود - هزینه پایه
        profit_margin_percentage = flt(self.profit_margin or 0)
        if profit_margin_percentage > 0:
            actual_profit_amount = flt(item.total_cost) * (profit_margin_percentage / 100)
            item.profit_added_amount = actual_profit_amount
        else:
            item.profit_added_amount = 0
        
        # مبلغ بهره اضافه شده
        item.interest_added_amount = flt(item.total_interest) if item.total_interest else 0
        
        # مبلغ کسر کمیسیون
        item.commission_deduction_amount = flt(item.commission_amount) if item.commission_amount else 0
        
        # مبلغ افزایش قیمت (مارکآپ)
        item.markup_added_amount = flt(item.required_markup_amount) if item.required_markup_amount else 0
        
        # محاسبه تعدیل رند کردن
        if self.price_rounding_amount and self.price_rounding_amount > 0:
            # محاسبه قیمت قبل از رند کردن
            price_before_rounding = item.final_selected_price
            for step in reversed(sorted(self.pricing_steps, key=lambda x: x.step_order)):
                if step.step_type == "رند کردن":
                    # پیدا کردن قیمت قبل از آخرین رند کردن
                    import math
                    rounding_amount = flt(self.price_rounding_amount)
                    price_before_rounding = math.floor(item.final_selected_price / rounding_amount) * rounding_amount
                    if price_before_rounding < item.final_selected_price:
                        price_before_rounding += (item.final_selected_price % rounding_amount)
                    break
            
            item.rounding_adjustment_amount = flt(item.final_selected_price) - flt(price_before_rounding)
        else:
            item.rounding_adjustment_amount = 0
        
        # محاسبه گام به گام
        step_calculation = self.generate_step_by_step_calculation(item)
        item.step_by_step_calculation = step_calculation
    
    def get_selected_price_before_rounding(self, item):
        """
        محاسبه قیمت انتخاب شده قبل از رند کردن
        """
        pricing_steps = sorted(self.pricing_steps, key=lambda x: x.step_order)
        final_price = flt(item.selling_price)
        
        for step in pricing_steps:
            if step.step_type == "سود":
                final_price = flt(item.selling_price)
            elif step.step_type == "بهره تأخیری":
                if self.enable_installment and item.total_installment_amount:
                    final_price = flt(item.total_installment_amount)
            elif step.step_type == "تخفیف":
                if item.final_price_with_markup:
                    final_price = flt(item.final_price_with_markup)
            elif step.step_type == "افزایش قیمت":
                if self.direct_markup_percentage:
                    markup_amount = final_price * (flt(self.direct_markup_percentage) / 100)
                    final_price += markup_amount
        
        return final_price
    
    def generate_step_by_step_calculation(self, item):
        """
        تولید توضیح گام به گام محاسبه قیمت بر اساس مراحل تعریف شده در pricing_steps
        """
        from frappe.utils import flt
        
        calculation_steps = []
        current_price = flt(item.total_cost)
        step_number = 1
        
        calculation_steps.append(f"۱. هزینه کل تولید: {self.format_money_no_decimal(current_price)}")
        step_number += 1
        
        # مرتب‌سازی مراحل بر اساس ترتیب
        pricing_steps = sorted(self.pricing_steps, key=lambda x: x.step_order)
        
        # نمایش فقط مراحل تعریف شده
        for step in pricing_steps:
            if step.step_type == "سود" and item.profit_amount:
                calculation_steps.append(f"{step_number}. اضافه کردن سود ({int(self.profit_margin)}%): +{self.format_money_no_decimal(item.profit_amount)} = {self.format_money_no_decimal(current_price + item.profit_amount)}")
                current_price += item.profit_amount
                step_number += 1
                
            elif step.step_type == "بهره تأخیری" and item.total_interest:
                calculation_steps.append(f"{step_number}. اضافه کردن بهره قسطی ({int(self.monthly_interest_rate)}% ماهانه): +{self.format_money_no_decimal(item.total_interest)} = {self.format_money_no_decimal(item.total_installment_amount)}")
                current_price = flt(item.total_installment_amount)
                step_number += 1
                
            elif step.step_type == "تخفیف" and item.commission_amount:
                calculation_steps.append(f"{step_number}. کسر کمیسیون ({int(self.commission_percentage)}%): -{self.format_money_no_decimal(item.commission_amount)}")
                calculation_steps.append(f"   سود خالص بعد از کمیسیون: {self.format_money_no_decimal(item.net_profit_after_commission)}")
                if item.required_markup_amount:
                    calculation_steps.append(f"   افزایش برای امکان تخفیف ({int(self.target_discount_percentage)}%): +{self.format_money_no_decimal(item.required_markup_amount)} = {self.format_money_no_decimal(item.final_price_with_markup)}")
                    current_price = flt(item.final_price_with_markup)
                step_number += 1
                
            elif step.step_type == "افزایش قیمت" and self.direct_markup_percentage:
                markup_amount = current_price * (flt(self.direct_markup_percentage) / 100)
                calculation_steps.append(f"{step_number}. افزایش مستقیم قیمت ({int(self.direct_markup_percentage)}%): +{self.format_money_no_decimal(markup_amount)} = {self.format_money_no_decimal(current_price + markup_amount)}")
                current_price += markup_amount
                step_number += 1
                
            elif step.step_type == "رند کردن" and self.price_rounding_amount:
                rounded_price = self.round_price_up(current_price, self.price_rounding_amount)
                rounding_adjustment = rounded_price - current_price
                if rounding_adjustment > 0:
                    calculation_steps.append(f"{step_number}. رند کردن به {self.format_money_no_decimal(self.price_rounding_amount)}: +{self.format_money_no_decimal(rounding_adjustment)} = {self.format_money_no_decimal(rounded_price)}")
                    current_price = rounded_price
                step_number += 1
        
        calculation_steps.append(f"\n🎯 قیمت نهایی: {self.format_money_no_decimal(item.final_selected_price)}")
        
        return "\n".join(calculation_steps)
    
    def format_money_no_decimal(self, amount):
        """فرمت کردن مبلغ بدون اعشار"""
        if not amount:
            return "0 ریال"
        return f"{int(round(amount)):,} ریال".replace(',', '،')
    
    # تابع رند کردن قیمت به سمت بالا
    # این تابع قیمت را به مضرب مشخص شده رند می‌کند
    # منابع داده: قیمت و مبلغ رند
    # هدف اصلی: رند کردن قیمت‌ها برای سهولت فروش
    def round_price_up(self, price, rounding_amount):
        import math
        if rounding_amount <= 0:
            return price
        return math.ceil(price / rounding_amount) * rounding_amount
    
    def calculate_commission_and_discount(self, selling_price, total_cost):
        """
        محاسبه کمیسیون و تعدیلات تخفیف
        این تابع مبلغ کمیسیون و سود خالص پس از کمیسیون را محاسبه می‌کند
        همچنین درصد مارکآپ لازم برای اعمال تخفیف هدف را محاسبه می‌کند
        هدف بهینه‌سازی قیمت‌گذاری با در نظر گیری هزینه‌های فروش است
        """
        commission_percentage = flt(self.commission_percentage or 0)
        target_discount_percentage = flt(self.target_discount_percentage or 0)
        
        # Initialize default values
        required_markup = 0
        final_price_with_markup = selling_price
        required_markup_amount = 0
        
        # Calculate commission amount
        commission_amount = selling_price * (commission_percentage / 100)
        net_profit_after_commission = (selling_price - total_cost) - commission_amount
        
        # Calculate required markup for target discount
        if target_discount_percentage:
            # فرمول محاسبه افزایش قیمت مورد نیاز برای رسیدن به تخفیف هدف
            # اگر می‌خواهیم 30% تخفیف بدهیم، باید 42.86% افزایش قیمت داشته باشیم
            required_markup = (target_discount_percentage / (100 - target_discount_percentage)) * 100
            self.required_markup_percentage = required_markup
            
            # محاسبه قیمت فروش با افزایش قیمت
            markup_amount = (selling_price * required_markup) / 100
            final_price_with_markup = selling_price + markup_amount
            required_markup_amount = markup_amount
            self.final_selling_price_with_markup = final_price_with_markup
            
            # اعمال این محاسبات به هر آیتم
            for item in self.items:
                if item.selling_price:
                    # محاسبه قیمت با تخفیف و قسط ترکیبی
                    base_price = item.selling_price
                    
                    # اگر هم تخفیف و هم قسط فعال باشد
                    if self.enable_installment and self.target_discount_percentage:
                        # ابتدا افزایش قیمت برای تخفیف
                        item_markup_amount = (base_price * required_markup) / 100
                        price_with_markup = base_price + item_markup_amount
                        
                        # سپس محاسبه قسط روی قیمت با تخفیف
                        installment_details = self.calculate_installment_payment(price_with_markup)
                        item.final_price_with_markup = price_with_markup
                        item.required_markup_amount = item_markup_amount
                        
                        # به‌روزرسانی جزئیات قسط
                        item.down_payment_amount = installment_details.get('down_payment_amount', 0)
                        item.monthly_payment = installment_details.get('monthly_payment', 0)
                        item.total_installment_amount = installment_details.get('total_amount', 0)
                        item.total_interest = installment_details.get('total_interest', 0)
                    else:
                        # فقط تخفیف
                        item_markup_amount = (base_price * required_markup) / 100
                        item.final_price_with_markup = base_price + item_markup_amount
                        item.required_markup_amount = item_markup_amount
        
        return {
            'commission_amount': commission_amount,
            'net_profit_after_commission': net_profit_after_commission,
            'required_markup_percentage': required_markup,
            'final_price_with_markup': final_price_with_markup,
            'required_markup_amount': required_markup_amount
        }
    
    def calculate_summary_fields(self):
        """
        محاسبه فیلدهای خلاصه برای سند
        این تابع مجموع فروش، هزینه، سود و کمیسیون را محاسبه می‌کند
        همچنین درصد مارکآپ لازم برای تخفیف هدف را محاسبه می‌کند
        هدف ارائه خلاصه‌ای از عملکرد مالی لیست قیمت است
        """
        if not self.items:
            return
        
        total_selling_price = sum(item.selling_price for item in self.items if item.selling_price)
        total_cost = sum(item.total_cost for item in self.items if item.total_cost)
        
        # Commission calculations
        if self.commission_percentage and total_selling_price:
            total_commission = total_selling_price * (flt(self.commission_percentage) / 100)
            self.net_profit_after_commission = self.total_profit - total_commission
            self.net_profit_percentage_after_commission = (self.net_profit_after_commission / total_cost) * 100 if total_cost else 0
        
        # Discount calculations
        if self.target_discount_percentage:
            self.required_markup_percentage = (flt(self.target_discount_percentage) / (100 - flt(self.target_discount_percentage))) * 100
            self.final_selling_price_with_markup = total_selling_price / (1 - (flt(self.target_discount_percentage) / 100))
    
    def generate_price_comparison(self):
        """
        تولید مقایسه قیمت با لیست قیمت انتخاب شده
        این تابع قیمت‌های فعلی کالاها را با لیست قیمت مرجع مقایسه می‌کند
        تحلیل سودآوری، ضرر و تفاوت قیمت‌ها را انجام داده و گزارش HTML تولید می‌کند
        داده‌ها از جدول Item Price دریافت شده و هدف تصمیم‌گیری بهتر در قیمت‌گذاری است
        """
        if not self.compare_with_price_list or not self.items:
            return
        
        comparison_data = []
        total_variance = 0
        profitable_items = 0
        loss_items = 0
        
        for item in self.items:
            # Get current price from comparison price list
            current_price = frappe.db.get_value("Item Price", {
                "item_code": item.item_code,
                "price_list": self.compare_with_price_list
            }, "price_list_rate") or 0
            
            variance = flt(current_price) - flt(item.total_cost)
            variance_percentage = (variance / flt(item.total_cost)) * 100 if item.total_cost else 0
            
            if variance > 0:
                profitable_items += 1
                status = "Profitable"
                status_color = "green"
            elif variance < 0:
                loss_items += 1
                status = "Loss"
                status_color = "red"
            else:
                status = "Break-even"
                status_color = "orange"
            
            total_variance += variance
            
            comparison_data.append({
                'item_code': item.item_code,
                'item_name': item.item_name,
                'current_cost': item.total_cost,
                'current_selling_price': current_price,
                'new_selling_price': item.selling_price,
                'variance': variance,
                'variance_percentage': variance_percentage,
                'status': status,
                'status_color': status_color
            })
        
        # Generate HTML summary
        html_content = self.generate_comparison_html(comparison_data, total_variance, profitable_items, loss_items)
        self.price_comparison_summary = html_content
    
    def generate_comparison_html(self, comparison_data, total_variance, profitable_items, loss_items):
        """Generate HTML content for price comparison"""
        html = f"""
        <div style="padding: 15px; border: 1px solid #ddd; border-radius: 5px; background-color: #f9f9f9;">
            <h4>Price Comparison Summary</h4>
            <div style="display: flex; gap: 20px; margin-bottom: 15px;">
                <div style="background: #d4edda; padding: 10px; border-radius: 5px; flex: 1;">
                    <strong style="color: #155724;">Profitable Items: {profitable_items}</strong>
                </div>
                <div style="background: #f8d7da; padding: 10px; border-radius: 5px; flex: 1;">
                    <strong style="color: #721c24;">Loss Items: {loss_items}</strong>
                </div>
                <div style="background: #fff3cd; padding: 10px; border-radius: 5px; flex: 1;">
                    <strong style="color: #856404;">Total Variance: {frappe.format_value(total_variance, 'Currency')}</strong>
                </div>
            </div>
            <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
                <thead>
                    <tr style="background-color: #e9ecef;">
                        <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Item</th>
                        <th style="border: 1px solid #ddd; padding: 8px; text-align: right;">Current Cost</th>
                        <th style="border: 1px solid #ddd; padding: 8px; text-align: right;">Current Price</th>
                        <th style="border: 1px solid #ddd; padding: 8px; text-align: right;">New Price</th>
                        <th style="border: 1px solid #ddd; padding: 8px; text-align: right;">Variance</th>
                        <th style="border: 1px solid #ddd; padding: 8px; text-align: center;">Status</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for item in comparison_data[:10]:  # Show first 10 items
            html += f"""
                    <tr>
                        <td style="border: 1px solid #ddd; padding: 8px;">{item['item_code']}</td>
                        <td style="border: 1px solid #ddd; padding: 8px; text-align: right;">{frappe.format_value(item['current_cost'], 'Currency')}</td>
                        <td style="border: 1px solid #ddd; padding: 8px; text-align: right;">{frappe.format_value(item['current_selling_price'], 'Currency')}</td>
                        <td style="border: 1px solid #ddd; padding: 8px; text-align: right;">{frappe.format_value(item['new_selling_price'], 'Currency')}</td>
                        <td style="border: 1px solid #ddd; padding: 8px; text-align: right; color: {'green' if item['variance'] > 0 else 'red' if item['variance'] < 0 else 'orange'};">
                            {frappe.format_value(item['variance'], 'Currency')} ({item['variance_percentage']:.1f}%)
                        </td>
                        <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">
                            <span style="color: {item['status_color']}; font-weight: bold;">{item['status']}</span>
                        </td>
                    </tr>
            """
        
        html += """
                </tbody>
            </table>
        </div>
        """
        
        return html
    
    def calculate_competitor_analysis(self):
        """Analyze competitor pricing and market positioning"""
        return self.pricing_ai.calculate_competitor_analysis()
    
    def suggest_optimal_pricing(self):
        """Suggest optimal pricing based on cost, market, and profit targets"""
        suggestions = []
        
        for item in self.items:
            suggestion = {
                'item_code': item.item_code,
                'current_price': item.selling_price,
                'suggested_price': item.selling_price,
                'reason': 'Current pricing is optimal'
            }
            
            # Check if profit margin is too low
            if item.total_cost > 0:
                current_margin = ((item.selling_price - item.total_cost) / item.total_cost) * 100
                
                if current_margin < 15:  # Less than 15% margin
                    suggested_price = item.total_cost * 1.20  # 20% margin
                    suggestion.update({
                        'suggested_price': suggested_price,
                        'reason': f'Low profit margin ({current_margin:.1f}%). Suggested 20% margin.'
                    })
                elif current_margin > 50:  # More than 50% margin
                    suggested_price = item.total_cost * 1.35  # 35% margin
                    suggestion.update({
                        'suggested_price': suggested_price,
                        'reason': f'High margin ({current_margin:.1f}%). Consider competitive pricing.'
                    })
            
            suggestions.append(suggestion)
        
        return suggestions
    
    def generate_pricing_strategy_report(self):
        """Generate comprehensive pricing strategy report"""
        if not self.items:
            return "No items to analyze"
        
        # Calculate key metrics
        total_items = len(self.items)
        avg_margin = sum((item.selling_price - item.total_cost) / item.total_cost * 100 
                        for item in self.items if item.total_cost > 0) / total_items
        
        high_margin_items = sum(1 for item in self.items 
                            if item.total_cost > 0 and 
                               ((item.selling_price - item.total_cost) / item.total_cost * 100) > 30)
        
        low_margin_items = sum(1 for item in self.items 
                            if item.total_cost > 0 and 
                                ((item.selling_price - item.total_cost) / item.total_cost * 100) < 15)
        
        # Generate recommendations
        recommendations = []
        
        if avg_margin < 20:
            recommendations.append("Consider increasing overall profit margins - current average is below 20%")
        
        if low_margin_items > total_items * 0.3:
            recommendations.append(f"{low_margin_items} items have margins below 15% - review pricing strategy")
        
        if self.commission_percentage and self.commission_percentage > 25:
            recommendations.append("High commission percentage may impact profitability - consider optimization")
        
        report = f"""
        PRICING STRATEGY REPORT
        =====================
        
        Summary:
        - Total Items: {total_items}
        - Average Margin: {avg_margin:.1f}%
        - High Margin Items (>30%): {high_margin_items}
        - Low Margin Items (<15%): {low_margin_items}
        
        Recommendations:
        {chr(10).join('- ' + rec for rec in recommendations)}
        """
        
        return report
    
    def get_detailed_pricing_breakdown(self, item):
        """
        محاسبه جزئیات کامل قیمت‌گذاری برای هر آیتم
        شامل تفکیک سود، بهره، کمیسیون و سایر اجزا
        """
        breakdown = {
            'base_cost': item.total_cost,
            'base_selling_price': item.selling_price,
            'base_profit': item.profit_amount,
            'base_profit_percentage': (item.profit_amount / item.total_cost * 100) if item.total_cost > 0 else 0
        }
        
        # محاسبه جزئیات کمیسیون و تخفیف
        if self.commission_percentage and self.commission_percentage > 0:
            breakdown['commission_percentage'] = self.commission_percentage
            breakdown['commission_amount'] = item.commission_amount
            breakdown['net_profit_after_commission'] = item.net_profit_after_commission
            breakdown['commission_impact'] = item.profit_amount - item.net_profit_after_commission
        
        # محاسبه جزئیات markup و تخفیف
        if self.target_discount_percentage and self.target_discount_percentage > 0:
            breakdown['target_discount_percentage'] = self.target_discount_percentage
            breakdown['required_markup_percentage'] = self.required_markup_percentage
            breakdown['markup_amount'] = item.required_markup_amount
            breakdown['price_with_markup'] = item.final_price_with_markup
            breakdown['discount_amount'] = item.final_price_with_markup * (self.target_discount_percentage / 100)
            breakdown['price_after_discount'] = breakdown['price_with_markup'] - breakdown['discount_amount']
        
        # محاسبه جزئیات قسط
        if self.enable_installment:
            breakdown['installment_details'] = {
                'down_payment_percentage': self.down_payment_percentage,
                'down_payment_amount': item.down_payment_amount,
                'monthly_interest_rate': self.monthly_interest_rate,
                'number_of_months': self.number_of_months,
                'monthly_payment': item.monthly_payment,
                'total_installment_amount': item.total_installment_amount,
                'total_interest': item.total_interest,
                'interest_percentage': (item.total_interest / item.selling_price * 100) if item.selling_price > 0 else 0
            }
        
        # تعیین قیمت نهایی بر اساس مراحل قیمت‌گذاری
        breakdown['final_price'] = item.final_selected_price
        breakdown['selected_strategy'] = "pricing_steps"
        
        # محاسبه تفاوت‌ها بر اساس مراحل قیمت‌گذاری
        breakdown['strategy_benefit'] = item.final_selected_price - item.total_cost
        breakdown['strategy_description'] = "قیمت‌گذاری مرحله‌ای"
        
        return breakdown
    
    @frappe.whitelist()
    def apply_combined_pricing_strategy(self, strategy_key):
        """
        اعمال استراتژی قیمت‌گذاری ترکیبی انتخاب شده
        """
        try:
            # محاسبه مجدد قیمت‌ها با مراحل جدید
            self.update_item_prices_with_details()
            
            # ذخیره تغییرات
            self.save()
            
            frappe.msgprint(f"استراتژی {strategy_key} با موفقیت اعمال شد", alert=True)
            
            return {
                'status': 'success',
                'message': f'استراتژی {strategy_key} اعمال شد',
                'selected_strategy': strategy_key
            }
            
        except Exception as e:
            frappe.logger().error(f"Error applying combined pricing strategy: {e}")
            frappe.throw(f"خطا در اعمال استراتژی: {str(e)}")
    
    def calculate_step_by_step_pricing(self, item):
        """محاسبه قیمت‌گذاری مرحله به مرحله بر اساس جدول مراحل"""
        current_price = item.total_cost
        
        # شروع با قیمت پایه
        current_price = item.total_cost
        
        # پردازش مراحل از جدول pricing_steps
        if not self.pricing_steps:
            return
            
        # مرتب‌سازی بر اساس ترتیب
        sorted_steps = sorted(self.pricing_steps, key=lambda x: x.step_order or 0)
        
        for idx, step in enumerate(sorted_steps[:5]):  # حداکثر ۵ مرحله
            step_num = idx + 1
            
            # تبدیل نوع فارسی به انگلیسی
            english_type = step.get_english_type() if hasattr(step, 'get_english_type') else self.get_english_type_from_persian(step.step_type)
            
            # محاسبه قیمت جدید بر اساس نوع عامل
            if english_type == 'profit_margin':
                if self.profit_margin:
                    new_price = current_price * (1 + self.profit_margin / 100)
                    description = f"سود {self.profit_margin}%"
                else:
                    new_price = current_price
                    description = "سود (غیرفعال)"
                
            elif english_type == 'target_discount_percentage' or english_type == 'افزایش قیمت':
                if self.required_markup_percentage:
                    new_price = current_price * (1 + self.required_markup_percentage / 100)
                    description = f"افزایش قیمت {self.required_markup_percentage}%"
                else:
                    new_price = current_price
                    description = "افزایش قیمت (غیرفعال)"
                
            elif english_type == 'commission_percentage':
                if self.commission_percentage:
                    # کمیسیون باید از قیمت کسر شود، نه اضافه
                    commission_amount = current_price * (self.commission_percentage / 100)
                    new_price = current_price - commission_amount
                    description = f"کمیسیون {self.commission_percentage}%: -{commission_amount:,.0f}"
                else:
                    new_price = current_price
                    description = "کمیسیون (غیرفعال)"
                
            elif english_type == 'installment_interest':
                # محاسبه بهره قسطی
                if self.enable_installment and self.installment_total_interest_percentage:
                    new_price = current_price * (1 + self.installment_total_interest_percentage / 100)
                    description = f"بهره قسطی {self.installment_total_interest_percentage}% کل"
                else:
                    new_price = current_price
                    description = "بهره قسطی (غیرفعال)"
                    
            elif english_type == 'deferred_payment_interest':
                # محاسبه بهره تأخیری
                if self.enable_deferred_payment and self.deferred_payment_total_interest_percentage:
                    new_price = current_price * (1 + self.deferred_payment_total_interest_percentage / 100)
                    description = f"بهره تأخیری {self.deferred_payment_total_interest_percentage}% کل"
                else:
                    new_price = current_price
                    description = "بهره تأخیری (غیرفعال)"
                    
            elif english_type == 'rounding':
                # رند کردن قیمت
                if self.price_rounding_amount and self.price_rounding_amount > 0:
                    new_price = math.ceil(current_price / self.price_rounding_amount) * self.price_rounding_amount
                    description = f"رند کردن {frappe.utils.fmt_money(self.price_rounding_amount, currency='IRR')}"
                else:
                    new_price = current_price
                    description = "رند کردن (غیرفعال)"
            else:
                new_price = current_price
                description = "نامشخص"
            
            # به‌روزرسانی قیمت فعلی برای مرحله بعد
            current_price = new_price
        
        # به‌روزرسانی قیمت نهایی انتخاب شده با آخرین مرحله
        item.final_selected_price = current_price
        item.selling_price = current_price
    
    def get_english_type_from_persian(self, persian_type):
        """تبدیل نوع فارسی به انگلیسی"""
        persian_to_english = {
            'سود': 'profit_margin',
            'تخفیف': 'target_discount_percentage',
            'افزایش قیمت': 'target_discount_percentage',
            'کمیسیون': 'commission_percentage',
            'بهره قسطی': 'installment_interest',
            'بهره تأخیری': 'deferred_payment_interest',
            'رند کردن': 'rounding'
        }
        return persian_to_english.get(persian_type, 'unknown')

    @frappe.whitelist()
    def compare_combined_strategies(self):
        """
        مقایسه استراتژی‌های مختلف قیمت‌گذاری
        """
        try:
            if not self.items:
                frappe.throw("هیچ آیتمی برای مقایسه وجود ندارد")
            
            # انتخاب یک آیتم نمونه برای مقایسه
            sample_item = self.items[0]
            
            strategies_comparison = {}
            
            # محاسبه قیمت برای هر استراتژی
            original_strategy = self.selected_price_type
            
            strategies = [
                ('base_price', 'قیمت پایه'),
                ('discount_only', 'تخفیف'),
                ('installment_only', 'قسط'),
                ('combined_discount_installment', 'ترکیب تخفیف و قسط')
            ]
            
            for strategy_key, strategy_name in strategies:
                # تنظیم موقت استراتژی
                self.selected_price_type = strategy_key
                
                # محاسبه قیمت برای این استراتژی
                temp_price = self.get_selected_price(sample_item)
                
                strategies_comparison[strategy_key] = {
                    'name': strategy_name,
                    'price': temp_price,
                    'difference_from_base': temp_price - sample_item.selling_price if sample_item.selling_price else 0
                }
            
            # بازگرداندن استراتژی اصلی
            self.selected_price_type = original_strategy
            
            return strategies_comparison
            
        except Exception as e:
            frappe.logger().error(f"Error comparing strategies: {e}")
            frappe.throw(f"خطا در مقایسه استراتژی‌ها: {str(e)}")

    def on_update(self):
        """Called after document is saved"""
        pass  # Remove automatic calculation to prevent database locks
        
    def before_save(self):
        """Called before document is saved"""
        # Store current state for comparison
        if hasattr(self, 'manual_material_prices'):
            self._old_manual_prices = {mp.item_code: mp.manual_price for mp in (self.manual_material_prices or [])}
    
    def on_change(self):
        """Called when document fields change"""
        # Force recalculation when manual material prices change
        if hasattr(self, '_old_manual_prices'):
            new_manual_prices = {mp.item_code: mp.manual_price for mp in (self.manual_material_prices or [])}
            
            if self._old_manual_prices != new_manual_prices:
                frappe.logger().info("Manual material prices changed, will need recalculation...")
                # Don't auto-calculate to prevent locks, user can trigger manually

    def validate(self):
        """Validate the Auto Price List document"""
        self.validate_dates()
        self.validate_profit_margin()
        self.validate_installment_settings()
        
    
    def update_item_prices_with_final_selected(self):
        """
        به‌روزرسانی قیمت‌های کالا با قیمت نهایی انتخاب شده
        این تابع فقط قیمت نهایی انتخاب شده (final_selected_price) را به لیست قیمت ارسال می‌کند
        منابع داده: فیلد final_selected_price از هر آیتم
        هدف اصلی: اعمال قیمت نهایی در سیستم
        """
        for item in self.items:
            if item.final_selected_price and item.final_selected_price > 0:
                # حذف قیمت قبلی اگر وجود دارد
                existing_price = frappe.db.get_value("Item Price", {
                    "item_code": item.item_code,
                    "price_list": self.price_list
                }, "name")
                
                if existing_price:
                    frappe.delete_doc("Item Price", existing_price)
                
                # ایجاد قیمت جدید با قیمت نهایی انتخاب شده
                item_price = frappe.get_doc({
                    "doctype": "Item Price",
                    "item_code": item.item_code,
                    "price_list": self.price_list,
                    "price_list_rate": item.final_selected_price,
                    "valid_from": self.valid_from,
                    "valid_upto": self.valid_until
                })
                item_price.insert()
                
        frappe.msgprint(f"قیمت‌های نهایی انتخاب شده برای {len(self.items)} کالا به لیست قیمت {self.price_list} اعمال شد")
    
    def before_submit(self):
        """
        اعتبارسنجی قبل از تایید
        این تابع قبل از تایید سند اجرا شده و صحت تنظیمات قسط را بررسی می‌کند
        بررسی می‌کند که درصد پیش پرداخت، تعداد ماه و نرخ بهره به درستی تعریف شده باشد
        هدف جلوگیری از تایید سند با تنظیمات ناقص یا نادرست است
        """
        if self.enable_installment:
            if not self.down_payment_percentage or self.down_payment_percentage <= 0:
                frappe.throw("Down Payment Percentage is required when installment is enabled")
            if not self.number_of_months or self.number_of_months <= 0:
                frappe.throw("Number of Months is required when installment is enabled")
            if not self.monthly_interest_rate or self.monthly_interest_rate < 0:
                frappe.throw("Monthly Interest Rate is required when installment is enabled")
    
    def before_save(self):
        """Calculate fields before saving"""
        pass  # Remove automatic calculation to prevent database locks
        
        # Setup cost monitoring on save
        if self.items:
            try:
                self.setup_cost_monitoring()
            except:
                pass  # Don't fail save if monitoring setup fails
    
    def validate_pricing_rules(self):
        """Validate pricing rules and constraints"""
        errors = []
        
        for item in self.items:
            # Check minimum margin requirement
            if item.total_cost > 0:
                margin = ((item.selling_price - item.total_cost) / item.total_cost) * 100
                if margin < 5:  # Less than 5% margin
                    errors.append(f"Item {item.item_code}: Margin too low ({margin:.1f}%)")
            
            # Check if selling price is below cost
            if item.selling_price < item.total_cost:
                errors.append(f"Item {item.item_code}: Selling price below cost")
        
        if errors:
            frappe.throw("Pricing validation errors:\n" + "\n".join(errors))
    
    def validate_profit_margin(self):
        """Validate profit margin settings"""
        if self.profit_margin and self.profit_margin < 0:
            frappe.throw(_("Profit margin cannot be negative"))
        
        if self.profit_margin and self.profit_margin > 1000:
            frappe.throw(_("Profit margin seems too high (>1000%). Please check your input."))
    
    def validate_installment_settings(self):
        """Validate installment payment settings"""
        if self.enable_installment:
            if not self.down_payment_percentage or self.down_payment_percentage <= 0:
                frappe.throw(_("Down payment percentage is required for installment payments"))
            
            if self.down_payment_percentage >= 100:
                frappe.throw(_("Down payment percentage cannot be 100% or more"))
            
            if not self.number_of_months or self.number_of_months <= 0:
                frappe.throw(_("Number of months is required for installment payments"))
            
            if not self.monthly_interest_rate or self.monthly_interest_rate < 0:
                frappe.throw(_("Monthly interest rate is required for installment payments"))
            
            if self.monthly_interest_rate > 50:
                frappe.throw(_("Monthly interest rate seems too high (>50%). Please check your input."))
    
    def validate_dates(self):
        """Validate date fields"""
        if self.valid_from and self.valid_until:
            if self.valid_from > self.valid_until:
                frappe.throw(_("Valid From date cannot be after Valid Until date"))
    
    def auto_optimize_pricing(self):
        """Automatically optimize pricing based on market conditions"""
        return self.pricing_ai.auto_optimize_pricing()

    def update_item_prices(self):
        """
        به‌روزرسانی رکوردهای قیمت کالا
        این تابع قیمت‌های محاسبه شده را در جدول Item Price ثبت یا به‌روزرسانی می‌کند
        برای هر کالا بررسی می‌کند که آیا قیمت قبلی وجود دارد یا باید جدید ایجاد کند
        داده‌ها در جدول Item Price ذخیره شده و هدف تامین قیمت برای فاکتورها و سفارشات است
        """
        for item in self.items:
            # Check if price exists
            existing_price = frappe.db.exists("Item Price", {
                "item_code": item.item_code,
                "price_list": self.price_list,
                "valid_from": self.valid_from,
                "valid_upto": self.valid_until
            })
            
            if existing_price:
                # Update existing price
                frappe.db.set_value("Item Price", existing_price, {
                    "price_list_rate": item.selling_price,
                    "currency": frappe.defaults.get_global_default("currency")
                })
            else:
                # Create new price
                frappe.get_doc({
                    "doctype": "Item Price",
                    "item_code": item.item_code,
                    "price_list": self.price_list,
                    "valid_from": self.valid_from,
                    "valid_upto": self.valid_until,
                    "price_list_rate": item.selling_price,
                    "currency": frappe.defaults.get_global_default("currency")
                }).insert()

    def on_cancel(self):
        """
        حذف رکوردهای قیمت کالا هنگام لغو لیست قیمت
        این تابع هنگام لغو سند اجرا شده و تمام قیمت‌های ثبت شده را از سیستم حذف می‌کند
        از جدول Item Price تمام قیمت‌های مربوط به این لیست قیمت را پاک می‌کند
        هدف جلوگیری از استفاده قیمت‌های لغو شده در فاکتورها و سفارشات است
        """
        frappe.db.delete("Item Price", {
            "price_list": self.price_list,
            "valid_from": self.valid_from,
            "valid_upto": self.valid_until
        })

    def apply_advanced_pricing(self, base_price, item_code, quantity=1, customer=None):
        """Apply advanced pricing strategies like volume, seasonal, and customer tier pricing"""
        final_price = base_price
        
        # Apply seasonal pricing with dynamic calculation
        if self.enable_seasonal_pricing:
            if self.seasonal_factor:
                seasonal_adjustment = 1 + (self.seasonal_factor / 100)
            else:
                # Calculate dynamic seasonal factor
                dynamic_seasonal = self.calculate_dynamic_seasonal_factor(item_code)
                seasonal_adjustment = 1 + (dynamic_seasonal / 100)
            final_price = final_price * seasonal_adjustment
        
        # Apply volume pricing
        if self.enable_volume_pricing and quantity > 1:
            volume_discount = self.get_volume_discount(quantity, item_code)
            if volume_discount > 0:
                final_price = final_price * (1 - volume_discount / 100)
        
        # Apply customer tier pricing
        if self.enable_customer_tier_pricing and customer:
            customer_tier = self.get_dynamic_customer_tier(customer)
            tier_discount = self.get_customer_tier_discount(customer_tier)
            if tier_discount > 0:
                final_price = final_price * (1 - tier_discount / 100)
        
        return final_price
    
    def get_volume_discount(self, quantity, item_code=None):
        """Get volume discount based on quantity tiers with enhanced logic"""
        if not self.enable_volume_pricing or not self.volume_pricing_tiers:
            return 0
        
        # Sort tiers by min_quantity to ensure proper tier selection
        sorted_tiers = sorted(self.volume_pricing_tiers, key=lambda x: x.min_quantity or 0)
        
        for tier in sorted_tiers:
            min_qty = tier.min_quantity or 0
            max_qty = tier.max_quantity or float('inf')
            
            if min_qty <= quantity <= max_qty:
                return tier.discount_percentage or 0
        
        return 0
    
    def apply_volume_pricing(self, item, base_price, quantity=1):
        """Apply volume pricing to item price"""
        if not self.enable_volume_pricing:
            return base_price
        
        volume_discount = self.get_volume_discount(quantity, item.item_code)
        if volume_discount > 0:
            discounted_price = base_price * (1 - volume_discount / 100)
            return discounted_price
        
        return base_price
    
    def get_customer_tier_discount(self, customer_tier):
        """Get discount based on customer tier with enhanced logic"""
        if not self.enable_customer_tier_pricing or not self.customer_tier_discounts:
            return 0
        
        for discount in self.customer_tier_discounts:
            if discount.customer_tier == customer_tier:
                return discount.discount_percentage or 0
        
        return 0
    
    def get_dynamic_customer_tier(self, customer):
        """Dynamically determine customer tier based on purchase history"""
        if not customer:
            return "جدید"
        
        # Get customer's purchase history
        total_purchases = frappe.db.sql("""
            SELECT SUM(grand_total) as total, COUNT(*) as count
            FROM `tabSales Invoice`
            WHERE customer = %(customer)s
            AND docstatus = 1
            AND posting_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
        """, {"customer": customer}, as_dict=1)
        
        if not total_purchases or not total_purchases[0].total:
            return "جدید"
        
        total_amount = total_purchases[0].total
        order_count = total_purchases[0].count
        
        # Dynamic tier assignment based on purchase behavior
        if total_amount >= 1000000000 and order_count >= 50:  # 1B+ and 50+ orders
            return "VIP"
        elif total_amount >= 500000000 and order_count >= 20:  # 500M+ and 20+ orders
            return "عمده‌فروش"
        elif total_amount >= 100000000 or order_count >= 10:   # 100M+ or 10+ orders
            return "عادی"
        else:
            return "جدید"
    
    def apply_customer_tier_pricing(self, item, base_price, customer=None):
        """Apply customer tier pricing to item price"""
        if not self.enable_customer_tier_pricing:
            return base_price
        
        customer_tier = self.get_dynamic_customer_tier(customer)
        tier_discount = self.get_customer_tier_discount(customer_tier)
        
        if tier_discount > 0:
            discounted_price = base_price * (1 - tier_discount / 100)
            return discounted_price
        
        return base_price
    
    def get_market_data(self, item_code, force_refresh=False):
        """Get real-time market data for item pricing"""
        return self.pricing_ai.get_market_data(item_code, force_refresh)
    
    def ai_optimize_pricing(self, item):
        """AI-powered pricing optimization using advanced machine learning"""
        return self.pricing_ai.ai_optimize_pricing(item)
    
    def ml_optimize_pricing(self, item):
        """Machine Learning based price optimization"""
        return self.pricing_ai.ml_optimize_pricing(item)
    
    def prepare_ml_features(self, item):
        """Prepare features for machine learning model"""
        return self.pricing_ai.prepare_ml_features(item)
    
    def get_training_data(self, item_code):
        """Get historical training data for ML model"""
        return self.pricing_ai.get_training_data(item_code)
    
    def train_and_predict_price(self, training_data, features):
        """Train ML model and predict optimal price"""
        return self.pricing_ai.train_and_predict_price(training_data, features)
    
    def rule_based_optimize_pricing(self, item):
        """Fallback rule-based pricing optimization"""
        return self.pricing_ai.rule_based_optimize_pricing(item)
    
    def calculate_dynamic_seasonal_factor(self, item_code, current_date=None):
        """Calculate dynamic seasonal factor based on historical sales data"""
        return self.pricing_ai.calculate_dynamic_seasonal_factor(item_code, current_date)
    
    def setup_cost_monitoring(self):
        """Setup real-time cost monitoring and alerts"""
        return self.pricing_ai.setup_cost_monitoring()
    
    def create_cost_change_notifications(self, cost_alerts):
        """Create notifications for cost changes"""
        return self.pricing_ai.create_cost_change_notifications(cost_alerts)
    
    def get_external_market_data(self, item_code):
        """Get market data from external APIs (placeholder for future integration)"""
        return self.pricing_ai.get_external_market_data(item_code)
    
    def calculate_price_elasticity(self, item_code):
        """Calculate price elasticity based on historical sales data"""
        return self.pricing_ai.calculate_price_elasticity(item_code)
    
    def generate_pricing_insights(self):
        """Generate advanced pricing insights and recommendations"""
        return self.pricing_ai.generate_pricing_insights()

    def generate_pricing_report(self):
        """Generate comprehensive pricing analysis report"""
        return self.pricing_ai.generate_pricing_report()
    
    def predict_demand_forecast(self, item_code, periods=12):
        """Predict demand forecast using time series analysis"""
        return self.pricing_ai.predict_demand_forecast(item_code, periods)
    
    def simple_demand_forecast(self, item_code, periods=12):
        """Simple demand forecast using moving average"""
        return self.pricing_ai.simple_demand_forecast(item_code, periods)
    
    def get_seasonal_adjustment(self, month):
        """Get seasonal adjustment factor for a given month"""
        return self.pricing_ai.get_seasonal_adjustment(month)
    
    def get_raw_material_insights(self):
        """Get insights about raw material cost trends"""
        return self.pricing_ai.get_raw_material_insights()
    
    @frappe.whitelist()
    def ai_optimize_all_items(self):
        """AI optimization for all items"""
        return self.pricing_ai.ai_optimize_all_items()
    
    @frappe.whitelist()
    def get_real_time_market_data(self, item_codes=None):
        """Get real-time market data for items"""
        return self.pricing_ai.get_real_time_market_data(item_codes)
    
    @frappe.whitelist()
    def calculate_all_seasonal_factors(self):
        """Calculate seasonal factors for all items"""
        return self.pricing_ai.calculate_all_seasonal_factors()
    
    @frappe.whitelist()
    def get_ml_pricing_insights(self):
        """Get ML-based pricing insights"""
        return self.pricing_ai.get_ml_pricing_insights()
    
    @frappe.whitelist()
    def get_demand_forecast(self, item_code, periods=12):
        """Get demand forecast for specific item"""
        return self.pricing_ai.get_demand_forecast(item_code, periods)
    
    @frappe.whitelist()
    def get_inventory_optimization(self, item_code):
        """Get inventory optimization suggestions"""
        return self.pricing_ai.get_inventory_optimization(item_code)
    
    @frappe.whitelist()
    def run_price_elasticity_analysis(self, item_code):
        """Run price elasticity analysis for item"""
        return self.pricing_ai.run_price_elasticity_analysis(item_code)
    
    @frappe.whitelist()
    def get_advanced_competitor_analysis(self):
        """Get advanced competitor analysis"""
        return self.pricing_ai.get_advanced_competitor_analysis()
    
    @frappe.whitelist()
    def integrate_real_data_for_pricing(self):
        """Integrate real purchase invoice data into pricing"""
        return self.pricing_ai.integrate_real_data_for_pricing()
    
    @frappe.whitelist()
    def calculate_combined_pricing_strategies(self, selling_price=None, total_cost=None):
        """
        محاسبه استراتژی‌های قیمت‌گذاری ترکیبی
        """
        try:
            if not selling_price or not total_cost:
                frappe.throw("قیمت فروش و هزینه کل الزامی است")
            
            selling_price = float(selling_price)
            total_cost = float(total_cost)
            
            strategies = {
                'base_strategy': {
                    'name': 'قیمت‌گذاری پایه',
                    'final_price': selling_price,
                    'profit_margin': ((selling_price - total_cost) / total_cost) * 100,
                    'description': 'قیمت بر اساس هزینه + حاشیه سود'
                }
            }
            
            # Add discount strategy if applicable
            if self.target_discount_percentage:
                markup_required = (100 / (100 - self.target_discount_percentage)) - 1
                markup_price = total_cost * (1 + markup_required)
                discounted_price = markup_price * (1 - self.target_discount_percentage / 100)
                
                strategies['discount_strategy'] = {
                    'name': 'قیمت‌گذاری با تخفیف',
                    'markup_price': markup_price,
                    'final_price': discounted_price,
                    'discount_percentage': self.target_discount_percentage,
                    'description': f'قیمت با {self.target_discount_percentage}% تخفیف'
                }
            
            # Add installment strategy if applicable
            if self.enable_installment and self.number_of_months and self.monthly_interest_rate:
                down_payment = selling_price * (self.down_payment_percentage / 100)
                remaining_amount = selling_price - down_payment
                
                # Calculate monthly payment with compound interest
                monthly_rate = self.monthly_interest_rate / 100
                monthly_payment = remaining_amount * (monthly_rate * (1 + monthly_rate)**self.number_of_months) / ((1 + monthly_rate)**self.number_of_months - 1)
                total_installment = down_payment + (monthly_payment * self.number_of_months)
                
                strategies['installment_strategy'] = {
                    'name': 'قیمت‌گذاری قسطی',
                    'down_payment': down_payment,
                    'monthly_payment': monthly_payment,
                    'total_amount': total_installment,
                    'interest_amount': total_installment - selling_price,
                    'description': f'{self.number_of_months} قسط ماهانه با {self.monthly_interest_rate}% بهره'
                }
            
            return strategies
            
        except Exception as e:
            frappe.log_error(f"Combined pricing strategies error: {str(e)}")
            frappe.throw(f"خطا در محاسبه استراتژی‌های ترکیبی: {str(e)}")
    
    @frappe.whitelist()
    def setup_cost_monitoring(self):
        """
        راه‌اندازی نظارت بر هزینه‌ها
        """
        try:
            monitoring_data = {
                'status': 'فعال',
                'items_count': len(self.items) if self.items else 0,
                'total_cost': sum([item.total_cost or 0 for item in self.items]) if self.items else 0,
                'average_margin': self.profit_margin or 0,
                'last_update': frappe.utils.now(),
                'alerts': []
            }
            
            # Check for cost variations
            if self.items:
                for item in self.items:
                    if item.total_cost and item.total_cost > 0:
                        # Check if cost is significantly different from expected
                        expected_cost = item.raw_material_cost or 0
                        if expected_cost > 0:
                            variation = abs(item.total_cost - expected_cost) / expected_cost
                            if variation > 0.1:  # 10% variation threshold
                                monitoring_data['alerts'].append({
                                    'item': item.item_name,
                                    'type': 'تغییر هزینه',
                                    'variation': f"{variation * 100:.1f}%",
                                    'message': f'هزینه {item.item_name} {variation * 100:.1f}% تغییر کرده است'
                                })
            
            return monitoring_data
            
        except Exception as e:
            frappe.log_error(f"Cost monitoring setup error: {str(e)}")
            return {'status': 'خطا', 'message': str(e)}
    
    @frappe.whitelist()
    def compare_combined_strategies(self):
        """
        مقایسه استراتژی‌های مختلف قیمت‌گذاری
        """
        try:
            if not self.items:
                frappe.throw("هیچ کالایی برای مقایسه یافت نشد")
            
            comparison_data = {
                'strategies': [],
                'recommendations': [],
                'summary': {}
            }
            
            total_base_price = 0
            total_discount_price = 0
            total_installment_revenue = 0
            
            for item in self.items:
                if item.total_cost and item.total_cost > 0:
                    # Base strategy
                    base_price = item.selling_price or 0
                    total_base_price += base_price
                    
                    # Discount strategy
                    if self.target_discount_percentage:
                        discount_price = item.final_price_with_markup or 0
                        total_discount_price += discount_price
                    
                    # Installment strategy
                    if self.enable_installment:
                        installment_total = item.total_installment_amount or 0
                        total_installment_revenue += installment_total
            
            # Add strategy comparisons
            comparison_data['strategies'].append({
                'name': 'قیمت‌گذاری پایه',
                'total_revenue': total_base_price,
                'profit_margin': self.profit_margin or 0,
                'risk_level': 'کم',
                'description': 'استراتژی محافظه‌کارانه با ریسک کم'
            })
            
            if self.target_discount_percentage and total_discount_price > 0:
                comparison_data['strategies'].append({
                    'name': 'قیمت‌گذاری با تخفیف',
                    'total_revenue': total_discount_price,
                    'discount_impact': f"{self.target_discount_percentage}% تخفیف",
                    'risk_level': 'متوسط',
                    'description': 'جذب مشتری بیشتر با تخفیف'
                })
            
            if self.enable_installment and total_installment_revenue > 0:
                comparison_data['strategies'].append({
                    'name': 'قیمت‌گذاری قسطی',
                    'total_revenue': total_installment_revenue,
                    'additional_revenue': total_installment_revenue - total_base_price,
                    'risk_level': 'بالا',
                    'description': 'درآمد بیشتر با ریسک بالاتر'
                })
            
            # Add recommendations
            if total_installment_revenue > total_base_price * 1.1:
                comparison_data['recommendations'].append(
                    'قیمت‌گذاری قسطی درآمد 10% بیشتری دارد - توصیه می‌شود'
                )
            
            if self.target_discount_percentage and self.target_discount_percentage > 20:
                comparison_data['recommendations'].append(
                    'تخفیف بالای 20% ممکن است سودآوری را کاهش دهد'
                )
            
            comparison_data['summary'] = {
                'best_revenue': max(total_base_price, total_discount_price, total_installment_revenue),
                'safest_option': 'قیمت‌گذاری پایه',
                'highest_profit': 'قیمت‌گذاری قسطی' if total_installment_revenue > total_base_price else 'قیمت‌گذاری پایه'
            }
            
            return comparison_data
            
        except Exception as e:
            frappe.log_error(f"Strategy comparison error: {str(e)}")
            frappe.throw(f"خطا در مقایسه استراتژی‌ها: {str(e)}")
    
    @frappe.whitelist()
    def calculate_item_prices(self):
        """Wrapper method for JavaScript compatibility"""
        return self.calculate_item_prices_internal()
    
    @frappe.whitelist()
    def update_item_prices_with_details(self):
        """
        به‌روزرسانی رکوردهای Item Price با جزئیات کامل قیمت‌گذاری
        """
        import frappe
        from frappe.utils import flt
        
        if not self.price_list:
            return
        
        # First calculate all item prices with stepwise pricing
        self.calculate_item_prices_internal()
        
        for item in self.items:
            if not item.item_code:
                continue
                
            # جستجو برای Item Price موجود
            existing_price = frappe.db.get_value("Item Price", {
                "item_code": item.item_code,
                "price_list": self.price_list
            }, "name")
            
            if existing_price:
                # به‌روزرسانی Item Price موجود
                item_price_doc = frappe.get_doc("Item Price", existing_price)
            else:
                # ایجاد Item Price جدید
                item_price_doc = frappe.new_doc("Item Price")
                item_price_doc.item_code = item.item_code
                item_price_doc.price_list = self.price_list
            
            # تنظیم قیمت اصلی (final_selected_price -> price_list_rate)
            item_price_doc.price_list_rate = flt(item.final_selected_price)
            
            # تنظیم فیلدهای هزینه
            if hasattr(item, 'raw_material_cost'):
                item_price_doc.raw_material_cost = flt(item.raw_material_cost)
            if hasattr(item, 'electricity_cost'):
                item_price_doc.electricity_cost = flt(item.electricity_cost)
            if hasattr(item, 'consumable_cost'):
                item_price_doc.consumable_cost = flt(item.consumable_cost)
            if hasattr(item, 'rent_cost'):
                item_price_doc.rent_cost = flt(item.rent_cost)
            if hasattr(item, 'labor_cost'):
                item_price_doc.labor_cost = flt(item.labor_cost)
            if hasattr(item, 'operation_cost'):
                item_price_doc.operation_cost = flt(item.operation_cost)
            if hasattr(item, 'subcontracting_cost'):
                item_price_doc.subcontracting_cost = flt(item.subcontracting_cost)
            if hasattr(item, 'overhead_cost'):
                item_price_doc.overhead_cost = flt(item.overhead_cost)
            if hasattr(item, 'total_cost'):
                item_price_doc.total_cost = flt(item.total_cost)
            
            # تنظیم فیلدهای قیمت و سود
            if hasattr(item, 'selling_price'):
                item_price_doc.selling_price = flt(item.selling_price)
            if hasattr(item, 'profit_amount'):
                item_price_doc.profit_amount = flt(item.profit_amount)
            
            # تنظیم فیلدهای مقایسه بازار
            if hasattr(item, 'current_market_price'):
                item_price_doc.current_market_price = flt(item.current_market_price)
            if hasattr(item, 'profit_loss_status'):
                item_price_doc.profit_loss_status = item.profit_loss_status or ""
            if hasattr(item, 'profit_loss_amount'):
                item_price_doc.profit_loss_amount = flt(item.profit_loss_amount)
            
            # تنظیم فیلدهای کمیسیون و مارکآپ
            if hasattr(item, 'commission_amount'):
                item_price_doc.commission_amount = flt(item.commission_amount)
            if hasattr(item, 'net_profit_after_commission'):
                item_price_doc.net_profit_after_commission = flt(item.net_profit_after_commission)
            if hasattr(item, 'final_price_with_markup'):
                item_price_doc.final_price_with_markup = flt(item.final_price_with_markup)
            if hasattr(item, 'required_markup_amount'):
                item_price_doc.required_markup_amount = flt(item.required_markup_amount)
            
            # تنظیم فیلدهای تفکیک دقیق
            if hasattr(item, 'base_cost_amount'):
                item_price_doc.base_cost_amount = flt(item.base_cost_amount)
            if hasattr(item, 'profit_added_amount'):
                item_price_doc.profit_added_amount = flt(item.profit_added_amount)
            if hasattr(item, 'interest_added_amount'):
                item_price_doc.interest_added_amount = flt(item.interest_added_amount)
            if hasattr(item, 'commission_deduction_amount'):
                item_price_doc.commission_deduction_amount = flt(item.commission_deduction_amount)
            if hasattr(item, 'markup_added_amount'):
                item_price_doc.markup_added_amount = flt(item.markup_added_amount)
            if hasattr(item, 'rounding_adjustment_amount'):
                item_price_doc.rounding_adjustment_amount = flt(item.rounding_adjustment_amount)
            
            # تنظیم فیلدهای قسط
            if hasattr(item, 'down_payment_amount'):
                item_price_doc.down_payment_amount = flt(item.down_payment_amount)
            if hasattr(item, 'monthly_payment'):
                item_price_doc.monthly_payment = flt(item.monthly_payment)
            if hasattr(item, 'total_installment_amount'):
                item_price_doc.total_installment_amount = flt(item.total_installment_amount)
            if hasattr(item, 'total_interest'):
                item_price_doc.total_interest = flt(item.total_interest)
            
            # تنظیم فیلد notes با step_by_step_calculation
            if hasattr(item, 'step_by_step_calculation') and item.step_by_step_calculation:
                item_price_doc.notes = item.step_by_step_calculation
            
            # Use database transaction with proper error handling
            try:
                # Use frappe.db.sql for direct database operations to avoid locks
                if existing_price:
                    # Update existing record directly
                    frappe.db.sql("""
                        UPDATE `tabItem Price` 
                        SET price_list_rate = %s, modified = NOW()
                        WHERE name = %s
                    """, (
                        flt(item.final_selected_price),
                        existing_price
                    ))
                else:
                    # Insert new record directly
                    frappe.db.sql("""
                        INSERT INTO `tabItem Price` 
                        (name, item_code, price_list, price_list_rate, docstatus, creation, modified, owner, modified_by)
                        VALUES (%s, %s, %s, %s, 0, NOW(), NOW(), %s, %s)
                    """, (
                        frappe.generate_hash(length=10),
                        item.item_code,
                        self.price_list,
                        flt(item.final_selected_price),
                        frappe.session.user,
                        frappe.session.user
                    ))
                
                frappe.logger().info(f"Item Price برای {item.item_code} با موفقیت ذخیره شد")
                
            except Exception as e:
                frappe.log_error(f"خطا در به‌روزرسانی Item Price برای {item.item_code}: {str(e)}")
                continue
            
            
    @frappe.whitelist() 
    def get_items_bom_status(self):
        """
        بررسی وضعیت BOM فعال برای تمام محصولات در لیست
        برمی‌گرداند: لیست محصولاتی که BOM فعال ندارند
        """
        try:
            items_without_bom = []
            
            if not self.items:
                return {"items_without_bom": []}
            
            for item in self.items:
                if not item.item_code:
                    continue
                
                # بررسی وجود BOM فعال و پیش‌فرض
                bom_exists = frappe.db.exists("BOM", {
                    "item": item.item_code,
                    "is_active": 1,
                    "is_default": 1
                })
                
                if not bom_exists:
                    items_without_bom.append({
                        "item_code": item.item_code,
                        "item_name": item.item_name or item.item_code,
                        "idx": item.idx
                    })
            
            frappe.logger().info(f"🔍 محصولات بدون BOM فعال: {len(items_without_bom)} از {len(self.items)}")
            
            return {
                "items_without_bom": items_without_bom,
                "total_items": len(self.items),
                "items_without_bom_count": len(items_without_bom)
            }
            
        except Exception as e:
            frappe.logger().error(f"خطا در بررسی وضعیت BOM: {str(e)}")
            return {
                "items_without_bom": [],
                "error": str(e)
            }

    @frappe.whitelist()
    def update_material_substitution_prices(self):
        """به‌روزرسانی خودکار قیمت‌های جایگزینی مواد"""
        try:
            updated_count = 0
            
            if not self.material_substitutions:
                return {"message": "هیچ جایگزینی موادی تعریف نشده است", "updated_count": 0}
            
            for substitution in self.material_substitutions:
                if substitution.original_item and substitution.substitute_item:
                    # محاسبه قیمت‌ها
                    substitution.original_item_price = self.get_material_price(substitution.original_item)
                    substitution.substitute_item_price = self.get_material_price(substitution.substitute_item)
                    
                    # محاسبه تفاوت قیمت و درصد صرفه‌جویی
                    if substitution.original_item_price and substitution.substitute_item_price:
                        substitution.price_difference = substitution.original_item_price - substitution.substitute_item_price
                        
                        if substitution.original_item_price > 0:
                            substitution.cost_savings_percentage = (substitution.price_difference / substitution.original_item_price) * 100
                        else:
                            substitution.cost_savings_percentage = 0
                    
                    updated_count += 1
            
            frappe.logger().info(f"🔄 قیمت‌های جایگزینی مواد به‌روزرسانی شد: {updated_count} مورد")
            
            return {
                "message": f"قیمت‌های {updated_count} جایگزینی ماده با موفقیت به‌روزرسانی شد",
                "updated_count": updated_count
            }
            
        except Exception as e:
            frappe.logger().error(f"خطا در به‌روزرسانی قیمت‌های جایگزینی مواد: {str(e)}")
            return {
                "message": f"خطا در به‌روزرسانی: {str(e)}",
                "updated_count": 0
            }

    def get_material_price(self, item_code):
        """دریافت قیمت ماده اولیه از منابع مختلف"""
        try:
            # 1. ابتدا از قیمت‌های دستی بگیر
            manual_price = self.get_manual_material_price(item_code)
            if manual_price and manual_price > 0:
                frappe.logger().info(f"✋ قیمت دستی {item_code}: {manual_price}")
                return manual_price
            
            # 2. از Item Price فروش بگیر
            selling_price = frappe.db.get_value("Item Price", {
                "item_code": item_code,
                "selling": 1
            }, "price_list_rate")
            
            if selling_price and selling_price > 0:
                frappe.logger().info(f"💰 قیمت فروش {item_code}: {selling_price}")
                return selling_price
            
            # 3. از Item Price خرید بگیر
            buying_price = frappe.db.get_value("Item Price", {
                "item_code": item_code,
                "buying": 1
            }, "price_list_rate")
            
            if buying_price and buying_price > 0:
                frappe.logger().info(f"🛒 قیمت خرید {item_code}: {buying_price}")
                return buying_price
            
            # 4. از BOM محاسبه کن
            bom_cost = frappe.db.get_value("BOM", {
                "item": item_code,
                "is_active": 1,
                "is_default": 1
            }, "total_cost")
            
            if bom_cost and bom_cost > 0:
                frappe.logger().info(f"🔧 هزینه BOM {item_code}: {bom_cost}")
                return bom_cost
            
            # 5. از Standard Rate کالا استفاده کن
            standard_rate = frappe.db.get_value("Item", item_code, "standard_rate")
            if standard_rate and standard_rate > 0:
                frappe.logger().info(f"📊 نرخ استاندارد {item_code}: {standard_rate}")
                return standard_rate
            
            # 6. از Valuation Rate استفاده کن
            valuation_rate = frappe.db.get_value("Item", item_code, "valuation_rate")
            if valuation_rate and valuation_rate > 0:
                frappe.logger().info(f"💎 نرخ ارزش‌گذاری {item_code}: {valuation_rate}")
                return valuation_rate
            
            # 7. از آخرین Purchase Receipt بگیر
            last_purchase_rate = self.get_last_purchase_rate(item_code)
            if last_purchase_rate and last_purchase_rate > 0:
                frappe.logger().info(f"📦 آخرین قیمت خرید {item_code}: {last_purchase_rate}")
                return last_purchase_rate
            
            # 8. از Stock Ledger Entry بگیر
            stock_rate = self.get_stock_rate(item_code)
            if stock_rate and stock_rate > 0:
                frappe.logger().info(f"📋 نرخ موجودی {item_code}: {stock_rate}")
                return stock_rate
            
            frappe.logger().warning(f"⚠️ هیچ قیمتی برای {item_code} یافت نشد")
            return 0
            
        except Exception as e:
            frappe.logger().error(f"خطا در دریافت قیمت {item_code}: {str(e)}")
            return 0

    def get_manual_material_price(self, item_code):
        """دریافت قیمت دستی ماده اولیه از جدول manual_material_prices"""
        try:
            if not self.manual_material_prices:
                return None
            
            for manual_price in self.manual_material_prices:
                if manual_price.item_code == item_code:
                    return manual_price.manual_price
            
            return None
            
        except Exception as e:
            frappe.logger().error(f"خطا در دریافت قیمت دستی {item_code}: {str(e)}")
            return None

    @frappe.whitelist()
    def get_substitution_analysis(self):
        """تحلیل جایگزینی مواد و صرفه‌جویی"""
        try:
            analysis = {
                "total_substitutions": 0,
                "cost_saving_substitutions": 0,
                "cost_increasing_substitutions": 0,
                "total_savings": 0,
                "substitutions_details": []
            }
            
            if not self.material_substitutions:
                return analysis
            
            for substitution in self.material_substitutions:
                if not (substitution.original_item and substitution.substitute_item):
                    continue
                
                analysis["total_substitutions"] += 1
                
                if substitution.price_difference and substitution.cost_savings_percentage:
                    if substitution.price_difference > 0:
                        analysis["cost_saving_substitutions"] += 1
                        analysis["total_savings"] += substitution.price_difference
                    else:
                        analysis["cost_increasing_substitutions"] += 1
                    
                    analysis["substitutions_details"].append({
                        "original_item": substitution.original_item,
                        "substitute_item": substitution.substitute_item,
                        "original_price": substitution.original_item_price or 0,
                        "substitute_price": substitution.substitute_item_price or 0,
                        "price_difference": substitution.price_difference or 0,
                        "savings_percentage": substitution.cost_savings_percentage or 0
                    })
            
            return analysis
            
        except Exception as e:
            frappe.logger().error(f"خطا در تحلیل جایگزینی مواد: {str(e)}")
            return {"error": str(e)}

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
    def scan_missing_material_prices(self):
        """اسکن BOMهای محصولات و شناسایی مواد اولیه بدون قیمت"""
        try:
            missing_materials = {}
            processed_items = set()
            
            if not self.items:
                return {"message": "هیچ محصولی در لیست وجود ندارد", "missing_count": 0}
            
            # بررسی BOM هر محصول
            for item in self.items:
                if not item.item_code or item.item_code in processed_items:
                    continue
                
                processed_items.add(item.item_code)
                
                # یافتن BOM فعال محصول
                bom_name = frappe.db.get_value("BOM", {
                    "item": item.item_code,
                    "is_active": 1,
                    "is_default": 1
                }, "name")
                
                if not bom_name:
                    continue
                
                # بررسی مواد اولیه BOM
                bom_items = frappe.db.sql("""
                    SELECT item_code, item_name, qty, uom
                    FROM `tabBOM Item`
                    WHERE parent = %s
                    AND parenttype = 'BOM'
                """, (bom_name,), as_dict=True)
                
                for bom_item in bom_items:
                    material_code = bom_item.item_code
                    
                    # اگر قبلاً بررسی شده، رد کن
                    if material_code in missing_materials:
                        # فقط محصول جدید رو به لیست تأثیرپذیرها اضافه کن
                        if item.item_code not in missing_materials[material_code]['affected_items']:
                            missing_materials[material_code]['affected_items'].append(item.item_code)
                            missing_materials[material_code]['bom_usage_count'] += 1
                        continue
                    
                    # بررسی وجود قیمت
                    price_info = self.check_material_price(material_code)
                    
                    if price_info['price'] == 0:  # قیمت یافت نشد
                        missing_materials[material_code] = {
                            'item_code': material_code,
                            'item_name': bom_item.item_name or material_code,
                            'current_price': 0,
                            'suggested_price': self.calculate_suggested_price(material_code),
                            'manual_price': 0,
                            'uom': bom_item.uom,
                            'bom_usage_count': 1,
                            'affected_items': [item.item_code],
                            'price_source': price_info['source'],
                            'notes': f"یافت شده در BOM {bom_name}"
                        }
            
            # پاک کردن جدول فعلی
            self.missing_material_prices = []
            
            # اضافه کردن مواد جدید
            for material_data in missing_materials.values():
                material_data['affected_items'] = ", ".join(material_data['affected_items'][:5])
                if len(missing_materials) > 5:
                    material_data['affected_items'] += "..."
                
                self.append('missing_material_prices', material_data)
            
            frappe.logger().info(f"🔍 مواد اولیه بدون قیمت شناسایی شد: {len(missing_materials)} مورد")
            
            return {
                "message": f"{len(missing_materials)} ماده اولیه بدون قیمت شناسایی شد",
                "missing_count": len(missing_materials),
                "materials": list(missing_materials.keys())
            }
            
        except Exception as e:
            frappe.logger().error(f"خطا در اسکن مواد اولیه بدون قیمت: {str(e)}")
            return {
                "message": f"خطا در اسکن: {str(e)}",
                "missing_count": 0
            }

    def check_material_price(self, item_code):
        """بررسی وجود قیمت برای ماده اولیه"""
        try:
            # استفاده از همان الگوریتم قیمت‌گیری
            price = self.get_material_price(item_code)
            
            if price > 0:
                return {"price": price, "source": "قیمت موجود"}
            else:
                return {"price": 0, "source": "قیمت یافت نشد"}
                
        except Exception as e:
            return {"price": 0, "source": f"خطا: {str(e)}"}

    def calculate_suggested_price(self, item_code):
        """محاسبه قیمت پیشنهادی برای ماده اولیه"""
        try:
            # گرفتن item group
            item_group = frappe.db.get_value("Item", item_code, "item_group")
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
            """, (item_group, item_code))
            
            if avg_price and avg_price[0][0]:
                return avg_price[0][0]
            
            # اگر میانگین نبود، از valuation rate استفاده کن
            valuation_rate = frappe.db.get_value("Item", item_code, "valuation_rate")
            if valuation_rate and valuation_rate > 0:
                return valuation_rate * 1.2  # 20% markup
            
            return 0
            
        except Exception as e:
            frappe.logger().error(f"خطا در محاسبه قیمت پیشنهادی {item_code}: {str(e)}")
            return 0

    @frappe.whitelist()
    def apply_missing_material_prices(self):
        """اعمال قیمت‌های دستی مواد اولیه بدون قیمت"""
        try:
            applied_count = 0
            price_changes = []
            
            if not self.missing_material_prices:
                return {"message": "هیچ ماده اولیه بدون قیمتی وجود ندارد", "applied_count": 0}
            
            # ذخیره قیمت‌های فعلی محصولات قبل از تغییر
            items_before = {}
            if self.items:
                for item in self.items:
                    old_price = getattr(item, 'selling_price', 0) or 0
                    items_before[item.item_code] = {
                        'item_name': item.item_name,
                        'old_price': old_price
                    }
            
            for missing_material in self.missing_material_prices:
                if missing_material.manual_price and missing_material.manual_price > 0:
                    # اضافه کردن به جدول قیمت‌های دستی
                    existing_manual = None
                    for manual_price in self.manual_material_prices:
                        if manual_price.item_code == missing_material.item_code:
                            existing_manual = manual_price
                            break
                    
                    if existing_manual:
                        # به‌روزرسانی قیمت موجود
                        existing_manual.manual_price = missing_material.manual_price
                        existing_manual.notes = f"به‌روزرسانی شده از مواد بدون قیمت - {missing_material.notes}"
                    else:
                        # اضافه کردن قیمت جدید
                        self.append('manual_material_prices', {
                            'item_code': missing_material.item_code,
                            'item_name': missing_material.item_name,
                            'manual_price': missing_material.manual_price,
                            'uom': missing_material.uom,
                            'effective_date': frappe.utils.today(),
                            'notes': f"اضافه شده از مواد بدون قیمت - {missing_material.notes}"
                        })
                    
                    applied_count += 1
            
            # حذف موارد اعمال شده از جدول مواد بدون قیمت
            remaining_materials = []
            for missing_material in self.missing_material_prices:
                if not (missing_material.manual_price and missing_material.manual_price > 0):
                    remaining_materials.append(missing_material)
            
            self.missing_material_prices = remaining_materials
            
            # محاسبه مجدد قیمت‌ها برای تهیه گزارش تغییرات
            if applied_count > 0:
                self.calculate_item_prices()
                
                # مقایسه قیمت‌های قبل و بعد
                for item_code, before_data in items_before.items():
                    # پیدا کردن قیمت جدید
                    new_price = 0
                    if self.items:
                        for item in self.items:
                            if item.item_code == item_code:
                                new_price = getattr(item, 'selling_price', 0) or 0
                                break
                    
                    if new_price != before_data['old_price']:
                        price_change = new_price - before_data['old_price']
                        price_change_percent = 0
                        if before_data['old_price'] > 0:
                            price_change_percent = (price_change / before_data['old_price']) * 100
                        
                        price_changes.append({
                            'item_code': item_code,
                            'item_name': before_data['item_name'],
                            'old_price': before_data['old_price'],
                            'new_price': new_price,
                            'price_change': price_change,
                            'price_change_percent': price_change_percent
                        })
            
            frappe.logger().info(f"✅ قیمت‌های دستی اعمال شد: {applied_count} مورد")
            
            return {
                "message": f"قیمت‌های دستی {applied_count} ماده اولیه با موفقیت اعمال شد",
                "applied_count": applied_count,
                "price_changes": price_changes,
                "refresh_needed": True
            }
            
        except Exception as e:
            frappe.logger().error(f"خطا در اعمال قیمت‌های دستی مواد اولیه: {str(e)}")
            return {
                "message": f"خطا در اعمال: {str(e)}",
                "applied_count": 0
            }

    @frappe.whitelist()
    def get_price_change_report(self):
        """تهیه گزارش جامع تغییرات قیمت بعد از اعمال قیمت‌های دستی"""
        try:
            if not self.items:
                return {"success": False, "message": "هیچ محصولی در لیست قیمت وجود ندارد"}
            
            report_data = []
            total_items = 0
            items_with_changes = 0
            total_price_increase = 0
            total_price_decrease = 0
            
            for item in self.items:
                # محاسبه قیمت بدون قیمت‌های دستی (قیمت پایه)
                base_cost = self.calculate_item_cost_without_manual_prices(item.item_code)
                
                # محاسبه قیمت با قیمت‌های دستی (قیمت فعلی)
                current_cost = self.calculate_item_cost_with_exploded_items(item.item_code)
                
                # محاسبه قیمت فروش
                base_selling_price = base_cost * (1 + (self.profit_margin or 0) / 100)
                current_selling_price = getattr(item, 'selling_price', 0) or 0
                
                price_difference = current_selling_price - base_selling_price
                price_change_percent = 0
                if base_selling_price > 0:
                    price_change_percent = (price_difference / base_selling_price) * 100
                
                # تشخیص مواد اولیه تأثیرگذار
                affected_materials = []
                if self.manual_material_prices:
                    for manual_price in self.manual_material_prices:
                        # بررسی آیا این ماده در BOM این محصول استفاده شده
                        bom_materials = self.get_bom_exploded_items(item.item_code)
                        for bom_item in bom_materials:
                            if bom_item.get('item_code') == manual_price.item_code:
                                affected_materials.append({
                                    'item_code': manual_price.item_code,
                                    'item_name': manual_price.item_name,
                                    'manual_price': manual_price.manual_price,
                                    'quantity': bom_item.get('qty', 0)
                                })
                                break
                
                report_item = {
                    'item_code': item.item_code,
                    'item_name': item.item_name,
                    'base_cost': base_cost,
                    'current_cost': current_cost,
                    'cost_difference': current_cost - base_cost,
                    'base_selling_price': base_selling_price,
                    'current_selling_price': current_selling_price,
                    'price_difference': price_difference,
                    'price_change_percent': price_change_percent,
                    'affected_materials': affected_materials,
                    'has_price_change': abs(price_difference) > 0.01
                }
                
                report_data.append(report_item)
                total_items += 1
                
                if report_item['has_price_change']:
                    items_with_changes += 1
                    if price_difference > 0:
                        total_price_increase += price_difference
                    else:
                        total_price_decrease += abs(price_difference)
            
            # آمار کلی
            summary = {
                'total_items': total_items,
                'items_with_changes': items_with_changes,
                'items_without_changes': total_items - items_with_changes,
                'total_price_increase': total_price_increase,
                'total_price_decrease': total_price_decrease,
                'net_price_change': total_price_increase - total_price_decrease,
                'average_price_change_percent': sum([item['price_change_percent'] for item in report_data if item['has_price_change']]) / max(items_with_changes, 1)
            }
            
            return {
                "success": True,
                "report_data": report_data,
                "summary": summary,
                "manual_materials_count": len(self.manual_material_prices) if self.manual_material_prices else 0
            }
            
        except Exception as e:
            frappe.logger().error(f"خطا در تهیه گزارش تغییرات قیمت: {str(e)}")
            return {"success": False, "message": f"خطا در تهیه گزارش: {str(e)}"}

    def calculate_item_cost_without_manual_prices(self, item_code):
        """محاسبه هزینه محصول بدون در نظر گیری قیمت‌های دستی"""
        try:
            bom_items = self.get_bom_exploded_items(item_code)
            total_cost = 0
            
            for bom_item in bom_items:
                material_code = bom_item.get('item_code')
                qty = bom_item.get('qty', 0)
                
                # گرفتن قیمت بدون قیمت‌های دستی
                price = self.get_material_price_without_manual(material_code)
                total_cost += price * qty
            
            return total_cost
            
        except Exception as e:
            frappe.logger().error(f"خطا در محاسبه هزینه بدون قیمت دستی {item_code}: {str(e)}")
            return 0

    def get_material_price_without_manual(self, item_code):
        """گرفتن قیمت ماده اولیه بدون در نظر گیری قیمت‌های دستی"""
        try:
            # 1. Item Price - Selling
            selling_price = frappe.db.get_value("Item Price", {
                "item_code": item_code,
                "price_list": self.selling_price_list,
                "selling": 1
            }, "price_list_rate")
            
            if selling_price and selling_price > 0:
                return selling_price
            
            # 2. Item Price - Buying
            buying_price = frappe.db.get_value("Item Price", {
                "item_code": item_code,
                "buying": 1
            }, "price_list_rate")
            
            if buying_price and buying_price > 0:
                return buying_price
            
            # 3. BOM Cost
            bom_cost = self.get_bom_cost(item_code)
            if bom_cost > 0:
                return bom_cost
            
            # 4. Standard Rate
            standard_rate = frappe.db.get_value("Item", item_code, "standard_rate")
            if standard_rate and standard_rate > 0:
                return standard_rate
            
            # 5. Valuation Rate
            valuation_rate = frappe.db.get_value("Item", item_code, "valuation_rate")
            if valuation_rate and valuation_rate > 0:
                return valuation_rate
            
            # 6. Last Purchase Rate
            last_purchase_rate = frappe.db.sql("""
                SELECT pri.rate
                FROM `tabPurchase Receipt Item` pri
                INNER JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent
                WHERE pri.item_code = %s AND pr.docstatus = 1
                ORDER BY pr.posting_date DESC, pr.posting_time DESC
                LIMIT 1
            """, (item_code,))
            
            if last_purchase_rate and last_purchase_rate[0][0] > 0:
                return last_purchase_rate[0][0]
            
            return 0
            
        except Exception as e:
            frappe.logger().error(f"خطا در گرفتن قیمت بدون دستی {item_code}: {str(e)}")
            return 0

def run_enhanced_ml_optimization(docname, item_code):
    """API method for enhanced ML optimization"""
    try:
        doc = frappe.get_doc("Auto Price List", docname)
        result = doc.enhanced_ml_price_optimization(item_code)
        return result
    except Exception as e:
        frappe.log_error(f"Enhanced ML optimization API error: {str(e)}")
        return {'status': 'error', 'message': str(e)}

@frappe.whitelist()
def integrate_real_data_for_pricing(docname):
    """API method to integrate real purchase and quotation data"""
    try:
        doc = frappe.get_doc("Auto Price List", docname)
        result = doc.integrate_real_data_costs()
        return result
    except Exception as e:
        frappe.log_error(f"Error in real data integration API: {str(e)}")
        return {'status': 'error', 'message': str(e)}

# Module-level AI functions for JavaScript calls
@frappe.whitelist()
def ai_optimize_all_items(docname):
    """AI optimization for all items - Module level function"""
    try:
        doc = frappe.get_doc("Auto Price List", docname)
        return doc.ai_optimize_all_items()
    except Exception as e:
        frappe.log_error(f"AI optimize all items error: {str(e)}")
        return {'status': 'error', 'message': str(e)}

@frappe.whitelist()
def get_real_time_market_data(docname, item_codes=None):
    """Get real-time market data - Module level function"""
    try:
        doc = frappe.get_doc("Auto Price List", docname)
        return doc.get_real_time_market_data(item_codes)
    except Exception as e:
        frappe.log_error(f"Real-time market data error: {str(e)}")
        return {'status': 'error', 'message': str(e)}

@frappe.whitelist()
def calculate_all_seasonal_factors(docname):
    """Calculate seasonal factors - Module level function"""
    try:
        doc = frappe.get_doc("Auto Price List", docname)
        return doc.calculate_all_seasonal_factors()
    except Exception as e:
        frappe.log_error(f"Calculate seasonal factors error: {str(e)}")
        return {'status': 'error', 'message': str(e)}

@frappe.whitelist()
def get_ml_pricing_insights(docname):
    """Get ML pricing insights - Module level function"""
    try:
        doc = frappe.get_doc("Auto Price List", docname)
        return doc.get_ml_pricing_insights()
    except Exception as e:
        frappe.log_error(f"ML pricing insights error: {str(e)}")
        return {'status': 'error', 'message': str(e)}

@frappe.whitelist()
def get_demand_forecast(docname, item_code, periods=12):
    """Get demand forecast - Module level function"""
    try:
        doc = frappe.get_doc("Auto Price List", docname)
        return doc.get_demand_forecast(item_code, periods)
    except Exception as e:
        frappe.log_error(f"Demand forecast error: {str(e)}")
        return {'status': 'error', 'message': str(e)}

@frappe.whitelist()
def get_inventory_optimization(docname, item_code):
    """Get inventory optimization - Module level function"""
    try:
        doc = frappe.get_doc("Auto Price List", docname)
        return doc.get_inventory_optimization(item_code)
    except Exception as e:
        frappe.log_error(f"Inventory optimization error: {str(e)}")
        return {'status': 'error', 'message': str(e)}

@frappe.whitelist()
def run_price_elasticity_analysis(docname, item_code):
    """Run price elasticity analysis - Module level function"""
    try:
        doc = frappe.get_doc("Auto Price List", docname)
        return doc.run_price_elasticity_analysis(item_code)
    except Exception as e:
        frappe.log_error(f"Price elasticity analysis error: {str(e)}")
        return {'status': 'error', 'message': str(e)}

@frappe.whitelist()
def get_advanced_competitor_analysis(docname):
    """Get advanced competitor analysis - Module level function"""
    try:
        doc = frappe.get_doc("Auto Price List", docname)
        return doc.get_advanced_competitor_analysis()
    except Exception as e:
        frappe.log_error(f"Advanced competitor analysis error: {str(e)}")
        return {'status': 'error', 'message': str(e)}

@frappe.whitelist()
def get_manual_price_impact(price_list_name):
    """
    نمایش تأثیر قیمت‌های دستی مواد اولیه روی یک لیست قیمت
    """
    try:
        price_list = frappe.get_doc("Auto Price List", price_list_name)
        
        # پیدا کردن قیمت‌های دستی
        manual_prices = {}
        if price_list.manual_material_prices:
            for mp in price_list.manual_material_prices:
                manual_prices[mp.item_code] = mp.manual_price
        
        if not manual_prices:
            html = "<p>هیچ قیمت دستی‌ای تعریف نشده است</p>"
            return {"html": html}
        
        # ساخت HTML نمایش تأثیر
        title = getattr(price_list, 'name', price_list.name)
        html = f"""
        <div style="margin: 10px 0;">
            <h4>📊 تأثیر قیمت‌های دستی مواد اولیه</h4>
            <p><strong>لیست قیمت:</strong> {title}</p>
            <p><strong>تعداد قیمت‌های دستی:</strong> {len(manual_prices)}</p>
            
            <table class="table table-bordered">
                <thead>
                    <tr>
                        <th>کد ماده</th>
                        <th>نام ماده</th>
                        <th>قیمت دستی</th>
                        <th>محصولات متأثر</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for item_code, manual_price in manual_prices.items():
            item_name = frappe.db.get_value("Item", item_code, "item_name")
            
            # پیدا کردن محصولات متأثر
            affected_products = frappe.db.sql("""
                SELECT COUNT(DISTINCT b.item) as count
                FROM `tabBOM` b
                INNER JOIN `tabBOM Item` bi ON b.name = bi.parent
                WHERE bi.item_code = %s 
                AND b.is_active = 1
            """, (item_code,), as_dict=True)
            
            affected_count = affected_products[0].count if affected_products else 0
            
            html += f"""
                <tr>
                    <td>{item_code}</td>
                    <td>{item_name}</td>
                    <td>{frappe.format_value(manual_price, 'Currency')}</td>
                    <td>{affected_count} محصول</td>
                </tr>
            """
        
        html += """
                </tbody>
            </table>
            
            <div class="alert alert-info">
                <p><strong>نکته:</strong> برای اعمال این قیمت‌ها روی محصولات، از دکمه "به‌روزرسانی با قیمت‌های دستی" استفاده کنید.</p>
            </div>
        </div>
        """
        
        return {"html": html}
        
    except Exception as e:
        frappe.log_error(f"Error in get_manual_price_impact: {str(e)}")
        return {"html": f"<p>خطا در محاسبه: {str(e)}</p>"}


@frappe.whitelist()
def recalculate_with_manual_prices(price_list_name):
    """
    محاسبه مجدد قیمت‌های تمام آیتم‌ها با در نظر گیری قیمت‌های دستی جدید
    """
    print("🚀 ==> recalculate_with_manual_prices فراخوانی شد!")
    print(f"🚀 ==> price_list_name: {price_list_name}")
    frappe.logger().info(f"🚀 ==> recalculate_with_manual_prices فراخوانی شد برای {price_list_name}")
    try:
        price_list = frappe.get_doc("Auto Price List", price_list_name)
        
        frappe.logger().info("🚀 شروع recalculate_with_manual_prices")
        print("🚀 شروع recalculate_with_manual_prices")
        updated_count = 0
        
        # ایجاد mapping قیمت‌های دستی برای بررسی سریع
        manual_price_map = {}
        if price_list.manual_material_prices:
            for manual_price in price_list.manual_material_prices:
                if manual_price.item_code and manual_price.manual_price:
                    manual_price_map[manual_price.item_code] = manual_price.manual_price
        
        # اگر قیمت دستی وجود ندارد، هیچ کاری نکن
        if not manual_price_map:
            print("❌ هیچ قیمت دستی وجود ندارد")
            return {"updated_count": 0, "message": "هیچ قیمت دستی‌ای تعریف نشده است"}
        
        # لاگ شروع فرآیند
        frappe.logger().info(f"🔄 شروع به‌روزرسانی قیمت‌ها با {len(manual_price_map)} قیمت دستی")
        print(f"🔄 شروع به‌روزرسانی قیمت‌ها با {len(manual_price_map)} قیمت دستی")
        print(f"📋 قیمت‌های دستی: {manual_price_map}")
        for manual_item, manual_price in manual_price_map.items():
            frappe.logger().info(f"📋 قیمت دستی: {manual_item} = {manual_price:,.0f}")
        
        # شمارش کل آیتم‌ها
        total_items = len(price_list.items)
        affected_items = 0
        processed_items = 0
        price_changes = []
        
        frappe.logger().info(f"📊 تعداد کل آیتم‌ها: {total_items}")
        print(f"📊 تعداد کل آیتم‌ها: {total_items}")
        print(f"📊 قیمت‌های دستی: {manual_price_map}")
        
        for item in price_list.items:
            try:
                processed_items += 1
                frappe.logger().info(f"🔍 [{processed_items}/{total_items}] بررسی آیتم: {item.item_code}")
                print(f"🔍 [{processed_items}/{total_items}] بررسی آیتم: {item.item_code}")
                
                # بررسی اینکه آیا این آیتم تحت تأثیر قیمت‌های دستی است یا نه
                print(f"   🚀 فراخوانی is_item_affected_by_manual_prices برای {item.item_code}")
                item_affected = price_list.is_item_affected_by_manual_prices(item.item_code, manual_price_map)
                print(f"   🔍 آیتم {item.item_code} تحت تأثیر است؟ {item_affected}")
                
                if not item_affected:
                    frappe.logger().info(f"   ❌ آیتم {item.item_code} تحت تأثیر قیمت‌های دستی نیست")
                    print(f"   ❌ آیتم {item.item_code} تحت تأثیر قیمت‌های دستی نیست")
                    continue
                
                affected_items += 1
                frappe.logger().info(f"   ✅ آیتم {item.item_code} تحت تأثیر است - شروع محاسبه")
                
                # محاسبه مجدد قیمت با قیمت‌های دستی جدید
                old_cost = item.raw_material_cost or 0
                old_price = item.selling_price or 0
                
                frappe.logger().info(f"   📊 قیمت‌های فعلی: هزینه={old_cost:,.0f}, قیمت={old_price:,.0f}")
                
                # محاسبه قیمت جدید با قیمت‌های دستی
                print(f"   🚀 شروع محاسبه هزینه جدید برای {item.item_code}...")
                new_cost = price_list.calculate_item_cost_with_exploded_items(item.item_code)
                cost_difference = new_cost - old_cost
                
                frappe.logger().info(f"   🧮 تفاوت هزینه محاسبه شده: {cost_difference:,.0f}")
                print(f"   🧮 تفاوت هزینه محاسبه شده: {cost_difference:,.0f}")
                
                print(f"   🔍 جزئیات محاسبه:")
                print(f"      - قیمت قدیمی: {old_cost:,.0f}")
                print(f"      - قیمت جدید محاسبه شده: {new_cost:,.0f}")
                print(f"      - تفاوت محاسبه شده: {cost_difference:,.0f}")
                print(f"      - مقدار مطلق تفاوت: {abs(cost_difference):,.2f}")
                print(f"      - آیا تفاوت > 0.01؟ {abs(cost_difference) > 0.01}")
                
                # بررسی اینکه آیا قیمت جدید معتبر است
                print(f"   🔍 بررسی شرایط:")
                print(f"      - new_cost: {new_cost:,.0f}")
                print(f"      - new_cost <= 0: {new_cost <= 0}")
                print(f"      - abs(cost_difference): {abs(cost_difference):,.2f}")
                print(f"      - abs(cost_difference) < 0.01: {abs(cost_difference) < 0.01}")
                
                if new_cost <= 0:
                    frappe.logger().info(f"   ❌ قیمت جدید نامعتبر است: {new_cost}")
                    print(f"   ❌ قیمت جدید نامعتبر است: {new_cost}")
                    continue
                    
                if abs(cost_difference) < 0.01:
                    frappe.logger().info(f"   ℹ️ تفاوت هزینه ناچیز است: {abs(cost_difference):.6f}")
                    print(f"   ℹ️ تفاوت هزینه ناچیز است: {abs(cost_difference):.6f}")
                    print(f"   ⚠️ آیتم {item.item_code} به‌روزرسانی نمی‌شود چون تفاوت کمتر از 0.01 است")
                    continue
                
                # بررسی اینکه آیا نیاز به به‌روزرسانی هست یا نه
                cost_diff = abs(cost_difference)
                frappe.logger().info(f"   📏 مقدار تفاوت هزینه: {cost_diff:,.2f}")
                print(f"   📏 مقدار تفاوت هزینه: {cost_diff:,.2f}")
                
                # فقط اگر تفاوت معنی‌دار باشد، به‌روزرسانی کن
                should_update = cost_diff > 0.01
                print(f"   🔍 نیاز به به‌روزرسانی: {should_update} (تفاوت > 0.01)")
                
                if should_update:
                    print(f"   ✅ شروع به‌روزرسانی {item.item_code}")
                    try:
                        # ابتدا raw_material_cost را به‌روزرسانی کن
                        item.raw_material_cost = new_cost
                        
                        # سپس قیمت نهایی را محاسبه کن
                        new_price = price_list.calculate_final_price_for_item(item)
                        frappe.logger().info(f"   💰 قیمت نهایی محاسبه شده: {new_price:,.0f}")
                        
                        # لاگ تفصیلی تغییرات
                        cost_change = new_cost - old_cost
                        price_change = new_price - old_price
                        cost_percent = (cost_change / old_cost * 100) if old_cost > 0 else 0
                        price_percent = (price_change / old_price * 100) if old_price > 0 else 0
                        
                        frappe.logger().info(f"   ✅ به‌روزرسانی {item.item_code}:")
                        frappe.logger().info(f"      💰 هزینه مواد: {old_cost:,.0f} → {new_cost:,.0f} ({cost_change:+,.0f} | {cost_percent:+.1f}%)")
                        frappe.logger().info(f"      💵 قیمت فروش: {old_price:,.0f} → {new_price:,.0f} ({price_change:+,.0f} | {price_percent:+.1f}%)")
                        
                        # اضافه کردن تغییرات به لیست برای نمایش
                        item_name = frappe.db.get_value("Item", item.item_code, "item_name") or item.item_code
                        price_changes.append({
                            "item_code": item.item_code,
                            "item_name": item_name,
                            "old_cost": old_cost,
                            "new_cost": new_cost,
                            "cost_change": cost_change,
                            "cost_percent": cost_percent,
                            "old_price": old_price,
                            "new_price": new_price,
                            "price_change": price_change,
                            "price_percent": price_percent
                        })
                        
                        # به‌روزرسانی قیمت فروش در جدول items
                        item.selling_price = new_price
                        updated_count += 1
                        
                    except Exception as calc_error:
                        frappe.logger().error(f"   ❌ خطا در محاسبه قیمت نهایی: {str(calc_error)}")
                        print(f"   ❌ خطا در محاسبه قیمت نهایی: {str(calc_error)}")
                        # حداقل هزینه مواد را به‌روزرسانی کن
                        item.raw_material_cost = new_cost
                        updated_count += 1
                    
                else:
                    frappe.logger().info(f"   ⏭️ آیتم {item.item_code}: تغییر معنی‌داری نداشت (تفاوت: {cost_diff:,.2f})")
                    print(f"   ⏭️ آیتم {item.item_code}: تغییر معنی‌داری نداشت (تفاوت: {cost_diff:,.2f})")
            
            except Exception as e:
                frappe.logger().error(f"   ❌ خطا در به‌روزرسانی {item.item_code}: {str(e)}")
                import traceback
                frappe.logger().error(f"   🔍 جزئیات خطا: {traceback.format_exc()}")
                continue
        
        frappe.logger().info(f"📈 خلاصه: {processed_items} آیتم بررسی شد، {affected_items} تحت تأثیر بود، {updated_count} تغییر کرد")
        
        # ذخیره تغییرات
        if updated_count > 0:
            # اجبار به refresh کردن child table
            for item in price_list.items:
                item.db_update()
            
            price_list.save()
            frappe.db.commit()
            frappe.logger().info(f"🎉 به‌روزرسانی کامل شد: {updated_count} آیتم تغییر کرد")
            print(f"🎉 به‌روزرسانی کامل شد: {updated_count} آیتم تغییر کرد")
        else:
            frappe.logger().info(f"ℹ️  هیچ آیتمی نیاز به تغییر نداشت")
            print(f"ℹ️  هیچ آیتمی نیاز به تغییر نداشت")
        
        # اضافه کردن جزئیات بیشتر به response
        response = {
            "updated_count": updated_count,
            "total_items": total_items,
            "affected_items": affected_items,
            "processed_items": processed_items,
            "manual_prices_count": len(manual_price_map),
            "manual_prices": list(manual_price_map.keys()),
            "price_changes": price_changes,
            "success": True,
            "refresh_needed": updated_count > 0
        }
        
        frappe.logger().info(f"📈 خلاصه نهایی: {response}")
        print(f"📈 خلاصه نهایی: {response}")
        
        return response
        
    except Exception as e:
        error_msg = f"Recalc error: {str(e)}"
        frappe.logger().error(error_msg)
        print(f"❌ خطا: {error_msg}")
        return {
            "success": False,
            "error": str(e),
            "updated_count": 0,
            "total_items": 0,
            "affected_items": 0,
            "processed_items": 0,
            "manual_prices_count": 0,
            "manual_prices": [],
            "price_changes": []
        }

