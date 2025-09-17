# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class RawMaterialPriceHistory(Document):
    def validate(self):
        """Validate price history data"""
        if self.price and self.previous_price:
            # Calculate price change
            self.price_change = self.price - self.previous_price
            
            # Calculate percentage change
            if self.previous_price != 0:
                self.price_change_percent = (self.price_change / self.previous_price) * 100
            
            # Set change direction
            if self.price_change > 0:
                self.change_direction = "Increase"
            elif self.price_change < 0:
                self.change_direction = "Decrease"
            else:
                self.change_direction = "No Change"
    
    def before_insert(self):
        """Actions before inserting new price history record"""
        # Set source if not provided
        if not self.source:
            self.source = "Manual Entry"
        
        # Validate date
        if not self.date:
            self.date = frappe.utils.today()
    
    @staticmethod
    def add_price_record(material_code, price, source="Manual", notes=None):
        """Add a new price history record"""
        # Get previous price
        previous_record = frappe.get_all("Raw Material Price History",
            filters={"parent": material_code},
            fields=["price"],
            order_by="date desc",
            limit=1)
        
        previous_price = previous_record[0].price if previous_record else 0
        
        # Create new record
        history = frappe.get_doc({
            "doctype": "Raw Material Price History",
            "parent": material_code,
            "parenttype": "Raw Material Pricing",
            "parentfield": "price_history",
            "date": frappe.utils.today(),
            "price": price,
            "previous_price": previous_price,
            "source": source,
            "notes": notes
        })
        
        history.insert()
        return history
