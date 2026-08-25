import frappe
from frappe import _

def execute(filters=None):
    if not filters:
        filters = {}

    columns = get_columns()
    data = get_data(filters)

    return columns, data

def get_columns():
    return [
        {
            "fieldname": "item_code",
            "label": _("Item Code"),
            "fieldtype": "Link",
            "options": "Item",
            "width": 120
        },
        {
            "fieldname": "item_name",
            "label": _("Item Name"),
            "fieldtype": "Data",
            "width": 200
        },
        {
            "fieldname": "raw_material_cost",
            "label": _("Raw Material Cost"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "labor_cost",
            "label": _("Labor Cost"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "machine_cost",
            "label": _("Machine Cost"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "overhead_cost",
            "label": _("Overhead Cost"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "total_cost",
            "label": _("Total Cost"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "profit_margin",
            "label": _("Profit Margin"),
            "fieldtype": "Percent",
            "width": 120
        },
        {
            "fieldname": "selling_price",
            "label": _("Selling Price"),
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "fieldname": "profit_amount",
            "label": _("Profit Amount"),
            "fieldtype": "Currency",
            "width": 120
        }
    ]

def get_data(filters):
    conditions = get_conditions(filters)
    
    data = frappe.db.sql("""
        SELECT
            api.item_code,
            api.item_name,
            api.raw_material_cost,
            api.labor_cost,
            api.machine_cost,
            api.overhead_cost,
            api.total_cost,
            api.profit_margin,
            api.selling_price,
            (api.selling_price - api.total_cost) as profit_amount
        FROM
            `tabAuto Price List Item` api
            INNER JOIN `tabAuto Price List` apl ON api.parent = apl.name
        WHERE
            apl.is_active = 1
            AND apl.valid_from <= %(to_date)s
            AND (apl.valid_until IS NULL OR apl.valid_until >= %(from_date)s)
            {conditions}
        ORDER BY
            api.item_code
    """.format(conditions=conditions), filters, as_dict=1)

    return data

def get_conditions(filters):
    conditions = []
    
    if filters.get("item_code"):
        conditions.append("api.item_code = %(item_code)s")
    
    if filters.get("price_list"):
        conditions.append("apl.name = %(price_list)s")
    
    return " AND " + " AND ".join(conditions) if conditions else "" 