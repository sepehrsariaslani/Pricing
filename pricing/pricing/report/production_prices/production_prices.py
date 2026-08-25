# Copyright (c) 2024, Sepehr and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import math


def execute(filters=None):
	if filters and filters.get("show_comparison"):
		columns = get_comparison_columns()
		data = get_comparison_data(filters)
	elif filters and filters.get("show_summary"):
		columns = get_summary_columns()
		data = get_summary_data(filters)
	else:
		columns = get_columns()
		data = get_data(filters)
	return columns, data


def get_filters():
	"""Define report filters"""
	return [
		{
			"fieldname": "item_code",
			"label": "کد محصول",
			"fieldtype": "Link",
			"options": "Item",
			"width": "80"
		},
		{
			"fieldname": "item_group",
			"label": "گروه محصول",
			"fieldtype": "Link",
			"options": "Item Group",
			"width": "80"
		},
		{
			"fieldname": "workstation",
			"label": "ایستگاه کاری",
			"fieldtype": "Link",
			"options": "Workstation",
			"width": "80"
		}
	]


def get_columns():
	"""Define report columns"""
	return [
		{
			"label": "نام محصول",
			"fieldname": "main_item_name",
			"fieldtype": "Data",
			"width": 200
		},
		{
			"label": "گروه محصول",
			"fieldname": "item_group",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"label": "مورد تولید",
			"fieldname": "production_item",
			"fieldtype": "Data",
			"width": 180
		},
		{
			"label": "عملیات",
			"fieldname": "operation",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"label": "زمان عملیات",
			"fieldname": "time_in_mins",
			"fieldtype": "Float",
			"width": 100
		},
		{
			"label": "ایستگاه کاری",
			"fieldname": "workstation",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": "بخش کاری",
			"fieldname": "department",
			"fieldtype": "Data",
			"width": 120
		},
		{
			"label": "مزد",
			"fieldname": "labor_cost_per_hour",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": "هزینه برق",
			"fieldname": "electricity_cost_per_hour",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": "هزینه اجاره",
			"fieldname": "rent_cost_per_hour",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": "هزینه کل عملیات",
			"fieldname": "operation_total_cost",
			"fieldtype": "Currency",
			"width": 140
		}
	]


def get_data(filters=None):
	"""Get report data"""
	data = []
	
	# Build BOM filters
	bom_filters = {"is_active": 1, "is_default": 1}
	
	# If no specific filters are applied, get all BOMs (default behavior)
	show_all_by_default = True
	
	# Apply BOM filter if specified
	if filters and filters.get("bom"):
		bom_list = filters.get("bom")
		if isinstance(bom_list, str):
			bom_list = [bom_list]
		bom_filters["name"] = ["in", bom_list]
	
	# Apply item filter if specified
	if filters and filters.get("item_code"):
		item_list = filters.get("item_code")
		if isinstance(item_list, str):
			item_list = [item_list]
		bom_filters["item"] = ["in", item_list]
	
	# Apply item group filter if specified
	if filters and filters.get("item_group"):
		item_group_list = filters.get("item_group")
		if isinstance(item_group_list, str):
			item_group_list = [item_group_list]
		
		# Get items in the specified item groups
		items_in_groups = frappe.get_all("Item", 
			filters={"item_group": ["in", item_group_list]},
			fields=["name"]
		)
		if items_in_groups:
			item_codes = [item.name for item in items_in_groups]
			if filters.get("item_code"):
				# Intersect with existing item filter
				existing_items = filters.get("item_code")
				if isinstance(existing_items, str):
					existing_items = [existing_items]
				item_codes = list(set(item_codes) & set(existing_items))
			bom_filters["item"] = ["in", item_codes]
		else:
			# No items in group, return empty data
			return []
	
	# Get BOMs based on filters
	boms = frappe.get_all("BOM", 
		filters=bom_filters,
		fields=["name", "item", "item_name", "uom"]
	)
	
	# Get item groups for all items
	if boms:
		item_codes = [bom.item for bom in boms]
		items_with_groups = frappe.get_all("Item",
			filters={"name": ["in", item_codes]},
			fields=["name", "item_group"]
		)
		item_group_map = {item.name: item.item_group for item in items_with_groups}
	else:
		item_group_map = {}
	
	for bom in boms:
		# Build operation filters
		operation_filters = {"parent": bom.name}
		
		# Apply workstation filter if specified
		if filters and filters.get("workstation"):
			workstation_list = filters.get("workstation")
			if isinstance(workstation_list, str):
				workstation_list = [workstation_list]
			operation_filters["workstation"] = ["in", workstation_list]
		
		# Get BOM operations
		operations = frappe.get_all("BOM Operation",
			filters=operation_filters,
			fields=[
				"operation", "workstation", "time_in_mins", 
				"hour_rate", "base_hour_rate"
			],
			order_by="idx"
		)
		
		if not operations:
			# If no operations, show item without operation details
			data.append({
				"main_item_name": bom.item_name,
				"item_group": item_group_map.get(bom.item, ""),
				"production_item": bom.item_name,
				"operation": "",
				"time_in_mins": 0,
				"workstation": "",
				"department": "",
				"labor_cost_per_hour": 0,
				"electricity_cost_per_hour": 0,
				"rent_cost_per_hour": 0,
				"operation_total_cost": 0
			})
		else:
			# First, add direct operations from the main BOM
			for operation in operations:
				# Get workstation cost details
				workstation_costs = get_workstation_costs(operation.workstation)
				
				# Calculate total hourly cost (labor + electricity + rent)
				total_hourly_cost = (
					workstation_costs.get("labor_cost_per_hour", 0) +
					workstation_costs.get("electricity_cost_per_hour", 0) +
					workstation_costs.get("rent_cost_per_hour", 0)
				)
				
				# Calculate operation total cost and round up to nearest 5000
				time_in_hours = operation.time_in_mins / 60 if operation.time_in_mins else 0
				operation_total_cost = total_hourly_cost * time_in_hours
				operation_total_cost = math.ceil(operation_total_cost / 5000) * 5000 if operation_total_cost > 0 else 0
				
				# Show actual hourly rates (don't round hourly rates, only round total operation cost)
				labor_cost = workstation_costs.get("labor_cost_per_hour", 0)
				electricity_cost = workstation_costs.get("electricity_cost_per_hour", 0)
				rent_cost = workstation_costs.get("rent_cost_per_hour", 0)
				
				data.append({
					"main_item_name": bom.item_name,
					"item_group": item_group_map.get(bom.item, ""),
					"production_item": bom.item_name,
					"operation": operation.operation,
					"time_in_mins": operation.time_in_mins or 0,
					"workstation": operation.workstation,
					"department": workstation_costs.get("department", ""),
					"labor_cost_per_hour": labor_cost,
					"electricity_cost_per_hour": electricity_cost,
					"rent_cost_per_hour": rent_cost,
					"operation_total_cost": operation_total_cost
				})
			
			# Then, add operations from nested BOMs
			max_level = filters.get("max_level", 3) if filters else 3
			nested_operations = get_nested_bom_operations(
				bom.name, 
				bom.item_name, 
				item_group_map.get(bom.item, ""),
				qty=1,
				level=0,
				max_level=max_level,
				workstation_filter=filters.get("workstation") if filters else None
			)
			data.extend(nested_operations)
	
	return data


def get_summary_columns():
	"""Define summary report columns"""
	return [
		{
			"label": "نام محصول",
			"fieldname": "main_item_name",
			"fieldtype": "Data",
			"width": 200
		},
		{
			"label": "گروه محصول",
			"fieldname": "item_group",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"label": "بخش کاری",
			"fieldname": "department",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"label": "تعداد عملیات",
			"fieldname": "operation_count",
			"fieldtype": "Int",
			"width": 100
		},
		{
			"label": "کل زمان (دقیقه)",
			"fieldname": "total_time",
			"fieldtype": "Float",
			"width": 120
		},
		{
			"label": "کل هزینه مزد",
			"fieldname": "total_labor_cost",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": "کل هزینه برق",
			"fieldname": "total_electricity_cost",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": "کل هزینه اجاره",
			"fieldname": "total_rent_cost",
			"fieldtype": "Currency",
			"width": 120
		},
		{
			"label": "کل هزینه بخش",
			"fieldname": "total_department_cost",
			"fieldtype": "Currency",
			"width": 140
		}
	]


def get_summary_data(filters=None):
	"""Get summary data grouped by department"""
	# First get detailed data
	detailed_data = get_data(filters)
	
	# Group by main item and department
	summary_dict = {}
	
	for row in detailed_data:
		key = (row.get("main_item_name", ""), row.get("item_group", ""), row.get("department", ""))
		
		if key not in summary_dict:
			summary_dict[key] = {
				"main_item_name": row.get("main_item_name", ""),
				"item_group": row.get("item_group", ""),
				"department": row.get("department", ""),
				"operation_count": 0,
				"total_time": 0,
				"total_labor_cost": 0,
				"total_electricity_cost": 0,
				"total_rent_cost": 0,
				"total_department_cost": 0
			}
		
		summary_dict[key]["operation_count"] += 1
		summary_dict[key]["total_time"] += row.get("time_in_mins", 0)
		summary_dict[key]["total_labor_cost"] += row.get("labor_cost_per_hour", 0) * (row.get("time_in_mins", 0) / 60)
		summary_dict[key]["total_electricity_cost"] += row.get("electricity_cost_per_hour", 0) * (row.get("time_in_mins", 0) / 60)
		summary_dict[key]["total_rent_cost"] += row.get("rent_cost_per_hour", 0) * (row.get("time_in_mins", 0) / 60)
		summary_dict[key]["total_department_cost"] += row.get("operation_total_cost", 0)
	
	# Convert to list and round values
	summary_data = []
	for summary in summary_dict.values():
		# Round up to nearest 5000
		summary["total_labor_cost"] = math.ceil(summary["total_labor_cost"] / 5000) * 5000 if summary["total_labor_cost"] > 0 else 0
		summary["total_electricity_cost"] = math.ceil(summary["total_electricity_cost"] / 5000) * 5000 if summary["total_electricity_cost"] > 0 else 0
		summary["total_rent_cost"] = math.ceil(summary["total_rent_cost"] / 5000) * 5000 if summary["total_rent_cost"] > 0 else 0
		summary["total_department_cost"] = math.ceil(summary["total_department_cost"] / 5000) * 5000 if summary["total_department_cost"] > 0 else 0
		
		summary_data.append(summary)
	
	# Sort by main item name and department
	summary_data.sort(key=lambda x: (x["main_item_name"], x["department"]))
	
	return summary_data


def get_comparison_columns():
	"""Define comparison report columns"""
	return [
		{
			"label": "بخش کاری",
			"fieldname": "department",
			"fieldtype": "Data",
			"width": 150
		},
		{
			"label": "تعداد محصولات",
			"fieldname": "product_count",
			"fieldtype": "Int",
			"width": 100
		},
		{
			"label": "میانگین زمان (دقیقه)",
			"fieldname": "avg_time",
			"fieldtype": "Float",
			"width": 120
		},
		{
			"label": "میانگین مزد ساعتی",
			"fieldname": "avg_labor_rate",
			"fieldtype": "Currency",
			"width": 130
		},
		{
			"label": "میانگین برق ساعتی",
			"fieldname": "avg_electricity_rate",
			"fieldtype": "Currency",
			"width": 130
		},
		{
			"label": "میانگین اجاره ساعتی",
			"fieldname": "avg_rent_rate",
			"fieldtype": "Currency",
			"width": 130
		},
		{
			"label": "میانگین هزینه کل",
			"fieldname": "avg_total_cost",
			"fieldtype": "Currency",
			"width": 140
		},
		{
			"label": "کل هزینه بخش",
			"fieldname": "total_department_cost",
			"fieldtype": "Currency",
			"width": 140
		}
	]


def get_comparison_data(filters=None):
	"""Get comparison data grouped by department across multiple products"""
	# First get detailed data
	detailed_data = get_data(filters)
	
	# Group by department
	department_dict = {}
	
	for row in detailed_data:
		department = row.get("department", "نامشخص")
		
		if department not in department_dict:
			department_dict[department] = {
				"department": department,
				"products": set(),
				"total_time": 0,
				"total_labor_cost": 0,
				"total_electricity_cost": 0,
				"total_rent_cost": 0,
				"total_operation_cost": 0,
				"operation_count": 0,
				"labor_rates": [],
				"electricity_rates": [],
				"rent_rates": []
			}
		
		dept_data = department_dict[department]
		dept_data["products"].add(row.get("main_item_name", ""))
		dept_data["total_time"] += row.get("time_in_mins", 0)
		dept_data["total_operation_cost"] += row.get("operation_total_cost", 0)
		dept_data["operation_count"] += 1
		
		# Collect rates for averaging
		if row.get("labor_cost_per_hour", 0) > 0:
			dept_data["labor_rates"].append(row.get("labor_cost_per_hour", 0))
		if row.get("electricity_cost_per_hour", 0) > 0:
			dept_data["electricity_rates"].append(row.get("electricity_cost_per_hour", 0))
		if row.get("rent_cost_per_hour", 0) > 0:
			dept_data["rent_rates"].append(row.get("rent_cost_per_hour", 0))
	
	# Convert to list and calculate averages
	comparison_data = []
	for dept_data in department_dict.values():
		if dept_data["operation_count"] > 0:
			avg_labor_rate = sum(dept_data["labor_rates"]) / len(dept_data["labor_rates"]) if dept_data["labor_rates"] else 0
			avg_electricity_rate = sum(dept_data["electricity_rates"]) / len(dept_data["electricity_rates"]) if dept_data["electricity_rates"] else 0
			avg_rent_rate = sum(dept_data["rent_rates"]) / len(dept_data["rent_rates"]) if dept_data["rent_rates"] else 0
			avg_total_cost = dept_data["total_operation_cost"] / dept_data["operation_count"]
			
			comparison_data.append({
				"department": dept_data["department"],
				"product_count": len(dept_data["products"]),
				"avg_time": dept_data["total_time"] / dept_data["operation_count"],
				"avg_labor_rate": avg_labor_rate,
				"avg_electricity_rate": avg_electricity_rate,
				"avg_rent_rate": avg_rent_rate,
				"avg_total_cost": avg_total_cost,
				"total_department_cost": dept_data["total_operation_cost"]
			})
	
	# Sort by department name
	comparison_data.sort(key=lambda x: x["department"])
	
	return comparison_data


def get_nested_bom_operations(bom_name, parent_item_name, parent_item_group, qty=1, level=0, max_level=3, workstation_filter=None):
	"""Recursively get operations from nested BOMs"""
	if level > max_level:
		return []
	
	operations_data = []
	
	# Get BOM items (sub-assemblies)
	bom_items = frappe.get_all("BOM Item",
		filters={"parent": bom_name},
		fields=["item_code", "item_name", "qty", "bom_no"]
	)
	
	for bom_item in bom_items:
		if bom_item.bom_no:  # This item has its own BOM
			# Build operation filters for sub-BOM
			sub_operation_filters = {"parent": bom_item.bom_no}
			
			# Apply workstation filter if specified
			if workstation_filter:
				workstation_list = workstation_filter
				if isinstance(workstation_list, str):
					workstation_list = [workstation_list]
				sub_operation_filters["workstation"] = ["in", workstation_list]
			
			# Get operations from the sub-BOM
			sub_operations = frappe.get_all("BOM Operation",
				filters=sub_operation_filters,
				fields=["operation", "workstation", "time_in_mins", "hour_rate", "base_hour_rate"],
				order_by="idx"
			)
			
			for operation in sub_operations:
				# Get workstation cost details
				workstation_costs = get_workstation_costs(operation.workstation)
				
				# Calculate adjusted time based on quantity
				adjusted_time = (operation.time_in_mins or 0) * (bom_item.qty or 1) * qty
				
				# Calculate total hourly cost (labor + electricity + rent)
				total_hourly_cost = (
					workstation_costs.get("labor_cost_per_hour", 0) +
					workstation_costs.get("electricity_cost_per_hour", 0) +
					workstation_costs.get("rent_cost_per_hour", 0)
				)
				
				# Calculate operation total cost and round up to nearest 5000
				time_in_hours = adjusted_time / 60 if adjusted_time else 0
				operation_total_cost = total_hourly_cost * time_in_hours
				operation_total_cost = math.ceil(operation_total_cost / 5000) * 5000
				
				# Show actual hourly rates (don't round hourly rates, only round total operation cost)
				labor_cost = workstation_costs.get("labor_cost_per_hour", 0)
				electricity_cost = workstation_costs.get("electricity_cost_per_hour", 0)
				rent_cost = workstation_costs.get("rent_cost_per_hour", 0)
				
				operations_data.append({
					"main_item_name": parent_item_name.split(" → ")[0],  # Always show the main product
					"item_group": parent_item_group,
					"production_item": bom_item.item_name,  # Show what's being produced at this level
					"operation": operation.operation,
					"time_in_mins": adjusted_time,
					"workstation": operation.workstation,
					"department": workstation_costs.get("department", ""),
					"labor_cost_per_hour": labor_cost,
					"electricity_cost_per_hour": electricity_cost,
					"rent_cost_per_hour": rent_cost,
					"operation_total_cost": operation_total_cost,
					"level": level + 1
				})
			
			# Recursively get operations from deeper levels
			nested_ops = get_nested_bom_operations(
				bom_item.bom_no, 
				f"{parent_item_name} → {bom_item.item_name}",
				parent_item_group,
				bom_item.qty * qty, 
				level + 1, 
				max_level,
				workstation_filter
			)
			operations_data.extend(nested_ops)
	
	return operations_data


def get_workstation_costs(workstation_name):
	"""Get workstation hourly costs and department info"""
	if not workstation_name:
		return {
			"labor_cost_per_hour": 0,
			"electricity_cost_per_hour": 0,
			"consumable_cost_per_hour": 0,
			"rent_cost_per_hour": 0,
			"department": ""
		}
	
	try:
		# Get fresh workstation data to ensure latest costs
		workstation = frappe.get_doc("Workstation", workstation_name)
		
		# Get costs from workstation using correct field names (always fresh from workstation)
		costs = {
			"labor_cost_per_hour": workstation.get("hour_rate_labour") or 0,
			"electricity_cost_per_hour": workstation.get("hour_rate_electricity") or 0,
			"consumable_cost_per_hour": workstation.get("hour_rate_consumable") or 0,
			"rent_cost_per_hour": workstation.get("hour_rate_rent") or 0,
			"department": workstation.get("workstation_type") or workstation.get("plant_floor") or ""
		}
		
		return costs
		
	except frappe.DoesNotExistError:
		return {
			"labor_cost_per_hour": 0,
			"electricity_cost_per_hour": 0,
			"consumable_cost_per_hour": 0,
			"rent_cost_per_hour": 0,
			"department": ""
		}
