# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, today


class RawMaterialSupplier(Document):
    def validate(self):
        """Validate supplier data"""
        # Get supplier details if not provided
        if self.supplier and not self.supplier_name:
            supplier_doc = frappe.get_doc("Supplier", self.supplier)
            self.supplier_name = supplier_doc.supplier_name
        
        # Set last updated date
        if not self.last_updated:
            self.last_updated = today()
        
        # Validate rating
        if self.supplier_rating and (self.supplier_rating < 1 or self.supplier_rating > 5):
            frappe.throw("Supplier rating must be between 1 and 5")
        
        # Calculate price competitiveness if market price is available
        if self.quoted_price and hasattr(self, 'market_price') and self.market_price:
            self.price_competitiveness = ((self.market_price - self.quoted_price) / self.market_price) * 100
    
    def get_supplier_details(self):
        """Get detailed supplier information"""
        if self.supplier:
            return frappe.get_doc("Supplier", self.supplier)
        return None
    
    def calculate_total_score(self):
        """Calculate total supplier score based on price, rating, and lead time"""
        scores = []
        
        # Price score (lower price = higher score)
        if self.quoted_price and hasattr(self, 'market_price') and self.market_price:
            price_ratio = self.quoted_price / self.market_price
            price_score = max(0, (2 - price_ratio) * 50)  # 0-100 scale
            scores.append(price_score)
        
        # Rating score
        if self.supplier_rating:
            rating_score = (self.supplier_rating / 5) * 100  # Convert to 0-100 scale
            scores.append(rating_score)
        
        # Lead time score (shorter lead time = higher score)
        if self.lead_time_days:
            # Assume 30 days is baseline, shorter is better
            lead_time_score = max(0, (30 - self.lead_time_days) / 30 * 100)
            scores.append(lead_time_score)
        
        # Calculate weighted average
        if scores:
            return sum(scores) / len(scores)
        
        return 0
    
    def is_preferred_supplier(self):
        """Check if this is a preferred supplier based on score and rating"""
        total_score = self.calculate_total_score()
        return total_score >= 70 and (self.supplier_rating or 0) >= 4
