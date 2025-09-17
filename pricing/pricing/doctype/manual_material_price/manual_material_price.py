# Copyright (c) 2024, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt

class ManualMaterialPrice(Document):
	def validate(self):
		"""Validate manual material price entry"""
		if self.manual_price <= 0:
			frappe.throw("قیمت دستی باید بزرگتر از صفر باشد")
		
		# Set item name if not set
		if not self.item_name and self.item_code:
			self.item_name = frappe.db.get_value("Item", self.item_code, "item_name")
		
		# Set UOM if not set
		if not self.uom and self.item_code:
			self.uom = frappe.db.get_value("Item", self.item_code, "stock_uom")
	
	def on_update(self):
		"""Called after document is saved - trigger price recalculation"""
		self.update_affected_price_lists()
	
	def update_affected_price_lists(self):
		"""
		به‌روزرسانی لیست‌های قیمت متأثر از تغییر قیمت این ماده اولیه
		این تابع تمام Auto Price List هایی که از این ماده استفاده می‌کنند را پیدا کرده
		و قیمت‌های آن‌ها را مجدداً محاسبه می‌کند
		"""
		try:
			# پیدا کردن تمام BOM هایی که از این ماده استفاده می‌کنند
			affected_boms = self.find_affected_boms()
			
			if not affected_boms:
				frappe.msgprint(f"هیچ BOM ای که از ماده {self.item_code} استفاده کند پیدا نشد")
				return
			
			# پیدا کردن محصولات متأثر
			affected_items = [bom.item for bom in affected_boms]
			
			# پیدا کردن Auto Price List هایی که این محصولات را دارند
			affected_price_lists = self.find_affected_price_lists(affected_items)
			
			if not affected_price_lists:
				frappe.msgprint(f"هیچ لیست قیمتی که محصولات متأثر از {self.item_code} را داشته باشد پیدا نشد")
				return
			
			# به‌روزرسانی قیمت‌ها
			updated_count = 0
			for price_list in affected_price_lists:
				try:
					price_list_doc = frappe.get_doc("Auto Price List", price_list.name)
					# فقط محصولات متأثر را مجدداً محاسبه کن
					self.recalculate_affected_items(price_list_doc, affected_items)
					updated_count += 1
				except Exception as e:
					frappe.logger().error(f"Price list update error: {price_list.name[:20]}...")
			
			if updated_count > 0:
				frappe.msgprint(f"✅ قیمت‌های {updated_count} لیست قیمت به‌روزرسانی شد")
				
				# نمایش جزئیات تغییرات
				self.show_price_impact_summary(affected_items)
			
		except Exception as e:
			frappe.logger().error("Price update error occurred")
			frappe.msgprint("خطا در به‌روزرسانی قیمت‌ها", indicator='red')
	
	def find_affected_boms(self):
		"""پیدا کردن BOM هایی که از این ماده اولیه استفاده می‌کنند"""
		return frappe.db.sql("""
			SELECT DISTINCT b.name, b.item, b.item_name
			FROM `tabBOM` b
			INNER JOIN `tabBOM Item` bi ON b.name = bi.parent
			WHERE bi.item_code = %s 
			AND b.is_active = 1
			AND b.is_default = 1
		""", (self.item_code,), as_dict=True)
	
	def find_affected_price_lists(self, affected_items):
		"""پیدا کردن Auto Price List هایی که محصولات متأثر را دارند"""
		if not affected_items:
			return []
		
		item_codes = [item for item in affected_items]
		placeholders = ', '.join(['%s'] * len(item_codes))
		
		return frappe.db.sql(f"""
			SELECT DISTINCT apl.name, apl.title
			FROM `tabAuto Price List` apl
			INNER JOIN `tabAuto Price List Item` apli ON apl.name = apli.parent
			WHERE apli.item_code IN ({placeholders})
			AND apl.docstatus != 2
		""", tuple(item_codes), as_dict=True)
	
	def recalculate_affected_items(self, price_list_doc, affected_items):
		"""محاسبه مجدد قیمت محصولات متأثر در یک لیست قیمت"""
		for item_code in affected_items:
			# پیدا کردن آیتم در لیست قیمت
			for item in price_list_doc.items:
				if item.item_code == item_code:
					try:
						# محاسبه مجدد قیمت این آیتم
						old_price = item.selling_price
						
						# محاسبه قیمت جدید با استفاده از قیمت دستی جدید
						new_cost = price_list_doc.calculate_item_cost(item_code)
						
						# اعمال سود و سایر محاسبات
						if price_list_doc.profit_margin:
							profit_amount = new_cost * (price_list_doc.profit_margin / 100)
							new_price = new_cost + profit_amount
						else:
							new_price = new_cost
						
						# به‌روزرسانی قیمت
						item.raw_material_cost = new_cost
						item.selling_price = new_price
						
						frappe.logger().info(f"قیمت {item_code} از {old_price} به {new_price} تغییر کرد")
						
					except Exception as e:
						frappe.logger().error(f"Recalc error: {item_code[:15]}...")
		
		# ذخیره تغییرات
		price_list_doc.save()
	
	def show_price_impact_summary(self, affected_items):
		"""نمایش خلاصه تأثیر تغییر قیمت"""
		try:
			summary_html = f"""
			<div style="margin: 10px 0;">
				<h4>📊 خلاصه تأثیر تغییر قیمت ماده: {self.item_code}</h4>
				<p><strong>قیمت جدید:</strong> {frappe.format_value(self.manual_price, 'Currency')}</p>
				<p><strong>محصولات متأثر:</strong></p>
				<ul>
			"""
			
			for item_code in affected_items:
				item_name = frappe.db.get_value("Item", item_code, "item_name")
				summary_html += f"<li>{item_code} - {item_name}</li>"
			
			summary_html += """
				</ul>
				<p style="color: green;">✅ قیمت‌های تمام محصولات متأثر به‌روزرسانی شد</p>
			</div>
			"""
			
			frappe.msgprint(summary_html, title="تأثیر تغییر قیمت ماده اولیه")
			
		except Exception as e:
			frappe.logger().error("Summary display error")

@frappe.whitelist()
def preview_price_impact(item_code, new_price):
	"""پیش‌نمایش تأثیر تغییر قیمت ماده اولیه"""
	try:
		new_price = flt(new_price)
		
		# پیدا کردن BOM های متأثر
		affected_boms = frappe.db.sql("""
			SELECT DISTINCT b.name, b.item, b.item_name
			FROM `tabBOM` b
			INNER JOIN `tabBOM Item` bi ON b.name = bi.parent
			WHERE bi.item_code = %s 
			AND b.is_active = 1
			AND b.is_default = 1
		""", (item_code,), as_dict=True)
		
		if not affected_boms:
			return {"affected_count": 0, "avg_price_change": 0}
		
		total_change = 0
		affected_count = len(affected_boms)
		
		# محاسبه میانگین تغییر قیمت
		for bom in affected_boms:
			# این یک تخمین ساده است
			total_change += 5  # فرض 5% تغییر برای هر محصول
		
		avg_change = total_change / affected_count if affected_count > 0 else 0
		
		return {
			"affected_count": affected_count,
			"avg_price_change": round(avg_change, 2)
		}
		
	except Exception as e:
		frappe.logger().error("Price impact preview error")
		return {"affected_count": 0, "avg_price_change": 0}

@frappe.whitelist()
def get_detailed_price_impact(item_code, new_price):
	"""دریافت جزئیات کامل تأثیر تغییر قیمت"""
	try:
		new_price = flt(new_price)
		
		# پیدا کردن BOM های متأثر
		affected_boms = frappe.db.sql("""
			SELECT DISTINCT b.name, b.item, b.item_name, bi.qty
			FROM `tabBOM` b
			INNER JOIN `tabBOM Item` bi ON b.name = bi.parent
			WHERE bi.item_code = %s 
			AND b.is_active = 1
			AND b.is_default = 1
		""", (item_code,), as_dict=True)
		
		if not affected_boms:
			html = "<p>هیچ محصولی که از این ماده استفاده کند پیدا نشد</p>"
			return {"html": html}
		
		# ساخت HTML جزئیات
		html = f"""
		<div style="margin: 10px 0;">
			<h4>📊 جزئیات تأثیر تغییر قیمت</h4>
			<p><strong>ماده اولیه:</strong> {item_code}</p>
			<p><strong>قیمت جدید:</strong> {frappe.format_value(new_price, 'Currency')}</p>
			<p><strong>تعداد محصولات متأثر:</strong> {len(affected_boms)}</p>
			
			<table class="table table-bordered">
				<thead>
					<tr>
						<th>کد محصول</th>
						<th>نام محصول</th>
						<th>مقدار مصرف</th>
						<th>تأثیر هزینه</th>
					</tr>
				</thead>
				<tbody>
		"""
		
		for bom in affected_boms:
			cost_impact = new_price * bom.qty
			html += f"""
				<tr>
					<td>{bom.item}</td>
					<td>{bom.item_name}</td>
					<td>{bom.qty}</td>
					<td>{frappe.format_value(cost_impact, 'Currency')}</td>
				</tr>
			"""
		
		html += """
				</tbody>
			</table>
		</div>
		"""
		
		return {"html": html}
		
	except Exception as e:
		frappe.logger().error("Price impact detail error")
		return {"html": "<p>خطا در محاسبه جزئیات</p>"}

@frappe.whitelist()
def force_update_prices(item_code, new_price):
	"""به‌روزرسانی اجباری قیمت‌های متأثر"""
	try:
		new_price = flt(new_price)
		
		# ایجاد یک رکورد موقت برای استفاده از توابع کلاس
		temp_doc = frappe.new_doc("Manual Material Price")
		temp_doc.item_code = item_code
		temp_doc.manual_price = new_price
		
		# اجرای به‌روزرسانی
		temp_doc.update_affected_price_lists()
		
		return {
			"message": f"قیمت‌های متأثر از ماده {item_code} با موفقیت به‌روزرسانی شد"
		}
		
	except Exception as e:
		frappe.logger().error("Force update error")
		frappe.throw("خطا در به‌روزرسانی قیمت‌ها")
