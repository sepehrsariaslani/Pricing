#!/usr/bin/env python3
"""
Update Pricing workspace with ERPNext DocTypes
"""

import frappe
import json


def add_erpnext_doctypes_to_workspace():
    """Add ERPNext related DocTypes to Pricing workspace"""
    
    workspace_name = "Pricing"
    
    # Check if workspace exists
    if not frappe.db.exists("Workspace", workspace_name):
        print(f"ERROR: Workspace '{workspace_name}' not found")
        return
    
    doc = frappe.get_doc("Workspace", workspace_name)
    
    # Define ERPNext DocTypes to add
    erpnext_card = {
        "label": "🔗 ارتباطات ERPNext",
        "type": "Card Break",
        "hidden": 0,
        "is_query_report": 0,
        "link_count": 0,
        "onboard": 0
    }
    
    erpnext_links = [
        {"label": "کالا", "link_to": "Item", "link_type": "DocType"},
        {"label": "قیمت کالا", "link_to": "Item Price", "link_type": "DocType"},
        {"label": "لیست قیمت", "link_to": "Price List", "link_type": "DocType"},
        {"label": "گروه کالا", "link_to": "Item Group", "link_type": "DocType"},
        {"label": "برند", "link_to": "Brand", "link_type": "DocType"},
        {"label": "فهرست مواد (BOM)", "link_to": "BOM", "link_type": "DocType"},
        {"label": "تامین‌کننده", "link_to": "Supplier", "link_type": "DocType"},
        {"label": "پیشنهاد قیمت تامین‌کننده", "link_to": "Supplier Quotation", "link_type": "DocType"},
        {"label": "سفارش خرید", "link_to": "Purchase Order", "link_type": "DocType"},
        {"label": "مشتری", "link_to": "Customer", "link_type": "DocType"},
        {"label": "پیشنهاد قیمت", "link_to": "Quotation", "link_type": "DocType"},
        {"label": "سفارش فروش", "link_to": "Sales Order", "link_type": "DocType"},
        {"label": "قانون قیمت‌گذاری", "link_to": "Pricing Rule", "link_type": "DocType"},
        {"label": "ارز", "link_to": "Currency", "link_type": "DocType"},
    ]
    
    # Add card break
    doc.append("links", erpnext_card)
    
    # Add links
    for link_data in erpnext_links:
        link_data.update({
            "type": "Link",
            "hidden": 0,
            "is_query_report": 0,
            "link_count": 0,
            "onboard": 0,
            "dependencies": ""
        })
        doc.append("links", link_data)
    
    # Update content to include new card
    content = json.loads(doc.content)
    content.append({
        "id": "card_7",
        "type": "card",
        "data": {
            "card_name": "🔗 ارتباطات ERPNext",
            "col": 4
        }
    })
    doc.content = json.dumps(content)
    
    # Save
    print("Saving updated workspace...")
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    
    print(f"✅ Added ERPNext DocTypes to Pricing workspace!")
    print(f"   - Total links now: {len(doc.links)}")
    print(f"   - Added 14 ERPNext DocTypes")
    
    return doc


if __name__ == "__main__":
    add_erpnext_doctypes_to_workspace()
