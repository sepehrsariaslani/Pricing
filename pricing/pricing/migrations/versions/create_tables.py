import frappe

def execute():
    # Create Auto Price List table if not exists
    if not frappe.db.exists("DocType", "Auto Price List"):
        frappe.get_doc({
            "doctype": "DocType",
            "name": "Auto Price List",
            "module": "Pricing",
            "fields": frappe.get_doc("DocType", "Auto Price List").fields,
            "permissions": frappe.get_doc("DocType", "Auto Price List").permissions
        }).insert()

    # Create Auto Price List Item table if not exists
    if not frappe.db.exists("DocType", "Auto Price List Item"):
        frappe.get_doc({
            "doctype": "DocType",
            "name": "Auto Price List Item",
            "module": "Pricing",
            "fields": frappe.get_doc("DocType", "Auto Price List Item").fields,
            "permissions": frappe.get_doc("DocType", "Auto Price List Item").permissions
        }).insert()

    # Create Price List Customer Group table if not exists
    if not frappe.db.exists("DocType", "Price List Customer Group"):
        frappe.get_doc({
            "doctype": "DocType",
            "name": "Price List Customer Group",
            "module": "Pricing",
            "fields": frappe.get_doc("DocType", "Price List Customer Group").fields,
            "permissions": frappe.get_doc("DocType", "Price List Customer Group").permissions
        }).insert() 