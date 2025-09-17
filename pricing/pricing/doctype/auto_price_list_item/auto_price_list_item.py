import frappe
from frappe.model.document import Document

class AutoPriceListItem(Document):
    def validate(self):
        """Validate the item"""
        self.validate_item()
        self.set_item_details()

    def validate_item(self):
        """Validate if item exists"""
        if not frappe.db.exists("Item", self.item_code):
            frappe.throw(f"Item {self.item_code} does not exist")

    def set_item_details(self):
        """Set item details from Item master"""
        if self.item_code:
            item = frappe.get_doc("Item", self.item_code)
            self.item_name = item.item_name
            self.item_group = item.item_group
            self.brand = item.brand 