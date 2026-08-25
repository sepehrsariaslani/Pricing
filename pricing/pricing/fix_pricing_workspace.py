#!/usr/bin/env python3
"""
Force sync Pricing workspace to database
"""

import frappe
import json
import os


def force_sync_pricing_workspace():
    """Force sync the Pricing workspace from JSON file to database"""
    
    # Path to the workspace JSON file
    workspace_name = "Pricing"
    app_name = "pricing"
    json_path = frappe.get_app_path(app_name, "pricing", "workspace", "pricing", "pricing.json")
    
    print(f"Loading workspace JSON from: {json_path}")
    
    # Check if file exists
    if not os.path.exists(json_path):
        print(f"ERROR: Workspace JSON file not found at {json_path}")
        return
    
    # Load JSON data
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    print(f"Loaded workspace data for: {data.get('name')}")
    
    # Check if workspace exists in database by label (since name might be in Persian)
    workspace_label = data.get("label")
    existing = frappe.db.get_value("Workspace", {"label": workspace_label}, "name")
    
    if existing:
        print(f"Workspace with label '{workspace_label}' exists (name: {existing}). Updating...")
        doc = frappe.get_doc("Workspace", existing)
    else:
        print(f"Workspace '{workspace_name}' does not exist. Creating new...")
        doc = frappe.new_doc("Workspace")
        doc.name = workspace_name
    
    # Update workspace fields using the update() method to handle child tables correctly
    doc.update({
        "label": data.get("label"),
        "title": data.get("title") or data.get("label"),
        "icon": data.get("icon"),
        "module": data.get("module"),
        "public": data.get("public", 1),
        "content": data.get("content"),
        "sequence_id": data.get("sequence_id", 10),
        "is_hidden": data.get("is_hidden", 0),
        "extends": data.get("extends", ""),
        "extends_another_page": data.get("extends_another_page", 0),
        "onboarding": data.get("onboarding", ""),
    })
    
    # Handle shortcuts child table
    doc.set("shortcuts", [])
    for shortcut in data.get("shortcuts", []):
        doc.append("shortcuts", shortcut)
    
    # Handle links child table
    doc.set("links", [])
    for link in data.get("links", []):
        doc.append("links", link)
    
    # Handle charts child table
    doc.set("charts", [])
    for chart in data.get("charts", []):
        doc.append("charts", chart)
    
    # Handle quick_lists child table
    doc.set("quick_lists", [])
    for quick_list in data.get("quick_lists", []):
        doc.append("quick_lists", quick_list)
    
    # Handle number_cards child table
    doc.set("number_cards", [])
    for number_card in data.get("number_cards", []):
        doc.append("number_cards", number_card)
    
    # Handle custom_blocks child table
    doc.set("custom_blocks", [])
    for custom_block in data.get("custom_blocks", []):
        doc.append("custom_blocks", custom_block)
    
    # Save the document
    print("Saving workspace...")
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    
    print(f"✅ Pricing workspace synced successfully!")
    print(f"   - Label: {doc.label}")
    print(f"   - Module: {doc.module}")
    print(f"   - Shortcuts: {len(doc.shortcuts)}")
    print(f"   - Links: {len(doc.links)}")
    print(f"   - Public: {doc.public}")
    
    return doc


if __name__ == "__main__":
    # This allows running the script directly with bench execute
    force_sync_pricing_workspace()
