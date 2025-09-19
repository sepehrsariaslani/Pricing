# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class BulkPricingItem(Document):
	def before_save(self):
		"""Auto-populate item details when item_code is selected"""
		if self.item_code:
			item_doc = frappe.get_doc("Item", self.item_code)
			self.item_name = item_doc.item_name
			self.item_group = item_doc.item_group
			self.brand = item_doc.brand
