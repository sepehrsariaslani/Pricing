import frappe
from frappe import _
from frappe.utils import flt, cint

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart_data(data)
    
    return columns, data, None, chart

def get_columns():
    return [
        {
            "label": _("Auto Price List"),
            "fieldname": "auto_price_list",
            "fieldtype": "Link",
            "options": "Auto Price List",
            "width": 150
        },
        {
            "label": _("Item Code"),
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 120
        },
        {
            "label": _("Item Name"),
            "fieldname": "item_name",
            "fieldtype": "Data",
            "width": 150
        },
        {
            "label": _("Raw Material Cost"),
            "fieldname": "raw_material_cost",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Operation Cost"),
            "fieldname": "operation_cost",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Overhead Cost"),
            "fieldname": "overhead_cost",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Total Cost"),
            "fieldname": "total_cost",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Selling Price"),
            "fieldname": "selling_price",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Profit Amount"),
            "fieldname": "profit_amount",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Profit %"),
            "fieldname": "profit_percentage",
            "fieldtype": "Percent",
            "width": 100
        },
        {
            "label": _("Commission Amount"),
            "fieldname": "commission_amount",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Net Profit After Commission"),
            "fieldname": "net_profit_after_commission",
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "label": _("Final Price with Markup"),
            "fieldname": "final_price_with_markup",
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "label": _("Current Market Price"),
            "fieldname": "current_market_price",
            "fieldtype": "Currency",
            "width": 130
        },
        {
            "label": _("Price Variance"),
            "fieldname": "price_variance",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Status"),
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 100
        }
    ]

def get_data(filters):
    conditions = []
    values = {}
    
    if filters.get("auto_price_list"):
        conditions.append("apl.name = %(auto_price_list)s")
        values["auto_price_list"] = filters.get("auto_price_list")
    
    if filters.get("item_group"):
        conditions.append("apli.item_group = %(item_group)s")
        values["item_group"] = filters.get("item_group")
    
    if filters.get("from_date"):
        conditions.append("apl.valid_from >= %(from_date)s")
        values["from_date"] = filters.get("from_date")
    
    if filters.get("to_date"):
        conditions.append("apl.valid_until <= %(to_date)s")
        values["to_date"] = filters.get("to_date")
    
    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)
    
    query = f"""
        SELECT 
            apl.name as auto_price_list,
            apli.item_code,
            apli.item_name,
            apli.raw_material_cost,
            apli.operation_cost,
            apli.overhead_cost,
            apli.total_cost,
            apli.selling_price,
            apli.profit_amount,
            apli.commission_amount,
            apli.net_profit_after_commission,
            apli.final_price_with_markup,
            apl.commission_percentage,
            apl.compare_with_price_list
        FROM `tabAuto Price List` apl
        LEFT JOIN `tabAuto Price List Item` apli ON apl.name = apli.parent
        {where_clause}
        ORDER BY apl.name, apli.selling_price DESC
    """
    
    data = frappe.db.sql(query, values, as_dict=1)
    
    # Calculate additional fields
    for row in data:
        # Calculate profit percentage
        if row.total_cost:
            row.profit_percentage = (row.profit_amount / row.total_cost) * 100
        else:
            row.profit_percentage = 0
        
        # Get current market price if comparison price list exists
        if row.compare_with_price_list:
            current_price = frappe.db.get_value("Item Price", {
                "item_code": row.item_code,
                "price_list": row.compare_with_price_list
            }, "price_list_rate") or 0
            row.current_market_price = current_price
            
            # Calculate variance
            row.price_variance = current_price - row.total_cost
            
            # Determine status
            if row.price_variance > 0:
                row.status = "Profitable"
            elif row.price_variance < 0:
                row.status = "Loss"
            else:
                row.status = "Break-even"
        else:
            row.current_market_price = 0
            row.price_variance = 0
            row.status = "No Comparison"
    
    return data

def get_chart_data(data):
    if not data:
        return None
    
    # Profit margin distribution chart
    margin_ranges = {"0-10%": 0, "10-20%": 0, "20-30%": 0, "30-50%": 0, "50%+": 0}
    
    for row in data:
        margin = row.profit_percentage or 0
        if margin < 10:
            margin_ranges["0-10%"] += 1
        elif margin < 20:
            margin_ranges["10-20%"] += 1
        elif margin < 30:
            margin_ranges["20-30%"] += 1
        elif margin < 50:
            margin_ranges["30-50%"] += 1
        else:
            margin_ranges["50%+"] += 1
    
    chart = {
        "data": {
            "labels": list(margin_ranges.keys()),
            "datasets": [
                {
                    "name": "Items Count",
                    "values": list(margin_ranges.values())
                }
            ]
        },
        "type": "bar",
        "colors": ["#ff9999", "#ffcc99", "#99ff99", "#99ccff", "#cc99ff"]
    }
    
    return chart
