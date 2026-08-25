# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt

class AutoPriceListManualItemPrice(Document):
	def validate(self):
		"""Validate the manual item price"""
		self.calculate_total_manual_cost()
		self.set_tracking_info()
	
	def calculate_total_manual_cost(self):
		"""Calculate total manual cost from individual components"""
		self.total_manual_cost = (
			flt(self.manual_raw_material_cost or 0) +
			flt(self.manual_operation_cost or 0) +
			flt(self.manual_overhead_cost or 0)
		)
	
	def set_tracking_info(self):
		"""Set tracking information"""
		if not self.created_by:
			self.created_by = frappe.session.user
		self.last_updated = frappe.utils.now()
