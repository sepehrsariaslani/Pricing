# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class FixedCostAccount(Document):
	def validate(self):
		"""Validation before saving"""
		if self.account:
			# بررسی اینکه حساب از نوع Expense باشد
			account_type = frappe.db.get_value("Account", self.account, "account_type")
			if account_type != "Expense":
				frappe.throw(f"حساب {self.account} باید از نوع 'Expense' باشد")
			
			# دریافت نام حساب
			self.account_name = frappe.db.get_value("Account", self.account, "account_name")
