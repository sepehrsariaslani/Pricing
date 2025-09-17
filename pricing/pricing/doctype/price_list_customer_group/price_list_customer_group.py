import frappe
from frappe.model.document import Document

class PriceListCustomerGroup(Document):
    def validate(self):
        self.validate_customer_group()

    def validate_customer_group(self):
        if not frappe.db.exists("Customer Group", self.customer_group):
            frappe.throw(f"Customer Group {self.customer_group} does not exist") 