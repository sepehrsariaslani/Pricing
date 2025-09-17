import frappe
from frappe import _
from frappe.utils import flt

def execute(filters=None):
    if not filters:
        filters = {}
        
    columns = get_columns()
    data = get_data(filters)
    
    return columns, data

def get_columns():
    return [
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
            "width": 200
        },
        {
            "label": _("Price List"),
            "fieldname": "price_list",
            "fieldtype": "Link",
            "options": "Auto Price List",
            "width": 120
        },
        {
            "label": _("Raw Material Cost"),
            "fieldname": "raw_material_cost",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Labor Cost"),
            "fieldname": "labor_cost",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": _("Machine Cost"),
            "fieldname": "machine_cost",
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
            "label": _("Profit Margin %"),
            "fieldname": "profit_margin",
            "fieldtype": "Percent",
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
            "label": _("Cost Breakdown"),
            "fieldname": "cost_breakdown",
            "fieldtype": "Data",
            "width": 200
        }
    ]

def get_data(filters):
    conditions = get_conditions(filters)
    
    data = frappe.db.sql("""
        SELECT 
            i.item_code,
            i.item_name,
            p.price_list_name as price_list,
            i.raw_material_cost,
            i.labor_cost,
            i.machine_cost,
            i.overhead_cost,
            i.total_cost,
            i.profit_margin,
            i.selling_price,
            (i.selling_price - i.total_cost) as profit_amount
        FROM 
            `tabAuto Price List Item` i
            INNER JOIN `tabAuto Price List` p ON i.parent = p.name
        WHERE 
            {conditions}
        ORDER BY 
            p.price_list_name, i.item_code
    """.format(conditions=conditions), filters, as_dict=1)
    
    for row in data:
        # Calculate cost breakdown percentages
        total = flt(row.total_cost)
        if total:
            raw_pct = (flt(row.raw_material_cost) / total) * 100
            labor_pct = (flt(row.labor_cost) / total) * 100
            machine_pct = (flt(row.machine_cost) / total) * 100
            overhead_pct = (flt(row.overhead_cost) / total) * 100
            
            row.cost_breakdown = (
                f"Raw: {raw_pct:.1f}%, "
                f"Labor: {labor_pct:.1f}%, "
                f"Machine: {machine_pct:.1f}%, "
                f"Overhead: {overhead_pct:.1f}%"
            )
    
    return data

def get_conditions(filters):
    conditions = ["p.docstatus = 1"]
    
    if filters.get("price_list"):
        conditions.append("p.name = %(price_list)s")
        
    if filters.get("item_code"):
        conditions.append("i.item_code = %(item_code)s")
        
    if filters.get("from_date"):
        conditions.append("p.valid_from >= %(from_date)s")
        
    if filters.get("to_date"):
        conditions.append("(p.valid_until IS NULL OR p.valid_until <= %(to_date)s)")
        
    return " AND ".join(conditions) 