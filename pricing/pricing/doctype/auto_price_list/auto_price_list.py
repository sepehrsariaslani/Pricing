import frappe
from frappe.model.document import Document
from frappe.utils import flt, cint, get_datetime, add_days, today, getdate
import math
import json
from datetime import datetime, timedelta
from collections import defaultdict
from .ai import PricingAI
from .price_comparison_methods import get_price_comparison_data
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
    
    # کنترل لاگ‌گیری debug - برای غیرفعال‌سازی در production این را False کنید
    DEBUG_MODE = False
    
    def __init__(self, *args, **kwargs):
        # حل مشکل database lock timeout با مدیریت بهتر تراکنش
        try:
            super().__init__(*args, **kwargs)
        except frappe.QueryTimeoutError as e:
            if self.DEBUG_MODE:
                frappe.logger("pricing").debug(f"خطای database lock در __init__: {str(e)}")
            # تلاش برای بارگذاری بدون lock
            if len(args) >= 2 and isinstance(args[1], str):
                kwargs_no_lock = kwargs.copy()
                kwargs_no_lock.pop('for_update', None)
                super().__init__(args[0], args[1], **kwargs_no_lock)
            else:
                super().__init__(args[0] if args else 'Auto Price List')
        
        self._overhead_cache = None
        self._market_data_cache = {}
        self._bom_cache = {}
        self._workstation_cache = {}
        self._pricing_ai = None
        self._debug_mode = self.DEBUG_MODE
    
    def _log_debug(self, message):
        """لاگ‌گیری شرطی - فقط در حالت debug"""
        if self._debug_mode:
            frappe.logger("pricing").debug(message)
    
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
    def before_insert(self):
        """
        اجرا قبل از insert - پاکسازی و آماده‌سازی child tables برای duplicate
        """
        # پاکسازی name و parent از تمام child rows برای duplicate
        # این کار باعث میشه Frappe خودش این فیلدها رو بعد از insert parent set کنه
        
        def clear_and_reinit_child(child, doctype):
            """پاکسازی و re-init کردن child برای جلوگیری از مشکل duplicate"""
            # ذخیره data فعلی
            child_data = child.as_dict()
            
            # پاک کردن fields مربوط به database
            child_data['name'] = None
            child_data['parent'] = None
            child_data['parenttype'] = self.doctype
            
            # Re-init کردن child با data جدید
            # این کار باعث میشه Frappe تمام internal attributes رو درست set کنه
            from frappe.model.document import Document
            new_child = Document(child_data)
            
            # کپی کردن attributes جدید به child قدیمی
            for key, value in new_child.__dict__.items():
                setattr(child, key, value)
        
        # پاکسازی و re-init تمام child tables
        for item in self.items or []:
            clear_and_reinit_child(item, 'Auto Price List Item')
        
        for bundle in self.product_bundles or []:
            clear_and_reinit_child(bundle, 'Auto Price List Product Bundle')
        
        for prev_item in self.prev_items or []:
            clear_and_reinit_child(prev_item, 'Auto Price List Prev Item')
        
        for bulk_item in self.bulk_pricing_items or []:
            clear_and_reinit_child(bulk_item, 'Auto Price List Bulk Pricing Item')
        
        for manual_price in self.manual_material_prices or []:
            clear_and_reinit_child(manual_price, 'Manual Material Price')
        
        for step in self.pricing_steps or []:
            clear_and_reinit_child(step, 'Auto Price List Pricing Step')
    
    def _validate_links(self):
        """
        Override validation links برای جلوگیری از خطا در duplicate
        وقتی سند جدید هست (is_new) و parent هنوز در database نیست، validation رو skip میکنیم
        """
        if self.is_new() and not self.get('name'):
            # سند جدیده و name هنوز set نشده، پس در حال duplicate هستیم
            # skip link validation برای child tables
            return
        
        # در غیر این صورت، validation عادی رو اجرا کن
        super()._validate_links()
    
    # [validate moved to end of file]


    # [validate_dates moved to end of file]

    
    def _init_batch_cache(self, item_codes):
        """
        بارگذاری همه داده‌های مورد نیاز به صورت دسته‌ای
        این متد سرعت محاسبات را به شدت افزایش می‌دهد
        """
        if not item_codes:
            return
        
        # پاک کردن cache قبلی
        self._bom_cache = {}
        self._item_price_cache = {}
        self._exploded_items_cache = {}
        self._manual_prices_cache = {}
        
        # 1. بارگذاری همه BOM ها با یک query
        boms = frappe.get_all("BOM", 
            filters={
                "item": ["in", item_codes],
                "is_active": 1,
                "is_default": 1
            },
            fields=["name", "item", "raw_material_cost", "operating_cost"]
        )
        for bom in boms:
            self._bom_cache[bom.item] = bom
        
        # 2. بارگذاری قیمت‌های آیتم‌ها با یک query (از آخرین خرید)
        bom_names = [bom.name for bom in boms]
        if bom_names:
            # گرفتن همه exploded items
            exploded_items = frappe.db.sql("""
                SELECT bei.parent, bei.item_code, bei.qty_consumed_per_unit, bei.rate, bei.amount
                FROM `tabBOM Explosion Item` bei
                WHERE bei.parent IN %(bom_names)s
            """, {"bom_names": bom_names}, as_dict=True)
            
            for ei in exploded_items:
                if ei.parent not in self._exploded_items_cache:
                    self._exploded_items_cache[ei.parent] = []
                self._exploded_items_cache[ei.parent].append(ei)
            
            # گرفتن همه کدهای مواد اولیه یکتا
            raw_material_codes = list(set(ei.item_code for ei in exploded_items))
            
            if raw_material_codes:
                # گرفتن قیمت‌ها از آخرین خرید
                prices = frappe.db.sql("""
                    SELECT item_code, rate
                    FROM (
                        SELECT pi.item_code, pi.rate, pi.creation,
                               ROW_NUMBER() OVER (PARTITION BY pi.item_code ORDER BY pi.creation DESC) as rn
                        FROM `tabPurchase Invoice Item` pi
                        INNER JOIN `tabPurchase Invoice` p ON pi.parent = p.name
                        WHERE pi.item_code IN %(item_codes)s
                          AND p.docstatus = 1
                    ) sub
                    WHERE rn = 1
                """, {"item_codes": raw_material_codes}, as_dict=True)
                
                for p in prices:
                    self._item_price_cache[p.item_code] = p.rate
                
                # fallback به valuation_rate برای آیتم‌هایی که خرید ندارند
                missing_items = [code for code in raw_material_codes if code not in self._item_price_cache]
                if missing_items:
                    valuation_rates = frappe.get_all("Item",
                        filters={"item_code": ["in", missing_items]},
                        fields=["item_code", "valuation_rate", "standard_rate"]
                    )
                    for item in valuation_rates:
                        if item.item_code not in self._item_price_cache:
                            self._item_price_cache[item.item_code] = flt(item.valuation_rate) or flt(item.standard_rate) or 0
        
        # 3. بارگذاری قیمت‌های دستی
        if self.manual_item_prices:
            for manual in self.manual_item_prices:
                if manual.item_code:
                    self._manual_prices_cache[manual.item_code] = {
                        'raw_material_cost': flt(manual.get('raw_material_cost')) if manual.get('raw_material_cost') else None,
                        'labor_cost': flt(manual.get('labor_cost')) if manual.get('labor_cost') else None,
                        'subcontracting_cost': flt(manual.get('subcontracting_cost')) if manual.get('subcontracting_cost') else None,
                        'electricity_cost': flt(manual.get('electricity_cost')) if manual.get('electricity_cost') else None,
                        'rent_cost': flt(manual.get('rent_cost')) if manual.get('rent_cost') else None,
                        'consumable_cost': flt(manual.get('consumable_cost')) if manual.get('consumable_cost') else None,
                        'operation_cost': flt(manual.get('operation_cost')) if manual.get('operation_cost') else None,
                        'overhead_cost': flt(manual.get('overhead_cost')) if manual.get('overhead_cost') else None,
                    }
        
        # 4. بارگذاری قیمت‌های دستی مواد اولیه (manual_material_prices)
        if self.manual_material_prices:
            for manual in self.manual_material_prices:
                if manual.item_code and manual.manual_price:
                    self._item_price_cache[manual.item_code] = flt(manual.manual_price)
    
    def _get_cached_bom(self, item_code):
        """دریافت BOM از cache"""
        if hasattr(self, '_bom_cache') and item_code in self._bom_cache:
            return self._bom_cache[item_code]
        return None
    
    def _get_cached_item_price(self, item_code):
        """دریافت قیمت آیتم از cache - برگشت None اگر در cache نیست"""
        if hasattr(self, '_item_price_cache') and item_code in self._item_price_cache:
            return self._item_price_cache[item_code]
        return None  # برگشت None به جای 0 برای تشخیص عدم وجود در cache
    
    def _get_cached_exploded_items(self, bom_name):
        """دریافت exploded items از cache"""
        if hasattr(self, '_exploded_items_cache') and bom_name in self._exploded_items_cache:
            return self._exploded_items_cache[bom_name]
        return None  # برگشت None به جای لیست خالی
    
    def _get_cached_manual_price(self, item_code):
        """دریافت قیمت دستی از cache"""
        if hasattr(self, '_manual_prices_cache') and item_code in self._manual_prices_cache:
            return self._manual_prices_cache[item_code]
        return None
    
    def _ensure_cache_initialized(self):
        """اطمینان از اینکه cache مقداردهی شده"""
        if not hasattr(self, '_item_price_cache'):
            item_codes = [item.item_code for item in self.items if item.item_code]
            if item_codes:
                self._init_batch_cache(item_codes)
    
    def calculate_total_interest_percentages(self):
        """محاسبه درصد کل بهره برای قسطی و تأخیری با فرمول بهره مرکب"""
        # محاسبه درصد کل بهره قسطی با فرمول بهره مرکب
        if self.enable_installment and self.monthly_interest_rate and self.number_of_months:
            monthly_rate = flt(self.monthly_interest_rate) / 100
            months = int(self.number_of_months)
            # فرمول بهره مرکب: ((1 + r)^n - 1) * 100
            self.installment_total_interest_percentage = ((1 + monthly_rate) ** months - 1) * 100
        else:
            self.installment_total_interest_percentage = 0
            
        # محاسبه درصد کل بهره تأخیری با فرمول بهره مرکب
        if self.enable_deferred_payment and self.deferred_payment_interest_rate and self.deferred_payment_months:
            monthly_rate = flt(self.deferred_payment_interest_rate) / 100
            months = int(self.deferred_payment_months)
            # فرمول بهره مرکب
            self.deferred_payment_total_interest_percentage = ((1 + monthly_rate) ** months - 1) * 100
        else:
            self.deferred_payment_total_interest_percentage = 0
        
        # به‌روزرسانی محاسبات تخفیف
        self._update_markup_calculations()
    
    def _update_markup_calculations(self):
        """به‌روزرسانی محاسبات افزایش قیمت بر اساس تخفیف هدف"""
        if self.target_discount_percentage and flt(self.target_discount_percentage) > 0:
            discount = flt(self.target_discount_percentage)
            # فرمول: اگر تخفیف x% است، افزایش قیمت = x / (100 - x) * 100
            self.required_markup_percentage = (discount / (100 - discount)) * 100
        else:
            self.required_markup_percentage = 0
            self.final_selling_price_with_markup = 0
    
    @frappe.whitelist()
    def update_discount_calculations(self):
        """
        به‌روزرسانی محاسبات تخفیف و افزایش قیمت
        این متد از سمت کلاینت فراخوانی می‌شود وقتی target_discount_percentage تغییر می‌کند
        """
        self._update_markup_calculations()
        
        # محاسبه مجموع قیمت فروش برای final_selling_price_with_markup
        total_selling_price = 0
        if self.items:
            total_selling_price = sum(flt(item.selling_price or 0) for item in self.items)
        
        if total_selling_price > 0 and self.target_discount_percentage:
            # قیمت با افزایش = قیمت فروش / (1 - درصد تخفیف)
            self.final_selling_price_with_markup = total_selling_price / (1 - flt(self.target_discount_percentage) / 100)
        
        return {
            'success': True,
            'required_markup_percentage': self.required_markup_percentage,
            'final_selling_price_with_markup': self.final_selling_price_with_markup,
            'target_discount_percentage': self.target_discount_percentage
        }
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
                
                frappe.logger("pricing").debug(f"عملیات پیمانکاری شناسایی شد: {operation.operation} - هزینه: {subcontracting_cost}")
            
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در محاسبه هزینه پیمانکاری: {str(e)}")
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
                        frappe.logger("pricing").debug(f"آیتم خدمات مرتبط پیدا شد: {item.item_name} - قیمت: {item.standard_rate}")
                        return item
            
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در جستجوی آیتم خدمات: {str(e)}")
        
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
                frappe.logger("pricing").debug(f"Error getting overhead costs: {str(e)}")
                self._overhead_cache = {'total_overhead': 0}
        return self._overhead_cache
    
    @frappe.whitelist()
    def load_raw_materials_from_purchases(self):
        """
        📦 بارگذاری مواد اولیه (آیتم‌های بدون BOM) با قیمت آخرین فاکتور خرید
        این متد:
        1. همه آیتم‌های بدون BOM را پیدا می‌کند
        2. قیمت آخرین فاکتور خرید را برای هر کدام می‌گیرد
        3. در جدول manual_material_prices ذخیره می‌کند
        """
        try:
            # 1. گرفتن همه آیتم‌هایی که BOM ندارند
            items_without_bom = self._get_items_without_bom()
            
            if not items_without_bom:
                return {
                    "success": False,
                    "message": "هیچ ماده اولیه‌ای (آیتم بدون BOM) یافت نشد"
                }
            
            # 2. گرفتن قیمت آخرین خرید برای همه آیتم‌ها
            purchase_prices = self._get_last_purchase_prices(items_without_bom)
            
            # 3. پاک کردن جدول موجود
            self.manual_material_prices = []
            
            # 4. اضافه کردن آیتم‌ها به جدول
            added_count = 0
            for item_code in items_without_bom:
                purchase_info = purchase_prices.get(item_code, {})
                
                # گرفتن اطلاعات آیتم
                item_info = frappe.db.get_value("Item", item_code, 
                    ["item_name", "item_group", "stock_uom"], as_dict=True) or {}
                
                self.append("manual_material_prices", {
                    "item_code": item_code,
                    "item_name": item_info.get("item_name", ""),
                    "item_group": item_info.get("item_group", ""),
                    "uom": item_info.get("stock_uom", ""),
                    "last_purchase_price": flt(purchase_info.get("rate", 0)),
                    "last_purchase_date": purchase_info.get("date"),
                    "last_supplier": purchase_info.get("supplier"),
                    "manual_price": 0,
                    "use_manual_price": 0,
                    "price_difference": 0,
                    "price_difference_percent": 0
                })
                added_count += 1
            
            # 5. ذخیره تغییرات
            self.save()
            
            return {
                "success": True,
                "message": f"✅ {added_count} ماده اولیه بارگذاری شد",
                "count": added_count
            }
            
        except Exception as e:
            frappe.log_error(f"خطا در بارگذاری مواد اولیه: {str(e)}")
            return {
                "success": False,
                "message": f"خطا: {str(e)}"
            }
    
    def _get_items_without_bom(self):
        """
        📦 استخراج مواد اولیه‌ای که در BOM آیتم‌های این سند استفاده شده‌اند
        فقط موادی که واقعاً در محصولات این لیست قیمت مصرف می‌شوند
        """
        # گرفتن لیست آیتم‌های موجود در این سند
        doc_item_codes = [item.item_code for item in self.items if item.item_code]
        
        if not doc_item_codes:
            return []
        
        # گرفتن BOM‌های مربوط به آیتم‌های این سند
        bom_names = frappe.db.sql_list("""
            SELECT name
            FROM `tabBOM`
            WHERE item IN %(items)s
              AND is_active = 1
              AND is_default = 1
        """, {"items": doc_item_codes})
        
        if not bom_names:
            return []
        
        # گرفتن مواد اولیه از BOM Explosion Items این BOM‌ها
        exploded_items = frappe.db.sql_list("""
            SELECT DISTINCT bei.item_code
            FROM `tabBOM Explosion Item` bei
            WHERE bei.parent IN %(bom_names)s
        """, {"bom_names": bom_names})
        
        if not exploded_items:
            return []
        
        # از بین این آیتم‌ها، فقط آن‌هایی که خودشان BOM فعال ندارند را بگیر
        # (مواد اولیه نهایی که دیگر تجزیه نمی‌شوند)
        items_with_bom = set(frappe.db.sql_list("""
            SELECT DISTINCT item 
            FROM `tabBOM` 
            WHERE is_active = 1
        """))
        
        # فقط آیتم‌هایی که در explosion هستند ولی BOM ندارند
        raw_materials = [item for item in exploded_items if item not in items_with_bom]
        
        return raw_materials
    
    def _get_last_purchase_prices(self, item_codes):
        """
        💰 دریافت قیمت آخرین فاکتور خرید برای لیستی از آیتم‌ها
        """
        if not item_codes:
            return {}
        
        # استفاده از window function برای گرفتن آخرین قیمت هر آیتم
        prices = frappe.db.sql("""
            SELECT item_code, rate, posting_date, supplier
            FROM (
                SELECT 
                    pii.item_code,
                    pii.rate,
                    pi.posting_date,
                    pi.supplier,
                    ROW_NUMBER() OVER (PARTITION BY pii.item_code ORDER BY pi.posting_date DESC, pi.creation DESC) as rn
                FROM `tabPurchase Invoice Item` pii
                INNER JOIN `tabPurchase Invoice` pi ON pii.parent = pi.name
                WHERE pi.docstatus = 1
                  AND pii.item_code IN %(item_codes)s
                  AND pii.rate > 0
            ) ranked
            WHERE rn = 1
        """, {"item_codes": item_codes}, as_dict=True)
        
        return {
            p['item_code']: {
                "rate": p['rate'],
                "date": p['posting_date'],
                "supplier": p['supplier']
            }
            for p in prices
        }

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

    # [validate_pricing_calculations moved to end of file]




    # 4. اصلاح calculate_item_prices_internal
    @frappe.whitelist()
    def calculate_item_prices_internal(self):
        """
        محاسبه قیمت‌ها - نسخه اصلاح شده
        """
        if not self.items:
            return
        
        # بارگذاری داده‌ها
        item_codes = [item.item_code for item in self.items if item.item_code]
        bom_data = self._batch_load_boms(item_codes)
        overhead_costs = self._get_cached_overhead_costs()
        
        # ایجاد mapping قیمت‌های دستی
        manual_price_map = {}
        if self.manual_material_prices:
            for mp in self.manual_material_prices:
                if mp.item_code and mp.manual_price:
                    manual_price_map[mp.item_code] = mp.manual_price
        
        for item in self.items:
            if not item.item_code:
                continue
            
            # بررسی Product Bundle
            if self.is_product_bundle(item.item_code):
                self.calculate_bundle_price(item)
                continue
            
            bom_info = bom_data.get(item.item_code)
            
            if bom_info:
                # 1. محاسبه مواد اولیه
                item.raw_material_cost = self.calculate_item_cost_with_exploded_items(item.item_code)
                
                # 2. محاسبه عملیات (با جزئیات کامل شامل پیمانکاری)
                self.calculate_operation_cost(item)
                # بعد از calculate_operation_cost، همه فیلدها پر شده‌اند:
                # - labor_cost, subcontracting_cost, electricity_cost, etc.
                # - operation_cost = labor + subcontracting
                
                # 3. محاسبه سربار (برق + اجاره + مصرفی)
                # calculate_operation_cost قبلاً این فیلدها را پر کرده
                # حالا فقط باید overhead_cost را محاسبه کنیم
                self.calculate_overhead_cost(item)
            
            # 4. محاسبه total_cost صحیح - فقط 3 جزء اصلی
            item.total_cost = (
                flt(item.raw_material_cost or 0) +
                flt(item.operation_cost or 0) +
                flt(item.overhead_cost or 0)
            )
            
            # 5. محاسبه قیمت نهایی با pricing steps
            if self.pricing_steps:
                self.calculate_step_by_step_pricing(item)
                final_price, steps = self.calculate_price_based_on_steps(item, item.total_cost)
                item.step_by_step_calculation = "\n".join(steps)
            else:
                # محاسبه ساده با حاشیه سود
                final_price = item.total_cost * (1 + (self.profit_margin or 0) / 100)
                item.final_selected_price = final_price
        
        frappe.logger("pricing").debug(f"✅ محاسبه قیمت برای {len(self.items)} کالا کامل شد")



    def get_bom_exploded_items(self, item_code):
        """
        دریافت لیست مواد اولیه از BOM exploded items
        """
        try:
            # پیدا کردن BOM فعال
            bom_name = frappe.db.get_value("BOM", {
                "item": item_code,
                "is_active": 1,
                "is_default": 1
            }, "name")
            
            if not bom_name:
                return []
            
            # دریافت exploded items
            exploded_items = frappe.get_all("BOM Explosion Item", 
                filters={"parent": bom_name},
                fields=["item_code", "qty_consumed_per_unit", "rate", "amount"]
            )
            
            if not exploded_items:
                # fallback به BOM items
                bom = frappe.get_doc("BOM", bom_name)
                exploded_items = []
                for bom_item in bom.items:
                    exploded_items.append({
                        "item_code": bom_item.item_code,
                        "qty_consumed_per_unit": bom_item.qty,
                        "rate": bom_item.rate,
                        "amount": bom_item.amount
                    })
            
            return exploded_items
            
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در دریافت BOM exploded items برای {item_code}: {str(e)}")
            return []

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
    
    def calculate_overhead_cost(self, item, force_recalculate=False):
        """
        محاسبه هزینه سربار برای یک کالا
        سربار = برق + اجاره + مصرفی
        """
        # جلوگیری از محاسبه تکراری
        if not force_recalculate and hasattr(item, '_overhead_calculated') and item._overhead_calculated:
            return
        
        # سربار = برق + اجاره + مصرفی
        item.overhead_cost = (
            flt(item.electricity_cost or 0) + 
            flt(item.rent_cost or 0) + 
            flt(item.consumable_cost or 0)
        )
        
        item._overhead_calculated = True

    def calculate_nested_operation_cost(self, item_code, processed_items=None):
        """
        محاسبه هزینه عملیات برای یک آیتم با در نظر گیری BOM چند سطحی
        شامل: برق، اجاره، کارگر، مصرفی، پیمانکاری
        (Optimized with Item Cost Caching)
        """
        if processed_items is None:
            processed_items = set()
        
        # Check Item Cache
        if hasattr(self, '_item_op_cost_cache') and item_code in self._item_op_cost_cache:
            return self._item_op_cost_cache[item_code]

        # جلوگیری از حلقه بی‌نهایت
        if item_code in processed_items:
            return {
                'total_operation_cost': 0,
                'electricity_cost': 0,
                'rent_cost': 0,
                'labor_cost': 0,
                'consumable_cost': 0,
                'subcontracting_cost': 0
            }
        
        processed_items.add(item_code)
        
        try:
            # پیدا کردن BOM فعال (Use Cache or lightweight query)
            if hasattr(self, '_bom_name_cache') and item_code in self._bom_name_cache:
                bom_name = self._bom_name_cache[item_code]
            else:
                bom_name = frappe.db.get_value("BOM", {
                    "item": item_code,
                    "is_active": 1,
                    "is_default": 1
                }, "name")
                if not hasattr(self, '_bom_name_cache'):
                    self._bom_name_cache = {}
                self._bom_name_cache[item_code] = bom_name
            
            if not bom_name:
                return {
                    'total_operation_cost': 0,
                    'electricity_cost': 0,
                    'rent_cost': 0,
                    'labor_cost': 0,
                    'consumable_cost': 0,
                    'subcontracting_cost': 0
                }
            
            # محاسبه هزینه‌های عملیاتی از operations این BOM
            operation_costs = self.calculate_bom_operation_costs(bom_name)
            
            # محاسبه هزینه‌های عملیاتی آیتم‌های فرعی (nested)
            bom_items = frappe.get_all("BOM Item", filters={"parent": bom_name}, fields=["item_code", "qty"])
            
            for bom_item in bom_items:
                # محاسبه هزینه‌های عملیاتی آیتم فرعی (Recursive)
                sub_costs = self.calculate_nested_operation_cost(bom_item.item_code, processed_items.copy())
                
                # اضافه کردن هزینه‌های فرعی با در نظر گیری مقدار
                qty_factor = bom_item.qty or 1
                operation_costs['electricity_cost'] += sub_costs['electricity_cost'] * qty_factor
                operation_costs['rent_cost'] += sub_costs['rent_cost'] * qty_factor
                operation_costs['labor_cost'] += sub_costs['labor_cost'] * qty_factor
                operation_costs['consumable_cost'] += sub_costs['consumable_cost'] * qty_factor
                operation_costs['subcontracting_cost'] += sub_costs['subcontracting_cost'] * qty_factor
            
            # محاسبه مجموع
            operation_costs['total_operation_cost'] = (
                operation_costs['electricity_cost'] +
                operation_costs['rent_cost'] +
                operation_costs['labor_cost'] +
                operation_costs['consumable_cost'] +
                operation_costs['subcontracting_cost']
            )
            
            # Cache the result for this item
            if not hasattr(self, '_item_op_cost_cache'):
                self._item_op_cost_cache = {}
            self._item_op_cost_cache[item_code] = operation_costs.copy()

            return operation_costs
            
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در محاسبه هزینه‌های عملیاتی {item_code}: {str(e)}")
            return {
                'total_operation_cost': 0,
                'electricity_cost': 0,
                'rent_cost': 0,
                'labor_cost': 0,
                'consumable_cost': 0,
                'subcontracting_cost': 0
            }

    def calculate_bom_operation_costs(self, bom_name):
        """
        محاسبه هزینه‌های عملیاتی از operations یک BOM
        شامل: برق، اجاره، کارگر، مصرفی، پیمانکاری
        (Optimized with Caching)
        """
        # Check cache if available
        if hasattr(self, '_bom_op_cost_cache') and bom_name in self._bom_op_cost_cache:
            return self._bom_op_cost_cache[bom_name]

        costs = {
            'electricity_cost': 0,
            'rent_cost': 0,
            'labor_cost': 0,
            'consumable_cost': 0,
            'subcontracting_cost': 0
        }
        
        try:
            # بررسی آیا این BOM پیمانکاری است
            # Use lightweight get_value or cache
            bom_data = frappe.db.get_value("BOM", bom_name, ["is_subcontracted", "service_item"], as_dict=True)
            if not bom_data:
                return costs

            is_subcontracted = bom_data.is_subcontracted
            service_item = bom_data.service_item
            
            # اگر BOM پیمانکاری است، هزینه پیمانکاری را محاسبه کن
            if is_subcontracted and service_item:
                subcontracting_cost = self.get_service_item_price_from_purchase(service_item)
                if subcontracting_cost > 0:
                    costs['subcontracting_cost'] = subcontracting_cost
            
            # دریافت operations این BOM
            operations = frappe.get_all("BOM Operation", 
                filters={"parent": bom_name},
                fields=["operation", "time_in_mins", "workstation", "hour_rate"]
            )
            
            # Initialize workstation cache if needed
            if not hasattr(self, '_workstation_cache'):
                self._workstation_cache = {}

            for operation in operations:
                if not operation.workstation or not operation.time_in_mins:
                    continue
                
                # دریافت اطلاعات workstation (Cached)
                ws_name = operation.workstation
                if ws_name in self._workstation_cache:
                    workstation = self._workstation_cache[ws_name]
                else:
                    workstation = frappe.db.get_value("Workstation", ws_name, 
                        ["hour_rate_electricity", "hour_rate_rent", "hour_rate_labour", "hour_rate_consumable"], 
                        as_dict=True) or {}
                    self._workstation_cache[ws_name] = workstation
                
                # تبدیل زمان از دقیقه به ساعت
                time_in_hours = flt(operation.time_in_mins) / 60.0
                
                # محاسبه هزینه‌های مختلف
                if workstation.get('hour_rate_electricity'):
                    costs['electricity_cost'] += flt(workstation.hour_rate_electricity) * time_in_hours
                
                if workstation.get('hour_rate_rent'):
                    costs['rent_cost'] += flt(workstation.hour_rate_rent) * time_in_hours
                
                if workstation.get('hour_rate_labour'):
                    costs['labor_cost'] += flt(workstation.hour_rate_labour) * time_in_hours
                
                if workstation.get('hour_rate_consumable'):
                    costs['consumable_cost'] += flt(workstation.hour_rate_consumable) * time_in_hours
            
            # Cache the result
            if not hasattr(self, '_bom_op_cost_cache'):
                self._bom_op_cost_cache = {}
            self._bom_op_cost_cache[bom_name] = costs
            
            return costs
            
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در محاسبه هزینه‌های operations BOM {bom_name}: {str(e)}")
            return costs

    def calculate_subcontracting_cost_from_bom(self, bom_name, operation_name):
        """
        محاسبه هزینه پیمانکاری از Subcontracting BOM و Service Item
        استراتژی: از آخرین فاکتور خرید یا سفارش خرید قیمت را می‌گیرد
        """
        try:
            # دریافت BOM اصلی
            main_bom = frappe.get_doc("BOM", bom_name)
            
            # بررسی آیا این BOM پیمانکاری دارد (is_subcontracted)
            if not getattr(main_bom, 'is_subcontracted', False):
                return 0
            
            # دریافت service_item از BOM
            service_item = getattr(main_bom, 'service_item', None)
            
            if not service_item:
                frappe.logger().warning(f"   ⚠️ BOM {bom_name} پیمانکاری است ولی service_item ندارد")
                return 0
            
            # گرفتن قیمت service_item از آخرین فاکتور خرید
            service_price = self.get_service_item_price_from_purchase(service_item)
            
            if service_price > 0:
                frappe.logger("pricing").debug(f"      🔨 پیمانکاری {operation_name}: service_item={service_item}, قیمت={service_price:,.0f}")
                return service_price
            
            # اگر در فاکتور خرید نبود، از قیمت استاندارد استفاده کن
            standard_price = frappe.db.get_value("Item", service_item, "standard_rate") or 0
            if standard_price > 0:
                frappe.logger("pricing").debug(f"      🔨 پیمانکاری {operation_name}: service_item={service_item}, قیمت استاندارد={standard_price:,.0f}")
                return standard_price
            
            frappe.logger().warning(f"   ⚠️ قیمتی برای service_item {service_item} پیدا نشد")
            return 0
            
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در محاسبه هزینه پیمانکاری {operation_name}: {str(e)}")
            import traceback
            frappe.logger("pricing").debug(traceback.format_exc())
            return 0
    
    def get_service_item_price_from_purchase(self, service_item):
        """
        دریافت قیمت Service Item از آخرین فاکتور خرید یا سفارش خرید
        """
        try:
            # روش 1: از Purchase Receipt (فاکتور خرید تأیید شده)
            last_pr_rate = frappe.db.sql("""
                SELECT pri.rate
                FROM `tabPurchase Receipt Item` pri
                INNER JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent
                WHERE pri.item_code = %s 
                    AND pr.docstatus = 1
                ORDER BY pr.posting_date DESC, pr.posting_time DESC
                LIMIT 1
            """, (service_item,))
            
            if last_pr_rate and last_pr_rate[0][0] > 0:
                frappe.logger("pricing").debug(f"         📦 قیمت از آخرین فاکتور خرید: {last_pr_rate[0][0]:,.0f}")
                return flt(last_pr_rate[0][0])
            
            # روش 2: از Purchase Order (سفارش خرید تأیید شده)
            last_po_rate = frappe.db.sql("""
                SELECT poi.rate
                FROM `tabPurchase Order Item` poi
                INNER JOIN `tabPurchase Order` po ON po.name = poi.parent
                WHERE poi.item_code = %s 
                    AND po.docstatus = 1
                ORDER BY po.transaction_date DESC, po.creation DESC
                LIMIT 1
            """, (service_item,))
            
            if last_po_rate and last_po_rate[0][0] > 0:
                frappe.logger("pricing").debug(f"         📋 قیمت از آخرین سفارش خرید: {last_po_rate[0][0]:,.0f}")
                return flt(last_po_rate[0][0])
            
            # روش 3: از Purchase Invoice
            last_pi_rate = frappe.db.sql("""
                SELECT pii.rate
                FROM `tabPurchase Invoice Item` pii
                INNER JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
                WHERE pii.item_code = %s 
                    AND pi.docstatus = 1
                ORDER BY pi.posting_date DESC, pi.posting_time DESC
                LIMIT 1
            """, (service_item,))
            
            if last_pi_rate and last_pi_rate[0][0] > 0:
                frappe.logger("pricing").debug(f"         🧾 قیمت از آخرین فاکتور خرید: {last_pi_rate[0][0]:,.0f}")
                return flt(last_pi_rate[0][0])
            
            frappe.logger().warning(f"   ⚠️ هیچ سابقه خریدی برای {service_item} پیدا نشد")
            return 0
            
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در دریافت قیمت service item {service_item}: {str(e)}")
            return 0

    # اصلاحات مهم برای حل مشکل محاسبات تکراری

    # 1. تصحیح محاسبه total_cost - فقط 3 جزء اصلی
    def calculate_correct_total_cost(item):
        """
        محاسبه صحیح total_cost - فقط شامل 3 جزء اصلی
        """
        # توجه: operation_cost خودش شامل تمام هزینه‌های عملیاتی است
        # نباید جزئیات را دوباره اضافه کنیم
        total_cost = (
            flt(item.raw_material_cost or 0) +  # هزینه مواد اولیه
            flt(item.operation_cost or 0) +      # مجموع هزینه‌های عملیاتی
            flt(item.overhead_cost or 0)          # هزینه سربار
        )
        return total_cost

    def calculate_operation_cost(self, item, force_recalculate=False):
        """
        محاسبه هزینه عملیات
        operation_cost = labor_cost + subcontracting_cost
        overhead (محاسبه شده جداگانه) = electricity_cost + rent_cost + consumable_cost
        """
        if not item.item_code:
            item.operation_cost = 0
            item.electricity_cost = 0
            item.rent_cost = 0
            item.labor_cost = 0
            item.consumable_cost = 0
            item.subcontracting_cost = 0
            return
        
        # جلوگیری از محاسبه تکراری
        if not force_recalculate and hasattr(item, '_operation_calculated') and item._operation_calculated:
            return
        
        # محاسبه هزینه‌های عملیاتی از BOM
        operation_costs = self.calculate_nested_operation_cost(item.item_code)
        
        item.electricity_cost = flt(operation_costs.get('electricity_cost', 0))
        item.rent_cost = flt(operation_costs.get('rent_cost', 0))
        item.labor_cost = flt(operation_costs.get('labor_cost', 0))
        item.consumable_cost = flt(operation_costs.get('consumable_cost', 0))
        item.subcontracting_cost = flt(operation_costs.get('subcontracting_cost', 0))
        
        # operation_cost = فقط کارگر + پیمانکاری
        item.operation_cost = flt(item.labor_cost) + flt(item.subcontracting_cost)
        
        item._operation_calculated = True

    # 3. اصلاح calculate_full_costing
    @frappe.whitelist()
    def calculate_full_costing(self):
        """
        محاسبه بهای تمام شده - Async با Background Job
        """
        try:
            if not self.items:
                return {
                    "success": False,
                    "message": "هیچ آیتمی برای محاسبه وجود ندارد"
                }
            
            # اگر تعداد آیتم‌ها بیشتر از 20 بود، از background job استفاده کن
            if len(self.items) > 20:
                frappe.enqueue(
                    'pricing.pricing.doctype.auto_price_list.auto_price_list.calculate_full_costing_background',
                    docname=self.name,
                    queue='long',
                    timeout=3600,  # 1 ساعت
                    is_async=True,
                    now=False
                )
                return {
                    "success": True,
                    "message": f"محاسبه بهای تمام شده برای {len(self.items)} محصول در پس‌زمینه آغاز شد...",
                    "background": True
                }
            
            # برای تعداد کم، محاسبه مستقیم
            return self._calculate_full_costing_sync()
            
        except Exception as e:
            frappe.db.rollback()
            error_msg = f"خطا در محاسبه بهای تمام شده: {str(e)}"
            frappe.logger("pricing").debug(error_msg)
            import traceback
            frappe.logger("pricing").debug(traceback.format_exc())
            return {
                "success": False,
                "message": error_msg
            }
    
    def _calculate_full_costing_sync(self):
        """
        محاسبه همزمان بهای تمام شده (برای تعداد کم)
        استفاده از get_comprehensive_cost_breakdown برای دقت بالا
        دقیقاً مطابق با گزارش جامع هزینه
        """
        try:
            updated_items = 0
            errors = []
            
            for item in self.items:
                if not item.item_code:
                    continue
                
                try:
                    # چک کردن قیمت‌های دستی محصول
                    manual_costs = self._get_manual_item_price(item.item_code)
                    
                    # پیدا کردن BOM
                    bom_name = frappe.db.get_value("BOM", {
                        "item": item.item_code,
                        "is_active": 1,
                        "is_default": 1
                    }, "name")
                    
                    if bom_name:
                        # استفاده از محاسبه جامع (دقیقاً مثل گزارش)
                        breakdown = self.get_comprehensive_cost_breakdown(item.item_code, bom_name)
                        
                        # 1. هزینه مواد اولیه از exploded_items
                        if manual_costs and manual_costs.get('raw_material_cost') is not None:
                            item.raw_material_cost = manual_costs['raw_material_cost']
                        else:
                            item.raw_material_cost = flt(breakdown.get('raw_material_cost', 0))
                        
                        # 2. هزینه‌های عملیاتی (از تمام سطوح BOM)
                        op_costs = breakdown.get('total_operation_costs', {})
                        
                        item.electricity_cost = flt(op_costs.get('electricity_cost', 0))
                        item.rent_cost = flt(op_costs.get('rent_cost', 0))
                        item.labor_cost = flt(op_costs.get('labor_cost', 0))
                        item.consumable_cost = flt(op_costs.get('consumable_cost', 0))
                        item.subcontracting_cost = flt(op_costs.get('subcontracting_cost', 0))
                        
                        # Override با قیمت‌های دستی
                        if manual_costs:
                            if manual_costs.get('labor_cost') is not None:
                                item.labor_cost = manual_costs['labor_cost']
                            if manual_costs.get('subcontracting_cost') is not None:
                                item.subcontracting_cost = manual_costs['subcontracting_cost']
                            if manual_costs.get('electricity_cost') is not None:
                                item.electricity_cost = manual_costs['electricity_cost']
                            if manual_costs.get('rent_cost') is not None:
                                item.rent_cost = manual_costs['rent_cost']
                            if manual_costs.get('consumable_cost') is not None:
                                item.consumable_cost = manual_costs['consumable_cost']
                        
                        # محاسبه operation_cost
                        if manual_costs and manual_costs.get('operation_cost') is not None:
                            item.operation_cost = manual_costs['operation_cost']
                        else:
                            item.operation_cost = flt(item.labor_cost) + flt(item.subcontracting_cost)
                        
                        # 3. هزینه سربار
                        if manual_costs and manual_costs.get('overhead_cost') is not None:
                            item.overhead_cost = manual_costs['overhead_cost']
                        else:
                            item.overhead_cost = flt(breakdown.get('overhead_cost', 0))
                        
                    else:
                        # بدون BOM - صفر کردن مقادیر
                        item.raw_material_cost = 0
                        item.electricity_cost = 0
                        item.rent_cost = 0
                        item.labor_cost = 0
                        item.consumable_cost = 0
                        item.subcontracting_cost = 0
                        item.operation_cost = 0
                        item.overhead_cost = 0
                    
                    # 4. محاسبه total_cost
                    item.total_cost = (
                        flt(item.raw_material_cost) +
                        flt(item.operation_cost) +
                        flt(item.overhead_cost)
                    )
                    
                    updated_items += 1
                    
                except Exception as item_error:
                    errors.append(f"{item.item_code}: {str(item_error)}")
                    continue
            
            # ذخیره با batch processing
            self._save_items_batch(self.items)
            
            message = f"✅ بهای تمام شده برای {updated_items} آیتم محاسبه شد"
            if errors:
                message += f"\n⚠️ {len(errors)} خطا: {', '.join(errors[:3])}"
            
            return {
                "success": True,
                "message": message,
                "updated_items": updated_items,
                "errors": errors
            }
                
        except Exception as e:
            import traceback
            self._log_debug(f"خطا در محاسبه: {str(e)}\n{traceback.format_exc()}", level='error')
            frappe.db.rollback()
            return {
                "success": False,
                "message": f"خطا: {str(e)}"
            }

    def _save_items_batch(self, items):
        """
        ذخیره دسته‌ای آیتم‌ها به صورت bulk برای جلوگیری از timeout
        بهینه‌سازی شده - بدون لاگ‌های تکراری
        """
        try:
            # آماده‌سازی داده‌ها برای bulk update
            update_data = []
            for item in items:
                if not item.item_code or not item.name:
                    continue
                
                # تصحیح خودکار قبل از ذخیره
                expected_operation = flt(item.labor_cost or 0) + flt(item.subcontracting_cost or 0)
                if abs(flt(item.operation_cost) - expected_operation) > 1:
                    item.operation_cost = expected_operation
                
                update_data.append({
                    'name': item.name,
                    'raw_material_cost': flt(item.raw_material_cost or 0),
                    'operation_cost': flt(item.operation_cost or 0),
                    'overhead_cost': flt(item.overhead_cost or 0),
                    'total_cost': flt(item.total_cost or 0),
                    'electricity_cost': flt(item.electricity_cost or 0),
                    'rent_cost': flt(item.rent_cost or 0),
                    'labor_cost': flt(item.labor_cost or 0),
                    'consumable_cost': flt(item.consumable_cost or 0),
                    'subcontracting_cost': flt(item.subcontracting_cost or 0),
                    'selling_price': flt(item.selling_price or 0),
                    'final_selected_price': flt(item.final_selected_price or 0),
                    'profit_amount': flt(item.profit_amount or 0)
                })
            
            # bulk update با یک کوئری
            for data in update_data:
                frappe.db.sql("""
                    UPDATE `tabAuto Price List Item`
                    SET 
                        raw_material_cost = %(raw_material_cost)s,
                        operation_cost = %(operation_cost)s,
                        overhead_cost = %(overhead_cost)s,
                        total_cost = %(total_cost)s,
                        electricity_cost = %(electricity_cost)s,
                        rent_cost = %(rent_cost)s,
                        labor_cost = %(labor_cost)s,
                        consumable_cost = %(consumable_cost)s,
                        subcontracting_cost = %(subcontracting_cost)s,
                        selling_price = %(selling_price)s,
                        final_selected_price = %(final_selected_price)s,
                        profit_amount = %(profit_amount)s,
                        modified = NOW()
                    WHERE name = %(name)s
                """, data)
            
            # به‌روزرسانی modified سند والد
            if self.name:
                frappe.db.sql("""
                    UPDATE `tabAuto Price List`
                    SET modified = NOW(), modified_by = %s
                    WHERE name = %s
                """, (frappe.session.user, self.name))
            
            frappe.db.commit()
            
        except Exception as e:
            self._log_debug(f"خطا در ذخیره batch: {str(e)}")
            frappe.db.rollback()
            raise

    @frappe.whitelist()
    def calculate_full_costing_ultra_fast(self):
        """
        🚀 محاسبه سریع بهای تمام شده (با progress bar)
        استفاده از همان روش get_comprehensive_cost_breakdown برای نتایج یکسان
        برای تعداد زیاد آیتم‌ها از background job استفاده میشه
        """
        import time
        start_time = time.time()
        
        try:
            if not self.items:
                return {
                    "success": False,
                    "message": "هیچ آیتمی برای محاسبه وجود ندارد"
                }
            
            items_count = len(self.items)
            
            # برای تعداد زیاد از background job استفاده کن
            if items_count > 200:
                frappe.enqueue(
                    'pricing.pricing.doctype.auto_price_list.auto_price_list.run_full_costing_background',
                    queue='long',
                    timeout=1800,  # 30 دقیقه
                    docname=self.name,
                    job_name=f"Full Costing {self.name}",
                )
                return {
                    "success": True,
                    "background": True,
                    "message": f"⏳ محاسبه {items_count} محصول در پس‌زمینه شروع شد. لطفاً صبر کنید..."
                }
            
            frappe.publish_realtime('costing_progress', {
                'progress': 5,
                'message': f'شروع محاسبه برای {items_count} محصول...'
            }, user=frappe.session.user)
            
            # مرحله 1: جمع‌آوری همه item_codes و BOMs
            item_codes = [item.item_code for item in self.items if item.item_code]
            bom_map = self._bulk_load_all_boms(item_codes)
            
            frappe.publish_realtime('costing_progress', {
                'progress': 15,
                'message': f'BOMs بارگذاری شد ({len(bom_map)} مورد)'
            }, user=frappe.session.user)
            
            # مرحله 2: محاسبه برای هر آیتم
            updated_count = 0
            errors = []
            
            for idx, item in enumerate(self.items):
                if not item.item_code:
                    continue
                
                try:
                    # چک کردن قیمت‌های دستی محصول
                    manual_costs = self._get_manual_item_price(item.item_code)
                    
                    # پیدا کردن BOM
                    bom_info = bom_map.get(item.item_code)
                    bom_name = bom_info['name'] if bom_info else None
                    
                    if not bom_name:
                        # بدون BOM
                        item.raw_material_cost = 0
                        item.electricity_cost = 0
                        item.rent_cost = 0
                        item.labor_cost = 0
                        item.consumable_cost = 0
                        item.subcontracting_cost = 0
                        item.operation_cost = 0
                        item.overhead_cost = 0
                        item.total_cost = 0
                        continue
                    
                    # استفاده از محاسبه جامع (دقیقاً مثل روش اصلی)
                    breakdown = self.get_comprehensive_cost_breakdown(item.item_code, bom_name)
                    
                    # 1. هزینه مواد اولیه
                    if manual_costs and manual_costs.get('raw_material_cost') is not None:
                        item.raw_material_cost = manual_costs['raw_material_cost']
                    else:
                        item.raw_material_cost = flt(breakdown.get('raw_material_cost', 0))
                    
                    # 2. هزینه‌های عملیاتی
                    op_costs = breakdown.get('total_operation_costs', {})
                    
                    item.electricity_cost = flt(op_costs.get('electricity_cost', 0))
                    item.rent_cost = flt(op_costs.get('rent_cost', 0))
                    item.labor_cost = flt(op_costs.get('labor_cost', 0))
                    item.consumable_cost = flt(op_costs.get('consumable_cost', 0))
                    item.subcontracting_cost = flt(op_costs.get('subcontracting_cost', 0))
                    
                    # Override با قیمت‌های دستی
                    if manual_costs:
                        if manual_costs.get('labor_cost') is not None:
                            item.labor_cost = manual_costs['labor_cost']
                        if manual_costs.get('subcontracting_cost') is not None:
                            item.subcontracting_cost = manual_costs['subcontracting_cost']
                        if manual_costs.get('electricity_cost') is not None:
                            item.electricity_cost = manual_costs['electricity_cost']
                        if manual_costs.get('rent_cost') is not None:
                            item.rent_cost = manual_costs['rent_cost']
                        if manual_costs.get('consumable_cost') is not None:
                            item.consumable_cost = manual_costs['consumable_cost']
                    
                    # محاسبه operation_cost
                    if manual_costs and manual_costs.get('operation_cost') is not None:
                        item.operation_cost = manual_costs['operation_cost']
                    else:
                        item.operation_cost = flt(item.labor_cost) + flt(item.subcontracting_cost)
                    
                    # 3. هزینه سربار
                    if manual_costs and manual_costs.get('overhead_cost') is not None:
                        item.overhead_cost = manual_costs['overhead_cost']
                    else:
                        item.overhead_cost = flt(breakdown.get('overhead_cost', 0))
                    
                    # 4. محاسبه total_cost
                    item.total_cost = (
                        flt(item.raw_material_cost) +
                        flt(item.operation_cost) +
                        flt(item.overhead_cost)
                    )
                    
                    # 5. محاسبه قیمت فروش
                    if item.total_cost > 0:
                        if self.pricing_steps:
                            final_price, _ = self.calculate_price_based_on_steps_fast(item, item.total_cost)
                            item.final_selected_price = final_price
                            item.selling_price = final_price
                        else:
                            profit_margin = flt(self.profit_margin or 0)
                            item.final_selected_price = item.total_cost * (1 + profit_margin / 100)
                            item.selling_price = item.final_selected_price
                        
                        item.profit_amount = flt(item.selling_price) - flt(item.total_cost)
                    
                    updated_count += 1
                    
                except Exception as e:
                    errors.append(f"{item.item_code}: {str(e)}")
                
                # گزارش پیشرفت هر 10 آیتم
                if (idx + 1) % 10 == 0 or idx == items_count - 1:
                    progress = 15 + int((idx + 1) / items_count * 75)
                    frappe.publish_realtime('costing_progress', {
                        'progress': progress,
                        'message': f'محاسبه شد: {idx + 1}/{items_count}'
                    }, user=frappe.session.user)
            
            frappe.publish_realtime('costing_progress', {
                'progress': 92,
                'message': 'ذخیره نتایج...'
            }, user=frappe.session.user)
            
            # ذخیره batch
            self._save_items_batch(self.items)
            
            elapsed_time = time.time() - start_time
            
            frappe.publish_realtime('costing_progress', {
                'progress': 100,
                'message': f'✅ کامل شد در {elapsed_time:.1f} ثانیه'
            }, user=frappe.session.user)
            
            message = f"✅ بهای تمام شده برای {updated_count} محصول در {elapsed_time:.1f} ثانیه محاسبه شد"
            if errors:
                message += f"\n⚠️ {len(errors)} خطا"
            
            return {
                "success": True,
                "message": message,
                "updated_items": updated_count,
                "elapsed_time": elapsed_time,
                "errors": errors[:5] if errors else []
            }
            

        except Exception as e:
            import traceback
            frappe.logger("pricing").error(f"خطا در محاسبه سریع: {str(e)}\n{traceback.format_exc()}")
            frappe.db.rollback()
            return {
                "success": False,
                "message": f"خطا: {str(e)}"
            }

    def _bulk_load_all_boms(self, item_codes):
        """Load همه BOMs با یک query"""
        if not item_codes:
            return {}
        
        boms = frappe.db.sql("""
            SELECT name, item, raw_material_cost, operating_cost, total_cost
            FROM `tabBOM`
            WHERE item IN %(item_codes)s
              AND is_active = 1
              AND is_default = 1
        """, {"item_codes": item_codes}, as_dict=True)
        
        return {bom['item']: bom for bom in boms}

    def _bulk_load_bom_items(self, bom_names):
        """Load همه BOM Items با یک query"""
        if not bom_names:
            return {}
        
        items = frappe.db.sql("""
            SELECT parent, item_code, qty, rate, amount
            FROM `tabBOM Item`
            WHERE parent IN %(bom_names)s
        """, {"bom_names": bom_names}, as_dict=True)
        
        result = defaultdict(list)
        for item in items:
            result[item['parent']].append(item)
        return dict(result)

    def _bulk_load_exploded_items(self, bom_names):
        """Load همه Exploded Items با یک query"""
        if not bom_names:
            return {}
        
        items = frappe.db.sql("""
            SELECT parent, item_code, qty_consumed_per_unit, rate, amount
            FROM `tabBOM Explosion Item`
            WHERE parent IN %(bom_names)s
        """, {"bom_names": bom_names}, as_dict=True)
        
        result = defaultdict(list)
        for item in items:
            result[item['parent']].append(item)
        return dict(result)

    def _bulk_load_bom_operations(self, bom_names):
        """Load همه عملیات BOM با یک query"""
        if not bom_names:
            return {}
        
        operations = frappe.db.sql("""
            SELECT bo.parent, bo.workstation, bo.time_in_mins, bo.operating_cost,
                   bo.hour_rate, bo.description,
                   w.name as ws_name, w.hour_rate as ws_hour_rate,
                   w.hour_rate_electricity as ws_electricity, 
                   w.hour_rate_rent as ws_rent,
                   w.hour_rate_consumable as ws_consumable,
                   w.hour_rate_labour as ws_labour
            FROM `tabBOM Operation` bo
            LEFT JOIN `tabWorkstation` w ON bo.workstation = w.name
            WHERE bo.parent IN %(bom_names)s
        """, {"bom_names": bom_names}, as_dict=True)
        
        result = defaultdict(list)
        for op in operations:
            result[op['parent']].append(op)
        return dict(result)

    def _bulk_load_all_prices(self, item_codes):
        """Load همه قیمت‌ها با حداقل query"""
        if not item_codes:
            return {}
        
        price_map = {}
        
        # 1. قیمت از آخرین فاکتور خرید
        try:
            prices = frappe.db.sql("""
                SELECT item_code, rate
                FROM (
                    SELECT pi.item_code, pi.rate,
                           ROW_NUMBER() OVER (PARTITION BY pi.item_code ORDER BY p.posting_date DESC, p.creation DESC) as rn
                    FROM `tabPurchase Invoice Item` pi
                    INNER JOIN `tabPurchase Invoice` p ON pi.parent = p.name
                    WHERE pi.item_code IN %(item_codes)s
                      AND p.docstatus = 1
                ) sub
                WHERE rn = 1
            """, {"item_codes": item_codes}, as_dict=True)
            
            for p in prices:
                if p['rate'] and p['rate'] > 0:
                    price_map[p['item_code']] = flt(p['rate'])
        except:
            pass
        
        # 2. آیتم‌هایی که قیمت ندارند از Item
        missing = [ic for ic in item_codes if ic and ic not in price_map]
        if missing:
            items = frappe.get_all("Item",
                filters={"item_code": ["in", missing]},
                fields=["item_code", "valuation_rate", "standard_rate"]
            )
            for item in items:
                if item['item_code'] not in price_map:
                    rate = flt(item.get('valuation_rate')) or flt(item.get('standard_rate')) or 0
                    price_map[item['item_code']] = rate
        
        return price_map

    def _calculate_raw_material_cost_fast(self, bom_name, exploded_items, bom_items, price_map, manual_prices_map):
        """محاسبه سریع هزینه مواد اولیه"""
        total_cost = 0
        
        # اولویت با exploded items
        items_to_use = exploded_items if exploded_items else bom_items
        
        for item in items_to_use:
            item_code = item.get('item_code')
            if not item_code:
                continue
            
            qty = flt(item.get('qty_consumed_per_unit') or item.get('qty') or 0)
            
            # اولویت: قیمت دستی > قیمت از price_map > amount از BOM
            if item_code in manual_prices_map:
                rate = manual_prices_map[item_code]
            elif item_code in price_map:
                rate = price_map[item_code]
            else:
                rate = flt(item.get('rate') or 0)
            
            if rate > 0 and qty > 0:
                total_cost += rate * qty
            elif item.get('amount'):
                total_cost += flt(item.get('amount'))
        
        return total_cost

    def _calculate_operation_costs_fast(self, operations):
        """محاسبه سریع هزینه‌های عملیات"""
        result = {
            'labor_cost': 0,
            'subcontracting_cost': 0,
            'electricity_cost': 0,
            'consumable_cost': 0,
            'rent_cost': 0
        }
        
        for op in operations:
            time_hrs = flt(op.get('time_in_mins', 0)) / 60
            
            # هزینه کار - از hour_rate_labour یا hour_rate
            labour_rate = flt(op.get('ws_labour') or op.get('ws_hour_rate') or op.get('hour_rate') or 0)
            result['labor_cost'] += time_hrs * labour_rate
            
            # هزینه‌های workstation
            result['electricity_cost'] += flt(op.get('ws_electricity') or 0) * time_hrs
            result['rent_cost'] += flt(op.get('ws_rent') or 0) * time_hrs
            result['consumable_cost'] += flt(op.get('ws_consumable') or 0) * time_hrs
            
            # پیمانکاری (از operating_cost)
            if op.get('operating_cost'):
                result['subcontracting_cost'] += flt(op.get('operating_cost'))
        
        return result

    @frappe.whitelist()
    def get_item_cost_breakdown(self, item_code):
        """
        گزارش جامع جزئیات هزینه یک محصول - نمایش تمام سطوح BOM و عملیات
        """
        try:
            if not item_code:
                return {
                    "success": False,
                    "message": "کد محصول ارائه نشده است"
                }
            
            # پیدا کردن BOM فعال
            bom_name = frappe.db.get_value("BOM", {
                "item": item_code,
                "is_active": 1,
                "is_default": 1
            }, "name")
            
            if not bom_name:
                return {
                    "success": False,
                    "message": f"BOM فعالی برای محصول {item_code} وجود ندارد"
                }
            
            # دریافت اطلاعات محصول
            item_info = frappe.get_doc("Item", item_code)
            
            # دریافت جزئیات از BOM
            breakdown_result = self.get_comprehensive_cost_breakdown(item_code, bom_name, set())
            
            return {
                "success": True,
                "item_code": item_code,
                "item_name": item_info.item_name,
                "bom_name": bom_name,
                **breakdown_result
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"خطا در دریافت جزئیات هزینه {item_code}: {str(e)}",
                "error": str(e)
            }

    def get_comprehensive_cost_breakdown(self, item_code, bom_name, processed_boms=None, level=0):
        """
        محاسبه جامع هزینه‌ها از تمام سطوح BOM با استفاده از exploded_items و operations
        بهینه‌سازی شده با batch queries
        """
        if processed_boms is None:
            processed_boms = set()
        
        processed_boms.add(bom_name)
        
        try:
            bom_doc = frappe.get_doc("BOM", bom_name)
            
            # 1. محاسبه هزینه مواد اولیه و جزئیات آنها
            raw_material_cost = 0
            raw_materials_breakdown = []
            
            # دریافت exploded_items
            exploded_items = bom_doc.exploded_items if hasattr(bom_doc, 'exploded_items') else []
            
            # اگر exploded_items خالی است، از BOM Items استفاده کن
            if not exploded_items and hasattr(bom_doc, 'items') and bom_doc.items:
                # ساخت لیست از BOM Items
                exploded_items = []
                for bom_item in bom_doc.items:
                    class ExplodedItemStub:
                        def __init__(self, data):
                            self.item_code = data['item_code']
                            self.qty_consumed_per_unit = data['qty']
                            self.stock_qty = data['stock_qty']
                            self.qty = data['qty']
                    
                    exploded_items.append(ExplodedItemStub({
                        'item_code': bom_item.item_code,
                        'qty': bom_item.qty or bom_item.stock_qty or 0,
                        'stock_qty': bom_item.stock_qty or bom_item.qty or 0
                    }))
            
            if exploded_items:
                # ایجاد cache از قیمت‌های دستی
                manual_price_map = {}
                if self.manual_material_prices:
                    for mp in self.manual_material_prices:
                        if mp.item_code and mp.manual_price:
                            manual_price_map[mp.item_code] = flt(mp.manual_price)
                
                # جمع‌آوری همه کدهای مواد برای batch query
                all_item_codes = [getattr(ei, 'item_code', None) for ei in exploded_items if getattr(ei, 'item_code', None)]
                
                # batch query برای قیمت‌ها (فقط آیتم‌هایی که قیمت دستی ندارند)
                items_needing_price = [ic for ic in all_item_codes if ic not in manual_price_map]
                item_price_map = {}
                
                if items_needing_price and self.price_list:
                    # دریافت قیمت‌ها با یک query
                    prices = frappe.db.sql("""
                        SELECT item_code, price_list_rate 
                        FROM `tabItem Price`
                        WHERE item_code IN %(items)s AND price_list = %(price_list)s
                    """, {"items": items_needing_price, "price_list": self.price_list}, as_dict=True)
                    
                    for p in prices:
                        item_price_map[p.item_code] = flt(p.price_list_rate)
                    
                    # fallback برای آیتم‌هایی که در price list نیستند
                    missing_items = [ic for ic in items_needing_price if ic not in item_price_map]
                    if missing_items:
                        fallback_prices = frappe.db.sql("""
                            SELECT item_code, price_list_rate 
                            FROM `tabItem Price`
                            WHERE item_code IN %(items)s
                            ORDER BY modified DESC
                        """, {"items": missing_items}, as_dict=True)
                        
                        for p in fallback_prices:
                            if p.item_code not in item_price_map:
                                item_price_map[p.item_code] = flt(p.price_list_rate)
                
                # batch query برای اطلاعات آیتم‌ها
                item_info_map = {}
                if all_item_codes:
                    item_infos = frappe.get_all("Item",
                        filters={"item_code": ["in", all_item_codes]},
                        fields=["item_code", "item_name", "stock_uom"]
                    )
                    for info in item_infos:
                        item_info_map[info.item_code] = info
                
                # محاسبه هزینه هر ماده
                for exploded_item in exploded_items:
                    item_code_rm = getattr(exploded_item, 'item_code', None)
                    if not item_code_rm:
                        continue
                    
                    qty = flt(getattr(exploded_item, 'qty_consumed_per_unit', None) or 
                             getattr(exploded_item, 'stock_qty', None) or 
                             getattr(exploded_item, 'qty', 0))
                    
                    # اولویت 1: قیمت دستی
                    if item_code_rm in manual_price_map:
                        unit_price = manual_price_map[item_code_rm]
                        price_source = "قیمت دستی"
                    # اولویت 2: Item Price
                    elif item_code_rm in item_price_map:
                        unit_price = item_price_map[item_code_rm]
                        price_source = "Item Price"
                    else:
                        unit_price = 0
                        price_source = "بدون قیمت"
                    
                    total_price = unit_price * qty
                    raw_material_cost += total_price
                    
                    # دریافت اطلاعات Item از cache
                    item_info = item_info_map.get(item_code_rm, {})
                    item_name_rm = item_info.get('item_name') or item_code_rm
                    uom = item_info.get('stock_uom') or ""
                    
                    raw_materials_breakdown.append({
                        "item_code": item_code_rm,
                        "item_name": item_name_rm,
                        "qty": qty,
                        "uom": uom,
                        "unit_price": unit_price,
                        "total_price": total_price,
                        "price_source": price_source
                    })
            
            # 2. جمع‌آوری تمام operations از تمام سطوح
            all_operations = []
            
            try:
                all_operations = self.collect_all_operations_from_bom_tree(bom_name, set(), 0)
            except Exception:
                all_operations = []
            
            # استفاده از operating_cost موجود در BOM اگر operations خالی است
            if not all_operations and bom_doc.operating_cost and bom_doc.operating_cost > 0:
                all_operations = [{
                    'operation': 'عملیات کلی از BOM',
                    'time_in_mins': 0,
                    'workstation': 'محاسبه شده از BOM',
                    'hour_rate': 0,
                    'description': 'محاسبه شده از operating_cost موجود در BOM',
                    'bom_name': bom_name,
                    'level': 0,
                    'qty_factor': 1,
                    'total_cost': flt(bom_doc.operating_cost or 0)
                }]
            
            # 3. محاسبه هزینه‌های عملیاتی
            operations_breakdown = []
            total_operation_costs = {
                'electricity_cost': 0,
                'rent_cost': 0,
                'labor_cost': 0,
                'consumable_cost': 0,
                'subcontracting_cost': 0
            }
            
            for i, op_info in enumerate(all_operations):
                # اگر operation از operating_cost موجود ساخته شده، هزینه را مستقیم استفاده کن
                if op_info.get('total_cost'):
                    operation_costs = {
                        'electricity_cost': 0,
                        'rent_cost': 0, 
                        'labor_cost': op_info['total_cost'],
                        'consumable_cost': 0,
                        'subcontracting_cost': 0
                    }
                    
                    time_mins = op_info['time_in_mins']
                    operation_breakdown = {
                        'operation': op_info['operation'],
                        'time_in_mins': time_mins,
                        'time_in_hours': time_mins / 60,
                        'workstation': op_info['workstation'],
                        'description': op_info.get('description', ''),
                        'level': op_info.get('level', 0),
                        'bom_name': op_info.get('bom_name', bom_name),
                        'qty_factor': op_info.get('qty_factor', 1),
                        'costs': operation_costs,
                        'workstation_rates': {}
                    }
                else:
                    # محاسبه هزینه‌های جزئی این operation
                    operation_detail = self.calculate_operation_detail_cost(op_info)
                    operation_costs = operation_detail.get('costs', {})
                    time_mins = operation_detail.get('time_in_mins', op_info.get('time_in_mins', 0))
                    
                    operation_breakdown = {
                        'operation': operation_detail.get('operation', op_info.get('operation', '')),
                        'time_in_mins': time_mins,
                        'time_in_hours': time_mins / 60,
                        'workstation': operation_detail.get('workstation', op_info.get('workstation', '')),
                        'description': operation_detail.get('description', op_info.get('description', '')),
                        'level': operation_detail.get('level', op_info.get('level', 0)),
                        'bom_name': operation_detail.get('bom_name', op_info.get('bom_name', bom_name)),
                        'qty_factor': operation_detail.get('qty_factor', op_info.get('qty_factor', 1)),
                        'costs': operation_costs,
                        'workstation_rates': operation_detail.get('workstation_rates', {})
                    }
                
                operations_breakdown.append(operation_breakdown)
                
                # جمع هزینه‌ها
                for cost_type in total_operation_costs:
                    if cost_type in operation_costs:
                        total_operation_costs[cost_type] += flt(operation_costs[cost_type] or 0)
            
            # 4. محاسبه هزینه سربار از هزینه‌های عملیاتی
            # سربار = برق + اجاره + مصرفی (از operations)
            overhead_cost = (
                flt(total_operation_costs.get('electricity_cost', 0)) +
                flt(total_operation_costs.get('rent_cost', 0)) +
                flt(total_operation_costs.get('consumable_cost', 0))
            )
            
            # هزینه عملیات = کارگر + پیمانکاری
            operation_cost = (
                flt(total_operation_costs.get('labor_cost', 0)) +
                flt(total_operation_costs.get('subcontracting_cost', 0))
            )
            
            # 5. ساختار سطوح BOM
            bom_levels = self.build_bom_level_structure(bom_name, processed_boms.copy())
            
            total_cost = raw_material_cost + operation_cost + overhead_cost
            
            return {
                "raw_material_cost": raw_material_cost,
                "raw_materials_breakdown": raw_materials_breakdown,
                "operations_breakdown": operations_breakdown,
                "total_operation_costs": total_operation_costs,
                "total_operation_cost": operation_cost,  # کارگر + پیمانکاری
                "overhead_cost": overhead_cost,  # برق + اجاره + مصرفی
                "total_cost": total_cost,
                "bom_levels": bom_levels
            }
            
        except Exception as e:
            # فقط در صورت خطا لاگ کن
            frappe.log_error(
                title=f"خطا در get_comprehensive_cost_breakdown - {bom_name}",
                message=f"Item: {item_code}, خطا: {str(e)}"
            )
            return {
                "raw_material_cost": 0,
                "raw_materials_breakdown": [],
                "operations_breakdown": [],
                "total_operation_costs": {},
                "total_operation_cost": 0,
                "overhead_cost": 0,
                "total_cost": 0,
                "bom_levels": []
            }

    @frappe.whitelist()
    def fetch_prev_price_list_items(self, prev_price_list=None):
        """
        Fetch items from a previous Price List that have a non-zero price
        and are NOT present in the Item master table (per user request).
        Returns list of {item_code, price_list_rate}
        """
        try:
            price_list_name = prev_price_list or self.compare_previous_price_list
            if not price_list_name:
                return {"items": []}

            # Get all item prices for that price list where rate > 0
            rows = frappe.get_all("Item Price", filters={
                "price_list": price_list_name,
                "price_list_rate": [">", 0]
            }, fields=["item_code", "price_list_rate"]) or []

            # Collect item_codes already in this document's items table
            existing_item_codes = set(item.item_code for item in self.items if item.item_code)

            results = []
            for r in rows:
                if r.item_code not in existing_item_codes:
                    results.append({
                        "item_code": r.item_code,
                        "price_list_rate": flt(r.price_list_rate)
                    })

            return {"items": results}
        except Exception as e:
            frappe.log_error(message=str(e), title="fetch_prev_price_list_items error")
            return {"items": []}

    @frappe.whitelist()
    def apply_prev_prices_to_price_list(self, to_apply=None, target_price_list=None):
        """
        Apply given [{item_code, price}] to the target Price List by creating/updating Item Price rows.
        to_apply: list of dicts
        """
        try:
            if isinstance(to_apply, str):
                to_apply = json.loads(to_apply)

            target = target_price_list or self.price_list
            if not target:
                return {"success": False, "message": "قصد اهدافی برای لیست قیمت مشخص نشده است"}

            created = 0
            updated = 0
            for entry in to_apply:
                item_code = entry.get('item_code')
                price = flt(entry.get('price') or 0)
                if not item_code or price <= 0:
                    continue

                # Check if Item Price exists
                ip_name = frappe.db.get_value('Item Price', {
                    'item_code': item_code,
                    'price_list': target
                }, 'name')

                if ip_name:
                    # update
                    frappe.db.set_value('Item Price', ip_name, 'price_list_rate', price)
                    updated += 1
                else:
                    # create
                    ip = frappe.get_doc({
                        'doctype': 'Item Price',
                        'item_code': item_code,
                        'price_list': target,
                        'price_list_rate': price,
                        'currency': frappe.db.get_value('Price List', target, 'currency') or 'IRR'
                    })
                    ip.insert(ignore_permissions=True)
                    created += 1

            frappe.db.commit()
            return {"success": True, "message": f"{created} رکورد ایجاد و {updated} رکورد به‌روز شد"}
        except Exception as e:
            frappe.log_error(message=str(e), title="apply_prev_prices_to_price_list error")
            frappe.db.rollback()
            return {"success": False, "message": str(e)}

    def _recalculate_existing_bundles(self):
        """
        به‌روزرسانی قیمت‌های بسته‌های موجود بدون reload کامل
        """
        if not self.product_bundles:
            return
        
        for bundle_row in self.product_bundles:
            bundle_name = bundle_row.product_bundle
            
            # دریافت آیتم‌های داخل بسته
            bundle_items = frappe.get_all("Product Bundle Item",
                filters={"parent": bundle_name},
                fields=["item_code", "qty"]
            )
            
            if not bundle_items:
                continue
            
            # محاسبه مجدد قیمت‌ها
            total_cost = 0
            total_selling_price = 0
            total_raw_material = 0
            total_operation = 0
            total_electricity = 0
            total_consumable = 0
            total_rent = 0
            total_labor = 0
            total_subcontracting = 0
            total_overhead = 0
            
            for item in bundle_items:
                item_code = item.item_code
                qty = flt(item.qty or 1)
                
                # دریافت قیمت فروش و هزینه‌ها
                item_selling_price = self.get_item_selling_price(item_code)
                cost_details = self.get_item_cost_details(item_code)
                
                # محاسبه مجموع
                item_total_cost = cost_details["total_cost"] * qty
                item_total_selling = item_selling_price * qty
                
                total_cost += item_total_cost
                total_selling_price += item_total_selling
                total_raw_material += cost_details["raw_material_cost"] * qty
                total_operation += cost_details["operation_cost"] * qty
                total_electricity += cost_details["electricity_cost"] * qty
                total_consumable += cost_details["consumable_cost"] * qty
                total_rent += cost_details["rent_cost"] * qty
                total_labor += cost_details["labor_cost"] * qty
                total_subcontracting += cost_details["subcontracting_cost"] * qty
                total_overhead += cost_details["overhead_cost"] * qty
            
            # به‌روزرسانی فیلدهای bundle
            bundle_row.total_cost = total_cost
            bundle_row.selling_price = total_selling_price
            bundle_row.raw_material_cost = total_raw_material
            bundle_row.operation_cost = total_operation
            bundle_row.electricity_cost = total_electricity
            bundle_row.consumable_cost = total_consumable
            bundle_row.rent_cost = total_rent
            bundle_row.labor_cost = total_labor
            bundle_row.subcontracting_cost = total_subcontracting
            bundle_row.overhead_cost = total_overhead
            
            # محاسبه سود
            profit_amount = total_selling_price - total_cost
            bundle_row.profit_amount = profit_amount
            bundle_row.profit_percentage = (profit_amount / total_cost * 100) if total_cost > 0 else 0

            # ساخت لیست آیتم‌ها برای تولید HTML
            bundle_items_list = []
            for item in bundle_items:
                item_code = item.item_code
                qty = flt(item.qty or 1)
                item_selling_price = self.get_item_selling_price(item_code)
                cost_details = self.get_item_cost_details(item_code)
                item_unit_cost = cost_details["total_cost"]
                item_total_cost = item_unit_cost * qty
                item_total_selling = item_selling_price * qty
                item_name = frappe.db.get_value("Item", item_code, "item_name") or item_code
                
                bundle_items_list.append({
                    "item_code": item_code,
                    "item_name": item_name,
                    "qty": qty,
                    "unit_cost": item_unit_cost,
                    "unit_selling_price": item_selling_price,
                    "total_cost": item_total_cost,
                    "total_selling_price": item_total_selling
                })

            # تولید HTML و JSON جدید
            bundle_row.bundle_items_html = self._generate_bundle_items_html(bundle_items_list)
            bundle_row.bundle_items_data = json.dumps(bundle_items_list, ensure_ascii=False)
        
        # ذخیره تغییرات
        self.save()

    @frappe.whitelist()
    def apply_filters_server_side(self):
        """
        Apply Advanced Filters Server-Side
        Replaces client-side filtering loop to prevent browser freeze/crash.
        """
        # 1. Clear existing items
        self.items = []
        
        # 2. Build Query Filters
        filters = {}
        if self.filter_item_name:
            filters["item_name"] = ["like", f"%{self.filter_item_name}%"]
        if self.filter_item_group:
            # Handle multi-select list or string
            if isinstance(self.filter_item_group, str):
                try: 
                    groups = json.loads(self.filter_item_group)
                    filters["item_group"] = ["in", groups]
                except:
                    filters["item_group"] = self.filter_item_group
            else:
                filters["item_group"] = ["in", self.filter_item_group]
                
        if self.filter_brand:
             if isinstance(self.filter_brand, str):
                try: 
                    brands = json.loads(self.filter_brand)
                    filters["brand"] = ["in", brands]
                except:
                    filters["brand"] = self.filter_brand
             else:
                filters["brand"] = ["in", self.filter_brand]

        # 3. Fetch Items
        items = frappe.get_all("Item", filters=filters, fields=["item_code", "item_name", "item_group", "brand", "stock_uom"])
        
        # 4. Filter by BOM Status if needed (Server-side check)
        final_items = []
        if self.filter_bom_status:
            for item in items:
                has_bom = frappe.db.exists("BOM", {"item": item.item_code, "is_active": 1, "is_default": 1})
                if self.filter_bom_status == 'بدون BOM' and not has_bom:
                    final_items.append(item)
                elif self.filter_bom_status == 'با BOM' and has_bom:
                    final_items.append(item)
                elif not self.filter_bom_status:
                    final_items.append(item)
        else:
            final_items = items

        # 5. Add to Child Table
        for item in final_items:
            self.append("items", {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "item_group": item.item_group,
                "brand": item.brand,
                "uom": item.stock_uom
            })
            
        # 6. Save (bypass standard validations to be fast)
        self.save(ignore_permissions=True)
        
        return {
            "success": True,
            "count": len(final_items),
            "message": f"تعداد {len(final_items)} کالا با موفقیت فیلتر و اضافه شد."
        }

    @frappe.whitelist()
    def add_bulk_items_server_side(self):
        """
        Add items to 'Manual Pricing' table based on filters (Server-Side)
        """
        filters = {}
        if self.bulk_filter_item_name:
             filters["item_name"] = ["like", f"%{self.bulk_filter_item_name}%"]
        
        # Fetch directly from Item master
        items = frappe.get_all("Item", filters=filters, fields=["item_code", "item_name", "item_group", "brand"])
        
        added_count = 0
        existing_codes = [row.item_code for row in self.bulk_pricing_items]
        
        for item in items:
            if item.item_code not in existing_codes:
                self.append("bulk_pricing_items", {
                    "item_code": item.item_code,
                    "item_name": item.item_name,
                    "item_group": item.item_group,
                    "selected": 1
                })
                added_count += 1
                
        self.save(ignore_permissions=True)
        
        return {
            "success": True,
            "added": added_count,
            "message": f"{added_count} کالا به لیست قیمت‌گذاری دستی اضافه شد."
        }

    @frappe.whitelist()
    def get_analytics_dashboard(self):
        """
        Generate Analytics Dashboard HTML Server-Side
        """
        if not self.items:
            return "<div class='alert alert-warning'>هیچ کالایی برای تحلیل وجود ندارد.</div>"

        total_items = len(self.items)
        high_margin_items = 0
        low_margin_items = 0
        profitable_items = 0
        loss_items = 0
        
        for item in self.items:
            selling_price = flt(item.selling_price)
            total_cost = flt(item.total_cost)
            
            if total_cost > 0:
                margin = ((selling_price - total_cost) / total_cost) * 100
                if margin > 30:
                    high_margin_items += 1
                elif margin < 15:
                    low_margin_items += 1
            
            if item.profit_loss_status == 'سودآور':
                profitable_items += 1
            elif item.profit_loss_status == 'ضررآور':
                loss_items += 1

        html = f"""
            <div style="direction: rtl; padding: 20px;">
                <h4 style="margin-bottom: 20px; color: #333;">📊 تحلیل پیشرفته قیمت‌گذاری</h4>
                <div class="row">
                    <div class="col-md-3">
                        <div class="metric-card" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; border-radius: 10px; text-align: center;">
                            <h3>{total_items}</h3>
                            <p>کل کالاها</p>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="metric-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 15px; border-radius: 10px; text-align: center;">
                            <h3>{high_margin_items}</h3>
                            <p>حاشیه بالا (+30%)</p>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="metric-card" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; padding: 15px; border-radius: 10px; text-align: center;">
                            <h3>{low_margin_items}</h3>
                            <p>حاشیه پایین (-15%)</p>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="metric-card" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%); color: white; padding: 15px; border-radius: 10px; text-align: center;">
                            <h3>{profitable_items}/{loss_items}</h3>
                            <p>سودآور/ضررآور</p>
                        </div>
                    </div>
                </div>
            </div>
        """
        return html

    @frappe.whitelist()
    def calculate_bundle_prices(self, docname):
        """
        محاسبه مجدد قیمت‌های بسته‌های محصولات موجود
        """
        doc = frappe.get_doc("Auto Price List", docname)
        doc._recalculate_existing_bundles()
        return {
            "success": True, 
            "message": f"قیمت {len(doc.product_bundles)} بسته محصول به‌روزرسانی شد"
        }

    def get_item_selling_price(self, item_code):
        """
        دریافت قیمت فروش آیتم از جدول items یا prev_items
        """
        # اول از جدول items بگیر
        for item_row in self.items or []:
            if item_row.item_code == item_code:
                return flt(item_row.selling_price or item_row.final_selected_price or 0)
        
        # اگر نبود از prev_items بگیر
        for prev_item in self.prev_items or []:
            if prev_item.item_code == item_code:
                return flt(prev_item.new_price or prev_item.prev_price or 0)
        
        # در نهایت از لیست قیمت بگیر
        item_price = self.get_item_price(item_code, self.price_list)
        if item_price:
            return flt(item_price)
        
        # قیمت استاندارد
        return flt(frappe.db.get_value("Item", item_code, "standard_rate") or 0)
    
    def get_item_cost_details(self, item_code):
        """
        دریافت جزئیات هزینه آیتم از جدول items
        """
        for item_row in self.items or []:
            if item_row.item_code == item_code:
                return {
                    "total_cost": flt(item_row.total_cost or 0),
                    "raw_material_cost": flt(item_row.raw_material_cost or 0),
                    "operation_cost": flt(item_row.operation_cost or 0),
                    "electricity_cost": flt(item_row.electricity_cost or 0),
                    "consumable_cost": flt(item_row.consumable_cost or 0),
                    "rent_cost": flt(item_row.rent_cost or 0),
                    "labor_cost": flt(item_row.labor_cost or 0),
                    "subcontracting_cost": flt(item_row.subcontracting_cost or 0),
                    "overhead_cost": flt(item_row.overhead_cost or 0),
                    "selling_price": flt(item_row.selling_price or item_row.final_selected_price or 0)
                }
        
        # اگر در items نبود، صفر برگردان
        return {
            "total_cost": 0,
            "raw_material_cost": 0,
            "operation_cost": 0,
            "electricity_cost": 0,
            "consumable_cost": 0,
            "rent_cost": 0,
            "labor_cost": 0,
            "subcontracting_cost": 0,
            "overhead_cost": 0,
            "selling_price": 0
        }

    @frappe.whitelist()
    def calculate_product_bundles(self):
        """
        محاسبه قیمت بسته‌های محصولات با فیلتر
        این متد از جدول Product Bundle آیتم‌ها را می‌گیرد
        و قیمت و هزینه هر آیتم را محاسبه می‌کند
        """
        try:
            # پاک کردن بسته‌های قبلی
            self.product_bundles = []
            
            # ساخت فیلتر
            filters = {"disabled": 0}
            if self.bundle_name_filter:
                filters["new_item_code"] = ["like", f"%{self.bundle_name_filter}%"]
            
            # دریافت Product Bundle ها
            bundles = frappe.get_all("Product Bundle", 
                fields=["name", "new_item_code"],
                filters=filters
            )
            
            if not bundles:
                return {
                    "success": True,
                    "message": "هیچ بسته محصولی یافت نشد",
                    "bundles_count": 0
                }
            
            calculated_count = 0
            
            for bundle in bundles:
                bundle_name = bundle.name
                bundle_item_code = bundle.new_item_code
                
                # دریافت آیتم‌های داخل بسته
                bundle_items = frappe.get_all("Product Bundle Item",
                    filters={"parent": bundle_name},
                    fields=["item_code", "qty", "description"]
                )
                
                if not bundle_items:
                    continue
                
                # متغیرهای جمع کل
                total_cost = 0
                total_selling_price = 0
                total_raw_material = 0
                total_operation = 0
                total_electricity = 0
                total_consumable = 0
                total_rent = 0
                total_labor = 0
                total_subcontracting = 0
                total_overhead = 0
                
                # لیست آیتم‌های داخل بسته برای اضافه کردن به جدول
                bundle_items_list = []
                
                for item in bundle_items:
                    item_code = item.item_code
                    qty = flt(item.qty or 1)
                    
                    # دریافت قیمت فروش
                    item_selling_price = self.get_item_selling_price(item_code)
                    
                    # دریافت جزئیات هزینه
                    cost_details = self.get_item_cost_details(item_code)
                    
                    # محاسبه مجموع برای این آیتم
                    item_unit_cost = cost_details["total_cost"]
                    item_total_cost = item_unit_cost * qty
                    item_total_selling = item_selling_price * qty
                    
                    # دریافت نام آیتم
                    item_name = frappe.db.get_value("Item", item_code, "item_name") or item_code
                    
                    # اضافه کردن به لیست آیتم‌های بسته
                    bundle_items_list.append({
                        "item_code": item_code,
                        "item_name": item_name,
                        "qty": qty,
                        "unit_cost": item_unit_cost,
                        "unit_selling_price": item_selling_price,
                        "total_cost": item_total_cost,
                        "total_selling_price": item_total_selling
                    })
                    
                    # جمع کل‌ها
                    total_cost += item_total_cost
                    total_selling_price += item_total_selling
                    total_raw_material += cost_details["raw_material_cost"] * qty
                    total_operation += cost_details["operation_cost"] * qty
                    total_electricity += cost_details["electricity_cost"] * qty
                    total_consumable += cost_details["consumable_cost"] * qty
                    total_rent += cost_details["rent_cost"] * qty
                    total_labor += cost_details["labor_cost"] * qty
                    total_subcontracting += cost_details["subcontracting_cost"] * qty
                    total_overhead += cost_details["overhead_cost"] * qty
                
                # محاسبه سود
                profit_amount = total_selling_price - total_cost
                profit_percentage = (profit_amount / total_cost * 100) if total_cost > 0 else 0
                
                # دریافت نام بسته
                bundle_display_name = frappe.db.get_value("Item", bundle_item_code, "item_name") or bundle_item_code
                
                # تبدیل لیست به JSON برای ذخیره
                items_json = json.dumps(bundle_items_list, ensure_ascii=False)
                
                # ساخت HTML جدول برای نمایش آیتم‌ها
                items_html = self._generate_bundle_items_html(bundle_items_list)
                frappe.logger().info(f"Generated HTML for bundle {bundle_name}, length: {len(items_html)}")
                
                # اضافه کردن به جدول
                bundle_row = self.append("product_bundles", {
                    "product_bundle": bundle_name,
                    "product_bundle_name": bundle_display_name,
                    "total_cost": total_cost,
                    "selling_price": total_selling_price,
                    "raw_material_cost": total_raw_material,
                    "operation_cost": total_operation,
                    "electricity_cost": total_electricity,
                    "consumable_cost": total_consumable,
                    "rent_cost": total_rent,
                    "labor_cost": total_labor,
                    "subcontracting_cost": total_subcontracting,
                    "overhead_cost": total_overhead,
                    "profit_amount": profit_amount,
                    "profit_percentage": profit_percentage,
                    "bundle_items_data": items_json,
                    "bundle_items_html": items_html
                })
                
                calculated_count += 1
            
            # ذخیره سند
            self.save()
            
            return {
                "success": True,
                "message": f"✅ {calculated_count} بسته محصول محاسبه شد",
                "bundles_count": calculated_count
            }
            
        except Exception as e:
            frappe.log_error(f"خطا در محاسبه بسته محصولات: {str(e)}")
            return {
                "success": False,
                "message": f"خطا: {str(e)}"
            }
    
    def _generate_bundle_items_html(self, bundle_items_list):
        """
        ساخت HTML جدول برای نمایش آیتم‌های داخل بسته
        """
        if not bundle_items_list:
            return ""
        
        html = """
        <div style='margin-top: 10px;'>
            <table class='table table-bordered table-hover' style='margin: 0; font-size: 12px; width: 100%;'>
                <thead style='background-color: #f5f5f5;'>
                    <tr>
                        <th style='padding: 8px; text-align: right;'>کد کالا</th>
                        <th style='padding: 8px; text-align: right;'>نام کالا</th>
                        <th style='padding: 8px; text-align: center; width: 80px;'>تعداد</th>
                        <th style='padding: 8px; text-align: right;'>هزینه واحد</th>
                        <th style='padding: 8px; text-align: right;'>قیمت واحد</th>
                        <th style='padding: 8px; text-align: right;'>هزینه کل</th>
                        <th style='padding: 8px; text-align: right;'>قیمت کل</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for item in bundle_items_list:
            html += f"""
                <tr>
                    <td style='padding: 8px;'>{item.get('item_code', '')}</td>
                    <td style='padding: 8px;'>{item.get('item_name', '')}</td>
                    <td style='padding: 8px; text-align: center;'>{flt(item.get('qty', 0))}</td>
                    <td style='padding: 8px; text-align: right;'>{frappe.format_value(item.get('unit_cost', 0), {'fieldtype': 'Currency'})}</td>
                    <td style='padding: 8px; text-align: right;'>{frappe.format_value(item.get('unit_selling_price', 0), {'fieldtype': 'Currency'})}</td>
                    <td style='padding: 8px; text-align: right;'>{frappe.format_value(item.get('total_cost', 0), {'fieldtype': 'Currency'})}</td>
                    <td style='padding: 8px; text-align: right;'>{frappe.format_value(item.get('total_selling_price', 0), {'fieldtype': 'Currency'})}</td>
                </tr>
            """
        
        html += """
                </tbody>
            </table>
        </div>
        """
        
        return html
    
    @frappe.whitelist()
    def apply_bundle_prices(self):
        """
        اعمال قیمت‌های بسته محصولات به لیست قیمت
        """
        try:
            if not self.product_bundles:
                return {
                    "success": False,
                    "message": "هیچ بسته محصولی برای اعمال وجود ندارد"
                }
            
            created = 0
            updated = 0
            
            currency = frappe.db.get_value("Price List", self.price_list, "currency") or "IRR"

            # Pre-fetch Bundle Items and UOMs
            bundle_names = [b.product_bundle for b in self.product_bundles if b.product_bundle]
            bundle_item_map = {} # Bundle Name -> Item Code
            item_uom_map = {} # Item Code -> Safe UOM
            
            if bundle_names:
                bundles = frappe.get_all("Product Bundle", 
                    filters={"name": ["in", bundle_names]}, 
                    fields=["name", "new_item_code"]
                )
                bundle_item_map = {b.name: b.new_item_code for b in bundles}
                
                # Fetch UOMs for these items
                target_item_codes =  list(set(filter(None, bundle_item_map.values())))
                if target_item_codes:
                    items_data = frappe.get_all("Item", 
                        filters={"name": ["in", target_item_codes]}, 
                        fields=["name", "stock_uom"]
                    )
                    item_uom_map = {d.name: d.stock_uom for d in items_data}

            for bundle_row in self.product_bundles:
                bundle_name = bundle_row.product_bundle
                bundle_selling_price = flt(bundle_row.selling_price or 0)
                
                if bundle_selling_price <= 0:
                    continue
                
                # دریافت item_code بسته
                bundle_item_code = bundle_item_map.get(bundle_name)
                
                if not bundle_item_code:
                    continue
                
                # بررسی وجود قیمت در لیست قیمت با UOM صحیح
                # FIX: Check if item exists in fetched map
                if bundle_item_code not in item_uom_map:
                    frappe.logger("pricing").warning(f"Item {bundle_item_code} for bundle {bundle_name} not found in Item master. Skipping.")
                    continue

                target_uom = item_uom_map.get(bundle_item_code)
                if not target_uom:
                    target_uom = "Nos" # Fallback

                existing_prices = frappe.get_all("Item Price", 
                    filters={
                        "item_code": bundle_item_code,
                        "price_list": self.price_list,
                        "uom": target_uom
                    }, 
                    order_by="valid_from desc", 
                    limit=1,
                    pluck="name"
                )
                
                if existing_prices:
                    # به‌روزرسانی قیمت موجود
                    frappe.db.set_value("Item Price", existing_prices[0], "price_list_rate", bundle_selling_price)
                    updated += 1
                else:
                    # ایجاد قیمت جدید
                    item_price_doc = frappe.get_doc({
                        "doctype": "Item Price",
                        "item_code": bundle_item_code,
                        "price_list": self.price_list,
                        "price_list_rate": bundle_selling_price,
                        "currency": currency,
                        "uom": target_uom
                    })
                    item_price_doc.insert(ignore_permissions=True)
                    created += 1
            
            frappe.db.commit()
            
            return {
                "success": True,
                "message": f"✅ {created} قیمت ایجاد و {updated} قیمت به‌روزرسانی شد",
                "created": created,
                "updated": updated
            }
            
        except Exception as e:
            frappe.log_error(f"خطا در اعمال قیمت بسته محصولات: {str(e)}")
            frappe.db.rollback()
            return {
                "success": False,
                "message": f"خطا: {str(e)}"
            }
    
    def calculate_raw_material_from_exploded_items(self, bom_name):
        """
        محاسبه هزینه مواد اولیه از exploded_items (child table در BOM)
        """
        try:
            # دریافت BOM document
            bom_doc = frappe.get_doc("BOM", bom_name)
            
            # دریافت exploded_items از child table
            exploded_items = bom_doc.exploded_items if hasattr(bom_doc, 'exploded_items') else []
            
            # اگر exploded_items خالی است، از BOM Items استفاده کن
            if not exploded_items:
                frappe.logger("pricing").debug(f"⚠️ exploded_items خالی است، از BOM Items استفاده می‌کنم")
                return self.calculate_raw_material_from_bom_items_recursive(bom_name)
            
            total_raw_cost = 0
            
            for exploded_item in exploded_items:
                item_code = exploded_item.item_code
                qty = flt(exploded_item.qty or exploded_item.stock_qty or 0)
                
                # بررسی قیمت دستی
                manual_price = self.get_manual_material_price(item_code)
                if manual_price and manual_price > 0:
                    item_cost = manual_price * qty
                    frappe.logger("pricing").debug(f"   📌 قیمت دستی {item_code}: {manual_price:,.0f} × {qty} = {item_cost:,.0f}")
                else:
                    # استفاده از rate موجود در exploded_item
                    rate = flt(exploded_item.rate or 0)
                    item_cost = rate * qty
                    frappe.logger("pricing").debug(f"   💰 قیمت عادی {item_code}: {rate:,.0f} × {qty} = {item_cost:,.0f}")
                
                total_raw_cost += item_cost
            
            frappe.logger("pricing").debug(f"💎 مجموع هزینه مواد اولیه از exploded_items: {total_raw_cost:,.0f}")
            return total_raw_cost
            
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در محاسبه مواد اولیه از exploded_items {bom_name}: {str(e)}")
            # fallback به BOM Items
            return self.calculate_raw_material_from_bom_items_recursive(bom_name)

    def calculate_raw_material_from_bom_items_recursive(self, bom_name, processed_boms=None):
        """
        محاسبه هزینه مواد اولیه از BOM Items به صورت recursive
        """
        if processed_boms is None:
            processed_boms = set()
        
        if bom_name in processed_boms:
            return 0
        
        processed_boms.add(bom_name)
        
        try:
            bom_doc = frappe.get_doc("BOM", bom_name)
            total_cost = 0
            
            for bom_item in bom_doc.items:
                item_code = bom_item.item_code
                qty = flt(bom_item.qty or 0)
                
                # بررسی آیا این آیتم خودش BOM دارد
                sub_bom_name = frappe.db.get_value("BOM", {
                    "item": item_code,
                    "is_active": 1,
                    "is_default": 1
                }, "name")
                
                if sub_bom_name and sub_bom_name not in processed_boms:
                    # اگر BOM فرعی دارد، recursive محاسبه کن
                    sub_cost = self.calculate_raw_material_from_bom_items_recursive(sub_bom_name, processed_boms.copy())
                    item_cost = sub_cost * qty
                    frappe.logger("pricing").debug(f"   🔗 BOM فرعی {item_code}: {sub_cost:,.0f} × {qty} = {item_cost:,.0f}")
                else:
                    # اگر BOM ندارد، ماده خام است
                    manual_price = self.get_manual_material_price(item_code)
                    if manual_price and manual_price > 0:
                        item_cost = manual_price * qty
                        frappe.logger("pricing").debug(f"   📌 قیمت دستی {item_code}: {manual_price:,.0f} × {qty} = {item_cost:,.0f}")
                    else:
                        rate = flt(bom_item.rate or 0)
                        item_cost = rate * qty
                        frappe.logger("pricing").debug(f"   💰 ماده خام {item_code}: {rate:,.0f} × {qty} = {item_cost:,.0f}")
                
                total_cost += item_cost
            
            return total_cost
            
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در محاسبه recursive مواد اولیه {bom_name}: {str(e)}")
            return 0

    def collect_all_operations_from_bom_tree(self, bom_name, processed_boms=None, level=0):
        """
        جمع‌آوری تمام operations از تمام سطوح BOM به صورت بازگشتی
        CRITICAL FIX: هر فراخوانی بازگشتی یک copy از processed_boms می‌گیرد
        """
        if processed_boms is None:
            processed_boms = set()
        
        # جلوگیری از حلقه بی‌نهایت
        if bom_name in processed_boms:
            frappe.logger("pricing").debug(f"⚠️ BOM {bom_name} قبلاً پردازش شده، رد می‌شود")
            return []
        
        # CRITICAL FIX: ساخت کپی برای این شاخه
        current_processed = processed_boms.copy()
        current_processed.add(bom_name)
        
        all_operations = []
        
        try:
            # دریافت BOM document
            bom_doc = frappe.get_doc("BOM", bom_name)
            
            # مرحله 1: دریافت operations مستقیم این BOM
            if hasattr(bom_doc, 'operations') and bom_doc.operations:
                frappe.logger("pricing").debug(f"✅ سطح {level}: {len(bom_doc.operations)} operation مستقیم در {bom_name}")
                
                for operation in bom_doc.operations:
                    op_dict = {
                        'operation': operation.operation,
                        'time_in_mins': flt(operation.time_in_mins or 0),
                        'workstation': operation.workstation,
                        'hour_rate': flt(operation.hour_rate or 0),
                        'description': getattr(operation, 'description', ''),
                        'bom_name': bom_name,
                        'level': level,
                        'qty_factor': 1.0,
                        'parent_item': ''
                    }
                    
                    frappe.logger("pricing").debug(f"   ⚙️ {op_dict['operation']}: {op_dict['time_in_mins']} دقیقه")
                    all_operations.append(op_dict)
            
            # مرحله 2: بررسی items این BOM برای پیدا کردن BOM های فرعی
            if hasattr(bom_doc, 'items') and bom_doc.items:
                for bom_item in bom_doc.items:
                    # جستجوی BOM فعال برای این item
                    sub_bom_name = frappe.db.get_value("BOM", {
                        "item": bom_item.item_code,
                        "is_active": 1,
                        "is_default": 1
                    }, "name")
                    
                    if sub_bom_name and sub_bom_name not in current_processed:
                        # CRITICAL FIX: ارسال کپی از current_processed
                        sub_operations = self.collect_all_operations_from_bom_tree(
                            sub_bom_name, current_processed.copy(), level + 1
                        )
                        
                        if sub_operations:
                            frappe.logger("pricing").debug(f"✅ سطح {level}: {len(sub_operations)} operation از {sub_bom_name}")
                            
                            # اعمال ضریب مقدار
                            qty_factor = flt(bom_item.qty or 1)
                            for op in sub_operations:
                                op['qty_factor'] = op.get('qty_factor', 1.0) * qty_factor
                                op['parent_item'] = bom_item.item_code
                            
                            all_operations.extend(sub_operations)
            
            frappe.logger("pricing").debug(f"📊 سطح {level}: مجموع {len(all_operations)} operation برگردانده می‌شود")
            return all_operations
            
        except Exception as e:
            frappe.logger("pricing").debug(f"❌ خطا در پردازش BOM {bom_name}: {str(e)}")
            import traceback
            frappe.logger("pricing").debug(f"Traceback: {traceback.format_exc()}")
            return []

    def calculate_operation_detail_cost(self, operation_info):

        operation_detail = {
            'operation': operation_info.get('operation', ''),
            'workstation': operation_info.get('workstation', ''),
            'time_in_mins': operation_info.get('time_in_mins', 0),
            'time_in_hours': (operation_info.get('time_in_mins', 0) or 0) / 60.0,
            'description': operation_info.get('description', ''),
            'bom_name': operation_info.get('bom_name', ''),
            'level': operation_info.get('level', 0),
            'qty_factor': operation_info.get('qty_factor', 1),
            'parent_item': operation_info.get('parent_item', ''),
            'costs': {
                'electricity_cost': 0,
                'rent_cost': 0,
                'labor_cost': 0,
                'consumable_cost': 0,
                'subcontracting_cost': 0
            },
            'workstation_rates': {}
        }
        
        if operation_info.get('workstation') and operation_info.get('time_in_mins'):
            try:
                workstation = frappe.get_doc("Workstation", operation_info['workstation'])
                time_in_hours = (operation_info['time_in_mins'] or 0) / 60.0
                qty_factor = operation_info.get('qty_factor', 1)
                
                # محاسبه هزینه‌های مختلف با در نظر گیری qty_factor
                if hasattr(workstation, 'hour_rate_electricity') and workstation.hour_rate_electricity:
                    cost = flt(workstation.hour_rate_electricity or 0) * flt(time_in_hours) * flt(qty_factor)
                    operation_detail['costs']['electricity_cost'] = cost
                
                if hasattr(workstation, 'hour_rate_rent') and workstation.hour_rate_rent:
                    cost = flt(workstation.hour_rate_rent or 0) * flt(time_in_hours) * flt(qty_factor)
                    operation_detail['costs']['rent_cost'] = cost
                
                if hasattr(workstation, 'hour_rate_labour') and workstation.hour_rate_labour:
                    cost = flt(workstation.hour_rate_labour or 0) * flt(time_in_hours) * flt(qty_factor)
                    operation_detail['costs']['labor_cost'] = cost
                
                if hasattr(workstation, 'hour_rate_consumable') and workstation.hour_rate_consumable:
                    cost = flt(workstation.hour_rate_consumable or 0) * flt(time_in_hours) * flt(qty_factor)
                    operation_detail['costs']['consumable_cost'] = cost
                
                # هزینه پیمانکاری
                subcontracting_cost = self.calculate_subcontracting_cost_from_bom(
                    operation_info.get('bom_name', ''), operation_info.get('operation', '')
                ) * qty_factor
                operation_detail['costs']['subcontracting_cost'] = subcontracting_cost
                
                # ذخیره نرخ‌های ساعتی
                operation_detail['workstation_rates'] = {
                    'hour_rate_electricity': flt(workstation.hour_rate_electricity or 0),
                    'hour_rate_rent': flt(workstation.hour_rate_rent or 0),
                    'hour_rate_labour': flt(workstation.hour_rate_labour or 0),
                    'hour_rate_consumable': flt(workstation.hour_rate_consumable or 0)
                }
                
            except Exception as e:
                frappe.logger("pricing").debug(f"خطا در محاسبه هزینه عملیات {operation_info.get('operation', '')}: {str(e)}")
        
        return operation_detail

    def build_bom_level_structure(self, bom_name, processed_boms=None, level=0):
        """
        ساخت ساختار سطوح BOM برای نمایش
        """
        if processed_boms is None:
            processed_boms = set()
        
        if bom_name in processed_boms:
            return []
        
        processed_boms.add(bom_name)
        bom_levels = []
        
        try:
            bom_doc = frappe.get_doc("BOM", bom_name)
            item_name = frappe.db.get_value("Item", bom_doc.item, "item_name")
            
            level_info = {
                'level': level,
                'bom_name': bom_name,
                'item_code': bom_doc.item,
                'item_name': item_name,
                'sub_items': []
            }
            
            # اضافه کردن آیتم‌های فرعی
            for bom_item in bom_doc.items:
                sub_bom_name = frappe.db.get_value("BOM", {
                    "item": bom_item.item_code,
                    "is_active": 1,
                    "is_default": 1
                }, "name")
                
                item_info = {
                    'item_code': bom_item.item_code,
                    'item_name': frappe.db.get_value("Item", bom_item.item_code, "item_name"),
                    'qty': bom_item.qty,
                    'has_bom': bool(sub_bom_name)
                }
                
                level_info['sub_items'].append(item_info)
                
                if sub_bom_name and sub_bom_name not in processed_boms:
                    sub_levels = self.build_bom_level_structure(sub_bom_name, processed_boms.copy(), level + 1)
                    bom_levels.extend(sub_levels)
            
            bom_levels.insert(0, level_info)
            return bom_levels
            
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در ساخت ساختار سطوح BOM {bom_name}: {str(e)}")
            return []


    def calculate_raw_material_cost_with_substitutions(self, bom):
        """
        محاسبه هزینه مواد اولیه با در نظر گیری جایگزینی مواد
        ⚠️ DEPRECATED: این تابع دیگر استفاده نمی‌شود. از calculate_item_cost_with_exploded_items استفاده کنید
        این تابع قبلاً از BOM.raw_material_cost استفاده می‌کرد که برای BOMs چند سطحی اشتباه بود
        چون شامل هزینه‌های عملیاتی BOMهای زیرین هم می‌شد
        """
        # Always use exploded_items method instead
        return self.calculate_item_cost_with_exploded_items(bom.item)
    
    
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
            # ✅ محاسبه total_cost با در نظر گیری تمام هزینه‌ها
            total_cost = (
                flt(item.raw_material_cost or 0) +
                flt(item.operation_cost or 0) +
                flt(item.overhead_cost or 0)
            )
            
            # اضافه کردن لاگ برای دیباگ
            frappe.logger("pricing").debug(f"🔍 محاسبه total_cost برای {item.item_code}:")
            frappe.logger("pricing").debug(f"   مواد اولیه: {flt(item.raw_material_cost or 0):,.0f}")
            frappe.logger("pricing").debug(f"   هزینه عملیات: {flt(item.operation_cost or 0):,.0f}")
            frappe.logger("pricing").debug(f"   هزینه سربار: {flt(item.overhead_cost or 0):,.0f}")
            frappe.logger("pricing").debug(f"   مجموع: {total_cost:,.0f}")
            
            # به‌روزرسانی total_cost در آیتم
            item.total_cost = total_cost
            
            # شروع با total_cost به جای فقط raw_material_cost
            current_price = total_cost
            
            if current_price <= 0:
                return 0
            
            frappe.logger("pricing").debug(f"      🧮 شروع محاسبه قیمت نهایی برای {item.item_code}")
            frappe.logger("pricing").debug(f"         مواد اولیه: {flt(item.raw_material_cost or 0):,.0f}")
            frappe.logger("pricing").debug(f"         هزینه عملیات: {flt(item.operation_cost or 0):,.0f}")
            frappe.logger("pricing").debug(f"         هزینه سربار: {flt(item.overhead_cost or 0):,.0f}")
            frappe.logger("pricing").debug(f"         مجموع هزینه (total_cost): {total_cost:,.0f}")
            
            # اعمال pricing steps به ترتیب
            if self.pricing_steps:
                for step in self.pricing_steps:
                    step_type = step.step_type
                    
                    # گرفتن درصد از فیلدهای اصلی Auto Price List بر اساس نوع مرحله
                    percentage = 0
                    if step_type == "سود":
                        percentage = flt(self.get('profit_margin') or 0)
                    elif step_type == "افزایش قیمت":
                        percentage = flt(self.get('required_markup_percentage') or 0)
                    elif step_type == "کمیسیون":
                        percentage = flt(self.get('commission_percentage') or 0)
                    elif step_type == "بهره تأخیری":
                        percentage = flt(self.get('deferred_payment_interest_rate') or 0)
                    elif step_type == "بهره قسطی":
                        percentage = flt(self.get('monthly_interest_rate') or 0)
                    elif step_type == "تخفیف":
                        percentage = flt(self.get('target_discount_percentage') or 0)
                    
                    if percentage == 0 and step_type != "رند کردن":
                        continue
                    
                    old_price = current_price
                    
                    if step_type == "سود":
                        # اضافه کردن سود - محاسبه صحیح
                        old_price = current_price
                        current_price = current_price * (1 + percentage / 100)
                        profit_amount = current_price - old_price
                        frappe.logger("pricing").debug(f"         سود {percentage}%: {old_price:,.0f} → {current_price:,.0f} (سود: {profit_amount:,.0f})")
                        
                    elif step_type == "افزایش قیمت":
                        # افزایش قیمت
                        current_price = current_price * (1 + percentage / 100)
                        frappe.logger("pricing").debug(f"         افزایش قیمت {percentage}%: {old_price:,.0f} → {current_price:,.0f}")
                        
                    elif step_type == "کمیسیون":
                        # کسر کمیسیون
                        current_price = current_price * (1 - percentage / 100)
                        frappe.logger("pricing").debug(f"         کمیسیون {percentage}%: {old_price:,.0f} → {current_price:,.0f}")
                        
                    elif step_type == "بهره تأخیری":
                        # اضافه کردن بهره تأخیری با فرمول بهره مرکب
                        if self.deferred_payment_months:
                            months = int(self.deferred_payment_months)
                            monthly_rate = percentage / 100
                            compound_rate = (1 + monthly_rate) ** months - 1
                            current_price = current_price * (1 + compound_rate)
                            frappe.logger("pricing").debug(f"         بهره تأخیری ({percentage}% ماهانه × {months} ماه = {compound_rate*100:.2f}% کل): {old_price:,.0f} → {current_price:,.0f}")
                    
                    elif step_type == "بهره قسطی":
                        # اضافه کردن بهره قسطی با فرمول بهره مرکب
                        if self.number_of_months:
                            months = int(self.number_of_months)
                            monthly_rate = percentage / 100
                            compound_rate = (1 + monthly_rate) ** months - 1
                            current_price = current_price * (1 + compound_rate)
                            frappe.logger("pricing").debug(f"         بهره قسطی ({percentage}% ماهانه × {months} ماه = {compound_rate*100:.2f}% کل): {old_price:,.0f} → {current_price:,.0f}")
                        
                    elif step_type == "رند کردن":
                        # رند کردن قیمت
                        rounding_method = self.get('rounding_method')
                        if rounding_method:
                            import math
                            if rounding_method == 'round_100':
                                current_price = round(current_price / 100) * 100
                            elif rounding_method == 'round_1000':
                                current_price = round(current_price / 1000) * 1000
                            elif rounding_method == 'round_10000':
                                current_price = round(current_price / 10000) * 10000
                            elif rounding_method == 'round_up_100':
                                current_price = math.ceil(current_price / 100) * 100
                            elif rounding_method == 'round_up_1000':
                                current_price = math.ceil(current_price / 1000) * 1000
                            frappe.logger("pricing").debug(f"         رند کردن ({rounding_method}): {old_price:,.0f} → {current_price:,.0f}")
                        
                    elif step_type == "تخفیف":
                        # کسر تخفیف
                        current_price = current_price * (1 - percentage / 100)
                        frappe.logger("pricing").debug(f"         تخفیف {percentage}%: {old_price:,.0f} → {current_price:,.0f}")
            
            frappe.logger("pricing").debug(f"         قیمت نهایی: {current_price:,.0f}")
            return current_price
            
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در محاسبه قیمت نهایی: {str(e)}")
            return flt(item.raw_material_cost or 0)
    
    def is_item_affected_by_manual_prices(self, item_code, manual_price_map):
        """
        بررسی اینکه آیا یک آیتم تحت تأثیر قیمت‌های دستی مواد اولیه است یا نه
        """
        try:
            frappe.logger("pricing").debug(f"      🔍 بررسی تأثیر قیمت‌های دستی برای {item_code}")
            print(f"      🔍 بررسی تأثیر قیمت‌های دستی برای {item_code}")
            
            # پیدا کردن BOM فعال
            bom_name = frappe.db.get_value("BOM", {
                "item": item_code,
                "is_active": 1,
                "is_default": 1
            }, "name")
            
            if not bom_name:
                frappe.logger("pricing").debug(f"      ❌ BOM فعال برای {item_code} پیدا نشد")
                print(f"      ❌ BOM فعال برای {item_code} پیدا نشد")
                return False
            
            frappe.logger("pricing").debug(f"      ✅ BOM پیدا شد: {bom_name}")
            print(f"      ✅ BOM پیدا شد: {bom_name}")
            
            # ابتدا بررسی exploded items
            exploded_items = frappe.get_all("BOM Explosion Item", 
                filters={"parent": bom_name},
                fields=["item_code"]
            )
            
            frappe.logger("pricing").debug(f"      📋 تعداد exploded items: {len(exploded_items)}")
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
                frappe.logger("pricing").debug(f"      ✅ مواد متأثر پیدا شد: {affected_materials}")
                print(f"      ✅ مواد متأثر پیدا شد: {affected_materials}")
                return True
            else:
                frappe.logger("pricing").debug(f"      ❌ هیچ ماده متأثری پیدا نشد")
                print(f"      ❌ هیچ ماده متأثری پیدا نشد")
                print(f"      🔍 دلیل: مواد موجود {all_materials} با قیمت‌های دستی {list(manual_price_map.keys())} مطابقت ندارند")
                return False
            
        except Exception as e:
            frappe.logger("pricing").debug(f"      ❌ خطا در بررسی تأثیر: {str(e)}")
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
                
            elif step.step_type == "بهره تأخیری" and self.enable_deferred_payment and self.deferred_payment_interest_rate and self.deferred_payment_months:
                # اضافه کردن بهره تأخیری با فرمول بهره مرکب
                monthly_rate = flt(self.deferred_payment_interest_rate) / 100
                months = int(self.deferred_payment_months)
                total_interest_rate = (1 + monthly_rate) ** months - 1
                current_price = current_price * (1 + total_interest_rate)
                
            elif step.step_type == "بهره قسطی" and self.enable_installment and self.monthly_interest_rate and self.number_of_months:
                # اضافه کردن بهره قسطی با فرمول بهره مرکب
                monthly_rate = flt(self.monthly_interest_rate) / 100
                months = int(self.number_of_months)
                total_interest_rate = (1 + monthly_rate) ** months - 1
                current_price = current_price * (1 + total_interest_rate)
                
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
        بهینه‌سازی شده با استفاده از cache - کاهش کوئری‌ها از N به 1
        """
        try:
            # اطمینان از وجود cache
            self._ensure_cache_initialized()
            
            # چک کردن قیمت دستی از cache
            cached_manual = self._get_cached_manual_price(item_code)
            if cached_manual and cached_manual.get('raw_material_cost') is not None:
                return cached_manual['raw_material_cost']
            
            # چک کردن BOM از cache یا دیتابیس
            cached_bom = self._get_cached_bom(item_code)
            if cached_bom:
                bom_name = cached_bom.name
            else:
                # fallback به query معمولی
                bom_name = frappe.db.get_value("BOM", {
                    "item": item_code,
                    "is_active": 1,
                    "is_default": 1
                }, "name")
            
            if not bom_name:
                return 0
            
            # چک کردن آیا هزینه مواد اولیه دستی وجود دارد (روش قدیمی)
            manual_costs = self._get_manual_item_price(item_code)
            if manual_costs and manual_costs.get('raw_material_cost') is not None:
                return manual_costs['raw_material_cost']
            
            # محاسبه هزینه از exploded items (از cache یا دیتابیس)
            total_cost = 0
            
            exploded_items = self._get_cached_exploded_items(bom_name)
            if exploded_items is None:
                # fallback به query معمولی - اما یکبار همه داده‌ها رو بگیر
                exploded_items = frappe.get_all("BOM Explosion Item", 
                    filters={"parent": bom_name},
                    fields=["item_code", "qty_consumed_per_unit", "rate", "amount"]
                )
                # ذخیره در cache برای دفعات بعدی
                if not hasattr(self, '_exploded_items_cache'):
                    self._exploded_items_cache = {}
                self._exploded_items_cache[bom_name] = exploded_items
            
            if not exploded_items:
                # fallback به BOM items - بدون get_doc برای سرعت بیشتر
                bom_items = frappe.get_all("BOM Item",
                    filters={"parent": bom_name},
                    fields=["item_code", "qty", "rate", "amount"]
                )
                
                if not bom_items:
                    return 0
                
                # جمع‌آوری همه item_codes برای یک batch query
                item_codes_needed = [bi['item_code'] for bi in bom_items]
                
                # batch load قیمت‌ها اگر در cache نیستند
                self._batch_load_missing_prices(item_codes_needed)
                
                for bom_item in bom_items:
                    item_code_exp = bom_item['item_code']
                    qty = flt(bom_item.get('qty') or 0)
                    
                    # استفاده از قیمت cache شده
                    cached_price = self._get_cached_item_price(item_code_exp)
                    if cached_price is not None:
                        item_cost = cached_price * qty
                    elif bom_item.get('amount'):
                        item_cost = flt(bom_item.get('amount'))
                    elif bom_item.get('rate'):
                        item_cost = flt(bom_item.get('rate')) * qty
                    else:
                        item_cost = 0
                    
                    total_cost += item_cost
                
                return total_cost
            
            # جمع‌آوری item_codes برای batch query
            item_codes_needed = []
            for ei in exploded_items:
                if isinstance(ei, dict):
                    item_codes_needed.append(ei.get('item_code'))
                else:
                    item_codes_needed.append(getattr(ei, 'item_code', None))
            
            # batch load قیمت‌ها
            self._batch_load_missing_prices([ic for ic in item_codes_needed if ic])
            
            for exploded_item in exploded_items:
                if isinstance(exploded_item, dict):
                    item_code_exp = exploded_item.get('item_code')
                    qty = flt(exploded_item.get('qty_consumed_per_unit') or 0)
                    amount = flt(exploded_item.get('amount') or 0)
                    rate = flt(exploded_item.get('rate') or 0)
                else:
                    item_code_exp = getattr(exploded_item, 'item_code', None)
                    qty = flt(getattr(exploded_item, 'qty_consumed_per_unit', 0) or 0)
                    amount = flt(getattr(exploded_item, 'amount', 0) or 0)
                    rate = flt(getattr(exploded_item, 'rate', 0) or 0)
                
                if not item_code_exp:
                    continue
                
                # استفاده از قیمت cache شده (اولویت اول)
                cached_price = self._get_cached_item_price(item_code_exp)
                if cached_price is not None:
                    item_cost = cached_price * qty
                elif amount > 0:
                    item_cost = amount
                elif rate > 0:
                    item_cost = rate * qty
                else:
                    item_cost = 0
                
                total_cost += item_cost
            
            return total_cost
            
        except Exception as e:
            # حذف print های debug - فقط log در صورت نیاز
            if getattr(self, '_debug_mode', False):
                frappe.logger("pricing").debug(f"خطا در محاسبه هزینه {item_code}: {str(e)}")
            return 0
    
    def _batch_load_missing_prices(self, item_codes):
        """
        بارگذاری دسته‌ای قیمت‌های آیتم‌هایی که در cache نیستند
        این متد تعداد کوئری‌های دیتابیس را به شدت کاهش می‌دهد
        """
        if not item_codes:
            return
        
        # فیلتر کردن آیتم‌هایی که در cache نیستند
        if not hasattr(self, '_item_price_cache'):
            self._item_price_cache = {}
        
        missing_codes = [ic for ic in item_codes if ic and ic not in self._item_price_cache]
        
        if not missing_codes:
            return
        
        # یک query برای همه قیمت‌ها
        try:
            # اول از Purchase Invoice
            prices = frappe.db.sql("""
                SELECT item_code, rate
                FROM (
                    SELECT pi.item_code, pi.rate,
                           ROW_NUMBER() OVER (PARTITION BY pi.item_code ORDER BY p.posting_date DESC, p.creation DESC) as rn
                    FROM `tabPurchase Invoice Item` pi
                    INNER JOIN `tabPurchase Invoice` p ON pi.parent = p.name
                    WHERE pi.item_code IN %(item_codes)s
                      AND p.docstatus = 1
                ) sub
                WHERE rn = 1
            """, {"item_codes": missing_codes}, as_dict=True)
            
            for p in prices:
                self._item_price_cache[p.item_code] = p.rate
            
            # آیتم‌هایی که هنوز قیمت ندارند
            still_missing = [ic for ic in missing_codes if ic not in self._item_price_cache]
            
            if still_missing:
                # fallback به valuation_rate یا standard_rate
                items = frappe.get_all("Item",
                    filters={"item_code": ["in", still_missing]},
                    fields=["item_code", "valuation_rate", "standard_rate"]
                )
                for item in items:
                    if item.item_code not in self._item_price_cache:
                        self._item_price_cache[item.item_code] = flt(item.valuation_rate) or flt(item.standard_rate) or 0
        
        except Exception as e:
            if getattr(self, '_debug_mode', False):
                frappe.logger("pricing").debug(f"خطا در batch load قیمت‌ها: {str(e)}")
    
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
            frappe.logger("pricing").debug(f"Error saving pricing breakdown: {e}")
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
        
        # لاگ تنظیمات pricing steps
        frappe.logger("pricing").debug(f"📋 تنظیمات pricing steps:")
        for i, step in enumerate(pricing_steps, 1):
            frappe.logger("pricing").debug(f"   {i}. {step.step_type} - ترتیب: {step.step_order}")
        
        # لاگ تنظیمات کلی
        frappe.logger("pricing").debug(f"📊 تنظیمات کلی:")
        frappe.logger("pricing").debug(f"   درصد سود: {self.profit_margin}")
        frappe.logger("pricing").debug(f"   درصد افزایش قیمت: {self.required_markup_percentage}")
        frappe.logger("pricing").debug(f"   درصد تخفیف هدف: {self.target_discount_percentage}")
        frappe.logger("pricing").debug(f"   درصد کمیسیون: {self.commission_percentage}")
        
        for step in pricing_steps:
            previous_price = current_price
            frappe.logger("pricing").debug(f"مرحله {step_counter}: {step.step_type} - قیمت فعلی: {current_price:,.0f}")
            
            step_result = self._apply_pricing_step(step, current_price, item)
            
            # همیشه مرحله را در گزارش نمایش بده، حتی اگر نتیجه‌ای نداشته باشد
            if step_result:
                frappe.logger("pricing").debug(f"نتیجه مرحله {step.step_type}: {step_result}")
                # بررسی صحت قیمت جدید
                new_price = step_result['new_price']
                if new_price is None or new_price <= 0:
                    # در صورت خطا، قیمت قبلی را حفظ کن و ادامه بده
                    calculation_steps.append(f"{step_counter}. {step.step_type}: خطا در محاسبه - قیمت قبلی حفظ شد ({current_price:,.0f} ریال)")
                    frappe.logger("pricing").debug(f"خطا در مرحله {step.step_type}: قیمت نامعتبر {new_price}")
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
        
        frappe.logger("pricing").debug(f"پایان اجرای مراحل - قیمت نهایی: {current_price:,.0f}")
        
        # تنظیم قیمت نهایی و گزارش
        item.final_selected_price = current_price
        
        # محاسبه سود واقعی: قیمت نهایی - هزینه - افزایش قیمت (برای تخفیف)
        # چون required_markup برای امکان تخفیف اضافه می‌شه، نباید جزو سود واقعی باشه
        real_profit = current_price - flt(total_cost) - flt(item.required_markup_amount or 0)
        item.profit_amount = real_profit
        
        frappe.logger("pricing").debug(f"💰 محاسبه سود واقعی:")
        frappe.logger("pricing").debug(f"   قیمت نهایی: {current_price:,.0f}")
        frappe.logger("pricing").debug(f"   هزینه کل: {total_cost:,.0f}")
        frappe.logger("pricing").debug(f"   افزایش برای تخفیف: {item.required_markup_amount or 0:,.0f}")
        frappe.logger("pricing").debug(f"   سود واقعی: {real_profit:,.0f}")
        
        calculation_steps.append(f"\n🎯 قیمت نهایی: {current_price:,.0f} ریال")
        calculation_steps.append(f"💰 سود واقعی: {real_profit:,.0f} ریال")
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
        
        # لاگ شروع مرحله
        frappe.logger("pricing").debug(f"🔄 شروع مرحله {step_type} برای {item.item_code if hasattr(item, 'item_code') else 'نامشخص'}")
        frappe.logger("pricing").debug(f"   قیمت ورودی: {current_price:,.0f}")
        
        try:
            if step_type == "سود":
                result = self._apply_profit_step(current_price, item)
            elif step_type == "افزایش قیمت":
                result = self._apply_markup_step(current_price, item)
            elif step_type == "کمیسیون":
                result = self._apply_commission_step(current_price, item)
            elif step_type == "بهره تأخیری":
                result = self._apply_interest_step(current_price, item)
            elif step_type == "بهره قسطی":
                result = self._apply_interest_step(current_price, item)  # استفاده از همان تابع بهره
            elif step_type == "تخفیف":
                result = self._apply_discount_step(current_price, item)
            elif step_type == "رند کردن":
                result = self._apply_rounding_step(current_price, item)
            else:
                # اگر نوع مرحله شناخته شده نیست
                result = {
                    'new_price': current_price,
                    'description': f"{step_type}: نوع مرحله شناخته شده نیست"
                }
            
            # لاگ نتیجه مرحله
            frappe.logger("pricing").debug(f"✅ پایان مرحله {step_type}")
            frappe.logger("pricing").debug(f"   قیمت خروجی: {result.get('new_price', current_price):,.0f}")
            frappe.logger("pricing").debug(f"   توضیحات: {result.get('description', 'بدون توضیحات')}")
            
            return result
            
        except Exception as e:
            # در صورت خطا، قیمت را حفظ کن
            frappe.logger("pricing").debug(f"❌ خطا در مرحله {step_type}: {str(e)}")
            return {
                'new_price': current_price,
                'description': f"{step_type}: خطا در اجرا - {str(e)}"
            }
    
    def _apply_profit_step(self, current_price, item):
        """اعمال مرحله سود - محاسبه صحیح سود بر اساس درصد"""
        from frappe.utils import flt
        
        if not self.profit_margin:
            return {
                'new_price': current_price,
                'description': f"سود: تنظیم نشده (0 ریال)"
            }
        
        # محاسبه صحیح سود: اگر 30% سود می‌خواهیم، باید قیمت فروش 130% هزینه باشد
        # فرمول: قیمت فروش = هزینه × (1 + درصد سود / 100)
        profit_percentage = flt(self.profit_margin)
        new_price = current_price * (1 + profit_percentage / 100)
        profit_amount = new_price - current_price
        
        # به‌روزرسانی فیلدهای آیتم
        item.selling_price = new_price
        item.profit_amount = profit_amount
        
        # اضافه کردن لاگ برای دیباگ
        frappe.logger("pricing").debug(f"💹 محاسبه سود برای {item.item_code}:")
        frappe.logger("pricing").debug(f"   هزینه پایه: {current_price:,.0f}")
        frappe.logger("pricing").debug(f"   درصد سود: {profit_percentage}%")
        frappe.logger("pricing").debug(f"   مبلغ سود: {profit_amount:,.0f}")
        frappe.logger("pricing").debug(f"   قیمت نهایی: {new_price:,.0f}")
        
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
                frappe.logger("pricing").debug(f"🔧 محاسبه خودکار افزایش قیمت برای تخفیف {discount}%: {markup_percentage:.2f}%")
        
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
        
        # اضافه کردن لاگ برای دیباگ
        frappe.logger("pricing").debug(f"📈 محاسبه افزایش قیمت:")
        frappe.logger("pricing").debug(f"   قیمت فعلی: {current_price:,.0f}")
        frappe.logger("pricing").debug(f"   درصد افزایش: {markup_percentage:.2f}%")
        frappe.logger("pricing").debug(f"   مبلغ افزایش: {markup_amount:,.0f}")
        frappe.logger("pricing").debug(f"   قیمت جدید: {new_price:,.0f}")
        
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
        
        # ذخیره قیمت قبل از رند کردن
        item._price_before_rounding = current_price
        
        if not self.price_rounding_amount or self.price_rounding_amount <= 0:
            return {
                'new_price': current_price,
                'description': f"رند کردن: تنظیم نشده (0 ریال)"
            }
        
        rounding_amount = flt(self.price_rounding_amount)
        rounded_price = math.ceil(current_price / rounding_amount) * rounding_amount
        rounding_adjustment = rounded_price - current_price
        
        frappe.logger("pricing").debug(f"🔢 رند کردن: {current_price:,.0f} → {rounded_price:,.0f} (تعدیل: +{rounding_adjustment:,.0f})")
        
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
        try:
            profit_margin_value = flt(self.get('profit_margin') or 0)
            if profit_margin_value > 0:
                actual_profit_amount = flt(item.total_cost) * (profit_margin_value / 100)
                item.profit_added_amount = actual_profit_amount
            else:
                item.profit_added_amount = 0
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در محاسبه سود: {str(e)}")
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
            frappe.logger("pricing").debug(f"Error applying combined pricing strategy: {e}")
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
            frappe.logger("pricing").debug(f"Error comparing strategies: {e}")
            frappe.throw(f"خطا در مقایسه استراتژی‌ها: {str(e)}")

    def on_update(self):
        """Called after document is saved"""
        pass  # Remove automatic calculation to prevent database locks
        
    def save(self, *args, **kwargs):
        """
        ذخیره با مدیریت بهتر timeout, lock و timestamp mismatch
        """
        import time
        max_retries = 3
        retry_delay = 1  # ثانیه
        
        for attempt in range(max_retries):
            try:
                # تنظیم timeout مناسب‌تر - 30 ثانیه به جای 3 ثانیه
                frappe.db.sql("SET SESSION innodb_lock_wait_timeout = 30")
                
                # اگر transaction های معلق وجود داره، rollback کن
                if attempt > 0:
                    try:
                        frappe.db.rollback()
                    except:
                        pass
                    time.sleep(retry_delay * attempt)  # افزایش تاخیر با هر تلاش
                    
                    # در تلاش‌های بعدی، سند رو از دیتابیس بخون و merge کن
                    try:
                        db_doc = frappe.get_doc(self.doctype, self.name)
                        self.modified = db_doc.modified
                    except:
                        pass
                
                return super().save(*args, **kwargs)
                
            except frappe.exceptions.TimestampMismatchError as e:
                frappe.logger("pricing").debug(f"تلاش {attempt + 1}/{max_retries}: TimestampMismatch - بازخوانی سند...")
                
                if attempt < max_retries - 1:
                    # بازخوانی timestamp از دیتابیس و تلاش مجدد
                    try:
                        db_doc = frappe.get_doc(self.doctype, self.name)
                        self.modified = db_doc.modified
                    except:
                        pass
                    continue
                else:
                    # آخرین تلاش - ذخیره اجباری
                    try:
                        self.flags.ignore_version = True
                        self.flags.ignore_validate_update_after_submit = True
                        db_doc = frappe.get_doc(self.doctype, self.name)
                        self.modified = db_doc.modified
                        return super().save(*args, **kwargs)
                    except Exception as final_e:
                        frappe.logger("pricing").error(f"خطا در ذخیره اجباری: {str(final_e)}")
                        raise frappe.ValidationError("سند توسط پروسس دیگری تغییر کرده. لطفاً صفحه را refresh کنید.")
                
            except frappe.QueryTimeoutError as e:
                frappe.logger("pricing").debug(f"تلاش {attempt + 1}/{max_retries}: خطای timeout در ذخیره: {str(e)}")
                
                if attempt < max_retries - 1:
                    # تلاش مجدد
                    continue
                    
                # آخرین تلاش - ذخیره مستقیم
                if (hasattr(self, 'manual_material_prices') and self.manual_material_prices) or \
                   (hasattr(self, 'manual_item_prices') and self.manual_item_prices):
                    return self._save_with_direct_sql()
                else:
                    raise frappe.ValidationError("ذخیره ناکام بود. لطفاً چند ثانیه صبر کرده و دوباره تلاش کنید.")
                    
            except Exception as e:
                frappe.logger("pricing").debug(f"خطا در ذخیره: {str(e)}")
                raise
    
    def _save_with_direct_sql(self):
        """
        ذخیره مستقیم با SQL برای مواقع بحرانی
        """
        try:
            frappe.logger("pricing").debug("🔧 شروع ذخیره مستقیم با SQL")
            
            # به‌روزرسانی فیلدهای اصلی سند
            frappe.db.sql("""
                UPDATE `tabAuto Price List`
                SET modified = NOW(), modified_by = %s
                WHERE name = %s
            """, (frappe.session.user, self.name))
            
            # ذخیره manual_material_prices اگر وجود دارد
            if hasattr(self, 'manual_material_prices') and self.manual_material_prices:
                self._save_manual_prices_direct_simple()
            
            # ذخیره manual_item_prices اگر وجود دارد
            if hasattr(self, 'manual_item_prices') and self.manual_item_prices:
                self._save_manual_item_prices_direct()
            
            frappe.db.commit()
            frappe.logger("pricing").debug("✅ ذخیره مستقیم با موفقیت انجام شد")
            
            return self
            
        except Exception as e:
            frappe.db.rollback()
            frappe.logger("pricing").debug(f"خطا در ذخیره مستقیم: {str(e)}")
            # اگر ذخیره مستقیم هم ناکام بود، خطا را باز پرتاب کن
            raise frappe.ValidationError(f"ذخیره ناکام بود. لطفاً دوباره تلاش کنید: {str(e)}")
    
    def _save_manual_item_prices_direct(self):
        """
        ذخیره مستقیم manual_item_prices با SQL
        """
        try:
            frappe.logger("pricing").debug("💾 شروع ذخیره مستقیم manual_item_prices")
            
            # حذف رکوردهای قبلی
            frappe.db.sql("""
                DELETE FROM `tabAuto Price List Manual Item Price`
                WHERE parent = %s
            """, (self.name,))
            
            # اضافه رکوردهای جدید
            for idx, mp in enumerate(self.manual_item_prices, 1):
                if not mp.get('item_code'):
                    continue
                    
                frappe.db.sql("""
                    INSERT INTO `tabAuto Price List Manual Item Price`
                    (name, parent, parentfield, parenttype, idx, item_code, item_name,
                     manual_raw_material_cost, manual_operation_cost, manual_overhead_cost,
                     manual_subcontracting_cost, manual_labor_cost, manual_electricity_cost,
                     manual_consumable_cost, manual_rent_cost, manual_overhead_additional_cost,
                     effective_date, notes, created_by, last_updated, creation, modified, modified_by, owner)
                    VALUES (%s, %s, 'manual_item_prices', 'Auto Price List', %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), %s, %s)
                """, (
                    frappe.generate_hash(length=10),
                    self.name,
                    idx,
                    mp.get('item_code'),
                    mp.get('item_name', mp.get('item_code')),
                    mp.get('manual_raw_material_cost', 0),
                    mp.get('manual_operation_cost', 0),
                    mp.get('manual_overhead_cost', 0),
                    mp.get('manual_subcontracting_cost', 0),
                    mp.get('manual_labor_cost', 0),
                    mp.get('manual_electricity_cost', 0),
                    mp.get('manual_consumable_cost', 0),
                    mp.get('manual_rent_cost', 0),
                    mp.get('manual_overhead_additional_cost', 0),
                    mp.get('effective_date', frappe.utils.today()),
                    mp.get('notes', ''),
                    mp.get('created_by', frappe.session.user),
                    mp.get('last_updated', frappe.utils.now()),
                    frappe.session.user,
                    frappe.session.user
                ))
            
            frappe.logger("pricing").debug(f"✅ ذخیره مستقیم {len(self.manual_item_prices)} رکورد manual_item_prices")
            
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در ذخیره مستقیم manual_item_prices: {str(e)}")
            raise

    def _save_manual_item_prices_direct_only(self):
        """
        ذخیره مستقیم فقط manual_item_prices برای API calls
        """
        try:
            frappe.logger("pricing").debug("🔧 شروع ذخیره مستقیم manual_item_prices...")
            
            if not hasattr(self, 'manual_item_prices') or not self.manual_item_prices:
                return {
                    "success": True,
                    "message": "هیچ manual_item_prices برای ذخیره وجود ندارد",
                    "updated_count": 0,
                    "added_count": 0
                }
            
            updated_count = 0
            added_count = 0
            
            for item_price in self.manual_item_prices:
                if not item_price.item_code:
                    continue
                
                # چک کردن وجود رکورد
                existing = frappe.db.sql("""
                    SELECT name FROM `tabAuto Price List Manual Item Price`
                    WHERE parent = %s AND item_code = %s
                """, (self.name, item_price.item_code))
                
                if existing:
                    # به‌روزرسانی رکورد موجود
                    frappe.db.sql("""
                        UPDATE `tabAuto Price List Manual Item Price`
                        SET item_name = %s, manual_raw_material_cost = %s,
                            manual_operation_cost = %s, manual_overhead_cost = %s,
                            manual_subcontracting_cost = %s, manual_labor_cost = %s,
                            manual_electricity_cost = %s, manual_consumable_cost = %s,
                            manual_rent_cost = %s, notes = %s, last_updated = %s,
                            modified = NOW(), modified_by = %s
                        WHERE parent = %s AND item_code = %s
                    """, (
                        item_price.item_name or item_price.item_code,
                        flt(item_price.manual_raw_material_cost or 0),
                        flt(item_price.manual_operation_cost or 0),
                        flt(item_price.manual_overhead_cost or 0),
                        flt(item_price.manual_subcontracting_cost or 0),
                        flt(item_price.manual_labor_cost or 0),
                        flt(item_price.manual_electricity_cost or 0),
                        flt(item_price.manual_consumable_cost or 0),
                        flt(item_price.manual_rent_cost or 0),
                        item_price.notes or '',
                        frappe.utils.now(),
                        frappe.session.user,
                        self.name,
                        item_price.item_code
                    ))
                    updated_count += 1
                else:
                    # ایجاد رکورد جدید
                    new_name = frappe.generate_hash(length=10)
                    frappe.db.sql("""
                        INSERT INTO `tabAuto Price List Manual Item Price`
                        (name, owner, creation, modified, modified_by, docstatus, idx,
                         item_code, item_name, manual_raw_material_cost, manual_operation_cost,
                         manual_overhead_cost, manual_subcontracting_cost, manual_labor_cost,
                         manual_electricity_cost, manual_consumable_cost, manual_rent_cost,
                         manual_overhead_additional_cost, effective_date, notes, created_by, last_updated,
                         parent, parentfield, parenttype, doctype)
                        VALUES (%s, %s, %s, %s, %s, 0, %s,
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s,
                                %s, 'manual_item_prices', 'Auto Price List', 'Auto Price List Manual Item Price')
                    """, (
                        new_name, frappe.session.user, frappe.utils.now(), frappe.utils.now(), frappe.session.user,
                        len(self.manual_item_prices),
                        item_price.item_code,
                        item_price.item_name or item_price.item_code,
                        flt(item_price.manual_raw_material_cost or 0),
                        flt(item_price.manual_operation_cost or 0),
                        flt(item_price.manual_overhead_cost or 0),
                        flt(item_price.manual_subcontracting_cost or 0),
                        flt(item_price.manual_labor_cost or 0),
                        flt(item_price.manual_electricity_cost or 0),
                        flt(item_price.manual_consumable_cost or 0),
                        flt(item_price.manual_rent_cost or 0),
                        flt(item_price.get('manual_overhead_additional_cost', 0)),
                        item_price.effective_date or frappe.utils.today(),
                        item_price.notes or '',
                        item_price.created_by or frappe.session.user,
                        item_price.last_updated or frappe.utils.now(),
                        self.name
                    ))
                    added_count += 1
            
            # به‌روزرسانی modified date سند اصلی
            frappe.db.sql("""
                UPDATE `tabAuto Price List`
                SET modified = NOW(), modified_by = %s
                WHERE name = %s
            """, (frappe.session.user, self.name))
            
            frappe.db.commit()
            
            message = f"✅ ذخیره مستقیم manual_item_prices کامل شد: {updated_count} به‌روزرسانی, {added_count} اضافه"
            frappe.logger("pricing").debug(message)
            
            return {
                "success": True,
                "message": message,
                "updated_count": updated_count,
                "added_count": added_count,
                "total_manual_prices": updated_count + added_count
            }
            
        except Exception as e:
            frappe.db.rollback()
            error_msg = f"خطا در ذخیره مستقیم manual_item_prices: {str(e)}"
            frappe.logger("pricing").debug(error_msg)
            return {
                "success": False,
                "message": error_msg,
                "error": str(e)
            }

    @frappe.whitelist()
    def get_raw_materials_report(self):
        """
        گزارش کامل مواد اولیه خام (بدون BOM) و قیمت‌هایشان
        """
        try:
            frappe.logger("pricing").debug("📊 شروع تهیه گزارش مواد اولیه خام")
            
            if not self.items:
                return {
                    "success": False,
                    "message": "هیچ آیتمی در لیست قیمت وجود ندارد"
                }
            
            # دریافت نقشه قیمت‌های دستی
            manual_prices_map = {}
            if hasattr(self, 'manual_item_prices') and self.manual_item_prices:
                for mp in self.manual_item_prices:
                    if mp.item_code:
                        manual_prices_map[mp.item_code] = mp
            
            raw_materials_summary = {}
            detailed_breakdown = []
            
            for item in self.items:
                if not item.item_code:
                    continue
                
                # دریافت مواد خام برای این آیتم
                raw_materials = self._get_deep_raw_materials(item.item_code, item.qty or 1)
                
                item_breakdown = {
                    'item_code': item.item_code,
                    'item_name': item.item_name or item.item_code,
                    'qty': item.qty or 1,
                    'raw_materials': [],
                    'total_raw_cost': 0
                }
                
                for raw_mat in raw_materials:
                    # دریافت قیمت از manual_item_prices یا قیمت پیش‌فرض
                    manual_price = manual_prices_map.get(raw_mat['item_code'])
                    
                    if manual_price and manual_price.manual_raw_material_cost:
                        unit_cost = manual_price.manual_raw_material_cost
                        price_source = 'دستی'
                    else:
                        # دریافت قیمت از Item Price یا Valuation Rate
                        unit_cost = self._get_item_rate(raw_mat['item_code'])
                        price_source = 'سیستم'
                    
                    total_cost = unit_cost * raw_mat['required_qty']
                    
                    raw_material_info = {
                        'item_code': raw_mat['item_code'],
                        'item_name': raw_mat['item_name'],
                        'required_qty': raw_mat['required_qty'],
                        'uom': raw_mat['uom'],
                        'unit_cost': unit_cost,
                        'total_cost': total_cost,
                        'price_source': price_source,
                        'manual_price_available': bool(manual_price)
                    }
                    
                    item_breakdown['raw_materials'].append(raw_material_info)
                    item_breakdown['total_raw_cost'] += total_cost
                    
                    # اضافه به خلاصه کلی
                    if raw_mat['item_code'] not in raw_materials_summary:
                        raw_materials_summary[raw_mat['item_code']] = {
                            'item_name': raw_mat['item_name'],
                            'total_required_qty': 0,
                            'uom': raw_mat['uom'],
                            'unit_cost': unit_cost,
                            'price_source': price_source,
                            'manual_price_available': bool(manual_price),
                            'used_in_items': []
                        }
                    
                    raw_materials_summary[raw_mat['item_code']]['total_required_qty'] += raw_mat['required_qty']
                    raw_materials_summary[raw_mat['item_code']]['used_in_items'].append({
                        'item_code': item.item_code,
                        'qty_needed': raw_mat['required_qty']
                    })
                
                detailed_breakdown.append(item_breakdown)
            
            # محاسبه آمار کلی
            total_raw_materials = len(raw_materials_summary)
            materials_with_manual_prices = len([rm for rm in raw_materials_summary.values() if rm['manual_price_available']])
            total_raw_materials_cost = sum([rm['total_required_qty'] * rm['unit_cost'] for rm in raw_materials_summary.values()])
            
            result = {
                "success": True,
                "summary": {
                    "total_items_analyzed": len(self.items),
                    "total_raw_materials": total_raw_materials,
                    "materials_with_manual_prices": materials_with_manual_prices,
                    "materials_with_system_prices": total_raw_materials - materials_with_manual_prices,
                    "total_raw_materials_cost": total_raw_materials_cost
                },
                "raw_materials_summary": raw_materials_summary,
                "detailed_breakdown": detailed_breakdown,
                "manual_prices_map": manual_prices_map
            }
            
            frappe.logger("pricing").debug(f"✅ گزارش مواد اولیه تهیه شد: {total_raw_materials} ماده خام")
            return result
            
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در تهیه گزارش مواد اولیه: {str(e)}")
            return {
                "success": False,
                "message": f"خطا در تهیه گزارش: {str(e)}"
            }
    
    def _get_deep_raw_materials(self, item_code, qty=1, processed_items=None):
        """
        دریافت مواد خام تا آخرین سطح (بدون BOM)
        """
        if processed_items is None:
            processed_items = set()
        
        # جلوگیری از حلقه بی‌نهایت
        if item_code in processed_items:
            return []
        
        processed_items.add(item_code)
        raw_materials = []
        
        # بررسی وجود BOM برای این آیتم
        bom_data = frappe.db.sql("""
            SELECT b.name, b.quantity
            FROM `tabBOM` b
            WHERE b.item = %s AND b.is_active = 1 AND b.is_default = 1
            ORDER BY b.creation DESC
            LIMIT 1
        """, (item_code,), as_dict=True)
        
        if not bom_data:
            # این آیتم BOM ندارد، پس ماده خام است
            item_info = frappe.db.get_value("Item", item_code, 
                                          ["item_name", "stock_uom"], as_dict=True)
            
            raw_materials.append({
                'item_code': item_code,
                'item_name': item_info.get('item_name', item_code) if item_info else item_code,
                'required_qty': qty,
                'uom': item_info.get('stock_uom', 'Nos') if item_info else 'Nos'
            })
            return raw_materials
        
        # این آیتم BOM دارد، باید به اجزای آن نگاه کنیم
        bom = bom_data[0]
        bom_qty = bom.quantity or 1
        
        # دریافت اجزای BOM
        bom_items = frappe.db.sql("""
            SELECT item_code, qty, uom
            FROM `tabBOM Item`
            WHERE parent = %s
        """, (bom.name,), as_dict=True)
        
        for bom_item in bom_items:
            # محاسبه مقدار مورد نیاز
            required_qty = (qty / bom_qty) * (bom_item.qty or 1)
            
            # بررسی عمقی این جزء
            sub_materials = self._get_deep_raw_materials(
                bom_item.item_code, 
                required_qty, 
                processed_items.copy()
            )
            raw_materials.extend(sub_materials)
        
        return raw_materials
    
    def _get_item_rate(self, item_code):
        """
        دریافت قیمت آیتم از Item Price یا Valuation Rate
        """
        try:
            # ابتدا از Item Price
            price = frappe.db.sql("""
                SELECT price_list_rate
                FROM `tabItem Price`
                WHERE item_code = %s AND selling = 1
                ORDER BY valid_from DESC, creation DESC
                LIMIT 1
            """, (item_code,), as_dict=True)
            
            if price and price[0].price_list_rate:
                return price[0].price_list_rate
            
            # اگر Item Price نداشت، از Valuation Rate
            valuation = frappe.db.get_value("Item", item_code, "valuation_rate")
            if valuation:
                return valuation
            
            # اگر هیچ کدام نداشت، صفر برگردان
            return 0
            
        except Exception:
            return 0
    
    def _save_manual_prices_direct_simple(self):
        """ذخیره ساده manual_material_prices"""
        try:
            # پاک کردن رکوردهای قبلی
            frappe.db.sql("""
                DELETE FROM `tabAuto Price List Manual Material Price`
                WHERE parent = %s
            """, (self.name,))
            
            # اضافه کردن رکوردهای جدید
            for idx, mp in enumerate(self.manual_material_prices, 1):
                if mp.item_code and (mp.manual_price or 0) > 0:
                    frappe.db.sql("""
                        INSERT INTO `tabAuto Price List Manual Material Price`
                        (name, parent, parenttype, parentfield, item_code, item_name, 
                         manual_price, effective_date, notes, idx, creation, modified, 
                         owner, modified_by, docstatus)
                        VALUES (%s, %s, 'Auto Price List', 'manual_material_prices', 
                                %s, %s, %s, %s, %s, %s, NOW(), NOW(), %s, %s, 0)
                    """, (
                        frappe.generate_hash(length=10),
                        self.name,
                        mp.item_code,
                        mp.get('item_name', mp.item_code),
                        mp.manual_price,
                        mp.get('effective_date', frappe.utils.today()),
                        mp.get('notes', ''),
                        idx,
                        frappe.session.user,
                        frappe.session.user
                    ))
            
            frappe.logger("pricing").debug(f"✅ {len(self.manual_material_prices)} رکورد manual_material_prices ذخیره شد")
            
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در ذخیره manual_material_prices: {str(e)}")
            raise
    
    def on_change(self):
        """Called when document fields change - غیرفعال برای جلوگیری از لاک"""
        # غیرفعال برای جلوگیری از محاسبات خودکار و لاک شدن
        pass

    def validate(self):
        """Validate the Auto Price List document"""
        # 🧪 LOG: Start of validate
        frappe.logger("pricing").debug(f"🔍 Python validate started for {self.name}. Items count: {len(self.items) if self.items else 0}")

        # Ported logic from original validate:
        # Request-Level Caching Initialization
        self._overhead_cache = None
        self._bom_op_cost_cache = {}
        self._workstation_cache = {}
        self._item_op_cost_cache = {}
        self._bom_name_cache = {}

        # 🛡️ GUARD: Prevent accidental deletion of items
        if not self.is_new() and not self.items:
            existing_count = frappe.db.count(
                'Auto Price List Item', 
                {'parent': self.name}
            )
            if existing_count > 0:
                frappe.logger("pricing").warning(
                    f"⚠️ VALIDATE GUARD: Client sent 0 items but DB has {existing_count} for {self.name}. Restoring."
                )
                self.items = []
                db_items = frappe.get_all(
                    'Auto Price List Item',
                    filters={'parent': self.name},
                    fields=['*'],
                    order_by='idx asc'
                )
                for db_item in db_items:
                    self.append('items', db_item)
        
        # برای duplicate: اگر سند جدیده و هنوز name نداره، validation چندگانه رو skip میکنیم
        if self.is_new() and not self.get('name'):
            self.validate_dates()
            self.calculate_total_interest_percentages()
            return

        self.validate_dates()
        self.validate_profit_margin()
        self.validate_installment_settings()
        self.calculate_total_interest_percentages()
        
    
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
        # 🧪 LOG: Start of before_save
        frappe.logger("pricing").debug(f"🔍 Python before_save started for {self.name}. Items count: {len(self.items) if self.items else 0}")
        
        # 🛡️ GUARD: Prevent accidental deletion of items
        if not self.is_new() and not self.items:
            existing_count = frappe.db.count(
                'Auto Price List Item', 
                {'parent': self.name}
            )
            if existing_count > 0:
                frappe.logger("pricing").warning(
                    f"⚠️ BEFORE_SAVE GUARD: Client sent 0 items but DB has {existing_count} for {self.name}. Restoring."
                )
                self.items = []
                db_items = frappe.get_all(
                    'Auto Price List Item',
                    filters={'parent': self.name},
                    fields=['*'],
                    order_by='idx asc'
                )
                for db_item in db_items:
                    self.append('items', db_item)
        
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
        به‌روزرسانی رکوردهای قیمت کالا با تمام فیلدهای هزینه و قیمت
        این تابع تمام فیلدهای محاسباتی را از Auto Price List Items به Item Price منتقل می‌کند
        """
        for item in self.items:
            # تهیه دیکشنری تمام فیلدهای قابل انتقال
            price_data = {
                "price_list_rate": flt(item.get("selling_price") or 0),
                "currency": frappe.defaults.get_global_default("currency"),
                # هزینه‌های مستقیم
                "raw_material_cost": flt(item.get("raw_material_cost") or 0),
                "electricity_cost": flt(item.get("electricity_cost") or 0),
                "consumable_cost": flt(item.get("consumable_cost") or 0),
                "rent_cost": flt(item.get("rent_cost") or 0),
                "labor_cost": flt(item.get("labor_cost") or 0),
                "operation_cost": flt(item.get("operation_cost") or 0),
                "overhead_cost": flt(item.get("overhead_cost") or 0),
                "total_cost": flt(item.get("total_cost") or 0),
                # قیمت‌ها و سود
                "selling_price": flt(item.get("selling_price") or 0),
                "profit_amount": flt(item.get("profit_amount") or 0),
                # قیمت بازار
                "current_market_price": flt(item.get("current_market_price") or 0),
                "profit_loss_status": item.get("profit_loss_status") or "",
                "profit_loss_amount": flt(item.get("profit_loss_amount") or 0),
                # کمیسیون
                "commission_amount": flt(item.get("commission_amount") or 0),
                "net_profit_after_commission": flt(item.get("net_profit_after_commission") or 0),
                # مارک آپ
                "final_price_with_markup": flt(item.get("final_price_with_markup") or 0),
                "required_markup_amount": flt(item.get("required_markup_amount") or 0),
                # جزئیات محاسباتی
                "base_cost_amount": flt(item.get("base_cost_amount") or 0),
                "profit_added_amount": flt(item.get("profit_added_amount") or 0),
                "interest_added_amount": flt(item.get("interest_added_amount") or 0),
                "commission_deduction_amount": flt(item.get("commission_deduction_amount") or 0),
                "markup_added_amount": flt(item.get("markup_added_amount") or 0),
                "rounding_adjustment_amount": flt(item.get("rounding_adjustment_amount") or 0),
                # اقساط
                "down_payment_amount": flt(item.get("down_payment_amount") or 0),
                "monthly_payment": flt(item.get("monthly_payment") or 0),
                "total_installment_amount": flt(item.get("total_installment_amount") or 0)
            }
            
            # Check if price exists
            existing_price = frappe.db.exists("Item Price", {
                "item_code": item.item_code,
                "price_list": self.price_list,
                "valid_from": self.valid_from,
                "valid_upto": self.valid_until
            })
            
            if existing_price:
                # Update existing price with all fields
                frappe.db.set_value("Item Price", existing_price, price_data)
            else:
                # Create new price with all fields
                new_price = {
                    "doctype": "Item Price",
                    "item_code": item.item_code,
                    "price_list": self.price_list,
                    "valid_from": self.valid_from,
                    "valid_upto": self.valid_until
                }
                new_price.update(price_data)
                frappe.get_doc(new_price).insert()

    @frappe.whitelist()
    def update_prices(self):
        """
        متد API برای به‌روزرسانی قیمت‌ها - قابل فراخوانی از JavaScript
        این متد برای دکمه‌های دستی استفاده می‌شود
        """
        try:
            if not self.items:
                return {
                    "success": False,
                    "message": "هیچ آیتمی برای به‌روزرسانی وجود ندارد"
                }
            
            created = 0
            updated = 0
            
            # Pre-fetch Item UOMs to allow smart upsert
            item_codes = [item.item_code for item in self.items if item.item_code]
            item_uom_map = {}
            if item_codes:
                items_data = frappe.get_all("Item", 
                    filters={"name": ["in", item_codes]}, 
                    fields=["name", "stock_uom"]
                )
                item_uom_map = {d.name: d.stock_uom for d in items_data}

            currency = frappe.db.get_value("Price List", self.price_list, "currency") or "IRR"
            
            for item in self.items:
                if not item.item_code:
                    continue
                    
                # قیمت نهایی
                selling_price = flt(item.final_selected_price or item.selling_price or 0)
                
                if selling_price <= 0:
                    continue
                
                target_uom = item_uom_map.get(item.item_code)
                
                # Find existing price with stricter matching (Item + Price List + UOM)
                # We sort by valid_from desc to update the "latest" one if multiple exist
                existing_prices = frappe.get_all("Item Price", 
                    filters={
                        "item_code": item.item_code,
                        "price_list": self.price_list,
                        "uom": target_uom
                    }, 
                    order_by="valid_from desc", 
                    limit=1,
                    pluck="name"
                )
                
                if existing_prices:
                    # به‌روزرسانی آخرین قیمت موجود برای همان واحد سنجش
                    price_name = existing_prices[0]
                    frappe.db.set_value("Item Price", price_name, "price_list_rate", selling_price)
                    updated += 1
                else:
                    # ایجاد قیمت جدید با واحد سنجش صحیح
                    item_price_doc = frappe.get_doc({
                        "doctype": "Item Price",
                        "item_code": item.item_code,
                        "price_list": self.price_list,
                        "price_list_rate": selling_price,
                        "currency": currency,
                        "uom": target_uom # Explicitly set UOM
                    })
                    item_price_doc.insert(ignore_permissions=True)
                    created += 1
            
            frappe.db.commit()
            
            return {
                "success": True,
                "message": f"✅ {created} قیمت ایجاد و {updated} قیمت به‌روزرسانی شد",
                "created": created,
                "updated": updated
            }
            
        except Exception as e:
            frappe.log_error(f"خطا در update_prices: {str(e)}")
            frappe.db.rollback()
            return {
                "success": False,
                "message": f"خطا: {str(e)}"
            }

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
    
    @frappe.whitelist()
    def cancel_document(self):
        """
        متد عمومی برای لغو سند - قابل فراخوانی از API
        """
        try:
            doc = frappe.get_doc("Auto Price List", self.name)
            if doc.docstatus == 1:
                doc.cancel()
                frappe.db.commit()
                return {
                    "success": True,
                    "message": "لیست قیمت با موفقیت لغو شد"
                }
            else:
                return {
                    "success": False,
                    "message": "فقط اسناد تأیید شده قابل لغو هستند"
                }
        except Exception as e:
            frappe.log_error(f"خطا در لغو Auto Price List: {str(e)}")
            return {
                "success": False,
                "message": f"خطا در لغو: {str(e)}"
            }

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
    
    def get_pricing_summary(self, item_code=None):
        """دریافت خلاصه محاسبات قیمت‌گذاری برای یک آیتم یا تمام آیتم‌ها"""
        if item_code:
            items = [item for item in self.items if item.item_code == item_code]
        else:
            items = self.items
        
        summary = []
        for item in items:
            if not item.item_code:
                continue
                
            item_summary = {
                'item_code': item.item_code,
                'item_name': item.item_name,
                'raw_material_cost': flt(item.raw_material_cost or 0),
                'operation_cost': flt(item.operation_cost or 0),
                'overhead_cost': flt(item.overhead_cost or 0),
                'total_cost': flt(item.total_cost or 0),
                'final_selected_price': flt(item.final_selected_price or 0),
                'profit_amount': flt(item.profit_amount or 0),
                'step_by_step_calculation': item.step_by_step_calculation or ""
            }
            
            # بررسی صحت محاسبات
            item_summary['calculation_valid'] = self.validate_pricing_calculations(item)
            
            summary.append(item_summary)
        
        return summary

    @frappe.whitelist()
    def fix_duplicate_cost_calculations(self):
        """
        تصحیح محاسبات تکراری هزینه‌ها
        این تابع همه operation_cost و overhead_cost را بر اساس جزئیات دوباره محاسبه می‌کند
        """
        try:
            frappe.logger("pricing").debug("🔧 شروع تصحیح محاسبات...")
            fixed_items = 0
            
            for item in self.items:
                if not item.item_code:
                    continue
                frappe.logger("pricing").debug(f"   overhead_cost فعلی={item.overhead_cost:,.0f}")
                
                # محاسبه صحیح operation_cost = کارگر + پیمانکاری
                calculated_operation = (
                    flt(item.labor_cost or 0) +
                    flt(item.subcontracting_cost or 0)
                )
                
                # محاسبه صحیح overhead_cost = برق + اجاره + مصرفی
                calculated_overhead = (
                    flt(item.electricity_cost or 0) +
                    flt(item.rent_cost or 0) +
                    flt(item.consumable_cost or 0)
                )
                
                changed = False
                
                # تصحیح operation_cost اگر لازم باشد
                if abs(calculated_operation - flt(item.operation_cost or 0)) > 1:
                    old_operation = item.operation_cost
                    item.operation_cost = calculated_operation
                    frappe.logger().warning(f"   ❌ operation_cost اشتباه بود: {old_operation:,.0f}")
                    frappe.logger("pricing").debug(f"   ✅ تصحیح شد به: {calculated_operation:,.0f}")
                    changed = True
                else:
                    frappe.logger("pricing").debug(f"   ✅ operation_cost درست است: {item.operation_cost:,.0f}")
                
                # تصحیح overhead_cost اگر لازم باشد
                if abs(calculated_overhead - flt(item.overhead_cost or 0)) > 1:
                    old_overhead = item.overhead_cost
                    item.overhead_cost = calculated_overhead
                    frappe.logger().warning(f"   ❌ overhead_cost اشتباه بود: {old_overhead:,.0f}")
                    frappe.logger("pricing").debug(f"   ✅ تصحیح شد به: {calculated_overhead:,.0f}")
                    changed = True
                else:
                    frappe.logger("pricing").debug(f"   ✅ overhead_cost درست است: {item.overhead_cost:,.0f}")
                
                if changed:
                    fixed_items += 1
                
                # محاسبه صحیح total_cost (فقط 3 جزء اصلی)
                correct_total = (
                    flt(item.raw_material_cost or 0) +
                    flt(item.operation_cost or 0) +
                    flt(item.overhead_cost or 0)
                )
                
                # تصحیح total_cost اگر لازم باشد
                if abs(correct_total - flt(item.total_cost or 0)) > 1:
                    old_total = item.total_cost
                    item.total_cost = correct_total
                    frappe.logger("pricing").debug(f"🔧 تصحیح total_cost برای {item.item_code}: {old_total:,.0f} → {correct_total:,.0f}")
                    fixed_items += 1
            
            # ذخیره تغییرات
            if fixed_items > 0:
                self.save()
                frappe.logger("pricing").debug(f"✅ {fixed_items} آیتم تصحیح شد")
                return {"success": True, "fixed_items": fixed_items}
            else:
                frappe.logger("pricing").debug("ℹ️ هیچ آیتمی نیاز به تصحیح نداشت")
                return {"success": True, "fixed_items": 0}
                
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در تصحیح محاسبات: {str(e)}")
            return {"success": False, "error": str(e)}

    @frappe.whitelist()
    def calculate_item_prices(self):
        """Wrapper method for JavaScript compatibility"""
        return self.calculate_item_prices_internal()
    
    # متد تکراری حذف شد - از متد خط 5138 استفاده می‌شود
    # @frappe.whitelist()
    # def update_item_prices_with_details(self):
    
    def _update_item_price_record_old(self, item):
        """
        Helper method to update Item Price record
        """
        import frappe
        from frappe.utils import flt
        
        if not self.price_list or not item.item_code:
            return
            
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
        
        # تنظیم قیمت اصلی
        item_price_doc.price_list_rate = flt(item.final_selected_price)
        
        # تنظیم واحد اندازه‌گیری
        item_uom = frappe.db.get_value("Item", item.item_code, "stock_uom")
        if item_uom:
            item_price_doc.uom = item_uom
        
        # تنظیم فیلدهای هزینه
        cost_fields = ['raw_material_cost', 'electricity_cost', 'consumable_cost', 
                      'rent_cost', 'labor_cost', 'operation_cost', 
                      'subcontracting_cost', 'overhead_cost', 'total_cost',
                      'selling_price', 'profit_amount']
        
        for field in cost_fields:
            if hasattr(item, field):
                setattr(item_price_doc, field, flt(getattr(item, field)))
        
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
            
            frappe.logger("pricing").debug(f"Item Price برای {item.item_code} با موفقیت ذخیره شد")
            
        except Exception as e:
            frappe.log_error(f"خطا در به‌روزرسانی Item Price برای {item.item_code}: {str(e)}")
            return False
        
        return True
            
            
    @frappe.whitelist()
    def get_items_bom_status(self):
        """
        بررسی وضعیت BOM فعال برای تمام محصولات در لیست
        برمی‌گرداند: 
        - لیست محصولاتی که BOM فعال ندارند (قرمز)
        - لیست محصولاتی که BOM دارند اما ارسال نشده (زرد)
        """
        try:
            items_without_bom = []  # قرمز - بدون BOM
            items_with_unsubmitted_bom = []  # زرد - BOM دارند اما ارسال نشده
            
            if not self.items:
                return {
                    "items_without_bom": [],
                    "items_with_unsubmitted_bom": []
                }
            
            for item in self.items:
                if not item.item_code:
                    continue
                
                # بررسی وجود BOM فعال و پیش‌فرض
                bom_data = frappe.db.get_value("BOM", {
                    "item": item.item_code,
                    "is_active": 1,
                    "is_default": 1
                }, ["name", "docstatus"], as_dict=True)
                
                if not bom_data:
                    # هیچ BOM فعال و پیش‌فرضی ندارد - قرمز
                    items_without_bom.append({
                        "item_code": item.item_code,
                        "item_name": item.item_name or item.item_code,
                        "idx": item.idx
                    })
                elif bom_data.docstatus == 0:
                    # BOM دارد اما ارسال نشده - زرد
                    items_with_unsubmitted_bom.append({
                        "item_code": item.item_code,
                        "item_name": item.item_name or item.item_code,
                        "idx": item.idx,
                        "bom_name": bom_data.name
                    })
            
            return {
                "items_without_bom": items_without_bom,
                "items_with_unsubmitted_bom": items_with_unsubmitted_bom,
                "total_items": len(self.items),
                "items_without_bom_count": len(items_without_bom),
                "items_with_unsubmitted_bom_count": len(items_with_unsubmitted_bom)
            }
            
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در بررسی وضعیت BOM: {str(e)}")
            return {
                "items_without_bom": [],
                "items_with_unsubmitted_bom": [],
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
            
            frappe.logger("pricing").debug(f"🔄 قیمت‌های جایگزینی مواد به‌روزرسانی شد: {updated_count} مورد")
            
            return {
                "message": f"قیمت‌های {updated_count} جایگزینی ماده با موفقیت به‌روزرسانی شد",
                "updated_count": updated_count
            }
            
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در به‌روزرسانی قیمت‌های جایگزینی مواد: {str(e)}")
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
                frappe.logger("pricing").debug(f"✋ قیمت دستی {item_code}: {manual_price}")
                return manual_price
            
            # 2. از Item Price فروش بگیر
            selling_price = frappe.db.get_value("Item Price", {
                "item_code": item_code,
                "selling": 1
            }, "price_list_rate")
            
            if selling_price and selling_price > 0:
                frappe.logger("pricing").debug(f"💰 قیمت فروش {item_code}: {selling_price}")
                return selling_price
            
            # 3. از Item Price خرید بگیر
            buying_price = frappe.db.get_value("Item Price", {
                "item_code": item_code,
                "buying": 1
            }, "price_list_rate")
            
            if buying_price and buying_price > 0:
                frappe.logger("pricing").debug(f"🛒 قیمت خرید {item_code}: {buying_price}")
                return buying_price
            
            # 4. از BOM محاسبه کن
            bom_cost = frappe.db.get_value("BOM", {
                "item": item_code,
                "is_active": 1,
                "is_default": 1
            }, "total_cost")
            
            if bom_cost and bom_cost > 0:
                frappe.logger("pricing").debug(f"🔧 هزینه BOM {item_code}: {bom_cost}")
                return bom_cost
            
            # 5. از Standard Rate کالا استفاده کن
            standard_rate = frappe.db.get_value("Item", item_code, "standard_rate")
            if standard_rate and standard_rate > 0:
                frappe.logger("pricing").debug(f"📊 نرخ استاندارد {item_code}: {standard_rate}")
                return standard_rate
            
            # 6. از Valuation Rate استفاده کن
            valuation_rate = frappe.db.get_value("Item", item_code, "valuation_rate")
            if valuation_rate and valuation_rate > 0:
                frappe.logger("pricing").debug(f"💎 نرخ ارزش‌گذاری {item_code}: {valuation_rate}")
                return valuation_rate
            
            # 7. از آخرین Purchase Receipt بگیر
            last_purchase_rate = self.get_last_purchase_rate(item_code)
            if last_purchase_rate and last_purchase_rate > 0:
                frappe.logger("pricing").debug(f"📦 آخرین قیمت خرید {item_code}: {last_purchase_rate}")
                return last_purchase_rate
            
            # 8. از Stock Ledger Entry بگیر
            stock_rate = self.get_stock_rate(item_code)
            if stock_rate and stock_rate > 0:
                frappe.logger("pricing").debug(f"📋 نرخ موجودی {item_code}: {stock_rate}")
                return stock_rate
            
            frappe.logger().warning(f"⚠️ هیچ قیمتی برای {item_code} یافت نشد")
            return 0
            
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در دریافت قیمت {item_code}: {str(e)}")
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
            frappe.logger("pricing").debug(f"خطا در دریافت قیمت دستی {item_code}: {str(e)}")
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
            frappe.logger("pricing").debug(f"خطا در تحلیل جایگزینی مواد: {str(e)}")
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
            frappe.logger("pricing").debug(f"خطا در دریافت آخرین قیمت خرید {item_code}: {str(e)}")
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
            frappe.logger("pricing").debug(f"خطا در دریافت نرخ موجودی {item_code}: {str(e)}")
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
            
            return {
                "message": f"{len(missing_materials)} ماده اولیه بدون قیمت شناسایی شد",
                "missing_count": len(missing_materials),
                "materials": list(missing_materials.keys())
            }
            
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در اسکن مواد اولیه بدون قیمت: {str(e)}")
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
            frappe.logger("pricing").debug(f"خطا در محاسبه قیمت پیشنهادی {item_code}: {str(e)}")
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
            
            # ذخیره تغییرات
            try:
                self.save(ignore_permissions=True)
                frappe.db.commit()
            except Exception as save_error:
                frappe.logger("pricing").debug(f"خطا در ذخیره تغییرات: {str(save_error)}")
                frappe.db.rollback()
                raise save_error
            
            # محاسبه مجدد قیمت‌ها برای تهیه گزارش تغییرات
            if applied_count > 0:
                try:
                    self.calculate_item_prices()
                except Exception as calc_error:
                    frappe.logger("pricing").debug(f"خطا در محاسبه مجدد قیمت‌ها: {str(calc_error)}")
                    # ادامه بدون محاسبه مجدد
                
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
            
            frappe.logger("pricing").debug(f"✅ قیمت‌های دستی اعمال شد: {applied_count} مورد")
            
            return {
                "success": True,
                "message": f"قیمت‌های دستی {applied_count} ماده اولیه با موفقیت اعمال شد",
                "applied_count": applied_count,
                "price_changes": price_changes,
                "refresh_needed": True
            }
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            frappe.logger("pricing").debug(f"خطا در اعمال قیمت‌های دستی مواد اولیه: {str(e)}")
            frappe.logger("pricing").debug(f"جزئیات خطا: {error_details}")
            
            # Rollback در صورت خطا
            frappe.db.rollback()
            
            return {
                "success": False,
                "message": f"خطا در اعمال قیمت‌های دستی: {str(e)}",
                "applied_count": 0,
                "error_details": str(e)
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
            frappe.logger("pricing").debug(f"خطا در تهیه گزارش تغییرات قیمت: {str(e)}")
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
            frappe.logger("pricing").debug(f"خطا در محاسبه هزینه بدون قیمت دستی {item_code}: {str(e)}")
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
            frappe.logger("pricing").debug(f"خطا در گرفتن قیمت بدون دستی {item_code}: {str(e)}")
            return 0



    @frappe.whitelist()
    def update_item_prices_with_details(self):
        """
        به‌روزرسانی قیمت‌ها با سیستم داینامیک - با Progress Bar
        """
        try:
            
            if not self.items:
                return {
                    "success": False,
                    "message": "هیچ آیتمی برای به‌روزرسانی وجود ندارد"
                }
            
            total_items = len(self.items)
            
            # ارسال پیام شروع
            frappe.publish_realtime(
                event='dynamic_pricing_progress',
                message={
                    'status': 'started',
                    'message': f'🚀 شروع محاسبه داینامیک قیمت برای {total_items} محصول',
                    'progress': 0,
                    'total': total_items
                },
                user=frappe.session.user
            )
            
            # بررسی و محاسبه بهای تمام شده
            items_without_cost = [item for item in self.items if not item.total_cost or item.total_cost <= 0]
            
            if items_without_cost:
                
                frappe.publish_realtime(
                    event='dynamic_pricing_progress',
                    message={
                        'status': 'calculating_costs',
                        'message': f'📊 در حال محاسبه بهای تمام شده برای {len(items_without_cost)} آیتم...',
                        'progress': 0,
                        'total': total_items
                    },
                    user=frappe.session.user
                )
                
                # محاسبه بهای تمام شده فقط برای آیتم‌های بدون هزینه
                for item in items_without_cost:
                    
                    if not item.raw_material_cost:
                        item.raw_material_cost = self.calculate_item_cost_with_exploded_items(item.item_code)
                    
                    self.calculate_operation_cost(item)
                    self.calculate_overhead_cost(item)
                    
                    item.total_cost = (
                        flt(item.raw_material_cost or 0) +
                        flt(item.operation_cost or 0) +
                        flt(item.overhead_cost or 0)
                    )
                
                # ذخیره تغییرات
                self._save_items_batch(self.items)
                self.reload()
            
            updated_count = 0
            errors = []
            
            # پردازش در دسته‌های کوچک برای جلوگیری از timeout
            batch_size = 10
            
            for i in range(0, len(self.items), batch_size):
                batch = self.items[i:i+batch_size]
                
                for idx, item in enumerate(batch, start=i):
                    if not item.item_code:
                        continue
                    
                    # بررسی اینکه آیتم قابل پردازش است
                    if not item.total_cost or item.total_cost <= 0:
                        
                        if not item.raw_material_cost:
                            item.raw_material_cost = self.calculate_item_cost_with_exploded_items(item.item_code)
                        
                        self.calculate_operation_cost(item)
                        self.calculate_overhead_cost(item)
                        
                        item.total_cost = (
                            flt(item.raw_material_cost or 0) +
                            flt(item.operation_cost or 0) +
                            flt(item.overhead_cost or 0)
                        )
                        
                        # Update in DB immediately
                        frappe.db.sql("""
                            UPDATE `tabAuto Price List Item`
                            SET 
                                raw_material_cost = %s,
                                operation_cost = %s,
                                overhead_cost = %s,
                                total_cost = %s,
                                modified = NOW()
                            WHERE name = %s
                        """, (
                            item.raw_material_cost or 0,
                            item.operation_cost or 0,
                            item.overhead_cost or 0,
                            item.total_cost or 0,
                            item.name
                        ))
                        
                        # If still zero, skip
                        if not item.total_cost or item.total_cost <= 0:
                            continue
                    
                    try:
                        # ارسال پیشرفت
                        frappe.publish_realtime(
                            event='dynamic_pricing_progress',
                            message={
                                'status': 'processing',
                                'message': f'💰 محاسبه قیمت داینامیک برای {item.item_code}',
                                'progress': idx + 1,
                                'total': total_items,
                                'current_item': item.item_code,
                                'percentage': round(((idx + 1) / total_items) * 100)
                            },
                            user=frappe.session.user
                        )
                        
                        # قیمت قبلی
                        old_price = flt(item.final_selected_price or item.selling_price or 0)
                        
                        # محاسبه قیمت جدید با pricing_steps
                        pricing_steps = self.get('pricing_steps') or []
                        
                        if pricing_steps:
                            # استفاده از سیستم داینامیک با pricing_steps
                            new_price, breakdown = self.calculate_price_with_steps(item, item.total_cost)
                            
                            # به‌روزرسانی فیلدهای breakdown
                            item.base_cost_amount = breakdown.get('base_cost', 0)
                            item.profit_added_amount = breakdown.get('profit_added', 0)
                            item.markup_added_amount = breakdown.get('markup_added', 0)
                            item.commission_deduction_amount = breakdown.get('commission_deducted', 0)
                            item.interest_added_amount = breakdown.get('interest_added', 0)
                            item.rounding_adjustment_amount = breakdown.get('rounding_adjustment', 0)
                        else:
                            # fallback: محاسبه ساده cost_plus
                            selected_type = self.get('selected_price_type') or 'cost_plus'
                            
                            if selected_type == 'cost_plus':
                                new_price = self.calculate_cost_plus_price(item)
                            elif selected_type == 'market_based':
                                new_price = self.calculate_market_based_price(item)
                            elif selected_type == 'dynamic':
                                new_price = self.calculate_dynamic_price(item)
                            else:
                                new_price = self.calculate_cost_plus_price(item)
                            
                            # Set base breakdown
                            item.base_cost_amount = item.total_cost
                            item.profit_added_amount = new_price - item.total_cost
                        
                        # رند کردن قیمت
                        rounding_method = self.get('rounding_method')
                        if rounding_method:
                            new_price = self.apply_rounding(new_price, rounding_method)
                        
                        # به‌روزرسانی فیلدها
                        item.final_selected_price = new_price
                        item.selling_price = new_price
                        
                        # محاسبه سود (اگر breakdown نداریم)
                        if not hasattr(item, 'base_cost_amount') or not item.base_cost_amount:
                            item.profit_amount = new_price - flt(item.total_cost or 0)
                        
                        # به‌روزرسانی در دیتابیس با breakdown fields
                        frappe.db.sql("""
                            UPDATE `tabAuto Price List Item` 
                            SET 
                                final_selected_price = %s,
                                selling_price = %s,
                                profit_amount = %s,
                                base_cost_amount = %s,
                                profit_added_amount = %s,
                                markup_added_amount = %s,
                                commission_deduction_amount = %s,
                                interest_added_amount = %s,
                                rounding_adjustment_amount = %s,
                                commission_amount = %s,
                                required_markup_amount = %s,
                                total_interest = %s,
                                modified = NOW()
                            WHERE name = %s
                        """, (
                            new_price,
                            new_price,
                            item.profit_amount or 0,
                            item.base_cost_amount or item.total_cost or 0,
                            item.profit_added_amount or 0,
                            item.markup_added_amount or 0,
                            item.commission_deduction_amount or 0,
                            item.interest_added_amount or 0,
                            item.rounding_adjustment_amount or 0,
                            getattr(item, 'commission_amount', 0) or 0,
                            getattr(item, 'required_markup_amount', 0) or 0,
                            getattr(item, 'total_interest', 0) or 0,
                            item.name
                        ))
                        
                        # به‌روزرسانی Item Price
                        self.update_item_price_record(item)
                        
                        updated_count += 1
                        
                    except Exception as item_error:
                        import traceback
                        error_msg = f"خطا در {item.item_code}: {str(item_error)}"
                        full_traceback = traceback.format_exc()
                        
                        # Log to console
                        frappe.logger("pricing").debug(error_msg)
                        frappe.logger("pricing").debug(full_traceback)
                        
                        # Log to Error Log in UI
                        frappe.log_error(
                            title=f"Dynamic Pricing Error - {item.item_code}",
                            message=f"{error_msg}\n\nFull Traceback:\n{full_traceback}"
                        )
                        
                        errors.append(error_msg)
                        continue
                
                # Commit هر دسته
                frappe.db.commit()
            
            # Commit نهایی
            frappe.db.commit()
            
            # به‌روزرسانی خودکار بسته‌های محصولات
            if self.product_bundles and len(self.product_bundles) > 0:
                frappe.publish_realtime(
                    event='dynamic_pricing_progress',
                    message={
                        'status': 'updating_bundles',
                        'message': '📦 در حال به‌روزرسانی بسته‌های محصولات...',
                        'progress': total_items,
                        'total': total_items
                    },
                    user=frappe.session.user
                )
                
                try:
                    # به‌روزرسانی قیمت‌های بسته‌ها
                    self._recalculate_existing_bundles()
                    frappe.db.commit()
                except Exception as bundle_error:
                    frappe.log_error(f"خطا در به‌روزرسانی بسته‌های محصولات: {str(bundle_error)}")
            
            # ارسال پیام پایان - همیشه!
            frappe.publish_realtime(
                event='dynamic_pricing_progress',
                message={
                    'status': 'completed',
                    'message': f'✅ محاسبه داینامیک قیمت تکمیل شد',
                    'progress': total_items,
                    'total': total_items,
                    'percentage': 100,
                    'updated_count': updated_count,
                    'errors_count': len(errors)
                },
                user=frappe.session.user
            )
            
            # پیام نهایی
            if updated_count > 0:
                message = f"🎉 قیمت {updated_count} محصول با موفقیت به‌روزرسانی شد"
                if errors:
                    message += f"\n⚠️ {len(errors)} خطا رخ داد"
                
                return {
                    "success": True,
                    "message": message,
                    "updated_items": updated_count,
                    "errors": errors if errors else None,
                    "refresh_needed": True
                }
            else:
                items_with_zero_cost = [item.item_code for item in self.items if not item.total_cost or item.total_cost <= 0]
                items_without_code = [i for i, item in enumerate(self.items) if not item.item_code]
                
                error_message = f"❌ هیچ آیتمی به‌روزرسانی نشد.\n\n"
                error_message += f"📊 تعداد کل آیتم‌ها: {len(self.items)}\n"
                error_message += f"📊 آیتم‌های با هزینه صفر: {len(items_with_zero_cost)}\n"
                
                if errors:
                    error_message += f"\n⚠️ تعداد خطاها: {len(errors)}\n"
                    # نمونه خطاها (فقط 5 تای اول)
                    error_message += f"\n🔍 نمونه خطاها:\n"
                    for err in errors[:5]:
                        error_message += f"  • {err}\n"
                    if len(errors) > 5:
                        error_message += f"  ... و {len(errors) - 5} خطای دیگر\n"
                    
                    error_message += f"\n💡 برای دیدن جزئیات کامل، Error Log را بررسی کنید."
                
                # Log a summary error
                frappe.log_error(
                    title=f"Dynamic Pricing Failed - No Items Updated",
                    message=f"{error_message}\n\nAll Errors:\n" + "\n".join(errors[:20])
                )
                
                
                # ارسال پیام خطا به UI
                frappe.publish_realtime(
                    event='dynamic_pricing_progress',
                    message={
                        'status': 'error',
                        'message': error_message,
                        'errors_count': len(errors)
                    },
                    user=frappe.session.user
                )
                
                return {
                    "success": False,
                    "message": error_message,
                    "errors": errors if errors else None,
                    "debug_info": {
                        "total_items": len(self.items),
                        "items_without_code": len(items_without_code),
                        "items_with_zero_cost": len(items_with_zero_cost),
                        "sample_zero_cost_items": items_with_zero_cost[:10],
                        "error_count": len(errors)
                    }
                }
            
        except Exception as e:
            error_msg = f"خطا در به‌روزرسانی قیمت‌ها: {str(e)}"
            import traceback
            frappe.logger("pricing").debug(traceback.format_exc())
            frappe.db.rollback()
            
            # ارسال پیام خطا
            frappe.publish_realtime(
                event='dynamic_pricing_progress',
                message={
                    'status': 'error',
                    'message': error_msg,
                    'error': str(e)
                },
                user=frappe.session.user
            )
            
            return {
                "success": False,
                "message": error_msg,
                "error": str(e)
            }
    
    def calculate_cost_plus_price(self, item):
        """محاسبه قیمت بر اساس هزینه + سود"""
        try:
            total_cost = flt(item.total_cost or 0)
            if total_cost <= 0:
                frappe.logger().warning(f"⚠️ {item.item_code}: total_cost صفر است")
                return 0
            
            profit_margin = flt(self.get('profit_margin') or 30) / 100
            new_price = total_cost * (1 + profit_margin)
            
            frappe.logger("pricing").debug(f"💰 {item.item_code}: cost={total_cost:,.0f}, margin={profit_margin*100:.1f}%, price={new_price:,.0f}")
            return new_price
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در محاسبه cost_plus برای {item.item_code}: {str(e)}")
            return flt(item.total_cost or 0)
    
    def calculate_market_based_price(self, item):
        """محاسبه قیمت بر اساس بازار"""
        try:
            compare_price_list = self.get('compare_with_price_list')
            if compare_price_list:
                market_price = frappe.db.get_value("Item Price", {
                    "item_code": item.item_code,
                    "price_list": compare_price_list
                }, "price_list_rate")
                
                if market_price and market_price > 0:
                    return flt(market_price) * 0.95  # 5% کمتر از قیمت بازار
            
            return self.calculate_cost_plus_price(item)
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در محاسبه market_based برای {item.item_code}: {str(e)}")
            return self.calculate_cost_plus_price(item)
    
    def calculate_dynamic_price(self, item):
        """محاسبه قیمت داینامیک"""
        try:
            base_price = self.calculate_cost_plus_price(item)
            market_price = self.calculate_market_based_price(item)
            
            # میانگین وزنی
            dynamic_price = (base_price * 0.7) + (market_price * 0.3)
            frappe.logger("pricing").debug(f"🔄 {item.item_code}: base={base_price:,.0f}, market={market_price:,.0f}, dynamic={dynamic_price:,.0f}")
            return dynamic_price
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در محاسبه dynamic برای {item.item_code}: {str(e)}")
            return self.calculate_cost_plus_price(item)
    
    def calculate_base_price(self, item):
        """محاسبه قیمت پایه"""
        return self.calculate_cost_plus_price(item)
    
    def calculate_price_with_steps(self, item, total_cost):
        """
        محاسبه قیمت با استفاده از pricing_steps و برگرداندن breakdown
        این wrapper بر روی calculate_price_based_on_steps موجود کار می‌کند
        """
        # ذخیره قیمت قبل از رند کردن
        price_before_rounding = flt(item.selling_price or total_cost)
        
        # استفاده از متد موجود برای محاسبه
        final_price, steps = self.calculate_price_based_on_steps(item, total_cost)
        
        # محاسبه صحیح rounding_adjustment
        # باید تفاوت قیمت قبل و بعد از آخرین مرحله رند کردن باشد
        rounding_adjustment = 0
        if hasattr(item, '_price_before_rounding'):
            rounding_adjustment = final_price - item._price_before_rounding
        
        # ایجاد breakdown از فیلدهای آیتم که توسط _apply_pricing_step پر شده‌اند
        breakdown = {
            'base_cost': total_cost,
            'profit_added': flt(item.profit_amount or 0),
            'markup_added': flt(item.required_markup_amount or 0),
            'commission_deducted': flt(item.commission_amount or 0),
            'interest_added': flt(item.total_interest or 0),
            'rounding_adjustment': rounding_adjustment
        }
        
        frappe.logger("pricing").debug(f"📊 Breakdown برای {item.item_code}:")
        frappe.logger("pricing").debug(f"   base_cost: {breakdown['base_cost']:,.0f}")
        frappe.logger("pricing").debug(f"   profit_added: {breakdown['profit_added']:,.0f}")
        frappe.logger("pricing").debug(f"   markup_added: {breakdown['markup_added']:,.0f}")
        frappe.logger("pricing").debug(f"   commission_deducted: {breakdown['commission_deducted']:,.0f}")
        frappe.logger("pricing").debug(f"   interest_added: {breakdown['interest_added']:,.0f}")
        frappe.logger("pricing").debug(f"   rounding_adjustment: {breakdown['rounding_adjustment']:,.0f}")
        
        return final_price, breakdown
    
    def apply_rounding(self, price, method):
        """اعمال رند کردن به قیمت"""
        if not method or method == 'none':
            return price
        elif method == 'round_100':
            return round(price / 100) * 100
        elif method == 'round_1000':
            return round(price / 1000) * 1000
        elif method == 'round_10000':
            return round(price / 10000) * 10000
        elif method == 'round_up_100':
            import math
            return math.ceil(price / 100) * 100
        elif method == 'round_up_1000':
            import math
            return math.ceil(price / 1000) * 1000
        else:
            return price
    
    def update_item_price_record(self, item):
        """به‌روزرسانی رکورد Item Price"""
        try:
            price_list = self.get('price_list')
            if not price_list or not item.item_code:
                return
            
            # بررسی وجود Item Price
            existing = frappe.db.get_value("Item Price", {
                "item_code": item.item_code,
                "price_list": price_list
            }, "name")
            
            if existing:
                # به‌روزرسانی مستقیم
                frappe.db.sql("""
                    UPDATE `tabItem Price`
                    SET 
                        price_list_rate = %s,
                        total_cost = %s,
                        raw_material_cost = %s,
                        operation_cost = %s,
                        overhead_cost = %s,
                        electricity_cost = %s,
                        rent_cost = %s,
                        labor_cost = %s,
                        consumable_cost = %s,
                        subcontracting_cost = %s,
                        modified = NOW()
                    WHERE name = %s
                """, (
                    flt(item.final_selected_price),
                    flt(item.total_cost),
                    flt(item.raw_material_cost),
                    flt(item.operation_cost),
                    flt(item.overhead_cost),
                    flt(item.electricity_cost),
                    flt(item.rent_cost),
                    flt(item.labor_cost),
                    flt(item.consumable_cost),
                    flt(item.subcontracting_cost),
                    existing
                ))
            else:
                # ایجاد رکورد جدید
                item_uom = frappe.db.get_value("Item", item.item_code, "stock_uom")
                
                frappe.db.sql("""
                    INSERT INTO `tabItem Price` (
                        name, item_code, price_list, price_list_rate, uom,
                        total_cost, raw_material_cost, operation_cost, overhead_cost,
                        electricity_cost, rent_cost, labor_cost, consumable_cost, subcontracting_cost,
                        creation, modified, owner, modified_by
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        NOW(), NOW(), %s, %s
                    )
                """, (
                    frappe.generate_hash(length=10),
                    item.item_code,
                    price_list,
                    flt(item.final_selected_price),
                    item_uom or 'Nos',
                    flt(item.total_cost),
                    flt(item.raw_material_cost),
                    flt(item.operation_cost),
                    flt(item.overhead_cost),
                    flt(item.electricity_cost),
                    flt(item.rent_cost),
                    flt(item.labor_cost),
                    flt(item.consumable_cost),
                    flt(item.subcontracting_cost),
                    frappe.session.user,
                    frappe.session.user
                ))
                
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در به‌روزرسانی Item Price برای {item.item_code}: {str(e)}")
            # ادامه بدون توقف
    
    @frappe.whitelist()
    def generate_price_change_analysis(self):
        """
        تولید گزارش تحلیل تغییرات قیمت
        مقایسه قیمت‌های فعلی با قیمت‌های قبلی و نمایش محصولات جایگزین
        """
        try:
            if not self.items:
                return {
                    "success": False,
                    "message": "هیچ آیتمی برای تحلیل وجود ندارد"
                }
            
            analysis_data = []
            
            for item in self.items:
                if not item.item_code:
                    continue
                
                # دریافت داده‌های قبلی از Item Price
                previous_data = self._get_previous_item_data(item.item_code)
                
                # محاسبه تغییرات
                cost_change = flt(item.total_cost) - flt(previous_data.get('total_cost', 0))
                price_change = flt(item.final_selected_price) - flt(previous_data.get('price_list_rate', 0))
                
                cost_change_percent = 0
                if previous_data.get('total_cost'):
                    cost_change_percent = (cost_change / flt(previous_data['total_cost'])) * 100
                
                # دریافت محصولات جایگزین
                substitute_data = self._get_substitute_items_data(item.item_code)
                
                # تعیین وضعیت رقابتی
                competitive_status = self._determine_competitive_status(
                    item.final_selected_price, 
                    substitute_data.get('avg_price', 0)
                )
                
                # تعیین دلیل تغییر
                change_reason = self._determine_change_reason(item, previous_data)
                
                analysis_data.append({
                    'item_code': item.item_code,
                    'item_name': item.item_name,
                    'previous_total_cost': previous_data.get('total_cost', 0),
                    'current_total_cost': item.total_cost,
                    'cost_change': cost_change,
                    'cost_change_percent': cost_change_percent,
                    'previous_selling_price': previous_data.get('price_list_rate', 0),
                    'current_selling_price': item.final_selected_price,
                    'price_change': price_change,
                    'substitute_items': substitute_data.get('items_list', ''),
                    'substitute_avg_price': substitute_data.get('avg_price', 0),
                    'competitive_status': competitive_status,
                    'change_reason': change_reason
                })
            
            return {
                "success": True,
                "data": analysis_data,
                "message": f"تحلیل تغییرات قیمت برای {len(analysis_data)} آیتم تولید شد"
            }
            
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در تولید تحلیل تغییرات قیمت: {str(e)}")
            return {
                "success": False,
                "message": f"خطا در تولید تحلیل: {str(e)}"
            }
    
    def _get_previous_item_data(self, item_code):
        """دریافت داده‌های قبلی آیتم از Item Price"""
        try:
            previous_price = frappe.db.sql("""
                SELECT 
                    price_list_rate,
                    total_cost,
                    raw_material_cost,
                    operation_cost,
                    overhead_cost,
                    electricity_cost,
                    rent_cost,
                    labor_cost,
                    subcontracting_cost
                FROM `tabItem Price`
                WHERE item_code = %s
                AND price_list = %s
                ORDER BY modified DESC
                LIMIT 1
            """, (item_code, self.price_list), as_dict=True)
            
            if previous_price:
                return previous_price[0]
            
            # اگر در Item Price نبود، از Item master بگیر
            item_data = frappe.db.get_value("Item", item_code, 
                                           ["standard_rate"], as_dict=True)
            
            return {
                'price_list_rate': item_data.get('standard_rate', 0) if item_data else 0,
                'total_cost': 0
            }
            
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در دریافت داده‌های قبلی {item_code}: {str(e)}")
            return {'price_list_rate': 0, 'total_cost': 0}
    
    def _get_substitute_items_data(self, item_code):
        """دریافت محصولات جایگزین و متوسط قیمت آنها"""
        try:
            # دریافت گروه آیتم
            item_group = frappe.db.get_value("Item", item_code, "item_group")
            if not item_group:
                return {'items_list': '', 'avg_price': 0}
            
            # جستجو برای آیتم‌های مشابه در همان گروه
            substitutes = frappe.db.sql("""
                SELECT 
                    i.item_code,
                    i.item_name,
                    COALESCE(ip.price_list_rate, i.standard_rate, 0) as price
                FROM `tabItem` i
                LEFT JOIN `tabItem Price` ip ON i.item_code = ip.item_code 
                    AND ip.price_list = %s
                WHERE i.item_group = %s 
                AND i.item_code != %s
                AND i.disabled = 0
                AND (ip.price_list_rate > 0 OR i.standard_rate > 0)
                ORDER BY price
                LIMIT 5
            """, (self.price_list, item_group, item_code), as_dict=True)
            
            if not substitutes:
                return {'items_list': '', 'avg_price': 0}
            
            # محاسبه متوسط قیمت
            total_price = sum(flt(sub.price) for sub in substitutes)
            avg_price = total_price / len(substitutes) if substitutes else 0
            
            # ایجاد لیست نام‌ها
            items_list = ', '.join([sub.item_code for sub in substitutes[:3]])
            if len(substitutes) > 3:
                items_list += f" و {len(substitutes) - 3} مورد دیگر"
            
            return {
                'items_list': items_list,
                'avg_price': avg_price
            }
            
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در دریافت محصولات جایگزین {item_code}: {str(e)}")
            return {'items_list': '', 'avg_price': 0}
    
    def _determine_competitive_status(self, current_price, substitute_avg_price):
        """تعیین وضعیت رقابتی"""
        if not substitute_avg_price:
            return "بدون رقیب"
        
        price_diff_percent = ((flt(current_price) - flt(substitute_avg_price)) / flt(substitute_avg_price)) * 100
        
        if price_diff_percent <= -10:
            return "بسیار رقابتی"
        elif price_diff_percent <= -5:
            return "رقابتی"
        elif price_diff_percent <= 5:
            return "متعادل"
        elif price_diff_percent <= 15:
            return "گران"
        else:
            return "بسیار گران"
    
    def _determine_change_reason(self, current_item, previous_data):
        """تعیین دلیل اصلی تغییر قیمت"""
        reasons = []
        
        # بررسی تغییر مواد اولیه
        prev_material = flt(previous_data.get('raw_material_cost', 0))
        curr_material = flt(current_item.raw_material_cost or 0)
        if abs(curr_material - prev_material) > 100:  # تغییر بیش از 100 واحد
            if curr_material > prev_material:
                reasons.append("افزایش مواد اولیه")
            else:
                reasons.append("کاهش مواد اولیه")
        
        # بررسی تغییر هزینه‌های عملیاتی
        prev_operation = flt(previous_data.get('operation_cost', 0))
        curr_operation = flt(current_item.operation_cost or 0)
        if abs(curr_operation - prev_operation) > 50:
            if curr_operation > prev_operation:
                reasons.append("افزایش هزینه عملیات")
            else:
                reasons.append("کاهش هزینه عملیات")
        
        # بررسی تغییر سربار
        prev_overhead = flt(previous_data.get('overhead_cost', 0))
        curr_overhead = flt(current_item.overhead_cost or 0)
        if abs(curr_overhead - prev_overhead) > 50:
            if curr_overhead > prev_overhead:
                reasons.append("افزایش سربار")
            else:
                reasons.append("کاهش سربار")
        
        # بررسی تغییر هزینه پیمانکاری
        prev_subcontracting = flt(previous_data.get('subcontracting_cost', 0))
        curr_subcontracting = flt(current_item.subcontracting_cost or 0)
        if abs(curr_subcontracting - prev_subcontracting) > 50:
            if curr_subcontracting > prev_subcontracting:
                reasons.append("افزایش پیمانکاری")
            else:
                reasons.append("کاهش پیمانکاری")
        
        if not reasons:
            return "تغییر جزئی"
        
        return " + ".join(reasons[:2])  # حداکثر 2 دلیل اصلی
    
    @frappe.whitelist()
    def calculate_breakeven_analysis(self):
        """
        محاسبه تحلیل نقطه سر به سر با درصدهای سود مختلف
        محاسبه حجم فروش مورد نیاز برای پوشش هزینه‌های ثابت
        """
        try:
            if not self.items:
                return {
                    "success": False,
                    "message": "هیچ آیتمی برای تحلیل وجود ندارد"
                }
            
            # دریافت هزینه‌های ثابت ماهانه
            monthly_fixed_costs = self._get_monthly_fixed_costs()
            
            # درصدهای سود برای تحلیل
            profit_margins = [5, 10, 15, 20, 25, 30]
            
            breakeven_data = []
            
            for profit_margin in profit_margins:
                # محاسبه متوسط مارجین سود واحد برای تمام محصولات
                total_unit_margin = 0
                valid_items_count = 0
                
                for item in self.items:
                    if not item.item_code or not item.total_cost:
                        continue
                    
                    # محاسبه قیمت فروش با این درصد سود
                    selling_price = flt(item.total_cost) * (1 + profit_margin / 100)
                    
                    # مارجین سود واحد (قیمت فروش - بهای تمام شده)
                    unit_margin = selling_price - flt(item.total_cost)
                    total_unit_margin += unit_margin
                    valid_items_count += 1
                
                if valid_items_count == 0:
                    continue
                
                # متوسط مارجین واحد
                avg_unit_margin = total_unit_margin / valid_items_count
                
                # حجم فروش مورد نیاز برای پوشش هزینه‌های ثابت
                if avg_unit_margin > 0:
                    required_units = monthly_fixed_costs / avg_unit_margin
                    required_revenue = required_units * (total_unit_margin / valid_items_count + 
                                                        sum(flt(item.total_cost) for item in self.items if item.total_cost) / valid_items_count)
                else:
                    required_units = 0
                    required_revenue = 0
                
                breakeven_data.append({
                    'profit_margin': profit_margin,
                    'avg_unit_margin': avg_unit_margin,
                    'required_units_monthly': required_units,
                    'required_revenue_monthly': required_revenue,
                    'required_units_daily': required_units / 30,
                    'monthly_fixed_costs': monthly_fixed_costs
                })
            
            # محاسبه تحلیل تفصیلی برای هر محصول
            detailed_analysis = self._calculate_detailed_breakeven_analysis(monthly_fixed_costs)
            
            return {
                "success": True,
                "breakeven_summary": breakeven_data,
                "detailed_analysis": detailed_analysis,
                "monthly_fixed_costs": monthly_fixed_costs,
                "message": f"تحلیل نقطه سر به سر برای {len(profit_margins)} درصد سود محاسبه شد"
            }
            
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در محاسبه تحلیل نقطه سر به سر: {str(e)}")
            return {
                "success": False,
                "message": f"خطا در محاسبه تحلیل: {str(e)}"
            }
    
    def _get_monthly_fixed_costs(self):
        """دریافت هزینه‌های ثابت ماهانه"""
        try:
            # از فیلدهای هزینه ثابت در Auto Price List
            fixed_costs = 0
            
            # هزینه‌های ثابت ماهانه از فیلدهای موجود
            if hasattr(self, 'monthly_fixed_costs') and self.monthly_fixed_costs:
                fixed_costs += flt(self.monthly_fixed_costs)
            
            # اگر فیلد مستقیم وجود ندارد، از روش قبلی استفاده کن
            if fixed_costs == 0:
                # محاسبه از هزینه‌های سربار و عملیاتی
                total_overhead = sum(flt(item.overhead_cost or 0) for item in self.items if item.overhead_cost)
                
                # تخمین هزینه‌های ثابت بر اساس سربار
                if total_overhead > 0:
                    # فرض کنیم که 60% سربار هزینه ثابت است
                    fixed_costs = total_overhead * 0.6
                else:
                    # مقدار پیش‌فرض برای هزینه‌های ثابت
                    fixed_costs = 10000000  # 10 میلیون تومان
            
            return fixed_costs
            
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در دریافت هزینه‌های ثابت: {str(e)}")
            return 10000000  # مقدار پیش‌فرض
    
    def _calculate_detailed_breakeven_analysis(self, monthly_fixed_costs):
        """محاسبه تحلیل تفصیلی برای هر محصول"""
        detailed_analysis = []
        
        for item in self.items:
            if not item.item_code or not item.total_cost:
                continue
            
            item_analysis = {
                'item_code': item.item_code,
                'item_name': item.item_name,
                'total_cost': item.total_cost,
                'profit_scenarios': []
            }
            
            # محاسبه برای درصدهای سود مختلف
            for profit_margin in [10, 15, 20, 25, 30]:
                selling_price = flt(item.total_cost) * (1 + profit_margin / 100)
                unit_margin = selling_price - flt(item.total_cost)
                
                # فرض کنیم این محصول باید تمام هزینه‌های ثابت را پوشش دهد
                if unit_margin > 0:
                    required_units = monthly_fixed_costs / unit_margin
                    required_revenue = required_units * selling_price
                else:
                    required_units = 0
                    required_revenue = 0
                
                item_analysis['profit_scenarios'].append({
                    'profit_margin': profit_margin,
                    'selling_price': selling_price,
                    'unit_margin': unit_margin,
                    'required_units_monthly': required_units,
                    'required_revenue_monthly': required_revenue,
                    'required_units_daily': required_units / 30
                })
            
            detailed_analysis.append(item_analysis)
        
        return detailed_analysis
    
    @frappe.whitelist()
    def apply_bulk_pricing(self, pricing_data):
        """
        اعمال قیمت‌گذاری دسته‌ای با مدیریت بهتر تراکنش
        حل مشکل database lock timeout
        """
        try:
            if isinstance(pricing_data, str):
                import json
                pricing_data = json.loads(pricing_data)
            
            if not pricing_data:
                return {
                    "success": False,
                    "message": "هیچ داده‌ای برای قیمت‌گذاری ارسال نشده"
                }
            
            frappe.logger("pricing").debug(f"📦 شروع اعمال قیمت‌گذاری دسته‌ای برای {len(pricing_data)} آیتم")
            
            # حذف reload برای جلوگیری از لاک شدن
            # self.reload()  # غیرفعال برای جلوگیری از لاک
            
            # آماده‌سازی manual_material_prices اگر وجود ندارد
            if not hasattr(self, 'manual_material_prices') or self.manual_material_prices is None:
                self.manual_material_prices = []
            
            updated_count = 0
            added_count = 0
            
            # پردازش هر آیتم قیمت‌گذاری
            for item_data in pricing_data:
                item_code = item_data.get('item_code')
                manual_price = flt(item_data.get('manual_price', 0))
                
                if not item_code or manual_price <= 0:
                    continue
                
                # جستجو برای رکورد موجود
                existing_record = None
                for mp in self.manual_material_prices:
                    if mp.item_code == item_code:
                        existing_record = mp
                        break
                
                if existing_record:
                    # به‌روزرسانی رکورد موجود
                    existing_record.manual_price = manual_price
                    existing_record.item_name = item_data.get('item_name', existing_record.item_name)
                    existing_record.notes = item_data.get('notes', f"به‌روزرسانی شده در {frappe.utils.now()}")
                    updated_count += 1
                    frappe.logger("pricing").debug(f"🔄 به‌روزرسانی {item_code}: {manual_price:,.0f}")
                else:
                    # اضافه کردن رکورد جدید
                    new_record = {
                        'item_code': item_code,
                        'item_name': item_data.get('item_name', item_code),
                        'manual_price': manual_price,
                        'effective_date': item_data.get('effective_date', frappe.utils.today()),
                        'notes': item_data.get('notes', f"اضافه شده در {frappe.utils.now()}")
                    }
                    self.append('manual_material_prices', new_record)
                    added_count += 1
                    frappe.logger("pricing").debug(f"➕ اضافه {item_code}: {manual_price:,.0f}")
            
            # ابتدا قیمت‌ها را به manual_item_prices اضافه کن
            try:
                manual_result = self._save_to_manual_item_prices_table(pricing_data)
                if not manual_result.get('success'):
                    return manual_result
                
                # حالا قیمت‌ها را از manual_item_prices به items اعمال کن
                return self._apply_manual_prices_to_items()
                
                
            except Exception as save_error:
                frappe.db.rollback()
                error_msg = f"خطا در ذخیره قیمت‌های دستی: {str(save_error)}"
                frappe.logger("pricing").debug(error_msg)
                
                return {
                    "success": False,
                    "message": error_msg,
                    "error": str(save_error)
                }
                
        except Exception as e:
            frappe.db.rollback()
            error_msg = f"خطا در اعمال قیمت‌گذاری دسته‌ای: {str(e)}"
            frappe.logger("pricing").debug(error_msg)
            import traceback
            frappe.logger("pricing").debug(f"جزئیات خطا: {traceback.format_exc()}")
            
            return {
                "success": False,
                "message": error_msg,
                "error": str(e)
            }
    
    def _save_manual_prices_direct(self, pricing_data):
        """
        ذخیره مستقیم قیمت‌های دستی با SQL و به‌روزرسانی total_cost
        """
        try:
            frappe.logger("pricing").debug("🔧 تلاش برای ذخیره مستقیم قیمت‌های دستی")
            
            updated_count = 0
            added_count = 0
            items_to_recalculate = []
            
            for item_data in pricing_data:
                item_code = item_data.get('item_code')
                manual_price = flt(item_data.get('manual_price', 0))
                
                if not item_code or manual_price <= 0:
                    continue
                
                # بررسی وجود رکورد
                existing = frappe.db.sql("""
                    SELECT name FROM `tabAuto Price List Manual Material Price`
                    WHERE parent = %s AND item_code = %s
                    LIMIT 1
                """, (self.name, item_code))
                
                if existing:
                    # به‌روزرسانی رکورد موجود
                    frappe.db.sql("""
                        UPDATE `tabAuto Price List Manual Material Price`
                        SET manual_price = %s, modified = NOW()
                        WHERE parent = %s AND item_code = %s
                    """, (manual_price, self.name, item_code))
                    updated_count += 1
                else:
                    # اضافه کردن رکورد جدید
                    frappe.db.sql("""
                        INSERT INTO `tabAuto Price List Manual Material Price`
                        (name, parent, parenttype, parentfield, item_code, item_name, manual_price, 
                         effective_date, notes, creation, modified, owner, modified_by, docstatus, idx)
                        VALUES (%s, %s, 'Auto Price List', 'manual_material_prices', %s, %s, %s, %s, %s, 
                                NOW(), NOW(), %s, %s, 0, 
                                (SELECT COALESCE(MAX(idx), 0) + 1 FROM `tabAuto Price List Manual Material Price` 
                                 WHERE parent = %s))
                    """, (
                        frappe.generate_hash(length=10),
                        self.name,
                        item_code,
                        item_data.get('item_name', item_code),
                        manual_price,
                        item_data.get('effective_date', frappe.utils.today()),
                        item_data.get('notes', f"اضافه شده در {frappe.utils.now()}"),
                        frappe.session.user,
                        frappe.session.user,
                        self.name
                    ))
                    added_count += 1
                
                # اضافه به لیست بازمحاسبه total_cost
                items_to_recalculate.append({
                    'item_code': item_code,
                    'manual_price': manual_price
                })
            
            # به‌روزرسانی total_cost برای آیتم‌های تغییر یافته
            self._update_total_costs_for_manual_prices(items_to_recalculate)
            
            frappe.db.commit()
            
            # بارگذاری مجدد سند برای نمایش تغییرات
            # self.reload()  # غیرفعال برای جلوگیری از لاک
            
            message = f"🔧 قیمت‌گذاری مستقیم با موفقیت اعمال شد: {updated_count} به‌روزرسانی, {added_count} اضافه"
            frappe.logger("pricing").debug(message)
            
            return {
                "success": True,
                "message": message,
                "updated_count": updated_count,
                "added_count": added_count,
                "method": "direct_sql"
            }
            
        except Exception as e:
            frappe.db.rollback()
            error_msg = f"خطا در ذخیره مستقیم: {str(e)}"
            frappe.logger("pricing").debug(error_msg)
            
            return {
                "success": False,
                "message": error_msg,
                "error": str(e)
            }
    
    def _update_total_costs_for_manual_prices(self, items_to_recalculate):
        """
        به‌روزرسانی total_cost برای آیتم‌هایی که قیمت دستی تغییر کرده
        """
        try:
            if not items_to_recalculate:
                return
            
            frappe.logger("pricing").debug(f"📊 به‌روزرسانی total_cost برای {len(items_to_recalculate)} آیتم")
            
            for item_info in items_to_recalculate:
                item_code = item_info['item_code']
                manual_price = item_info['manual_price']
                
                # پیدا کردن آیتم در لیست items
                for item in self.items:
                    if item.item_code == item_code:
                        # محاسبه مجدد total_cost با قیمت دستی جدید
                        old_raw_material_cost = flt(item.raw_material_cost or 0)
                        
                        # به‌روزرسانی raw_material_cost با قیمت دستی
                        item.raw_material_cost = manual_price
                        
                        # محاسبه مجدد total_cost
                        item.total_cost = (
                            flt(item.raw_material_cost or 0) +
                            flt(item.operation_cost or 0) +
                            flt(item.overhead_cost or 0)
                        )
                        
                        # محاسبه مجدد قیمت نهایی
                        if hasattr(item, 'final_selected_price'):
                            profit_margin = flt(self.profit_margin or 0) / 100
                            item.final_selected_price = item.total_cost * (1 + profit_margin)
                        
                        # به‌روزرسانی در دیتابیس
                        frappe.db.sql("""
                            UPDATE `tabAuto Price List Item`
                            SET raw_material_cost = %s, total_cost = %s, 
                                final_selected_price = %s, modified = NOW()
                            WHERE parent = %s AND item_code = %s
                        """, (
                            item.raw_material_cost,
                            item.total_cost,
                            item.final_selected_price,
                            self.name,
                            item_code
                        ))
                        
                        frappe.logger("pricing").debug(f"✅ به‌روزرسانی {item_code}: raw_material_cost={manual_price:,.0f}, total_cost={item.total_cost:,.0f}")
                        break
                        
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در به‌روزرسانی total_cost: {str(e)}")
            # ادامه عملیات حتی در صورت خطا
    
    def _save_to_manual_item_prices_table(self, pricing_data):
        """
        ذخیره قیمت‌های دستی در جدول جدید manual_item_prices
        این جدول قیمت‌ها را به صورت دائمی نگه می‌دارد
        """
        try:
            frappe.logger("pricing").debug(f"💾 ذخیره در جدول manual_item_prices برای {len(pricing_data)} آیتم")
            
            # آماده‌سازی manual_item_prices اگر وجود ندارد
            if not hasattr(self, 'manual_item_prices') or self.manual_item_prices is None:
                self.manual_item_prices = []
            
            updated_count = 0
            added_count = 0
            
            for item_data in pricing_data:
                item_code = item_data.get('item_code')
                manual_price = flt(item_data.get('manual_price', 0))
                
                if not item_code or manual_price <= 0:
                    continue
                
                # جستجو برای رکورد موجود
                existing_record = None
                for manual_item in self.manual_item_prices:
                    if manual_item.item_code == item_code:
                        existing_record = manual_item
                        break
                
                if existing_record:
                    # به‌روزرسانی رکورد موجود
                    existing_record.manual_raw_material_cost = manual_price
                    existing_record.manual_operation_cost = item_data.get('operation_cost', 0)
                    existing_record.manual_overhead_cost = item_data.get('overhead_cost', 0)
                    existing_record.notes = item_data.get('notes', f"به‌روزرسانی در {frappe.utils.now()}")
                    existing_record.last_updated = frappe.utils.now()
                    updated_count += 1
                    frappe.logger("pricing").debug(f"🔄 به‌روزرسانی {item_code}: {manual_price:,.0f}")
                else:
                    # ایجاد رکورد جدید
                    new_record = {
                        'item_code': item_code,
                        'item_name': item_data.get('item_name', item_code),
                        'manual_raw_material_cost': manual_price,
                        'manual_operation_cost': item_data.get('operation_cost', 0),
                        'manual_overhead_cost': item_data.get('overhead_cost', 0),
                        'effective_date': item_data.get('effective_date', frappe.utils.today()),
                        'notes': item_data.get('notes', f"اضافه شده در {frappe.utils.now()}"),
                        'created_by': frappe.session.user,
                        'last_updated': frappe.utils.now()
                    }
                    self.append('manual_item_prices', new_record)
                    added_count += 1
                    frappe.logger("pricing").debug(f"➕ اضافه {item_code}: {manual_price:,.0f}")
            
            # ذخیره سند
            self.save(ignore_permissions=True)
            
            message = f"✅ قیمت‌های دستی با موفقیت ذخیره شد: {updated_count} به‌روزرسانی, {added_count} اضافه"
            frappe.logger("pricing").debug(message)
            
            return {
                "success": True,
                "message": message,
                "updated_count": updated_count,
                "added_count": added_count,
                "total_manual_prices": len(self.manual_item_prices)
            }
            
        except Exception as e:
            frappe.db.rollback()
            error_msg = f"خطا در ذخیره جدول manual_item_prices: {str(e)}"
            frappe.logger("pricing").debug(error_msg)
            
            return {
                "success": False,
                "message": error_msg,
                "error": str(e)
            }
    
    def _get_manual_item_price(self, item_code):
        """
        دریافت قیمت دستی از جدول manual_item_prices
        ⚠️ هر فیلدی که صفر باشد، نادیده گرفته می‌شود و از BOM محاسبه می‌شود
        فقط فیلدهایی که مقدار مثبت دارند دستی محسوب می‌شوند
        برمیگردونه: dict با فیلدهای دستی یا None
        بهینه‌سازی شده: ابتدا از cache چک می‌کند
        """
        try:
            # اول از cache چک کن
            cached = self._get_cached_manual_price(item_code)
            if cached:
                # فیلتر کردن فیلدهای None و صفر
                return {k: v for k, v in cached.items() if v and v > 0} or None
            
            if not hasattr(self, 'manual_item_prices') or not self.manual_item_prices:
                return None
            
            for manual_item in self.manual_item_prices:
                if manual_item.item_code == item_code:
                    # فقط فیلدهایی که مقدار مثبت دارند رو برگردون
                    manual_costs = {}
                    
                    # ⚠️ صفر = نادیده گرفته شود، فقط مقادیر مثبت دستی محسوب می‌شوند
                    raw_material_cost = flt(manual_item.get('manual_raw_material_cost', 0))
                    if raw_material_cost > 0:
                        manual_costs['raw_material_cost'] = raw_material_cost
                        frappe.logger("pricing").debug(f"   🔧 هزینه مواد اولیه دستی: {raw_material_cost:,.0f}")
                    
                    operation_cost = flt(manual_item.get('manual_operation_cost', 0))
                    if operation_cost > 0:
                        manual_costs['operation_cost'] = operation_cost
                        frappe.logger("pricing").debug(f"   🔧 هزینه عملیات دستی: {operation_cost:,.0f}")
                    
                    # هزینه سربار (شامل سربار اضافی)
                    overhead_main = flt(manual_item.get('manual_overhead_cost', 0))
                    overhead_additional = flt(manual_item.get('manual_overhead_additional_cost', 0))
                    overhead_total = overhead_main + overhead_additional
                    if overhead_total > 0:
                        manual_costs['overhead_cost'] = overhead_total
                        frappe.logger("pricing").debug(f"   🔧 هزینه سربار دستی: {overhead_total:,.0f}")
                    
                    subcontracting_cost = flt(manual_item.get('manual_subcontracting_cost', 0))
                    if subcontracting_cost > 0:
                        manual_costs['subcontracting_cost'] = subcontracting_cost
                        frappe.logger("pricing").debug(f"   🔧 هزینه پیمانکاری دستی: {subcontracting_cost:,.0f}")
                    
                    labor_cost = flt(manual_item.get('manual_labor_cost', 0))
                    if labor_cost > 0:
                        manual_costs['labor_cost'] = labor_cost
                        frappe.logger("pricing").debug(f"   🔧 هزینه کارگر دستی: {labor_cost:,.0f}")
                    
                    electricity_cost = flt(manual_item.get('manual_electricity_cost', 0))
                    if electricity_cost > 0:
                        manual_costs['electricity_cost'] = electricity_cost
                        frappe.logger("pricing").debug(f"   🔧 هزینه برق دستی: {electricity_cost:,.0f}")
                    
                    consumable_cost = flt(manual_item.get('manual_consumable_cost', 0))
                    if consumable_cost > 0:
                        manual_costs['consumable_cost'] = consumable_cost
                        frappe.logger("pricing").debug(f"   🔧 هزینه مصرفی دستی: {consumable_cost:,.0f}")
                    
                    rent_cost = flt(manual_item.get('manual_rent_cost', 0))
                    if rent_cost > 0:
                        manual_costs['rent_cost'] = rent_cost
                        frappe.logger("pricing").debug(f"   🔧 هزینه اجاره دستی: {rent_cost:,.0f}")
                    
                    # اگر هیچ فیلد مثبتی نداشت، None برگردون (همه صفر بودن)
                    if not manual_costs:
                        frappe.logger("pricing").debug(f"⚠️ همه فیلدهای {item_code} صفر هستند - از BOM محاسبه می‌شود")
                        return None
                    
                    frappe.logger("pricing").debug(f"✅ فیلدهای دستی غیرصفر برای {item_code}: {list(manual_costs.keys())}")
                    return manual_costs
            
            return None
            
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در دریافت قیمت دستی برای {item_code}: {str(e)}")
            return None
    
    @frappe.whitelist()
    def clean_zero_manual_prices(self):
        """
        پاک کردن رکورد‌هایی که همه فیلدهایشان صفر است از جدول manual_item_prices
        """
        try:
            if not hasattr(self, 'manual_item_prices') or not self.manual_item_prices:
                return {
                    "success": True,
                    "message": "هیچ رکورد دستی‌ای برای پاک کردن وجود ندارد",
                    "cleaned_count": 0
                }
            
            cleaned_count = 0
            items_to_remove = []
            
            for i, manual_item in enumerate(self.manual_item_prices):
                # چک کردن تمام فیلدهای هزینه
                all_costs = [
                    flt(manual_item.get('manual_raw_material_cost', 0)),
                    flt(manual_item.get('manual_operation_cost', 0)),
                    flt(manual_item.get('manual_overhead_cost', 0)),
                    flt(manual_item.get('manual_overhead_additional_cost', 0)),
                    flt(manual_item.get('manual_subcontracting_cost', 0)),
                    flt(manual_item.get('manual_labor_cost', 0)),
                    flt(manual_item.get('manual_electricity_cost', 0)),
                    flt(manual_item.get('manual_consumable_cost', 0)),
                    flt(manual_item.get('manual_rent_cost', 0))
                ]
                
                # اگر همه فیلدها صفر باشند، برای حذف علامت‌گذاری کن
                if all(cost == 0 for cost in all_costs):
                    items_to_remove.append(i)
                    cleaned_count += 1
                    frappe.logger("pricing").debug(f"🗑️ علامت‌گذاری برای حذف: {manual_item.item_code}")
            
            # حذف از انتها به ابتدا تا index ها خراب نشوند
            for i in reversed(items_to_remove):
                self.manual_item_prices.pop(i)
            
            return {
                "success": True,
                "message": f"✅ {cleaned_count} رکورد صفر پاک شد",
                "cleaned_count": cleaned_count
            }
            
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در پاک کردن رکورد‌های صفر: {str(e)}")
            return {
                "success": False,
                "message": f"خطا در پاک کردن رکورد‌های صفر: {str(e)}",
                "cleaned_count": 0
            }

    @frappe.whitelist()
    def migrate_manual_prices_to_new_table(self):
        """
        انتقال قیمت‌های دستی از جدول قدیمی به جدول جدید
        """
        try:
            if not self.manual_material_prices:
                return {
                    "success": True,
                    "message": "هیچ قیمت دستی‌ای برای انتقال وجود ندارد"
                }
            
            # آماده‌سازی manual_item_prices
            if not hasattr(self, 'manual_item_prices') or self.manual_item_prices is None:
                self.manual_item_prices = []
            
            migrated_count = 0
            
            for old_price in self.manual_material_prices:
                if not old_price.item_code or not old_price.manual_price:
                    continue
                
                # بررسی اینکه قبلاً منتقل شده یا نه
                exists = False
                for new_price in self.manual_item_prices:
                    if new_price.item_code == old_price.item_code:
                        exists = True
                        break
                
                if not exists:
                    # ایجاد رکورد جدید
                    new_record = {
                        'item_code': old_price.item_code,
                        'item_name': old_price.get('item_name', old_price.item_code),
                        'manual_raw_material_cost': old_price.manual_price,
                        'manual_operation_cost': 0,
                        'manual_overhead_cost': 0,
                        'effective_date': old_price.get('effective_date', frappe.utils.today()),
                        'notes': f"منتقل شده از manual_material_prices در {frappe.utils.now()}",
                        'created_by': frappe.session.user,
                        'last_updated': frappe.utils.now()
                    }
                    self.append('manual_item_prices', new_record)
                    migrated_count += 1
                    frappe.logger("pricing").debug(f"✅ منتقل شد: {old_price.item_code} - {old_price.manual_price:,.0f}")
            
            if migrated_count > 0:
                self.save(ignore_permissions=True)
                message = f"✅ {migrated_count} قیمت دستی با موفقیت به جدول جدید منتقل شد"
            else:
                message = "ℹ️ همه قیمت‌ها قبلاً منتقل شده بودند"
            
            return {
                "success": True,
                "message": message,
                "migrated_count": migrated_count
            }
            
        except Exception as e:
            frappe.db.rollback()
            error_msg = f"خطا در انتقال قیمت‌ها: {str(e)}"
            frappe.logger("pricing").debug(error_msg)
            
            return {
                "success": False,
                "message": error_msg,
                "error": str(e)
            }
    
    @frappe.whitelist()
    def add_bulk_items_to_manual_prices(self):
        """
        اضافه قیمت‌های bulk_pricing_items به جدول manual_item_prices
        بدون ایجاد تکرار - فقط به‌روزرسانی یا اضافه
        """
        try:
            if not self.bulk_pricing_items:
                return {
                    "success": False,
                    "message": "هیچ آیتمی در bulk_pricing_items وجود ندارد"
                }
            
            # آماده‌سازی manual_item_prices
            if not hasattr(self, 'manual_item_prices') or self.manual_item_prices is None:
                self.manual_item_prices = []
            
            updated_count = 0
            added_count = 0
            
            frappe.logger("pricing").debug(f"📎 شروع اضافه {len(self.bulk_pricing_items)} آیتم به manual_item_prices")
            
            for bulk_item in self.bulk_pricing_items:
                if not bulk_item.item_code:
                    continue
                
                # جستجو برای رکورد موجود
                existing_record = None
                for manual_item in self.manual_item_prices:
                    if manual_item.item_code == bulk_item.item_code:
                        existing_record = manual_item
                        break
                
                # محاسبه قیمت جدید بر اساس bulk_cost_amount
                new_cost = self._calculate_new_cost_for_item(bulk_item)
                
                if existing_record:
                    # به‌روزرسانی رکورد موجود با تمام فیلدهای هزینه
                    existing_record.manual_raw_material_cost = flt(bulk_item.get('total_cost', existing_record.get('manual_raw_material_cost', 0)))
                    existing_record.manual_electricity_cost = flt(bulk_item.get('electricity_cost', existing_record.get('manual_electricity_cost', 0)))
                    existing_record.manual_consumable_cost = flt(bulk_item.get('consumable_cost', existing_record.get('manual_consumable_cost', 0)))
                    existing_record.manual_rent_cost = flt(bulk_item.get('rent_cost', existing_record.get('manual_rent_cost', 0)))
                    existing_record.manual_labor_cost = flt(bulk_item.get('labor_cost', existing_record.get('manual_labor_cost', 0)))
                    existing_record.manual_subcontracting_cost = flt(bulk_item.get('subcontracting_cost', existing_record.get('manual_subcontracting_cost', 0)))
                    existing_record.manual_overhead_cost = flt(bulk_item.get('overhead_cost', existing_record.get('manual_overhead_cost', 0)))
                    existing_record.notes = f"به‌روزرسانی از bulk_pricing در {frappe.utils.now()}"
                    existing_record.last_updated = frappe.utils.now()
                    updated_count += 1
                    frappe.logger("pricing").debug(f"🔄 به‌روزرسانی {bulk_item.item_code}: تمام فیلدهای هزینه")
                else:
                    # ایجاد رکورد جدید با تمام فیلدهای هزینه
                    new_record = {
                        'item_code': bulk_item.item_code,
                        'item_name': bulk_item.get('item_name', bulk_item.item_code),
                        'manual_raw_material_cost': flt(bulk_item.get('total_cost', 0)),
                        'manual_operation_cost': 0,
                        'manual_overhead_cost': flt(bulk_item.get('overhead_cost', 0)),
                        'manual_electricity_cost': flt(bulk_item.get('electricity_cost', 0)),
                        'manual_consumable_cost': flt(bulk_item.get('consumable_cost', 0)),
                        'manual_rent_cost': flt(bulk_item.get('rent_cost', 0)),
                        'manual_labor_cost': flt(bulk_item.get('labor_cost', 0)),
                        'manual_subcontracting_cost': flt(bulk_item.get('subcontracting_cost', 0)),
                        'manual_overhead_additional_cost': 0,
                        'effective_date': frappe.utils.today(),
                        'notes': f"اضافه شده از bulk_pricing در {frappe.utils.now()}",
                        'created_by': frappe.session.user,
                        'last_updated': frappe.utils.now()
                    }
                    self.append('manual_item_prices', new_record)
                    added_count += 1
                    frappe.logger("pricing").debug(f"➕ اضافه {bulk_item.item_code}: {new_cost:,.0f}")
            
            # ذخیره سند
            self.save(ignore_permissions=True)
            
            message = f"✅ قیمت‌ها با موفقیت به manual_item_prices اضافه شد: {updated_count} به‌روزرسانی, {added_count} اضافه"
            frappe.logger("pricing").debug(message)
            
            return {
                "success": True,
                "message": message,
                "updated_count": updated_count,
                "added_count": added_count,
                "total_manual_prices": len(self.manual_item_prices)
            }
            
        except Exception as e:
            frappe.db.rollback()
            error_msg = f"خطا در اضافه به manual_item_prices: {str(e)}"
            frappe.logger("pricing").debug(error_msg)
            
            return {
                "success": False,
                "message": error_msg,
                "error": str(e)
            }
    
    def _calculate_new_cost_for_item(self, bulk_item):
        """
        محاسبه قیمت جدید بر اساس bulk_cost_amount و selected_cost_fields
        """
        try:
            # اگر قیمت مشخص در bulk_item وجود دارد
            if hasattr(bulk_item, 'manual_price') and bulk_item.manual_price:
                return flt(bulk_item.manual_price)
            
            # اگر bulk_cost_amount وجود دارد
            if hasattr(self, 'bulk_cost_amount') and self.bulk_cost_amount:
                return flt(self.bulk_cost_amount)
            
            # برگرداندن قیمت فعلی آیتم اگر هیچ کدام وجود ندارد
            current_cost = self.calculate_item_cost_with_exploded_items(bulk_item.item_code)
            return current_cost or 0
            
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در محاسبه قیمت جدید برای {bulk_item.item_code}: {str(e)}")
            return 0
    
    def _apply_manual_prices_to_items(self):
        """
        اعمال قیمت‌های manual_item_prices به جدول items
        این باعث می‌شود قیمت‌ها در جدول items با manual_item_prices هماهنگ باشند
        """
        try:
            if not hasattr(self, 'manual_item_prices') or not self.manual_item_prices:
                return {
                    "success": True,
                    "message": "هیچ قیمت دستی‌ای برای اعمال وجود ندارد"
                }
            
            if not self.items:
                return {
                    "success": False,
                    "message": "هیچ آیتمی در جدول items وجود ندارد"
                }
            
            applied_count = 0
            
            frappe.logger("pricing").debug(f"🔄 شروع اعمال قیمت‌های manual_item_prices به {len(self.items)} آیتم")
            
            # ایجاد mapping قیمت‌های دستی - استفاده از _get_manual_item_price
            for item in self.items:
                if not item.item_code:
                    continue
                
                # دریافت قیمت‌های دستی (فقط فیلدهای غیرصفر)
                manual_costs = self._get_manual_item_price(item.item_code)
                
                if not manual_costs:
                    continue
                
                # ⚠️ مهم: اول مواد اولیه را اعمال کن
                if 'raw_material_cost' in manual_costs:
                    item.raw_material_cost = manual_costs['raw_material_cost']
                
                # ⚠️ مهم: اول calculate_operation_cost را صدا بزن تا همه فیلدها محاسبه شوند
                # این تضمین می‌کند که فیلدهایی مثل subcontracting_cost که دستی نیستند صفر نمی‌شوند
                self.calculate_operation_cost(item)
                
                # حالا فیلدهای دستی را override کن
                if 'labor_cost' in manual_costs:
                    item.labor_cost = manual_costs['labor_cost']
                if 'subcontracting_cost' in manual_costs:
                    item.subcontracting_cost = manual_costs['subcontracting_cost']
                if 'electricity_cost' in manual_costs:
                    item.electricity_cost = manual_costs['electricity_cost']
                if 'rent_cost' in manual_costs:
                    item.rent_cost = manual_costs['rent_cost']
                if 'consumable_cost' in manual_costs:
                    item.consumable_cost = manual_costs['consumable_cost']
                
                # بعد از override، دوباره operation_cost را محاسبه کن
                if 'operation_cost' in manual_costs:
                    item.operation_cost = manual_costs['operation_cost']
                else:
                    # محاسبه operation_cost از جزئیات (که الان ترکیبی از BOM + دستی هستند)
                    item.operation_cost = (
                        flt(item.labor_cost or 0) +
                        flt(item.subcontracting_cost or 0)
                    )
                
                # هزینه سربار
                if 'overhead_cost' in manual_costs:
                    item.overhead_cost = manual_costs['overhead_cost']
                else:
                    self.calculate_overhead_cost(item)
                
                # محاسبه مجدد total_cost
                item.total_cost = (
                    flt(item.raw_material_cost or 0) +
                    flt(item.operation_cost or 0) +
                    flt(item.overhead_cost or 0)
                )
                
                applied_count += 1
                frappe.logger("pricing").debug(f"✅ اعمال قیمت‌های دستی {item.item_code}: total_cost = {item.total_cost:,.0f}")
            
            # ذخیره تغییرات در دیتابیس
            updated_items = []
            for item in self.items:
                manual_costs = self._get_manual_item_price(item.item_code)
                if manual_costs:
                    updated_items.append(item)
            
            for item in updated_items:
                frappe.db.sql("""
                    UPDATE `tabAuto Price List Item`
                    SET 
                        raw_material_cost = %s, 
                        operation_cost = %s, 
                        overhead_cost = %s, 
                        total_cost = %s,
                        labor_cost = %s,
                        subcontracting_cost = %s,
                        electricity_cost = %s,
                        rent_cost = %s,
                        consumable_cost = %s,
                        modified = NOW()
                    WHERE parent = %s AND item_code = %s
                """, (
                    item.raw_material_cost,
                    item.operation_cost,
                    item.overhead_cost,
                    item.total_cost,
                    item.labor_cost or 0,
                    item.subcontracting_cost or 0,
                    item.electricity_cost or 0,
                    item.rent_cost or 0,
                    item.consumable_cost or 0,
                    self.name,
                    item.item_code
                ))
            
            frappe.db.commit()
            
            message = f"✅ قیمت‌های دستی با موفقیت به {applied_count} آیتم اعمال شد"
            frappe.logger("pricing").debug(message)
            
            return {
                "success": True,
                "message": message,
                "applied_count": applied_count,
                "total_items": len(self.items)
            }
            
        except Exception as e:
            frappe.db.rollback()
            error_msg = f"خطا در اعمال قیمت‌های دستی: {str(e)}"
            frappe.logger("pricing").debug(error_msg)
            
            return {
                "success": False,
                "message": error_msg,
                "error": str(e)
            }
    
    @frappe.whitelist()
    def calculate_full_costing_with_progress(self):
        """
        محاسبه بهای تمام شده با نمایش پیشرفت
        حل مشکل لاک شدن صفحه با progress bar
        """
        try:
            if not self.items:
                return {
                    "success": False,
                    "message": "هیچ آیتمی برای محاسبه وجود ندارد"
                }
            
            total_items = len(self.items)
            processed_items = 0
            
            # ایجاد progress tracking
            progress_id = frappe.generate_hash(length=10)
            
            frappe.logger("pricing").debug(f"🚀 شروع محاسبه بهای تمام شده برای {total_items} آیتم")
            
            # مرحله 1: بارگذاری قیمت‌های دستی از جدول جدید
            self._publish_progress(progress_id, 5, "📎 بارگذاری قیمت‌های دستی از manual_item_prices...")
            
            # بررسی تعداد قیمت‌های دستی موجود
            manual_prices_count = len(self.manual_item_prices) if hasattr(self, 'manual_item_prices') and self.manual_item_prices else 0
            frappe.logger("pricing").debug(f"📊 {manual_prices_count} قیمت دستی در manual_item_prices یافت شد")
            
            # برای سازگاری با کد قدیمی
            manual_price_map = {}
            if self.manual_material_prices:
                for manual_price in self.manual_material_prices:
                    if manual_price.item_code and manual_price.manual_price:
                        manual_price_map[manual_price.item_code] = manual_price.manual_price
            
            # مرحله 2: محاسبه هزینه‌ها از manual_item_prices یا BOM
            self._publish_progress(progress_id, 15, "📦 محاسبه هزینه‌ها...")
            for item in self.items:
                if item.item_code:
                    # چک کردن قیمت‌های دستی
                    manual_costs = self._get_manual_item_price(item.item_code)
                    
                    # 1. محاسبه مواد اولیه
                    if 'raw_material_cost' not in (manual_costs or {}):
                        item.raw_material_cost = self.calculate_item_cost_with_exploded_items(item.item_code)
                    else:
                        item.raw_material_cost = manual_costs['raw_material_cost']
                    
                    # 2. ⚠️ مهم: همیشه اول calculate_operation_cost را صدا بزن
                    # این تضمین می‌کند همه فیلدها (labor, subcontracting, etc.) محاسبه شوند
                    self.calculate_operation_cost(item)
                    
                    # 3. حالا فیلدهای دستی را override کن
                    if manual_costs:
                        if 'labor_cost' in manual_costs:
                            item.labor_cost = manual_costs['labor_cost']
                        
                        if 'subcontracting_cost' in manual_costs:
                            item.subcontracting_cost = manual_costs['subcontracting_cost']
                        
                        if 'electricity_cost' in manual_costs:
                            item.electricity_cost = manual_costs['electricity_cost']
                        
                        if 'consumable_cost' in manual_costs:
                            item.consumable_cost = manual_costs['consumable_cost']
                        
                        if 'rent_cost' in manual_costs:
                            item.rent_cost = manual_costs['rent_cost']
                        
                        # بعد از override، دوباره operation_cost را محاسبه کن
                        if 'operation_cost' in manual_costs:
                            item.operation_cost = manual_costs['operation_cost']
                        else:
                            item.operation_cost = flt(item.labor_cost or 0) + flt(item.subcontracting_cost or 0)
                    
                    # 4. محاسبه overhead
                    if 'overhead_cost' not in (manual_costs or {}):
                        self.calculate_overhead_cost(item)
                    else:
                        item.overhead_cost = manual_costs['overhead_cost']
                processed_items += 1
                if processed_items % 10 == 0:  # به‌روزرسانی هر 10 آیتم
                    progress = 15 + (processed_items / total_items) * 30
                    self._publish_progress(progress_id, progress, f"📦 محاسبه هزینه‌ها: {processed_items}/{total_items}")
            
            # مرحله 3: محاسبه مجموع هزینه‌ها
            self._publish_progress(progress_id, 75, "💰 محاسبه مجموع هزینه‌ها...")
            processed_items = 0
            for item in self.items:
                if item.item_code:
                    
                    # محاسبه نهایی total_cost (شامل همه فیلدها)
                    item.total_cost = (
                        flt(item.raw_material_cost or 0) +
                        flt(item.operation_cost or 0) +
                        flt(item.overhead_cost or 0) 
                    )
                processed_items += 1
                if processed_items % 10 == 0:
                    progress = 75 + (processed_items / total_items) * 20
                    self._publish_progress(progress_id, progress, f"📊 محاسبه سربار: {processed_items}/{total_items}")
            
            # مرحله 5: ذخیره نتایج
            self._publish_progress(progress_id, 95, "💾 ذخیره نتایج...")
            
            # ذخیره با بچ پروسسینگ برای جلوگیری از لاک
            batch_size = 20
            for i in range(0, len(self.items), batch_size):
                batch = self.items[i:i + batch_size]
                for item in batch:
                    frappe.db.sql("""
                        UPDATE `tabAuto Price List Item`
                        SET raw_material_cost = %s, operation_cost = %s, 
                            overhead_cost = %s, subcontracting_cost = %s,
                            labor_cost = %s, electricity_cost = %s,
                            consumable_cost = %s, rent_cost = %s,
                            total_cost = %s, modified = NOW()
                        WHERE parent = %s AND item_code = %s
                    """, (
                        flt(item.raw_material_cost or 0),
                        flt(item.operation_cost or 0),
                        flt(item.overhead_cost or 0),
                        flt(item.subcontracting_cost or 0),
                        flt(item.labor_cost or 0),
                        flt(item.electricity_cost or 0),
                        flt(item.consumable_cost or 0),
                        flt(item.rent_cost or 0),
                        flt(item.total_cost or 0),
                        self.name,
                        item.item_code
                    ))
                frappe.db.commit()  # commit هر batch
            
            self._publish_progress(progress_id, 100, "✅ محاسبه بهای تمام شده کامل شد")
            
            return {
                "success": True,
                "message": f"✅ محاسبه بهای تمام شده برای {total_items} آیتم کامل شد",
                "progress_id": progress_id,
                "total_items": total_items
            }
            
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در محاسبه بهای تمام شده: {str(e)}")
            self._publish_progress(progress_id, 0, f"❌ خطا: {str(e)}")
            return {
                "success": False,
                "message": f"خطا در محاسبه: {str(e)}"
            }
    
    @frappe.whitelist()
    def get_raw_materials_report(self):
        """
        تهیه گزارش کامل مواد اولیه خام
        """
        try:
            # جمع‌آوری تمام مواد اولیه از BOMهای موجود
            materials = {}
            
            if not self.items:
                return {
                    "success": False,
                    "message": "هیچ کالایی در لیست وجود ندارد. ابتدا کالاها را دریافت کنید."
                }
            
            for item in self.items:
                if not item.item_code:
                    continue
                
                # پیدا کردن BOM فعال
                bom = frappe.db.get_value("BOM", {
                    "item": item.item_code,
                    "is_active": 1,
                    "is_default": 1
                }, ["name"])
                
                if not bom:
                    continue
                
                # دریافت مواد اولیه از BOM
                bom_items = frappe.get_all("BOM Item", {
                    "parent": bom
                }, ["item_code", "item_name", "qty", "uom", "rate"])
                
                for bom_item in bom_items:
                    item_code = bom_item.item_code
                    
                    if item_code not in materials:
                        # دریافت اطلاعات کامل آیتم
                        item_doc = frappe.get_doc("Item", item_code)
                        
                        # دریافت آخرین قیمت از Item Price
                        latest_price = frappe.db.get_value("Item Price", {
                            "item_code": item_code,
                            "price_list": self.price_list
                        }, ["price_list_rate"], order_by="modified desc")
                        
                        if not latest_price:
                            # اگر قیمت در لیست قیمت فعلی نبود، از هر لیست قیمتی بگیر
                            latest_price = frappe.db.get_value("Item Price", {
                                "item_code": item_code
                            }, ["price_list_rate"], order_by="modified desc")
                        
                        materials[item_code] = {
                            "item_code": item_code,
                            "item_name": bom_item.item_name or item_doc.item_name,
                            "uom": bom_item.uom or item_doc.stock_uom,
                            "rate": latest_price or 0,
                            "bom_count": 1,
                            "total_qty": bom_item.qty or 0
                        }
                    else:
                        # اگر ماده قبلاً وجود داشت، تعداد BOM و مقدار را به‌روزرسانی کن
                        materials[item_code]["bom_count"] += 1
                        materials[item_code]["total_qty"] += (bom_item.qty or 0)
            
            # تبدیل به لیست و مرتب‌سازی
            materials_list = list(materials.values())
            materials_list.sort(key=lambda x: x["item_code"])
            
            # محاسبه آمار
            total_materials = len(materials_list)
            materials_with_price = len([m for m in materials_list if m["rate"] > 0])
            materials_without_price = total_materials - materials_with_price
            
            return {
                "success": True,
                "materials": materials_list,
                "total_materials": total_materials,
                "materials_with_price": materials_with_price,
                "materials_without_price": materials_without_price,
                "message": f"گزارش مواد اولیه تهیه شد: {total_materials} ماده، {materials_with_price} با قیمت، {materials_without_price} بدون قیمت"
            }
            
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در تهیه گزارش مواد اولیه: {str(e)}")
            return {
                "success": False,
                "message": f"خطا در تهیه گزارش مواد اولیه: {str(e)}"
            }
    
    def _publish_progress(self, progress_id, percentage, message):
        """
        ارسال پیشرفت به کلاینت برای نمایش progress bar
        """
        try:
            frappe.publish_realtime(
                event='pricing_progress',
                message={
                    'progress_id': progress_id,
                    'percentage': percentage,
                    'message': message,
                    'timestamp': frappe.utils.now()
                },
                user=frappe.session.user
            )
            frappe.logger("pricing").debug(f"📊 Progress: {percentage}% - {message}")
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در ارسال progress: {str(e)}")
    
    @frappe.whitelist()
    def clean_manual_prices(self):
        """
        تمیز کردن قیمت‌های دستی برای حل مشکل فیلدهای غیرقابل تغییر
        """
        try:
            if not hasattr(self, 'manual_material_prices') or not self.manual_material_prices:
                return {
                    "success": True,
                    "message": "هیچ قیمت دستی‌ای برای تمیز کردن وجود ندارد"
                }
            
            # حذف رکوردهای نامعتبر
            original_count = len(self.manual_material_prices)
            valid_prices = []
            
            for mp in self.manual_material_prices:
                if mp.item_code and flt(mp.manual_price or 0) > 0:
                    valid_prices.append(mp)
            
            # ذخیره مستقیم
            frappe.db.sql("""
                DELETE FROM `tabAuto Price List Manual Material Price`
                WHERE parent = %s
            """, (self.name,))
            
            for idx, mp in enumerate(valid_prices, 1):
                frappe.db.sql("""
                    INSERT INTO `tabAuto Price List Manual Material Price`
                    (name, parent, parenttype, parentfield, item_code, item_name, 
                     manual_price, effective_date, notes, idx, creation, modified, 
                     owner, modified_by, docstatus)
                    VALUES (%s, %s, 'Auto Price List', 'manual_material_prices', 
                            %s, %s, %s, %s, %s, %s, NOW(), NOW(), %s, %s, 0)
                """, (
                    frappe.generate_hash(length=10),
                    self.name,
                    mp.item_code,
                    mp.get('item_name', mp.item_code),
                    mp.manual_price,
                    mp.get('effective_date', frappe.utils.today()),
                    mp.get('notes', 'تمیز شده'),
                    idx,
                    frappe.session.user,
                    frappe.session.user
                ))
            
            frappe.db.commit()
            
            removed_count = original_count - len(valid_prices)
            message = f"✅ تمیز کردن کامل شد: {len(valid_prices)} رکورد معتبر باقی ماند, {removed_count} رکورد نامعتبر حذف شد"
            
            return {
                "success": True,
                "message": message,
                "valid_count": len(valid_prices),
                "removed_count": removed_count
            }
            
        except Exception as e:
            frappe.db.rollback()
            error_msg = f"خطا در تمیز کردن قیمت‌های دستی: {str(e)}"
            frappe.logger("pricing").debug(error_msg)
            
            return {
                "success": False,
                "message": error_msg,
                "error": str(e)
            }

    def get_automatic_monthly_fixed_costs(self):
        """
        استخراج خودکار هزینه‌های ثابت ماهانه از حسابداری ERPNext
        """
        try:
            # دریافت شرکت از لیست قیمت
            company = None
            if self.price_list:
                price_list_doc = frappe.get_doc("Price List", self.price_list)
                # اگر شرکت در Price List تعریف نشده، از شرکت پیش‌فرض استفاده کنیم
                company = getattr(price_list_doc, 'company', None) or frappe.defaults.get_user_default("Company")
            
            if not company:
                company = frappe.defaults.get_user_default("Company")
            
            if not company:
                frappe.logger().warning("شرکت برای محاسبه هزینه‌های ثابت پیدا نشد")
                return 0
            
            # تاریخ شروع و پایان ماه گذشته برای محاسبه میانگین
            from datetime import datetime, timedelta
            from dateutil.relativedelta import relativedelta
            
            today = datetime.now().date()
            # ماه گذشته
            last_month_start = (today.replace(day=1) - relativedelta(months=1))
            last_month_end = today.replace(day=1) - timedelta(days=1)
            
            # حساب‌های هزینه ثابت (بر اساس نام‌گذاری معمول ایرانی)
            fixed_cost_accounts = [
                # هزینه‌های اجاره
                "اجاره", "rent", "اجاره بها", "اجاره املاک", "کرایه",
                # هزینه‌های حقوق و دستمزد
                "حقوق", "salary", "دستمزد", "مزایا", "بیمه کارکنان", "عیدی", "پاداش",
                # هزینه‌های بیمه
                "بیمه", "insurance", "بیمه آتش سوزی", "بیمه مسئولیت",
                # هزینه‌های استهلاک
                "استهلاک", "depreciation", "مستهلکات",
                # هزینه‌های اداری ثابت
                "تلفن", "اینترنت", "آب", "گاز", "برق اداری", "نگهبانی", "نظافت",
                # هزینه‌های مالی ثابت
                "کارمزد بانک", "سود تسهیلات", "هزینه مالی"
            ]
            
            # ساخت شرط WHERE برای جستجو در نام حساب‌ها
            account_conditions = []
            for keyword in fixed_cost_accounts:
                account_conditions.append(f"acc.account_name LIKE '%{keyword}%'")
            
            account_where_clause = " OR ".join(account_conditions)
            
            # Query برای دریافت هزینه‌های ثابت از GL Entry
            query = f"""
                SELECT 
                    SUM(ABS(gle.debit - gle.credit)) as total_fixed_costs
                FROM `tabGL Entry` gle
                INNER JOIN `tabAccount` acc ON gle.account = acc.name
                WHERE 
                    gle.company = %s
                    AND gle.posting_date BETWEEN %s AND %s
                    AND acc.account_type = 'Expense'
                    AND ({account_where_clause})
                    AND gle.is_cancelled = 0
            """
            
            result = frappe.db.sql(query, (company, last_month_start, last_month_end), as_dict=True)
            
            monthly_fixed_costs = 0
            if result and result[0].get('total_fixed_costs'):
                monthly_fixed_costs = float(result[0]['total_fixed_costs'])
            
            # اگر داده‌ای پیدا نشد، از میانگین 3 ماه گذشته استفاده کنیم
            if monthly_fixed_costs == 0:
                three_months_ago = today.replace(day=1) - relativedelta(months=3)
                
                query_3months = f"""
                    SELECT 
                        AVG(monthly_costs.total) as avg_fixed_costs
                    FROM (
                        SELECT 
                            YEAR(gle.posting_date) as year,
                            MONTH(gle.posting_date) as month,
                            SUM(ABS(gle.debit - gle.credit)) as total
                        FROM `tabGL Entry` gle
                        INNER JOIN `tabAccount` acc ON gle.account = acc.name
                        WHERE 
                            gle.company = %s
                            AND gle.posting_date >= %s
                            AND acc.account_type = 'Expense'
                            AND ({account_where_clause})
                            AND gle.is_cancelled = 0
                        GROUP BY YEAR(gle.posting_date), MONTH(gle.posting_date)
                    ) as monthly_costs
                """
                
                result_3months = frappe.db.sql(query_3months, (company, three_months_ago), as_dict=True)
                
                if result_3months and result_3months[0].get('avg_fixed_costs'):
                    monthly_fixed_costs = float(result_3months[0]['avg_fixed_costs'])
            
            # اگر هنوز داده‌ای نیست، از تخمین بر اساس کل هزینه‌ها استفاده کنیم
            if monthly_fixed_costs == 0:
                total_expenses_query = """
                    SELECT 
                        SUM(ABS(gle.debit - gle.credit)) as total_expenses
                    FROM `tabGL Entry` gle
                    INNER JOIN `tabAccount` acc ON gle.account = acc.name
                    WHERE 
                        gle.company = %s
                        AND gle.posting_date BETWEEN %s AND %s
                        AND acc.account_type = 'Expense'
                        AND gle.is_cancelled = 0
                """
                
                total_result = frappe.db.sql(total_expenses_query, (company, last_month_start, last_month_end), as_dict=True)
                
                if total_result and total_result[0].get('total_expenses'):
                    total_expenses = float(total_result[0]['total_expenses'])
                    # تخمین 40% از کل هزینه‌ها به عنوان هزینه ثابت
                    monthly_fixed_costs = total_expenses * 0.4
            
            frappe.logger("pricing").debug(f"هزینه‌های ثابت ماهانه محاسبه شده: {monthly_fixed_costs:,.0f} ریال")
            return monthly_fixed_costs
            
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در محاسبه هزینه‌های ثابت خودکار: {str(e)}")
            import traceback
            frappe.logger("pricing").debug(f"جزئیات خطا: {traceback.format_exc()}")
            return 0
        
        
            # 5. اصلاح validate_pricing_calculations
    
    def validate_pricing_calculations(self, item):
        """
        اعتبارسنجی محاسبات - نسخه اصلاح شده
        """
        try:
            # بررسی total_cost (فقط 3 جزء اصلی)
            calculated_total = (
                flt(item.raw_material_cost or 0) +
                flt(item.operation_cost or 0) +
                flt(item.overhead_cost or 0)
            )
            
            if abs(calculated_total - flt(item.total_cost or 0)) > 1:
                frappe.logger().warning(f"⚠️ عدم تطابق total_cost برای {item.item_code}")
                frappe.logger().warning(f"   محاسبه شده: {calculated_total:,.0f}")
                frappe.logger().warning(f"   ذخیره شده: {flt(item.total_cost or 0):,.0f}")
                return False
            
            # بررسی operation_cost (مجموع جزئیات)
            calculated_operation = (
                flt(item.electricity_cost or 0) +
                flt(item.labor_cost or 0) +
                flt(item.consumable_cost or 0) +
                flt(item.subcontracting_cost or 0) +
                flt(item.rent_cost or 0)
            )
            
            if abs(calculated_operation - flt(item.operation_cost or 0)) > 1:
                frappe.logger().warning(f"⚠️ عدم تطابق operation_cost برای {item.item_code}")
                return False
            
            frappe.logger("pricing").debug(f"✅ محاسبات صحیح برای {item.item_code}")
            return True
            
        except Exception as e:
            frappe.logger("pricing").debug(f"خطا در اعتبارسنجی: {str(e)}")
            return False

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
        return doc.integrate_real_data_for_pricing()
    except Exception as e:
        frappe.log_error(f"Integrate real data error: {str(e)}")
        return {'status': 'error', 'message': str(e)}

@frappe.whitelist()
def get_raw_materials_report_api(docname):
    """API wrapper for raw materials report"""
    try:
        doc = frappe.get_doc("Auto Price List", docname)
        return doc.get_raw_materials_report()
    except Exception as e:
        frappe.log_error(f"Raw materials report API error: {str(e)}")
        return {'success': False, 'message': str(e)}

@frappe.whitelist()
def add_bulk_items_to_manual_prices_api(docname):
    """API function to add bulk items to manual prices - standalone implementation"""
    try:
        doc = frappe.get_doc("Auto Price List", docname)
        
        # Check if bulk_pricing_items exists
        if not hasattr(doc, 'bulk_pricing_items') or not doc.bulk_pricing_items:
            return {
                "success": False,
                "message": "هیچ آیتمی در bulk_pricing_items وجود ندارد"
            }
        
        # Check selected cost field and bulk cost amount
        if not hasattr(doc, 'selected_cost_fields') or not doc.selected_cost_fields:
            return {
                "success": False,
                "message": "لطفاً فیلد هزینه مورد نظر را انتخاب کنید"
            }
        
        if not hasattr(doc, 'bulk_cost_amount') or not doc.bulk_cost_amount:
            return {
                "success": False,
                "message": "لطفاً مبلغ هزینه را وارد کنید"
            }
        
        # نقشه‌برداری فیلدهای فارسی به انگلیسی
        field_mapping = {
            'هزینه مواد اولیه': 'manual_raw_material_cost',
            'هزینه عملیات': 'manual_operation_cost',
            'هزینه سربار': 'manual_overhead_cost',
            'هزینه برق': 'manual_electricity_cost',
            'هزینه مصرفی': 'manual_consumable_cost',
            'هزینه اجاره': 'manual_rent_cost',
            'هزینه کارگر': 'manual_labor_cost',
            'هزینه پیمانکاری': 'manual_subcontracting_cost',
            'هزینه سربار اضافی': 'manual_overhead_additional_cost'
        }
        
        # تشخیص فیلد انتخاب شده
        selected_field = field_mapping.get(doc.selected_cost_fields)
        if not selected_field:
            return {
                "success": False,
                "message": f"فیلد انتخاب شده '{doc.selected_cost_fields}' شناخته شده نیست"
            }
        
        # Initialize manual_item_prices if it doesn't exist
        if not hasattr(doc, 'manual_item_prices') or doc.manual_item_prices is None:
            doc.manual_item_prices = []
        
        updated_count = 0
        added_count = 0
        new_cost = doc.bulk_cost_amount
        
        frappe.logger("pricing").debug(f"📎 شروع اضافه {len(doc.bulk_pricing_items)} آیتم به manual_item_prices در فیلد {doc.selected_cost_fields}")
        
        for bulk_item in doc.bulk_pricing_items:
            if not bulk_item.item_code:
                continue
            
            # Search for existing record
            existing_record = None
            for manual_item in doc.manual_item_prices:
                if manual_item.item_code == bulk_item.item_code:
                    existing_record = manual_item
                    break
            
            if existing_record:
                # Update existing record - set the selected field
                setattr(existing_record, selected_field, new_cost)
                existing_record.notes = f"به‌روزرسانی {doc.selected_cost_fields} از bulk_pricing در {frappe.utils.now()}"
                existing_record.last_updated = frappe.utils.now()
                updated_count += 1
                frappe.logger("pricing").debug(f"🔄 به‌روزرسانی {bulk_item.item_code} - {doc.selected_cost_fields}: {new_cost:,.0f}")
            else:
                # Create new record with all fields initialized to 0, except the selected one
                new_record = {
                    'item_code': bulk_item.item_code,
                    'item_name': bulk_item.get('item_name', bulk_item.item_code),
                    'manual_raw_material_cost': 0,
                    'manual_operation_cost': 0,
                    'manual_overhead_cost': 0,
                    'manual_subcontracting_cost': 0,
                    'manual_labor_cost': 0,
                    'manual_electricity_cost': 0,
                    'manual_consumable_cost': 0,
                    'manual_rent_cost': 0,
                    'manual_overhead_additional_cost': 0,
                    'effective_date': frappe.utils.today(),
                    'notes': f"اضافه شده {doc.selected_cost_fields} از bulk_pricing در {frappe.utils.now()}",
                    'created_by': frappe.session.user,
                    'last_updated': frappe.utils.now()
                }
                
                # Set the selected field to the new cost
                new_record[selected_field] = new_cost
                
                doc.append('manual_item_prices', new_record)
                added_count += 1
                frappe.logger("pricing").debug(f"➕ اضافه {bulk_item.item_code} - {doc.selected_cost_fields}: {new_cost:,.0f}")
        
        # Save document با robust save mechanism
        try:
            doc.save(ignore_permissions=True)
        except frappe.QueryTimeoutError as e:
            frappe.logger("pricing").debug(f"خطای timeout در ذخیره manual_item_prices: {str(e)}")
            # تلاش برای ذخیره مستقیم فقط manual_item_prices
            return doc._save_manual_item_prices_direct_only()
        except Exception as e:
            frappe.logger("pricing").debug(f"خطای عمومی در ذخیره: {str(e)}")
            # تلاش برای ذخیره مستقیم
            return doc._save_manual_item_prices_direct_only()
        
        message = f"✅ {doc.selected_cost_fields} با موفقیت به manual_item_prices اضافه شد: {updated_count} به‌روزرسانی, {added_count} اضافه"
        frappe.logger("pricing").debug(message)
        
        return {
            "success": True,
            "message": message,
            "updated_count": updated_count,
            "added_count": added_count,
            "selected_field": doc.selected_cost_fields,
            "cost_amount": new_cost,
            "total_manual_prices": len(doc.manual_item_prices)
        }
        
    except Exception as e:
        frappe.db.rollback()
        error_msg = f"خطا در اضافه به manual_item_prices: {str(e)}"
        frappe.logger("pricing").debug(error_msg)
        
        return {
            "success": False,
            "message": error_msg,
            "error": str(e)
        }

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
    frappe.logger("pricing").debug(f"🚀 ==> recalculate_with_manual_prices فراخوانی شد برای {price_list_name}")
    try:
        # بررسی اولیه
        if not price_list_name:
            raise Exception("نام price list ارائه نشده است")
        
        # بررسی وجود document
        if not frappe.db.exists("Auto Price List", price_list_name):
            raise Exception(f"Auto Price List با نام {price_list_name} وجود ندارد")
        
        price_list = frappe.get_doc("Auto Price List", price_list_name)
        print(f"✅ Document loaded successfully: {price_list.name}")
        
        # بررسی وجود متدهای ضروری
        if not hasattr(price_list, 'is_item_affected_by_manual_prices'):
            raise Exception("متد is_item_affected_by_manual_prices وجود ندارد")
        if not hasattr(price_list, 'calculate_item_cost_with_exploded_items'):
            raise Exception("متد calculate_item_cost_with_exploded_items وجود ندارد")
        if not hasattr(price_list, 'calculate_final_price_for_item'):
            raise Exception("متد calculate_final_price_for_item وجود ندارد")
        print("✅ تمام متدهای ضروری موجود هستند")
        
        frappe.logger("pricing").debug("🚀 شروع recalculate_with_manual_prices")
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
        
        # بررسی وجود items
        if not price_list.items:
            print("❌ هیچ آیتمی در price list وجود ندارد")
            return {"updated_count": 0, "message": "هیچ آیتمی در price list وجود ندارد"}
        
        print(f"✅ تعداد آیتم‌ها: {len(price_list.items)}")
        print(f"✅ تعداد قیمت‌های دستی: {len(manual_price_map)}")
        
        # لاگ شروع فرآیند
        frappe.logger("pricing").debug(f"🔄 شروع به‌روزرسانی قیمت‌ها با {len(manual_price_map)} قیمت دستی")
        print(f"🔄 شروع به‌روزرسانی قیمت‌ها با {len(manual_price_map)} قیمت دستی")
        print(f"📋 قیمت‌های دستی: {manual_price_map}")
        for manual_item, manual_price in manual_price_map.items():
            frappe.logger("pricing").debug(f"📋 قیمت دستی: {manual_item} = {manual_price:,.0f}")
        
        # شمارش کل آیتم‌ها
        total_items = len(price_list.items)
        affected_items = 0
        processed_items = 0
        price_changes = []
        
        frappe.logger("pricing").debug(f"📊 تعداد کل آیتم‌ها: {total_items}")
        print(f"📊 تعداد کل آیتم‌ها: {total_items}")
        print(f"📊 قیمت‌های دستی: {manual_price_map}")
        
        for item in price_list.items:
            try:
                processed_items += 1
                frappe.logger("pricing").debug(f"🔍 [{processed_items}/{total_items}] بررسی آیتم: {item.item_code}")
                print(f"🔍 [{processed_items}/{total_items}] بررسی آیتم: {item.item_code}")
                
                # بررسی اینکه آیا این آیتم تحت تأثیر قیمت‌های دستی است یا نه
                print(f"   🚀 فراخوانی is_item_affected_by_manual_prices برای {item.item_code}")
                item_affected = price_list.is_item_affected_by_manual_prices(item.item_code, manual_price_map)
                print(f"   🔍 آیتم {item.item_code} تحت تأثیر است؟ {item_affected}")
                
                if not item_affected:
                    frappe.logger("pricing").debug(f"   ❌ آیتم {item.item_code} تحت تأثیر قیمت‌های دستی نیست")
                    print(f"   ❌ آیتم {item.item_code} تحت تأثیر قیمت‌های دستی نیست")
                    continue
                
                affected_items += 1
                frappe.logger("pricing").debug(f"   ✅ آیتم {item.item_code} تحت تأثیر است - شروع محاسبه")
                
                # محاسبه مجدد قیمت با قیمت‌های دستی جدید
                old_cost = item.raw_material_cost or 0
                old_price = item.selling_price or 0
                
                frappe.logger("pricing").debug(f"   📊 قیمت‌های فعلی: هزینه={old_cost:,.0f}, قیمت={old_price:,.0f}")
                
                # محاسبه قیمت جدید با قیمت‌های دستی
                print(f"   🚀 شروع محاسبه هزینه جدید برای {item.item_code}...")
                try:
                    new_cost = price_list.calculate_item_cost_with_exploded_items(item.item_code)
                    cost_difference = new_cost - old_cost
                    print(f"   ✅ محاسبه هزینه موفق: {new_cost:,.0f}")
                except Exception as calc_error:
                    print(f"   ❌ خطا در محاسبه هزینه: {str(calc_error)}")
                    import traceback
                    print(f"   🔍 جزئیات خطا: {traceback.format_exc()}")
                    continue
                
                frappe.logger("pricing").debug(f"   🧮 تفاوت هزینه محاسبه شده: {cost_difference:,.0f}")
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
                    frappe.logger("pricing").debug(f"   ❌ قیمت جدید نامعتبر است: {new_cost}")
                    print(f"   ❌ قیمت جدید نامعتبر است: {new_cost}")
                    continue
                    
                if abs(cost_difference) < 0.01:
                    frappe.logger("pricing").debug(f"   ℹ️ تفاوت هزینه ناچیز است: {abs(cost_difference):.6f}")
                    print(f"   ℹ️ تفاوت هزینه ناچیز است: {abs(cost_difference):.6f}")
                    print(f"   ⚠️ آیتم {item.item_code} به‌روزرسانی نمی‌شود چون تفاوت کمتر از 0.01 است")
                    continue
                
                # بررسی اینکه آیا نیاز به به‌روزرسانی هست یا نه
                cost_diff = abs(cost_difference)
                frappe.logger("pricing").debug(f"   📏 مقدار تفاوت هزینه: {cost_diff:,.2f}")
                print(f"   📏 مقدار تفاوت هزینه: {cost_diff:,.2f}")
                
                # فقط اگر تفاوت معنی‌دار باشد، به‌روزرسانی کن
                should_update = cost_diff > 0.01
                print(f"   🔍 نیاز به به‌روزرسانی: {should_update} (تفاوت > 0.01)")
                
                if should_update:
                    print(f"   ✅ شروع به‌روزرسانی {item.item_code}")
                    try:
                        # ابتدا raw_material_cost را به‌روزرسانی کن
                        item.raw_material_cost = new_cost
                        print(f"   ✅ raw_material_cost به‌روزرسانی شد: {new_cost:,.0f}")
                        
                        # سپس قیمت نهایی را محاسبه کن
                        print(f"   🚀 شروع محاسبه قیمت نهایی...")
                        try:
                            new_price = price_list.calculate_final_price_for_item(item)
                            print(f"   ✅ قیمت نهایی محاسبه شد: {new_price:,.0f}")
                            frappe.logger("pricing").debug(f"   💰 قیمت نهایی محاسبه شده: {new_price:,.0f}")
                        except Exception as price_calc_error:
                            print(f"   ❌ خطا در محاسبه قیمت نهایی: {str(price_calc_error)}")
                            # استفاده از محاسبه ساده در صورت خطا
                            profit_margin = price_list.profit_margin or 0
                            new_price = new_cost * (1 + profit_margin / 100)
                            print(f"   🔄 استفاده از محاسبه ساده: {new_price:,.0f} (سود {profit_margin}%)")
                            frappe.logger("pricing").debug(f"   🔄 استفاده از محاسبه ساده به دلیل خطا: {new_price:,.0f}")
                        
                        # لاگ تفصیلی تغییرات
                        cost_change = new_cost - old_cost
                        price_change = new_price - old_price
                        cost_percent = (cost_change / old_cost * 100) if old_cost > 0 else 0
                        price_percent = (price_change / old_price * 100) if old_price > 0 else 0
                        
                        frappe.logger("pricing").debug(f"   ✅ به‌روزرسانی {item.item_code}:")
                        frappe.logger("pricing").debug(f"      💰 هزینه مواد: {old_cost:,.0f} → {new_cost:,.0f} ({cost_change:+,.0f} | {cost_percent:+.1f}%)")
                        frappe.logger("pricing").debug(f"      💵 قیمت فروش: {old_price:,.0f} → {new_price:,.0f} ({price_change:+,.0f} | {price_percent:+.1f}%)")
                        
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
                        
                        # ✅ اطمینان از به‌روزرسانی total_cost
                        item.total_cost = new_cost + (item.operation_cost or 0) + (item.overhead_cost or 0)
                        print(f"   ✅ total_cost به‌روزرسانی شد: {item.total_cost:,.0f}")
                        
                        updated_count += 1
                        
                    except Exception as calc_error:
                        frappe.logger("pricing").debug(f"   ❌ خطا در محاسبه قیمت نهایی: {str(calc_error)}")
                        print(f"   ❌ خطا در محاسبه قیمت نهایی: {str(calc_error)}")
                        # حداقل هزینه مواد را به‌روزرسانی کن
                        item.raw_material_cost = new_cost
                        updated_count += 1
                    
                else:
                    frappe.logger("pricing").debug(f"   ⏭️ آیتم {item.item_code}: تغییر معنی‌داری نداشت (تفاوت: {cost_diff:,.2f})")
                    print(f"   ⏭️ آیتم {item.item_code}: تغییر معنی‌داری نداشت (تفاوت: {cost_diff:,.2f})")
            
            except Exception as e:
                frappe.logger("pricing").debug(f"   ❌ خطا در به‌روزرسانی {item.item_code}: {str(e)}")
                import traceback
                frappe.logger("pricing").debug(f"   🔍 جزئیات خطا: {traceback.format_exc()}")
                continue
        
        frappe.logger("pricing").debug(f"📈 خلاصه: {processed_items} آیتم بررسی شد، {affected_items} تحت تأثیر بود، {updated_count} تغییر کرد")
        
        # ذخیره تغییرات
        if updated_count > 0:
            print(f"💾 شروع ذخیره‌سازی {updated_count} آیتم...")
            
            # اجبار به refresh کردن child table
            for item in price_list.items:
                if hasattr(item, '_doc_before_save'):
                    # نمایش تغییرات برای دیباگ
                    print(f"   📝 ذخیره آیتم {item.item_code}:")
                    print(f"      raw_material_cost: {item.raw_material_cost:,.0f}")
                    print(f"      total_cost: {item.total_cost:,.0f}")
                    print(f"      selling_price: {item.selling_price:,.0f}")
                item.db_update()
            
            price_list.save()
            frappe.db.commit()
            frappe.logger("pricing").debug(f"🎉 به‌روزرسانی کامل شد: {updated_count} آیتم تغییر کرد")
            print(f"🎉 به‌روزرسانی کامل شد: {updated_count} آیتم تغییر کرد")
        else:
            frappe.logger("pricing").debug(f"ℹ️  هیچ آیتمی نیاز به تغییر نداشت")
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
        
        frappe.logger("pricing").debug(f"📈 خلاصه نهایی: {response}")
        print(f"📈 خلاصه نهایی: {response}")
        
        return response
        
    except Exception as e:
        import traceback
        error_msg = f"خطا در اعمال قیمت‌های دستی: {str(e)}"
        error_details = traceback.format_exc()
        
        frappe.logger("pricing").debug(f"❌ {error_msg}")
        frappe.logger("pricing").debug(f"🔍 جزئیات خطا: {error_details}")
        print(f"❌ خطا: {error_msg}")
        print(f"🔍 جزئیات خطا: {error_details}")
        
        # ارسال پیام خطای واضح‌تر
        frappe.throw(f"خطا در اعمال قیمت‌های دستی: {str(e)}")
        
        return {
            "success": False,
            "error": str(e),
            "message": f"خطا در اعمال قیمت‌های دستی: {str(e)}",
            "updated_count": 0,
            "total_items": 0,
            "affected_items": 0,
            "processed_items": 0,
            "manual_prices_count": 0,
            "manual_prices": [],
            "price_changes": []
        }

@frappe.whitelist()
def get_pricing_summary_api(docname, item_code=None):
    """API برای دریافت خلاصه محاسبات قیمت‌گذاری"""
    try:
        doc = frappe.get_doc("Auto Price List", docname)
        return doc.get_pricing_summary(item_code)
    except Exception as e:
        frappe.log_error(f"Error in get_pricing_summary_api: {str(e)}")
        return {"error": str(e)}

@frappe.whitelist()
def fix_duplicate_cost_calculations_api(docname):
    """API برای تصحیح محاسبات تکراری هزینه‌ها"""
    try:
        doc = frappe.get_doc("Auto Price List", docname)
        return doc.fix_duplicate_cost_calculations()
    except Exception as e:
        frappe.log_error(f"Error in fix_duplicate_cost_calculations_api: {str(e)}")
        return {"error": str(e)}

@frappe.whitelist()
def get_automatic_fixed_costs(doctype, name):
    """
    متد static برای دریافت هزینه‌های ثابت خودکار از تنظیمات
    """
    try:
        # ابتدا سعی می‌کنیم از تنظیمات Fixed Costs استفاده کنیم
        try:
            from pricing.pricing.doctype.fixed_costs_settings.fixed_costs_settings import get_current_fixed_costs
            fixed_costs = get_current_fixed_costs()
            if fixed_costs and fixed_costs > 0:
                return fixed_costs
        except:
            pass
        
        # اگر تنظیمات وجود نداشت، از روش قدیمی استفاده می‌کنیم
        doc = frappe.get_doc(doctype, name)
        return doc.get_automatic_monthly_fixed_costs()
    except Exception as e:
        frappe.logger("pricing").debug(f"خطا در دریافت هزینه‌های ثابت خودکار: {str(e)}")
        return 0

@frappe.whitelist()
def get_items_bom_status(doctype, name):
    """
    متد static برای بررسی وضعیت BOM فعال برای تمام محصولات در لیست
    """
    try:
        doc = frappe.get_doc(doctype, name)
        return doc.get_items_bom_status()
    except Exception as e:
        frappe.logger("pricing").debug(f"خطا در دریافت وضعیت BOM: {str(e)}")
        return {
            "items_without_bom": [],
            "items_with_unsubmitted_bom": []
        }

# اضافه کردن متدهای جدید به کلاس
AutoPriceList.get_price_comparison_data = get_price_comparison_data

@frappe.whitelist()
def update_item_prices_with_details_api(docname):
    """API wrapper برای محاسبه داینامیک قیمت‌ها"""
    try:
        doc = frappe.get_doc("Auto Price List", docname)
        
        if doc.items:
            for i, item in enumerate(doc.items[:3]):  # فقط 3 آیتم اول
                frappe.logger("pricing").debug(f"   آیتم {i+1}: {item.item_code}, total_cost: {item.total_cost}")
        
        result = doc.update_item_prices_with_details()
        frappe.logger("pricing").debug(f"🎯 نتیجه: {result}")
        return result
        
    except Exception as e:
        frappe.log_error(f"Error in update_item_prices_with_details_api: {str(e)}")
        import traceback
        frappe.logger("pricing").debug(traceback.format_exc())
        return {
            "success": False,
            "message": f"خطا در محاسبه: {str(e)}",
            "error": str(e)
        }

@frappe.whitelist()
def simple_dynamic_pricing_test(docname):
    """تست ساده برای محاسبه داینامیک قیمت‌ها"""
    try:
        doc = frappe.get_doc("Auto Price List", docname)
        
        if not doc.items:
            return {"success": False, "message": "هیچ آیتمی وجود ندارد"}
        
        updated_count = 0
        profit_margin = flt(doc.get('profit_margin') or 30)
        
        for item in doc.items:
            if not item.item_code:
                continue
                
            # اگر total_cost صفر است، یک مقدار پیش‌فرض بده
            if not item.total_cost or item.total_cost <= 0:
                item.total_cost = 100000  # مقدار پیش‌فرض برای تست
            
            # محاسبه قیمت ساده
            new_price = flt(item.total_cost) * (1 + profit_margin / 100)
            
            # به‌روزرسانی فیلدها
            item.selling_price = new_price
            item.final_selected_price = new_price
            item.profit_amount = new_price - flt(item.total_cost)
            
            updated_count += 1
            
            # محاسبه درصد سود برای لاگ
            profit_pct = (item.profit_amount / item.total_cost) * 100 if item.total_cost > 0 else 0
            frappe.logger("pricing").debug(f"✅ {item.item_code}: {item.total_cost:,.0f} → {new_price:,.0f} (سود: {profit_pct:.1f}%)")
        
        # ذخیره تغییرات
        doc.save()
        frappe.db.commit()
        
        return {
            "success": True,
            "message": f"قیمت {updated_count} محصول با موفقیت به‌روزرسانی شد"
        }
        
    except Exception as e:
        frappe.log_error(f"Error in simple_dynamic_pricing_test: {str(e)}")
        return {"success": False, "message": str(e)}

@frappe.whitelist()
def calculate_full_costing_background(docname):
    """
    محاسبه بهای تمام شده در پس‌زمینه (Background Job)
    """
    try:
        frappe.set_user("Administrator")
        doc = frappe.get_doc("Auto Price List", docname)
        
        # ارسال پیام شروع
        frappe.publish_realtime(
            event='costing_progress',
            message={
                'status': 'started',
                'message': f'🚀 شروع محاسبه بهای تمام شده برای {len(doc.items)} محصول',
                'progress': 0,
                'total': len(doc.items)
            },
            user=frappe.session.user,
            doctype='Auto Price List',
            docname=docname
        )
        
        # محاسبه با batch processing
        result = doc._calculate_full_costing_sync()
        
        # ارسال پیام پایان
        frappe.publish_realtime(
            event='costing_progress',
            message={
                'status': 'completed',
                'message': f'✅ محاسبه تکمیل شد',
                'progress': len(doc.items),
                'total': len(doc.items)
            },
            user=frappe.session.user,
            doctype='Auto Price List',
            docname=docname
        )
        
        return result
        
    except Exception as e:
        error_msg = f"خطا در محاسبه پس‌زمینه: {str(e)}"
        frappe.log_error(error_msg, "Background Costing Error")
        
        # ارسال پیام خطا
        frappe.publish_realtime(
            event='costing_progress',
            message={
                'status': 'error',
                'message': error_msg
            },
            user=frappe.session.user,
            doctype='Auto Price List',
            docname=docname
        )
        
        return {
            "success": False,
            "message": error_msg
        }

@frappe.whitelist()
def update_prices(docname):
    """
    API wrapper برای اعمال قیمت‌ها در لیست قیمت
    این تابع از JavaScript قابل فراخوانی است
    """
    try:
        doc = frappe.get_doc("Auto Price List", docname)
        return doc.update_prices()
    except Exception as e:
        frappe.log_error(f"خطا در update_prices API: {str(e)}")
        return {
            "success": False,
            "message": f"خطا: {str(e)}",
            "indicator": "red"
        }
        
        
# Module-level wrappers so frappe.call can find these methods via module path
@frappe.whitelist()
def fetch_prev_price_list_items(docname, prev_price_list=None):
    """Wrapper to call AutoPriceList.fetch_prev_price_list_items from client JS."""
    if not docname:
        return {"items": []}
    doc = frappe.get_doc('Auto Price List', docname)
    return doc.fetch_prev_price_list_items(prev_price_list)


@frappe.whitelist()
def apply_prev_prices_to_price_list(docname, to_apply=None, target_price_list=None):
    """Wrapper to call AutoPriceList.apply_prev_prices_to_price_list from client JS."""
    if not docname:
        return {"success": False, "message": "docname required"}
    doc = frappe.get_doc('Auto Price List', docname)
    return doc.apply_prev_prices_to_price_list(to_apply=to_apply, target_price_list=target_price_list)


@frappe.whitelist()
def calculate_product_bundles(docname):
    """محاسبه قیمت بسته‌های محصولات"""
    if not docname:
        return {"success": False, "message": "docname required"}
    doc = frappe.get_doc('Auto Price List', docname)
    return doc.calculate_product_bundles()


@frappe.whitelist()
def apply_bundle_prices(docname):
    """اعمال قیمت‌های بسته محصولات به لیست قیمت"""
    if not docname:
        return {"success": False, "message": "docname required"}
    doc = frappe.get_doc('Auto Price List', docname)
    return doc.apply_bundle_prices()


def run_full_costing_background(docname):
    """
    🚀 محاسبه بهای تمام شده در پس‌زمینه
    برای تعداد زیاد محصولات بدون timeout
    """
    import time
    start_time = time.time()
    
    try:
        doc = frappe.get_doc('Auto Price List', docname)
        items_count = len(doc.items)
        
        frappe.publish_realtime('costing_progress', {
            'progress': 5,
            'message': f'🔄 شروع محاسبه پس‌زمینه برای {items_count} محصول...'
        }, user=frappe.session.user)
        
        # جمع‌آوری همه item_codes و BOMs
        item_codes = [item.item_code for item in doc.items if item.item_code]
        bom_map = doc._bulk_load_all_boms(item_codes)
        
        frappe.publish_realtime('costing_progress', {
            'progress': 15,
            'message': f'BOMs بارگذاری شد ({len(bom_map)} مورد)'
        }, user=frappe.session.user)
        
        # محاسبه برای هر آیتم
        updated_count = 0
        errors = []
        
        for idx, item in enumerate(doc.items):
            if not item.item_code:
                continue
            
            try:
                # چک کردن قیمت‌های دستی محصول
                manual_costs = doc._get_manual_item_price(item.item_code)
                
                # پیدا کردن BOM
                bom_info = bom_map.get(item.item_code)
                bom_name = bom_info['name'] if bom_info else None
                
                if not bom_name:
                    item.raw_material_cost = 0
                    item.electricity_cost = 0
                    item.rent_cost = 0
                    item.labor_cost = 0
                    item.consumable_cost = 0
                    item.subcontracting_cost = 0
                    item.operation_cost = 0
                    item.overhead_cost = 0
                    item.total_cost = 0
                    continue
                
                # استفاده از محاسبه جامع
                breakdown = doc.get_comprehensive_cost_breakdown(item.item_code, bom_name)
                
                # 1. هزینه مواد اولیه
                if manual_costs and manual_costs.get('raw_material_cost') is not None:
                    item.raw_material_cost = manual_costs['raw_material_cost']
                else:
                    item.raw_material_cost = flt(breakdown.get('raw_material_cost', 0))
                
                # 2. هزینه‌های عملیاتی
                op_costs = breakdown.get('total_operation_costs', {})
                
                item.electricity_cost = flt(op_costs.get('electricity_cost', 0))
                item.rent_cost = flt(op_costs.get('rent_cost', 0))
                item.labor_cost = flt(op_costs.get('labor_cost', 0))
                item.consumable_cost = flt(op_costs.get('consumable_cost', 0))
                item.subcontracting_cost = flt(op_costs.get('subcontracting_cost', 0))
                
                # Override با قیمت‌های دستی
                if manual_costs:
                    if manual_costs.get('labor_cost') is not None:
                        item.labor_cost = manual_costs['labor_cost']
                    if manual_costs.get('subcontracting_cost') is not None:
                        item.subcontracting_cost = manual_costs['subcontracting_cost']
                    if manual_costs.get('electricity_cost') is not None:
                        item.electricity_cost = manual_costs['electricity_cost']
                    if manual_costs.get('rent_cost') is not None:
                        item.rent_cost = manual_costs['rent_cost']
                    if manual_costs.get('consumable_cost') is not None:
                        item.consumable_cost = manual_costs['consumable_cost']
                
                # محاسبه operation_cost
                if manual_costs and manual_costs.get('operation_cost') is not None:
                    item.operation_cost = manual_costs['operation_cost']
                else:
                    item.operation_cost = flt(item.labor_cost) + flt(item.subcontracting_cost)
                
                # 3. هزینه سربار
                if manual_costs and manual_costs.get('overhead_cost') is not None:
                    item.overhead_cost = manual_costs['overhead_cost']
                else:
                    item.overhead_cost = flt(breakdown.get('overhead_cost', 0))
                
                # 4. محاسبه total_cost
                item.total_cost = (
                    flt(item.raw_material_cost) +
                    flt(item.operation_cost) +
                    flt(item.overhead_cost)
                )
                
                # 5. محاسبه قیمت فروش
                if item.total_cost > 0:
                    if doc.pricing_steps:
                        final_price, _ = doc.calculate_price_based_on_steps_fast(item, item.total_cost)
                        item.final_selected_price = final_price
                        item.selling_price = final_price
                    else:
                        profit_margin = flt(doc.profit_margin or 0)
                        item.final_selected_price = item.total_cost * (1 + profit_margin / 100)
                        item.selling_price = item.final_selected_price
                    
                    item.profit_amount = flt(item.selling_price) - flt(item.total_cost)
                
                updated_count += 1
                
            except Exception as e:
                errors.append(f"{item.item_code}: {str(e)}")
            
            # گزارش پیشرفت هر 20 آیتم
            if (idx + 1) % 20 == 0 or idx == items_count - 1:
                progress = 15 + int((idx + 1) / items_count * 75)
                frappe.publish_realtime('costing_progress', {
                    'progress': progress,
                    'message': f'محاسبه شد: {idx + 1}/{items_count}'
                }, user=frappe.session.user)
        
        frappe.publish_realtime('costing_progress', {
            'progress': 92,
            'message': 'ذخیره نتایج...'
        }, user=frappe.session.user)
        
        # ذخیره batch
        doc._save_items_batch(doc.items)
        
        elapsed_time = time.time() - start_time
        
        frappe.publish_realtime('costing_progress', {
            'progress': 100,
            'message': f'✅ کامل شد در {elapsed_time:.1f} ثانیه'
        }, user=frappe.session.user)
        
        # اعلان پایان
        frappe.publish_realtime('costing_complete', {
            'docname': docname,
            'success': True,
            'message': f"✅ بهای تمام شده برای {updated_count} محصول در {elapsed_time:.1f} ثانیه محاسبه شد",
            'updated_items': updated_count,
            'elapsed_time': elapsed_time
        }, user=frappe.session.user)
        
        frappe.db.commit()
        
    except Exception as e:
        import traceback
        frappe.logger("pricing").error(f"خطا در محاسبه پس‌زمینه: {str(e)}\n{traceback.format_exc()}")
        frappe.db.rollback()
        
        frappe.publish_realtime('costing_complete', {
            'docname': docname,
            'success': False,
            'message': f"❌ خطا: {str(e)}"
        }, user=frappe.session.user)


@frappe.whitelist()
def calculate_full_costing_ultra_fast_api(docname):
    """
    ⚡ محاسبه فوق سریع بهای تمام شده - Module level API
    قابل فراخوانی از JavaScript
    """
    if not docname:
        return {"success": False, "message": "docname required"}
    
    try:
        doc = frappe.get_doc('Auto Price List', docname)
        return doc.calculate_full_costing_ultra_fast()
    except AttributeError:
        # fallback به متد معمولی
        frappe.logger("pricing").debug("calculate_full_costing_ultra_fast not found, using calculate_full_costing")
        doc = frappe.get_doc('Auto Price List', docname)
        return doc.calculate_full_costing()
    except Exception as e:
        frappe.log_error(f"Ultra fast costing error: {str(e)}")
        return {'success': False, 'message': str(e)}


# ═══════════════════════════════════════════════════════════════════════════
# 🔧 Manual API Trigger Methods (No Save Required from Client)
# ═══════════════════════════════════════════════════════════════════════════

@frappe.whitelist()
def calculate_item_prices_api(docname):
    """
    📊 مقایسه قیمت‌ها با لیست قیمت انتخاب شده
    این متد بدون نیاز به Save از سمت کلاینت، قیمت‌ها را محاسبه و ذخیره می‌کند
    """
    try:
        if not docname:
            return {"success": False, "message": "docname is required"}
        
        doc = frappe.get_doc("Auto Price List", docname)
        
        if not doc.compare_with_price_list:
            return {"success": False, "message": "لطفاً ابتدا لیست قیمت مقایسه را انتخاب کنید"}
        
        if not doc.items or len(doc.items) == 0:
            return {"success": False, "message": "هیچ آیتمی برای مقایسه وجود ندارد"}
        
        # Call the existing calculate_item_prices method
        doc.calculate_item_prices()
        doc.save()
        frappe.db.commit()
        
        return {
            "success": True, 
            "message": f"✅ قیمت‌های {len(doc.items)} آیتم با لیست {doc.compare_with_price_list} مقایسه شد"
        }
        
    except Exception as e:
        frappe.log_error(f"Error in calculate_item_prices_api: {str(e)}")
        return {"success": False, "message": f"❌ خطا: {str(e)}"}


@frappe.whitelist()
def recalculate_all_prices_api(docname, profit_margin=None, currency_exchange_rate=None, 
                             overhead_percentage=None, sales_tax_percentage=None):
    """
    🔄 محاسبه مجدد تمام قیمت‌ها در سرور
    این متد می‌تواند تنظیمات جدید را نیز دریافت و اعمال کند (شبیه Save عمل می‌کند اما سبک)
    """
    try:
        if not docname:
            return {"success": False, "message": "docname is required"}
        
        doc = frappe.get_doc("Auto Price List", docname)
        
        # 1. Update Global Parameters if provided
        changes_log = []
        if profit_margin is not None:
            doc.profit_margin = flt(profit_margin)
            changes_log.append(f"حاشیه سود: {doc.profit_margin}%")
            
        if currency_exchange_rate is not None:
            doc.currency_exchange_rate = flt(currency_exchange_rate)
            changes_log.append(f"نرخ ارز: {doc.currency_exchange_rate:,.0f}")
            
        if overhead_percentage is not None:
            doc.overhead_percentage = flt(overhead_percentage)
            
        if sales_tax_percentage is not None:
            doc.sales_tax_percentage = flt(sales_tax_percentage)

        if not doc.items or len(doc.items) == 0:
            doc.save() # Save parameters even if no items
            frappe.db.commit()
            return {"success": True, "message": "تنظیمات ذخیره شد (آیتمی برای محاسبه نبود)"}
        
        # 2. Recalculate Prices
        updated_count = 0
        effective_margin = flt(doc.profit_margin or 30)
        
        for item in doc.items:
            if not item.item_code:
                continue
            
            # Calculate selling price based on total_cost
            if item.total_cost and item.total_cost > 0:
                new_price = flt(item.total_cost) * (1 + effective_margin / 100)
                item.selling_price = new_price
                item.final_selected_price = new_price
                item.profit_amount = new_price - flt(item.total_cost)
                updated_count += 1
        
        doc.save()
        frappe.db.commit()
        
        msg = f"✅ تنظیمات ذخیره و قیمت {updated_count} محصول با سود {effective_margin}% محاسبه شد"
        return {
            "success": True,
            "message": msg
        }
        
    except Exception as e:
        frappe.log_error(f"Error in recalculate_all_prices_api: {str(e)}")
        return {"success": False, "message": f"❌ خطا: {str(e)}"}


@frappe.whitelist()
def clear_heavy_fields_api(docname):
    """
    🧹 پاکسازی فیلدهای سنگین از سند
    کاهش حجم سند و رفع مشکل 413 Request Entity Too Large
    """
    try:
        if not docname:
            return {"success": False, "message": "docname is required"}
        
        doc = frappe.get_doc("Auto Price List", docname)
        
        cleared_count = 0
        
        # 1. Clear heavy HTML dashboard fields
        html_fields = [
            'dashboard_html',
            'break_even_chart_html',
            'waterfall_chart_html',
            'bubble_chart_html',
            'sales_forecast_html',
            'roi_analysis_html',
            'product_ranking_html',
            'price_comparison_summary'
        ]
        
        for field in html_fields:
            if hasattr(doc, field) and getattr(doc, field):
                setattr(doc, field, "")
                cleared_count += 1
        
        # 2. Clear heavy item fields
        items_cleared = 0
        if doc.items:
            for item in doc.items:
                if hasattr(item, 'items_diff_log') and item.items_diff_log:
                    item.items_diff_log = ""
                    items_cleared += 1
                if hasattr(item, 'price_calculation_breakdown') and item.price_calculation_breakdown:
                    item.price_calculation_breakdown = ""
                if hasattr(item, 'pricing_breakdown') and item.pricing_breakdown:
                    item.pricing_breakdown = ""
                if hasattr(item, 'step_by_step_calculation') and item.step_by_step_calculation:
                    item.step_by_step_calculation = ""
        
        # 3. Clear Product Bundles data
        bundles_cleared = 0
        if doc.product_bundles:
            for bundle in doc.product_bundles:
                if hasattr(bundle, 'bundle_items_html') and bundle.bundle_items_html:
                    bundle.bundle_items_html = ""
                    bundles_cleared += 1
                if hasattr(bundle, 'bundle_items_data') and bundle.bundle_items_data:
                    bundle.bundle_items_data = ""
        
        doc.save()
        frappe.db.commit()
        
        # Calculate size reduction
        total_cleared = cleared_count + items_cleared + bundles_cleared
        
        return {
            "success": True,
            "message": f"✅ پاکسازی انجام شد: {cleared_count} فیلد HTML، {items_cleared} آیتم، {bundles_cleared} بسته محصول"
        }
        
    except Exception as e:
        frappe.log_error(f"Error in clear_heavy_fields_api: {str(e)}")
        return {"success": False, "message": f"❌ خطا: {str(e)}"}
@frappe.whitelist()
def add_items_server_side(docname, item_group=None, brand=None, name_filter=None):
    """
    Server-side method to fetch and add items to the Auto Price List.
    This bypasses client-side payload limits by handling the data on the server.
    """
    try:
        doc = frappe.get_doc("Auto Price List", docname)
        
        filters = {}
        if item_group:
            filters['item_group'] = item_group
        if brand:
            filters['brand'] = brand
        if name_filter:
            filters['item_name'] = ['like', f'%{name_filter}%']
            
        items_to_add = frappe.get_all('Item', filters=filters, fields=['item_code', 'item_name', 'item_group', 'brand'])
        
        existing_items = set(item.item_code for item in doc.items)
        added_count = 0
        
        for item in items_to_add:
            if item.item_code not in existing_items:
                doc.append('items', {
                    'item_code': item.item_code,
                    'item_name': item.item_name,
                    'item_group': item.item_group,
                    'brand': item.brand
                })
                existing_items.add(item.item_code)
                added_count += 1
        
        if added_count > 0:
            doc.save()
            frappe.db.commit()
            return {
                "success": True,
                "message": f"{added_count} item(s) added successfully.",
                "count": added_count
            }
        else:
            return {
                "success": False,
                "message": "No new items found to add.",
                "count": 0
            }
            
    except Exception as e:
        frappe.log_error(f"Error in add_items_server_side: {str(e)}")
        return {
            "success": False,
            "message": f"Error adding items: {str(e)}"
        }
