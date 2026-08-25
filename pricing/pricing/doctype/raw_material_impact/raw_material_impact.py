# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class RawMaterialImpact(Document):
    def validate(self):
        """Validate raw material impact data"""
        if self.current_cost_per_unit and self.new_cost_per_unit:
            # Calculate cost impact
            self.cost_impact_per_unit = self.new_cost_per_unit - self.current_cost_per_unit
            
            # Calculate total cost impact if usage quantity is provided
            if self.usage_quantity:
                self.total_cost_impact = self.cost_impact_per_unit * self.usage_quantity
            
            # Determine impact severity
            if self.cost_impact_per_unit != 0:
                impact_percent = abs(self.cost_impact_per_unit / self.current_cost_per_unit) * 100
                
                if impact_percent >= 20:
                    self.impact_severity = "Critical"
                elif impact_percent >= 10:
                    self.impact_severity = "High"
                elif impact_percent >= 5:
                    self.impact_severity = "Medium"
                else:
                    self.impact_severity = "Low"
            
            # Set recommended action based on impact
            self.recommended_action = self.get_recommended_action()
    
    def get_recommended_action(self):
        """Get recommended action based on impact severity and direction"""
        if not self.cost_impact_per_unit:
            return "Monitor"
        
        is_increase = self.cost_impact_per_unit > 0
        
        if self.impact_severity == "Critical":
            return "Find Alternative Supplier" if is_increase else "Negotiate Long-term Contract"
        elif self.impact_severity == "High":
            return "Negotiate Price" if is_increase else "Increase Order Quantity"
        elif self.impact_severity == "Medium":
            return "Review Pricing Strategy" if is_increase else "Optimize Usage"
        else:
            return "Monitor Trends"
    
    def get_item_details(self):
        """Get item details from Item master"""
        if self.item_code:
            item = frappe.get_doc("Item", self.item_code)
            self.item_name = item.item_name
            self.item_group = item.item_group
            return item
        return None
