"""
Pricing Dashboard Entry Point
This file serves the Vue.js application for the pricing management dashboard.
"""

import frappe
from frappe.utils import get_system_timezone, nowdate


no_cache = 1


def get_context(context):
    """Get context for the pricing dashboard"""
    csrf_token = frappe.sessions.get_csrf_token()
    frappe.db.commit()
    
    context.boot = get_boot()
    context.boot["csrf_token"] = csrf_token
    
    return context


@frappe.whitelist(methods=["POST"], allow_guest=True)
def get_context_for_dev():
    """Get context for development mode"""
    if not frappe.conf.developer_mode:
        frappe.throw("این متد فقط در حالت توسعه‌دهنده در دسترس است")
    return get_boot()


def get_boot():
    """Get boot data for the frontend"""
    user = frappe.session.user
    
    # Get user roles
    user_roles = frappe.get_roles(user) if user != "Guest" else []
    
    # Check if manager
    manager_roles = ["Sales Manager", "System Manager", "Administrator", "Accounts Manager"]
    is_manager = any(role in user_roles for role in manager_roles)
    
    # Get active price lists count
    active_price_lists = 0
    try:
        active_price_lists = frappe.db.count("Auto Price List", {
            "docstatus": ["<", 2]
        })
    except Exception:
        pass
    
    # User full name
    user_full_name = "مهمان"
    if user != "Guest":
        user_full_name = frappe.db.get_value("User", user, "full_name") or user
    
    # User role display
    if is_manager:
        user_role = "مدیر قیمت‌گذاری"
    else:
        user_role = "کاربر"
    
    return frappe._dict({
        "frappe_version": frappe.__version__,
        "site_name": frappe.local.site,
        "read_only_mode": frappe.flags.read_only,
        "system_timezone": get_system_timezone(),
        "user": user,
        "user_full_name": user_full_name,
        "user_role": user_role,
        "user_roles": user_roles,
        "is_manager": is_manager,
        "active_price_lists": active_price_lists,
    })

