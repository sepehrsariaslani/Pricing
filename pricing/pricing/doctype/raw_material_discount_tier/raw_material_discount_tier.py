# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate


class RawMaterialDiscountTier(Document):
    def validate(self):
        """Validate discount tier data"""
        # Validate quantity range
        if self.min_quantity and self.max_quantity:
            if self.min_quantity >= self.max_quantity:
                frappe.throw("Maximum quantity must be greater than minimum quantity")
        
        # Validate discount percentage
        if self.discount_percentage:
            if self.discount_percentage < 0 or self.discount_percentage > 100:
                frappe.throw("Discount percentage must be between 0 and 100")
        
        # Validate effective dates
        if self.effective_from and self.effective_to:
            if getdate(self.effective_from) > getdate(self.effective_to):
                frappe.throw("Effective To date must be after Effective From date")
        
        # Calculate discounted price if unit price is available
        if hasattr(self, 'unit_price') and self.unit_price and self.discount_percentage:
            self.discounted_price = self.unit_price * (1 - self.discount_percentage / 100)
    
    def is_applicable(self, quantity, date=None):
        """Check if this discount tier is applicable for given quantity and date"""
        if date is None:
            date = frappe.utils.today()
        
        date = getdate(date)
        
        # Check quantity range
        quantity_valid = True
        if self.min_quantity and quantity < self.min_quantity:
            quantity_valid = False
        if self.max_quantity and quantity > self.max_quantity:
            quantity_valid = False
        
        # Check date range
        date_valid = True
        if self.effective_from and date < getdate(self.effective_from):
            date_valid = False
        if self.effective_to and date > getdate(self.effective_to):
            date_valid = False
        
        return quantity_valid and date_valid
    
    def calculate_discount_amount(self, quantity, unit_price):
        """Calculate total discount amount for given quantity and unit price"""
        if not self.is_applicable(quantity):
            return 0
        
        total_value = quantity * unit_price
        discount_amount = total_value * (self.discount_percentage / 100)
        
        return discount_amount
    
    def get_tier_description(self):
        """Get human-readable description of this tier"""
        desc_parts = []
        
        if self.min_quantity and self.max_quantity:
            desc_parts.append(f"{self.min_quantity:,.0f} - {self.max_quantity:,.0f} units")
        elif self.min_quantity:
            desc_parts.append(f"{self.min_quantity:,.0f}+ units")
        elif self.max_quantity:
            desc_parts.append(f"Up to {self.max_quantity:,.0f} units")
        
        if self.discount_percentage:
            desc_parts.append(f"{self.discount_percentage}% discount")
        
        return " | ".join(desc_parts)
