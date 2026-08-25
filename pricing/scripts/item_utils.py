
import frappe
import re

@frappe.whitelist()
def clean_item_name(item_code):
    """
    Cleans the name and code of a single item.
    Returns dict with success status and changes.
    """
    if not frappe.has_permission("Item", "write"):
        frappe.throw("Permission Denied")

    item = frappe.get_doc("Item", item_code)
    
    # 1. Normalize Item Name
    old_item_name = item.item_name
    new_item_name = normalize_text(old_item_name)
    
    changes = []
    
    if old_item_name != new_item_name:
        item.item_name = new_item_name
        item.save()
        changes.append(f"Name: {old_item_name} -> {new_item_name}")
    
    # 2. Rename Item (Item Code)
    # Only rename if the current ID (item_code) is different from the normalized name
    # We use the Normalized Item Name as the target Item Code
    current_id = item.name
    target_id = new_item_name 
    
    if current_id != target_id:
        try:
            if frappe.db.exists("Item", target_id):
                changes.append(f"Skipped Rename: {target_id} already exists.")
            else:
                frappe.rename_doc("Item", current_id, target_id, force=True)
                changes.append(f"Renamed Code: {current_id} -> {target_id}")
                # Update item_code variable for return
                item_code = target_id
        except Exception as e:
            changes.append(f"Rename Failed: {e}")

    if changes:
        msg = "<br>".join(changes)
        frappe.msgprint(msg, title="Cleaned")
        return {"success": True, "changed": True, "old_name": old_item_name, "new_name": new_item_name, "changes": changes}
    
    return {"success": True, "changed": False, "message": "Item is already clean."}

@frappe.whitelist()
def clean_item_names():
    """
    Enqueues a background job to clean ALL items.
    Prevents 504 Gateway Time-out.
    """
    frappe.enqueue('pricing.scripts.item_utils.clean_all_items_background', queue='long', timeout=3600)
    return {"success": True, "message": "Cleaning job started in background. Check Error Logs for results."}

def clean_all_items_background():
    items = frappe.get_all("Item", fields=["name", "item_name"])
    count = 0
    renamed = 0
    errors = 0
    
    print(f"Starting name cleanup for {len(items)} items...")
    
    for item_data in items:
        try:
            current_id = item_data.name
            old_item_name = item_data.item_name
            if not old_item_name: continue
            
            new_item_name = normalize_text(old_item_name)
            
            # 1. Update Description (item_name)
            if old_item_name != new_item_name:
                frappe.db.set_value("Item", current_id, "item_name", new_item_name)
                count += 1
            
            # 2. Rename ID (Item Code)
            if current_id != new_item_name:
                if not frappe.db.exists("Item", new_item_name):
                    frappe.rename_doc("Item", current_id, new_item_name, force=True)
                    renamed += 1
            
            if count % 100 == 0:
                frappe.db.commit()
                print(f"Processed {count} items...")
                    
        except Exception as e:
            errors += 1
            print(f"Error cleaning {item_data.name}: {e}")

    frappe.db.commit()
    print(f"Completed. updated_names={count}, renamed_codes={renamed}, errors={errors}")

def normalize_text(text):
    if not text: return ""
    
    # 1. Arabic characters to Persian
    text = text.replace("ي", "ی")
    text = text.replace("ك", "ک")
    
    # 2. Replace hyphens with spaces (User requested format: "پارچه منتون 507")
    text = text.replace("-", " ")
    
    # 3. Convert English numbers to Persian
    english_numerals = '0123456789'
    persian_numerals = '۰۱۲۳۴۵۶۷۸۹'
    translation_table = str.maketrans(english_numerals, persian_numerals)
    text = text.translate(translation_table)

    # 4. Normalize spaces (collapse multiple to one)
    text = re.sub(r'\s+', ' ', text)
    
    # 5. Strip
    text = text.strip()
    
    return text
