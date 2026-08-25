# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

class FixedCostsSettings(Document):
	def validate(self):
		"""Validation before saving"""
		if self.months_for_average and self.months_for_average < 1:
			frappe.throw("تعداد ماه برای میانگین باید حداقل 1 باشد")
		
		if self.months_for_average and self.months_for_average > 12:
			frappe.throw("تعداد ماه برای میانگین نباید بیشتر از 12 باشد")

	def calculate_monthly_fixed_costs(self):
		"""
		محاسبه هزینه‌های ثابت ماهانه بر اساس حساب‌های تعریف شده
		"""
		try:
			if not self.fixed_costs_accounts:
				frappe.throw("هیچ حساب هزینه ثابتی تعریف نشده است")
			
			# دریافت شرکت پیش‌فرض
			company = frappe.defaults.get_user_default("Company")
			if not company:
				frappe.throw("شرکت پیش‌فرض تعریف نشده است")
			
			# تاریخ‌های محاسبه بر اساس روش انتخاب شده
			today = datetime.now().date()
			
			if self.calculation_method == "میانگین ماه گذشته":
				start_date = (today.replace(day=1) - relativedelta(months=1))
				end_date = today.replace(day=1) - timedelta(days=1)
			elif self.calculation_method == "میانگین چند ماه گذشته":
				months = self.months_for_average or 3
				start_date = (today.replace(day=1) - relativedelta(months=months))
				end_date = today.replace(day=1) - timedelta(days=1)
			else:  # مجموع ماه جاری
				start_date = today.replace(day=1)
				end_date = today
			
			# لیست حساب‌های انتخاب شده
			account_names = [acc.account for acc in self.fixed_costs_accounts if acc.account]
			
			if not account_names:
				frappe.throw("هیچ حساب معتبری انتخاب نشده است")
			
			# ساخت شرط WHERE برای حساب‌ها
			account_conditions = []
			for account in account_names:
				account_conditions.append(f"gle.account = '{account}'")
			
			account_where_clause = " OR ".join(account_conditions)
			
			# Query اصلی
			if self.calculation_method in ["میانگین ماه گذشته", "مجموع ماه جاری"]:
				query = f"""
					SELECT 
						SUM(ABS(gle.debit - gle.credit)) as total_fixed_costs
					FROM `tabGL Entry` gle
					WHERE 
						gle.company = %s
						AND gle.posting_date BETWEEN %s AND %s
						AND ({account_where_clause})
						AND gle.is_cancelled = 0
				"""
				
				result = frappe.db.sql(query, (company, start_date, end_date), as_dict=True)
				total_costs = result[0]['total_fixed_costs'] if result and result[0]['total_fixed_costs'] else 0
				
			else:  # میانگین چند ماه گذشته
				query = f"""
					SELECT 
						AVG(monthly_costs.total) as avg_fixed_costs
					FROM (
						SELECT 
							YEAR(gle.posting_date) as year,
							MONTH(gle.posting_date) as month,
							SUM(ABS(gle.debit - gle.credit)) as total
						FROM `tabGL Entry` gle
						WHERE 
							gle.company = %s
							AND gle.posting_date BETWEEN %s AND %s
							AND ({account_where_clause})
							AND gle.is_cancelled = 0
						GROUP BY YEAR(gle.posting_date), MONTH(gle.posting_date)
					) as monthly_costs
				"""
				
				result = frappe.db.sql(query, (company, start_date, end_date), as_dict=True)
				total_costs = result[0]['avg_fixed_costs'] if result and result[0]['avg_fixed_costs'] else 0
			
			# به‌روزرسانی فیلدها
			self.current_monthly_fixed_costs = float(total_costs) if total_costs else 0
			self.last_calculation_date = datetime.now()
			self.last_updated_by = frappe.session.user
			
			# ذخیره تغییرات
			self.save()
			
			frappe.logger().info(f"هزینه‌های ثابت ماهانه محاسبه شد: {self.current_monthly_fixed_costs:,.0f} ریال")
			
			return {
				"success": True,
				"monthly_fixed_costs": self.current_monthly_fixed_costs,
				"calculation_method": self.calculation_method,
				"accounts_count": len(account_names),
				"date_range": f"{start_date} تا {end_date}"
			}
			
		except Exception as e:
			frappe.logger().error(f"خطا در محاسبه هزینه‌های ثابت: {str(e)}")
			import traceback
			frappe.logger().error(f"جزئیات خطا: {traceback.format_exc()}")
			return {
				"success": False,
				"error": str(e),
				"monthly_fixed_costs": 0
			}

	def get_account_breakdown(self):
		"""
		دریافت تفکیک هزینه‌ها بر اساس هر حساب
		"""
		try:
			if not self.fixed_costs_accounts:
				return []
			
			company = frappe.defaults.get_user_default("Company")
			if not company:
				return []
			
			# تاریخ‌های محاسبه
			today = datetime.now().date()
			
			if self.calculation_method == "میانگین ماه گذشته":
				start_date = (today.replace(day=1) - relativedelta(months=1))
				end_date = today.replace(day=1) - timedelta(days=1)
			elif self.calculation_method == "میانگین چند ماه گذشته":
				months = self.months_for_average or 3
				start_date = (today.replace(day=1) - relativedelta(months=months))
				end_date = today.replace(day=1) - timedelta(days=1)
			else:  # مجموع ماه جاری
				start_date = today.replace(day=1)
				end_date = today
			
			breakdown = []
			
			for acc in self.fixed_costs_accounts:
				if not acc.account:
					continue
				
				# Query برای هر حساب جداگانه
				if self.calculation_method in ["میانگین ماه گذشته", "مجموع ماه جاری"]:
					query = """
						SELECT 
							SUM(ABS(gle.debit - gle.credit)) as account_total
						FROM `tabGL Entry` gle
						WHERE 
							gle.company = %s
							AND gle.posting_date BETWEEN %s AND %s
							AND gle.account = %s
							AND gle.is_cancelled = 0
					"""
					
					result = frappe.db.sql(query, (company, start_date, end_date, acc.account), as_dict=True)
					account_total = result[0]['account_total'] if result and result[0]['account_total'] else 0
					
				else:  # میانگین چند ماه گذشته
					query = """
						SELECT 
							AVG(monthly_costs.total) as avg_account_costs
						FROM (
							SELECT 
								YEAR(gle.posting_date) as year,
								MONTH(gle.posting_date) as month,
								SUM(ABS(gle.debit - gle.credit)) as total
							FROM `tabGL Entry` gle
							WHERE 
								gle.company = %s
								AND gle.posting_date BETWEEN %s AND %s
								AND gle.account = %s
								AND gle.is_cancelled = 0
							GROUP BY YEAR(gle.posting_date), MONTH(gle.posting_date)
						) as monthly_costs
					"""
					
					result = frappe.db.sql(query, (company, start_date, end_date, acc.account), as_dict=True)
					account_total = result[0]['avg_account_costs'] if result and result[0]['avg_account_costs'] else 0
				
				# دریافت نام حساب
				account_name = frappe.db.get_value("Account", acc.account, "account_name") or acc.account
				
				breakdown.append({
					"account": acc.account,
					"account_name": account_name,
					"description": acc.description or "",
					"amount": float(account_total) if account_total else 0,
					"percentage": 0  # محاسبه بعداً
				})
			
			# محاسبه درصدها
			total_amount = sum(item['amount'] for item in breakdown)
			if total_amount > 0:
				for item in breakdown:
					item['percentage'] = (item['amount'] / total_amount) * 100
			
			return breakdown
			
		except Exception as e:
			frappe.logger().error(f"خطا در دریافت تفکیک حساب‌ها: {str(e)}")
			return []

@frappe.whitelist()
def calculate_fixed_costs():
	"""
	متد عمومی برای محاسبه هزینه‌های ثابت
	"""
	try:
		settings = frappe.get_single("Fixed Costs Settings")
		return settings.calculate_monthly_fixed_costs()
	except Exception as e:
		frappe.logger().error(f"خطا در محاسبه هزینه‌های ثابت: {str(e)}")
		return {
			"success": False,
			"error": str(e),
			"monthly_fixed_costs": 0
		}

@frappe.whitelist()
def get_fixed_costs_breakdown():
	"""
	متد عمومی برای دریافت تفکیک هزینه‌های ثابت
	"""
	try:
		settings = frappe.get_single("Fixed Costs Settings")
		return settings.get_account_breakdown()
	except Exception as e:
		frappe.logger().error(f"خطا در دریافت تفکیک هزینه‌ها: {str(e)}")
		return []

@frappe.whitelist()
def get_current_fixed_costs():
	"""
	دریافت هزینه‌های ثابت فعلی
	"""
	try:
		settings = frappe.get_single("Fixed Costs Settings")
		return settings.current_monthly_fixed_costs or 0
	except Exception as e:
		frappe.logger().error(f"خطا در دریافت هزینه‌های ثابت فعلی: {str(e)}")
		return 0
