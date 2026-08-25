import frappe
from frappe.model.document import Document

class AutoPriceListPricingStep(Document):
    def validate(self):
        """اعتبارسنجی مرحله قیمت‌گذاری"""
        # تولید توضیح خودکار
        self.generate_description()
    
    def generate_description(self):
        """تولید توضیح خودکار برای مرحله"""
        if self.step_type == 'رند کردن':
            self.description = f"{self.step_type} (بر اساس تنظیمات)"
        elif self.step_type in ['بهره قسطی', 'بهره تأخیری']:
            self.description = f"{self.step_type} (بر اساس تنظیمات)"
        else:
            self.description = f"{self.step_type} (بر اساس تنظیمات)"
    
    def get_english_type(self):
        """تبدیل نوع فارسی به انگلیسی"""
        persian_to_english = {
            'سود': 'profit_margin',
            'تخفیف': 'target_discount_percentage',
            'کمیسیون': 'commission_percentage',
            'بهره قسطی': 'installment_interest',
            'بهره تأخیری': 'deferred_payment_interest',
            'رند کردن': 'rounding'
        }
        return persian_to_english.get(self.step_type, 'unknown')
