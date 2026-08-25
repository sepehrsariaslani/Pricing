#!/usr/bin/env python3
"""
اسکریپت برای حذف فیلد bundle_items از DocType و reload کردن meta
"""

import frappe
from frappe import _

def fix_bundle_doctype():
    """حذف فیلد قدیمی bundle_items و reload DocType"""
    
    frappe.init(site='den')
    frappe.connect()
    
    try:
        # Clear cache
        frappe.clear_cache(doctype='Auto Price List Product Bundle')
        
        # Reload DocType
        frappe.reload_doctype('Auto Price List Product Bundle', force=True)
        
        # Check if old field exists in DB and remove it
        doctype = 'Auto Price List Product Bundle'
        
        # Get current meta
        meta = frappe.get_meta(doctype)
        
        print(f"\n✓ Current fields in {doctype}:")
        for field in meta.fields:
            if 'bundle' in field.fieldname.lower():
                print(f"  - {field.fieldname}: {field.fieldtype}")
        
        # Try to remove column from database if it exists
        try:
            table_name = f"tab{doctype.replace(' ', '_')}"
            
            # Check if column exists
            result = frappe.db.sql(f"""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = '{table_name}'
                AND COLUMN_NAME = 'bundle_items'
            """)
            
            if result:
                print(f"\n⚠ Found old column 'bundle_items' in database")
                print(f"Removing it...")
                
                frappe.db.sql(f"ALTER TABLE `{table_name}` DROP COLUMN IF EXISTS `bundle_items`")
                frappe.db.commit()
                
                print(f"✓ Column 'bundle_items' removed from database")
            else:
                print(f"\n✓ Column 'bundle_items' does not exist in database")
        
        except Exception as db_error:
            print(f"⚠ Database error (safe to ignore if column doesn't exist): {db_error}")
        
        # Clear cache again
        frappe.clear_cache()
        
        # Reload DocType again
        frappe.reload_doctype('Auto Price List Product Bundle', force=True)
        
        print(f"\n✅ DocType reload complete!")
        print(f"\nNext steps:")
        print(f"1. Restart bench")
        print(f"2. Hard refresh browser (Ctrl+Shift+R)")
        print(f"3. Try fetch bundles again")
        
        frappe.db.commit()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        frappe.db.rollback()
    
    finally:
        frappe.destroy()

if __name__ == '__main__':
    fix_bundle_doctype()
