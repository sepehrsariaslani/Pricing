"""
Pricing Dashboard API - Backend APIs for the pricing management dashboard
"""

import frappe
from frappe import _
from frappe.utils import nowdate, getdate, flt, cint
import json


# ==================== Permission Check ====================

@frappe.whitelist(allow_guest=True)
def can_access_pricing():
    """Check if user can access pricing dashboard"""
    if frappe.session.user == "Guest":
        return False
    
    user_roles = frappe.get_roles(frappe.session.user)
    allowed_roles = ["Sales Manager", "System Manager", "Administrator", "Accounts Manager", "Sales User"]
    return any(role in user_roles for role in allowed_roles)


# ==================== Dashboard APIs ====================

@frappe.whitelist()
def get_dashboard_stats():
    """Get dashboard statistics"""
    
    # Count Auto Price Lists by status
    draft_count = frappe.db.count("Auto Price List", {"docstatus": 0})
    submitted_count = frappe.db.count("Auto Price List", {"docstatus": 1})
    
    # Get recent Auto Price Lists
    recent_price_lists = frappe.get_all(
        "Auto Price List",
        filters={"docstatus": ["<", 2]},
        fields=["name", "price_list", "valid_from", "valid_until", "profit_margin", "docstatus", "modified"],
        order_by="modified desc",
        limit=5
    )
    
    # Get Price Lists
    price_lists = frappe.get_all(
        "Price List",
        filters={"enabled": 1, "selling": 1},
        fields=["name", "currency"],
        limit=10
    )
    
    # Get item groups count
    item_groups_count = frappe.db.count("Item Group")
    
    # Get items with BOM count
    items_with_bom = frappe.db.sql("""
        SELECT COUNT(DISTINCT item) 
        FROM `tabBOM` 
        WHERE is_active = 1 AND is_default = 1
    """)[0][0] or 0
    
    return {
        "stats": {
            "draft_price_lists": draft_count,
            "submitted_price_lists": submitted_count,
            "total_price_lists": draft_count + submitted_count,
            "item_groups": item_groups_count,
            "items_with_bom": items_with_bom,
        },
        "recent_price_lists": recent_price_lists,
        "price_lists": price_lists,
    }


@frappe.whitelist()
def get_price_lists(filters=None):
    """Get all Auto Price Lists"""
    if filters and isinstance(filters, str):
        filters = json.loads(filters)
    
    query_filters = {"docstatus": ["<", 2]}
    if filters:
        if filters.get("price_list"):
            query_filters["price_list"] = filters["price_list"]
        if filters.get("docstatus") is not None:
            query_filters["docstatus"] = filters["docstatus"]
    
    price_lists = frappe.get_all(
        "Auto Price List",
        filters=query_filters,
        fields=[
            "name", "price_list", "valid_from", "valid_until", 
            "profit_margin", "docstatus", "modified", "creation",
            "total_profit", "enable_installment", "commission_percentage"
        ],
        order_by="modified desc"
    )
    
    # Get items count for each price list
    for pl in price_lists:
        pl["items_count"] = frappe.db.count(
            "Auto Price List Item", 
            {"parent": pl["name"]}
        )
    
    return price_lists


@frappe.whitelist()
def get_price_list_full_detail(name):
    """Alias for get_price_list_detail"""
    return get_price_list_detail(name)


@frappe.whitelist()
def get_price_list_detail(name):
    """Get single Auto Price List with details"""
    if not frappe.has_permission("Auto Price List", "read", name):
        frappe.throw(_("شما دسترسی به این لیست قیمت را ندارید"))
    
    doc = frappe.get_doc("Auto Price List", name)
    
    return {
        "name": doc.name,
        "price_list": doc.price_list,
        "valid_from": doc.valid_from,
        "valid_until": doc.valid_until,
        "profit_margin": doc.profit_margin,
        "docstatus": doc.docstatus,
        "enable_installment": doc.enable_installment,
        "down_payment_percentage": doc.down_payment_percentage,
        "number_of_months": doc.number_of_months,
        "monthly_interest_rate": doc.monthly_interest_rate,
        "commission_percentage": doc.commission_percentage,
        "target_discount_percentage": doc.target_discount_percentage,
        "price_rounding_amount": doc.price_rounding_amount,
        "items": [
            {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "item_group": item.item_group,
                "brand": item.brand,
                "raw_material_cost": item.raw_material_cost,
                "operation_cost": item.operation_cost,
                "overhead_cost": item.overhead_cost,
                "total_cost": item.total_cost,
                "selling_price": item.selling_price,
                "profit_amount": item.profit_amount,
                "final_selected_price": item.final_selected_price,
            }
            for item in doc.items
        ],
        "product_bundles": [
            {
                "bundle_item": bundle.bundle_item if hasattr(bundle, 'bundle_item') else bundle.get('bundle_item'),
                "bundle_name": bundle.bundle_name if hasattr(bundle, 'bundle_name') else bundle.get('bundle_name'),
                "total_cost": bundle.total_cost if hasattr(bundle, 'total_cost') else bundle.get('total_cost'),
                "selling_price": bundle.selling_price if hasattr(bundle, 'selling_price') else bundle.get('selling_price'),
            }
            for bundle in (doc.product_bundles or [])
        ],
        "manual_material_prices": [
            {
                "item_code": mp.item_code,
                "item_name": mp.item_name if hasattr(mp, 'item_name') else None,
                "manual_price": mp.manual_price if hasattr(mp, 'manual_price') else None,
            }
            for mp in (doc.manual_material_prices or [])
        ],
        "total_profit": doc.total_profit,
    }


@frappe.whitelist()
def create_price_list(data):
    """Create new Auto Price List"""
    if isinstance(data, str):
        data = json.loads(data)
    
    doc = frappe.new_doc("Auto Price List")
    doc.price_list = data.get("price_list")
    doc.valid_from = data.get("valid_from")
    doc.valid_until = data.get("valid_until")
    doc.profit_margin = data.get("profit_margin", 20)
    doc.enable_installment = data.get("enable_installment", 0)
    doc.commission_percentage = data.get("commission_percentage", 0)
    doc.price_rounding_amount = data.get("price_rounding_amount", 0)
    
    doc.insert()
    
    return {"name": doc.name, "success": True}


@frappe.whitelist()
def fetch_items_for_price_list(name, filters=None):
    """Fetch items for a price list based on filters"""
    if isinstance(filters, str):
        filters = json.loads(filters)
    
    doc = frappe.get_doc("Auto Price List", name)
    
    # Set filters on doc
    if filters:
        if filters.get("item_group"):
            doc.item_group = filters["item_group"]
        if filters.get("brand"):
            doc.brand = filters["brand"]
        if filters.get("item_name_filter"):
            doc.item_name_filter = filters["item_name_filter"]
    
    # Call fetch_items
    doc.fetch_items()
    doc.save()
    
    return {
        "success": True,
        "items_count": len(doc.items),
        "items": [
            {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "item_group": item.item_group,
                "brand": item.brand,
            }
            for item in doc.items
        ]
    }


@frappe.whitelist()
def calculate_prices(name):
    """Calculate prices for all items in a price list"""
    doc = frappe.get_doc("Auto Price List", name)
    doc.calculate_item_prices_internal()
    doc.save()
    
    return {
        "success": True,
        "items": [
            {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "raw_material_cost": item.raw_material_cost,
                "operation_cost": item.operation_cost,
                "overhead_cost": item.overhead_cost,
                "total_cost": item.total_cost,
                "selling_price": item.selling_price,
                "profit_amount": item.profit_amount,
                "final_selected_price": item.final_selected_price,
            }
            for item in doc.items
        ],
        "total_profit": doc.total_profit,
    }


@frappe.whitelist()
def update_prices_to_price_list(name):
    """Update calculated prices to the actual Price List"""
    doc = frappe.get_doc("Auto Price List", name)
    
    # Call the update prices method
    if hasattr(doc, 'update_prices_in_price_list'):
        result = doc.update_prices_in_price_list()
    else:
        # Manual update
        updated_count = 0
        for item in doc.items:
            if item.final_selected_price and item.final_selected_price > 0:
                # Check if item price exists
                existing = frappe.db.get_value("Item Price", {
                    "item_code": item.item_code,
                    "price_list": doc.price_list,
                }, "name")
                
                if existing:
                    frappe.db.set_value("Item Price", existing, "price_list_rate", item.final_selected_price)
                else:
                    item_price = frappe.new_doc("Item Price")
                    item_price.item_code = item.item_code
                    item_price.price_list = doc.price_list
                    item_price.price_list_rate = item.final_selected_price
                    item_price.insert()
                
                updated_count += 1
        
        frappe.db.commit()
        result = {"updated_count": updated_count}
    
    return {
        "success": True,
        "message": f"قیمت‌ها با موفقیت به‌روزرسانی شدند",
        **result
    }


@frappe.whitelist()
def get_item_groups():
    """Get all item groups"""
    return frappe.get_all(
        "Item Group",
        fields=["name", "parent_item_group", "is_group"],
        order_by="name"
    )


@frappe.whitelist()
def get_brands():
    """Get all brands"""
    return frappe.get_all(
        "Brand",
        fields=["name"],
        order_by="name"
    )


@frappe.whitelist()
def get_available_price_lists():
    """Get available Price Lists for selection"""
    return frappe.get_all(
        "Price List",
        filters={"enabled": 1, "selling": 1},
        fields=["name", "currency", "price_not_uom_dependent"],
        order_by="name"
    )


@frappe.whitelist()
def remove_items_from_price_list(name, filters=None):
    """Remove items from price list based on filters"""
    if isinstance(filters, str):
        filters = json.loads(filters)
    
    doc = frappe.get_doc("Auto Price List", name)
    
    if filters:
        if filters.get("item_group"):
            doc.remove_item_group = filters["item_group"]
        if filters.get("brand"):
            doc.remove_brand = filters["brand"]
        if filters.get("item_name_filter"):
            doc.remove_item_name_filter = filters["item_name_filter"]
    
    # Call remove items method if exists
    if hasattr(doc, 'remove_filtered_items'):
        doc.remove_filtered_items()
    else:
        # Manual removal
        items_to_keep = []
        for item in doc.items:
            should_remove = False
            if filters.get("item_group") and item.item_group == filters["item_group"]:
                should_remove = True
            if filters.get("brand") and item.brand == filters["brand"]:
                should_remove = True
            if filters.get("item_name_filter") and filters["item_name_filter"].lower() in (item.item_name or "").lower():
                should_remove = True
            
            if not should_remove:
                items_to_keep.append(item)
        
        doc.items = items_to_keep
    
    doc.save()
    
    return {
        "success": True,
        "remaining_items": len(doc.items)
    }


@frappe.whitelist()
def get_analytics_data(name):
    """Get analytics data for a price list"""
    doc = frappe.get_doc("Auto Price List", name)
    
    # Group items by item_group
    by_group = {}
    for item in doc.items:
        group = item.item_group or "بدون گروه"
        if group not in by_group:
            by_group[group] = {
                "count": 0,
                "total_cost": 0,
                "total_selling": 0,
                "total_profit": 0
            }
        by_group[group]["count"] += 1
        by_group[group]["total_cost"] += flt(item.total_cost or 0)
        by_group[group]["total_selling"] += flt(item.final_selected_price or item.selling_price or 0)
        by_group[group]["total_profit"] += flt(item.profit_amount or 0)
    
    # Calculate profit margins by group
    profit_by_group = []
    for group, data in by_group.items():
        margin = 0
        if data["total_cost"] > 0:
            margin = (data["total_profit"] / data["total_cost"]) * 100
        profit_by_group.append({
            "group": group,
            "count": data["count"],
            "total_cost": data["total_cost"],
            "total_selling": data["total_selling"],
            "profit": data["total_profit"],
            "margin": margin
        })
    
    # Sort by profit
    profit_by_group.sort(key=lambda x: x["profit"], reverse=True)
    
    # Top 10 most profitable items
    top_items = sorted(
        [item for item in doc.items if item.profit_amount],
        key=lambda x: flt(x.profit_amount or 0),
        reverse=True
    )[:10]
    
    return {
        "by_group": profit_by_group,
        "top_profitable_items": [
            {
                "item_code": item.item_code,
                "item_name": item.item_name,
                "profit": item.profit_amount,
                "margin": (flt(item.profit_amount or 0) / flt(item.total_cost or 1)) * 100 if item.total_cost else 0
            }
            for item in top_items
        ],
        "summary": {
            "total_items": len(doc.items),
            "total_cost": sum(flt(item.total_cost or 0) for item in doc.items),
            "total_selling": sum(flt(item.final_selected_price or item.selling_price or 0) for item in doc.items),
            "total_profit": sum(flt(item.profit_amount or 0) for item in doc.items),
            "avg_margin": doc.profit_margin
        }
    }


@frappe.whitelist()
def get_price_comparison(name, compare_price_list=None):
    """Compare prices with another price list"""
    doc = frappe.get_doc("Auto Price List", name)
    
    if not compare_price_list:
        compare_price_list = doc.compare_with_price_list
    
    if not compare_price_list:
        return {"error": "لطفاً لیست قیمت مقایسه را انتخاب کنید"}
    
    comparisons = []
    for item in doc.items:
        current_price = flt(item.final_selected_price or item.selling_price or 0)
        
        # Get price from comparison price list
        old_price = frappe.db.get_value("Item Price", {
            "item_code": item.item_code,
            "price_list": compare_price_list
        }, "price_list_rate") or 0
        
        old_price = flt(old_price)
        change = current_price - old_price
        change_percent = (change / old_price * 100) if old_price > 0 else 0
        
        comparisons.append({
            "item_code": item.item_code,
            "item_name": item.item_name,
            "old_price": old_price,
            "new_price": current_price,
            "change": change,
            "change_percent": change_percent
        })
    
    # Sort by change percent
    comparisons.sort(key=lambda x: x["change_percent"], reverse=True)
    
    return {
        "compare_price_list": compare_price_list,
        "items": comparisons,
        "summary": {
            "total_items": len(comparisons),
            "increased": len([c for c in comparisons if c["change"] > 0]),
            "decreased": len([c for c in comparisons if c["change"] < 0]),
            "unchanged": len([c for c in comparisons if c["change"] == 0]),
            "avg_change_percent": sum(c["change_percent"] for c in comparisons) / len(comparisons) if comparisons else 0
        }
    }


@frappe.whitelist()
def fetch_product_bundles(name, bundle_filter=None):
    """Fetch product bundles for a price list"""
    doc = frappe.get_doc("Auto Price List", name)
    
    if bundle_filter:
        doc.bundle_name_filter = bundle_filter
    
    if hasattr(doc, 'fetch_product_bundles'):
        doc.fetch_product_bundles()
        doc.save()
    
    return {
        "success": True,
        "bundles": [
            {
                "bundle_item": b.bundle_item if hasattr(b, 'bundle_item') else None,
                "bundle_name": b.bundle_name if hasattr(b, 'bundle_name') else None,
                "total_cost": b.total_cost if hasattr(b, 'total_cost') else None,
                "selling_price": b.selling_price if hasattr(b, 'selling_price') else None,
            }
            for b in (doc.product_bundles or [])
        ]
    }


@frappe.whitelist()
def update_manual_material_price(name, item_code, price):
    """Update manual material price"""
    doc = frappe.get_doc("Auto Price List", name)
    
    # Find or create manual material price entry
    found = False
    for mp in (doc.manual_material_prices or []):
        if mp.item_code == item_code:
            mp.manual_price = flt(price)
            found = True
            break
    
    if not found:
        doc.append("manual_material_prices", {
            "item_code": item_code,
            "manual_price": flt(price)
        })
    
    doc.save()
    
    return {"success": True}


@frappe.whitelist()
def submit_price_list(name):
    """Submit a price list"""
    doc = frappe.get_doc("Auto Price List", name)
    doc.submit()
    
    return {"success": True, "docstatus": doc.docstatus}


@frappe.whitelist()
def cancel_price_list(name):
    """Cancel a price list"""
    doc = frappe.get_doc("Auto Price List", name)
    doc.cancel()
    
    return {"success": True, "docstatus": doc.docstatus}


# ==================== Full Detail API ====================

@frappe.whitelist()
def get_price_list_full_detail(name):
    """Get complete Auto Price List with all fields for editing"""
    if not frappe.has_permission("Auto Price List", "read", name):
        frappe.throw(_("شما دسترسی به این لیست قیمت را ندارید"))
    
    doc = frappe.get_doc("Auto Price List", name)
    
    return {
        "name": doc.name,
        "docstatus": doc.docstatus,
        "is_editable": doc.docstatus == 0,
        
        # Basic Info
        "price_list": doc.price_list,
        "valid_from": doc.valid_from,
        "valid_until": doc.valid_until,
        "profit_margin": doc.profit_margin,
        
        # Installment Settings
        "enable_installment": doc.enable_installment,
        "down_payment_percentage": doc.down_payment_percentage,
        "number_of_months": doc.number_of_months,
        "monthly_interest_rate": doc.monthly_interest_rate,
        "installment_total_interest_percentage": doc.installment_total_interest_percentage,
        
        # Deferred Payment Settings
        "enable_deferred_payment": doc.enable_deferred_payment,
        "deferred_payment_months": doc.deferred_payment_months,
        "deferred_payment_interest_rate": doc.deferred_payment_interest_rate,
        "deferred_payment_total_interest_percentage": doc.deferred_payment_total_interest_percentage,
        
        # Commission Settings
        "commission_percentage": doc.commission_percentage,
        "net_profit_after_commission": doc.net_profit_after_commission,
        "net_profit_percentage_after_commission": doc.net_profit_percentage_after_commission,
        
        # Discount Settings
        "target_discount_percentage": doc.target_discount_percentage,
        "required_markup_percentage": doc.required_markup_percentage,
        "final_selling_price_with_markup": doc.final_selling_price_with_markup,
        "direct_markup_percentage": doc.direct_markup_percentage,
        
        # Advanced Pricing
        "enable_volume_pricing": doc.enable_volume_pricing,
        "enable_seasonal_pricing": doc.enable_seasonal_pricing,
        "seasonal_factor": doc.seasonal_factor,
        "enable_customer_tier_pricing": doc.enable_customer_tier_pricing,
        
        # Display Settings
        "price_rounding_amount": doc.price_rounding_amount,
        "show_base_cost": doc.show_base_cost,
        "show_profit_amount": doc.show_profit_amount,
        "show_commission_amount": doc.show_commission_amount,
        "show_installment_details": doc.show_installment_details,
        "show_discount_amount": doc.show_discount_amount,
        
        # Financial Analysis
        "monthly_fixed_costs": doc.monthly_fixed_costs,
        "target_monthly_revenue": doc.target_monthly_revenue,
        "break_even_point": doc.break_even_point,
        "profit_after_breakeven": doc.profit_after_breakeven,
        
        # Previous Price List
        "compare_previous_price_list": doc.compare_previous_price_list if hasattr(doc, 'compare_previous_price_list') else None,
        "prev_price_increase_percent": doc.prev_price_increase_percent if hasattr(doc, 'prev_price_increase_percent') else 0,
        "prev_price_rounding_amount": doc.prev_price_rounding_amount if hasattr(doc, 'prev_price_rounding_amount') else 0,
        
        # Comparison
        "compare_with_price_list": doc.compare_with_price_list,
        
        # Totals
        "total_profit": doc.total_profit,
        
        # Child Tables
        "items": [
            {
                "name": item.name,
                "idx": item.idx,
                "item_code": item.item_code,
                "item_name": item.item_name,
                "item_group": item.item_group,
                "brand": item.brand,
                "raw_material_cost": item.raw_material_cost,
                "electricity_cost": item.electricity_cost,
                "consumable_cost": item.consumable_cost,
                "rent_cost": item.rent_cost,
                "labor_cost": item.labor_cost,
                "operation_cost": item.operation_cost,
                "subcontracting_cost": item.subcontracting_cost,
                "overhead_cost": item.overhead_cost,
                "total_cost": item.total_cost,
                "selling_price": item.selling_price,
                "profit_amount": item.profit_amount,
                "final_selected_price": item.final_selected_price,
                "commission_amount": item.commission_amount,
                "net_profit_after_commission": item.net_profit_after_commission,
            }
            for item in doc.items
        ],
        
        "pricing_steps": [
            {
                "name": step.name,
                "idx": step.idx,
                "step_type": step.step_type if hasattr(step, 'step_type') else None,
                "step_name": step.step_name if hasattr(step, 'step_name') else None,
                "percentage": step.percentage if hasattr(step, 'percentage') else 0,
                "amount": step.amount if hasattr(step, 'amount') else 0,
                "enabled": step.enabled if hasattr(step, 'enabled') else 1,
            }
            for step in (doc.pricing_steps or [])
        ],
        
        "volume_pricing_tiers": [
            {
                "name": tier.name,
                "idx": tier.idx,
                "min_qty": tier.min_qty if hasattr(tier, 'min_qty') else 0,
                "max_qty": tier.max_qty if hasattr(tier, 'max_qty') else 0,
                "discount_percentage": tier.discount_percentage if hasattr(tier, 'discount_percentage') else 0,
            }
            for tier in (doc.volume_pricing_tiers or [])
        ],
        
        "customer_tier_discounts": [
            {
                "name": tier.name,
                "idx": tier.idx,
                "customer_group": tier.customer_group if hasattr(tier, 'customer_group') else None,
                "discount_percentage": tier.discount_percentage if hasattr(tier, 'discount_percentage') else 0,
            }
            for tier in (doc.customer_tier_discounts or [])
        ],
        
        "manual_material_prices": [
            {
                "name": mp.name,
                "idx": mp.idx,
                "item_code": mp.item_code,
                "item_name": mp.item_name if hasattr(mp, 'item_name') else None,
                "manual_price": mp.manual_price if hasattr(mp, 'manual_price') else 0,
            }
            for mp in (doc.manual_material_prices or [])
        ],
        
        "missing_material_prices": [
            {
                "name": mp.name,
                "idx": mp.idx,
                "item_code": mp.item_code if hasattr(mp, 'item_code') else None,
                "item_name": mp.item_name if hasattr(mp, 'item_name') else None,
            }
            for mp in (doc.missing_material_prices or [])
        ],
        
        "material_substitutions": [
            {
                "name": ms.name,
                "idx": ms.idx,
                "original_item": ms.original_item if hasattr(ms, 'original_item') else None,
                "substitute_item": ms.substitute_item if hasattr(ms, 'substitute_item') else None,
            }
            for ms in (doc.material_substitutions or [])
        ],
        
        "prev_items": [
            {
                "name": item.name,
                "idx": item.idx,
                "item_code": item.item_code,
                "prev_price": item.prev_price if hasattr(item, 'prev_price') else 0,
                "increase_percent": item.increase_percent if hasattr(item, 'increase_percent') else 0,
                "rounding_amount": item.rounding_amount if hasattr(item, 'rounding_amount') else 0,
                "new_price": item.new_price if hasattr(item, 'new_price') else 0,
                "include": item.include if hasattr(item, 'include') else 1,
            }
            for item in (doc.prev_items or [])
        ],
        
        "product_bundles": [
            {
                "name": bundle.name,
                "idx": bundle.idx,
                "bundle_item": bundle.bundle_item if hasattr(bundle, 'bundle_item') else None,
                "bundle_name": bundle.bundle_name if hasattr(bundle, 'bundle_name') else None,
                "total_cost": bundle.total_cost if hasattr(bundle, 'total_cost') else 0,
                "selling_price": bundle.selling_price if hasattr(bundle, 'selling_price') else 0,
            }
            for bundle in (doc.product_bundles or [])
        ],
        
        "manual_item_prices": [
            {
                "name": mp.name,
                "idx": mp.idx,
                "item_code": mp.item_code if hasattr(mp, 'item_code') else None,
                "raw_material_cost": mp.raw_material_cost if hasattr(mp, 'raw_material_cost') else 0,
                "labor_cost": mp.labor_cost if hasattr(mp, 'labor_cost') else 0,
                "subcontracting_cost": mp.subcontracting_cost if hasattr(mp, 'subcontracting_cost') else 0,
                "electricity_cost": mp.electricity_cost if hasattr(mp, 'electricity_cost') else 0,
                "rent_cost": mp.rent_cost if hasattr(mp, 'rent_cost') else 0,
                "consumable_cost": mp.consumable_cost if hasattr(mp, 'consumable_cost') else 0,
                "operation_cost": mp.operation_cost if hasattr(mp, 'operation_cost') else 0,
                "overhead_cost": mp.overhead_cost if hasattr(mp, 'overhead_cost') else 0,
            }
            for mp in (doc.manual_item_prices or [])
        ],
    }


# ==================== Edit APIs ====================

def check_editable(doc):
    """Check if document is editable (draft status)"""
    if doc.docstatus != 0:
        frappe.throw(_("این لیست قیمت قابل ویرایش نیست. فقط لیست‌های پیش‌نویس قابل ویرایش هستند."))


@frappe.whitelist()
def update_price_list_settings(name, data):
    """Update basic settings of a price list"""
    if isinstance(data, str):
        data = json.loads(data)
    
    doc = frappe.get_doc("Auto Price List", name)
    check_editable(doc)
    
    # Basic settings
    if "profit_margin" in data:
        doc.profit_margin = flt(data["profit_margin"])
    if "valid_from" in data:
        doc.valid_from = data["valid_from"]
    if "valid_until" in data:
        doc.valid_until = data["valid_until"]
    if "commission_percentage" in data:
        doc.commission_percentage = flt(data["commission_percentage"])
    if "target_discount_percentage" in data:
        doc.target_discount_percentage = flt(data["target_discount_percentage"])
    if "direct_markup_percentage" in data:
        doc.direct_markup_percentage = flt(data["direct_markup_percentage"])
    if "price_rounding_amount" in data:
        doc.price_rounding_amount = flt(data["price_rounding_amount"])
    
    # Display settings
    if "show_base_cost" in data:
        doc.show_base_cost = cint(data["show_base_cost"])
    if "show_profit_amount" in data:
        doc.show_profit_amount = cint(data["show_profit_amount"])
    if "show_commission_amount" in data:
        doc.show_commission_amount = cint(data["show_commission_amount"])
    if "show_installment_details" in data:
        doc.show_installment_details = cint(data["show_installment_details"])
    if "show_discount_amount" in data:
        doc.show_discount_amount = cint(data["show_discount_amount"])
    
    # Financial analysis
    if "monthly_fixed_costs" in data:
        doc.monthly_fixed_costs = flt(data["monthly_fixed_costs"])
    if "target_monthly_revenue" in data:
        doc.target_monthly_revenue = flt(data["target_monthly_revenue"])
    
    doc.save()
    
    return {"success": True, "message": "تنظیمات با موفقیت ذخیره شد"}


@frappe.whitelist()
def update_installment_settings(name, data):
    """Update installment and deferred payment settings"""
    if isinstance(data, str):
        data = json.loads(data)
    
    doc = frappe.get_doc("Auto Price List", name)
    check_editable(doc)
    
    # Installment settings
    if "enable_installment" in data:
        doc.enable_installment = cint(data["enable_installment"])
    if "down_payment_percentage" in data:
        doc.down_payment_percentage = flt(data["down_payment_percentage"])
    if "number_of_months" in data:
        doc.number_of_months = cint(data["number_of_months"])
    if "monthly_interest_rate" in data:
        doc.monthly_interest_rate = flt(data["monthly_interest_rate"])
    
    # Deferred payment settings
    if "enable_deferred_payment" in data:
        doc.enable_deferred_payment = cint(data["enable_deferred_payment"])
    if "deferred_payment_months" in data:
        doc.deferred_payment_months = cint(data["deferred_payment_months"])
    if "deferred_payment_interest_rate" in data:
        doc.deferred_payment_interest_rate = flt(data["deferred_payment_interest_rate"])
    
    doc.save()
    
    return {"success": True, "message": "تنظیمات قسط با موفقیت ذخیره شد"}


@frappe.whitelist()
def update_advanced_pricing(name, data):
    """Update advanced pricing settings (volume, seasonal, customer tier)"""
    if isinstance(data, str):
        data = json.loads(data)
    
    doc = frappe.get_doc("Auto Price List", name)
    check_editable(doc)
    
    # Advanced pricing flags
    if "enable_volume_pricing" in data:
        doc.enable_volume_pricing = cint(data["enable_volume_pricing"])
    if "enable_seasonal_pricing" in data:
        doc.enable_seasonal_pricing = cint(data["enable_seasonal_pricing"])
    if "seasonal_factor" in data:
        doc.seasonal_factor = flt(data["seasonal_factor"])
    if "enable_customer_tier_pricing" in data:
        doc.enable_customer_tier_pricing = cint(data["enable_customer_tier_pricing"])
    
    # Volume pricing tiers
    if "volume_pricing_tiers" in data:
        doc.volume_pricing_tiers = []
        for tier in data["volume_pricing_tiers"]:
            doc.append("volume_pricing_tiers", {
                "min_qty": tier.get("min_qty", 0),
                "max_qty": tier.get("max_qty", 0),
                "discount_percentage": tier.get("discount_percentage", 0),
            })
    
    # Customer tier discounts
    if "customer_tier_discounts" in data:
        doc.customer_tier_discounts = []
        for tier in data["customer_tier_discounts"]:
            doc.append("customer_tier_discounts", {
                "customer_group": tier.get("customer_group"),
                "discount_percentage": tier.get("discount_percentage", 0),
            })
    
    doc.save()
    
    return {"success": True, "message": "تنظیمات قیمت‌گذاری پیشرفته ذخیره شد"}


@frappe.whitelist()
def update_pricing_steps(name, steps):
    """Update pricing steps"""
    if isinstance(steps, str):
        steps = json.loads(steps)
    
    doc = frappe.get_doc("Auto Price List", name)
    check_editable(doc)
    
    doc.pricing_steps = []
    for step in steps:
        doc.append("pricing_steps", {
            "step_type": step.get("step_type"),
            "step_name": step.get("step_name"),
            "percentage": flt(step.get("percentage", 0)),
            "amount": flt(step.get("amount", 0)),
            "enabled": cint(step.get("enabled", 1)),
        })
    
    doc.save()
    
    return {"success": True, "message": "مراحل قیمت‌گذاری ذخیره شد"}


@frappe.whitelist()
def update_item_costs(name, item_code, costs):
    """Update costs for a specific item"""
    if isinstance(costs, str):
        costs = json.loads(costs)
    
    doc = frappe.get_doc("Auto Price List", name)
    check_editable(doc)
    
    # Find item in items table
    item_found = False
    for item in doc.items:
        if item.item_code == item_code:
            if "raw_material_cost" in costs:
                item.raw_material_cost = flt(costs["raw_material_cost"])
            if "electricity_cost" in costs:
                item.electricity_cost = flt(costs["electricity_cost"])
            if "consumable_cost" in costs:
                item.consumable_cost = flt(costs["consumable_cost"])
            if "rent_cost" in costs:
                item.rent_cost = flt(costs["rent_cost"])
            if "labor_cost" in costs:
                item.labor_cost = flt(costs["labor_cost"])
            if "subcontracting_cost" in costs:
                item.subcontracting_cost = flt(costs["subcontracting_cost"])
            if "overhead_cost" in costs:
                item.overhead_cost = flt(costs["overhead_cost"])
            
            # Recalculate totals
            item.operation_cost = flt(item.electricity_cost or 0) + flt(item.consumable_cost or 0) + flt(item.rent_cost or 0) + flt(item.labor_cost or 0) + flt(item.subcontracting_cost or 0)
            item.total_cost = flt(item.raw_material_cost or 0) + flt(item.operation_cost or 0) + flt(item.overhead_cost or 0)
            
            item_found = True
            break
    
    if not item_found:
        frappe.throw(_("کالا یافت نشد"))
    
    doc.save()
    
    return {"success": True, "message": "هزینه‌های کالا به‌روزرسانی شد"}


@frappe.whitelist()
def add_manual_item_price(name, data):
    """Add or update manual item price"""
    if isinstance(data, str):
        data = json.loads(data)
    
    doc = frappe.get_doc("Auto Price List", name)
    check_editable(doc)
    
    item_code = data.get("item_code")
    if not item_code:
        frappe.throw(_("کد کالا الزامی است"))
    
    # Check if already exists
    found = False
    for mp in (doc.manual_item_prices or []):
        if mp.item_code == item_code:
            mp.raw_material_cost = flt(data.get("raw_material_cost", 0))
            mp.labor_cost = flt(data.get("labor_cost", 0))
            mp.subcontracting_cost = flt(data.get("subcontracting_cost", 0))
            mp.electricity_cost = flt(data.get("electricity_cost", 0))
            mp.rent_cost = flt(data.get("rent_cost", 0))
            mp.consumable_cost = flt(data.get("consumable_cost", 0))
            mp.operation_cost = flt(data.get("operation_cost", 0))
            mp.overhead_cost = flt(data.get("overhead_cost", 0))
            found = True
            break
    
    if not found:
        doc.append("manual_item_prices", {
            "item_code": item_code,
            "raw_material_cost": flt(data.get("raw_material_cost", 0)),
            "labor_cost": flt(data.get("labor_cost", 0)),
            "subcontracting_cost": flt(data.get("subcontracting_cost", 0)),
            "electricity_cost": flt(data.get("electricity_cost", 0)),
            "rent_cost": flt(data.get("rent_cost", 0)),
            "consumable_cost": flt(data.get("consumable_cost", 0)),
            "operation_cost": flt(data.get("operation_cost", 0)),
            "overhead_cost": flt(data.get("overhead_cost", 0)),
        })
    
    doc.save()
    
    return {"success": True, "message": "قیمت دستی ذخیره شد"}


@frappe.whitelist()
def update_material_substitutions(name, substitutions):
    """Update material substitutions"""
    if isinstance(substitutions, str):
        substitutions = json.loads(substitutions)
    
    doc = frappe.get_doc("Auto Price List", name)
    check_editable(doc)
    
    doc.material_substitutions = []
    for sub in substitutions:
        doc.append("material_substitutions", {
            "original_item": sub.get("original_item"),
            "substitute_item": sub.get("substitute_item"),
        })
    
    doc.save()
    
    return {"success": True, "message": "جایگزینی مواد ذخیره شد"}


# ==================== Previous Price List Import APIs ====================

@frappe.whitelist()
def import_from_prev_price_list(name, prev_price_list, increase_percent=0, rounding_amount=0):
    """Import items from a previous price list"""
    doc = frappe.get_doc("Auto Price List", name)
    check_editable(doc)
    
    increase_percent = flt(increase_percent)
    rounding_amount = flt(rounding_amount)
    
    # Get prices from previous price list
    item_prices = frappe.get_all(
        "Item Price",
        filters={"price_list": prev_price_list},
        fields=["item_code", "price_list_rate"]
    )
    
    # Clear existing prev_items
    doc.prev_items = []
    doc.compare_previous_price_list = prev_price_list
    doc.prev_price_increase_percent = increase_percent
    doc.prev_price_rounding_amount = rounding_amount
    
    import math
    
    for ip in item_prices:
        prev_price = flt(ip.price_list_rate)
        new_price = prev_price * (1 + increase_percent / 100)
        
        if rounding_amount > 0:
            new_price = math.ceil(new_price / rounding_amount) * rounding_amount
        
        doc.append("prev_items", {
            "item_code": ip.item_code,
            "prev_price": prev_price,
            "increase_percent": increase_percent,
            "rounding_amount": rounding_amount,
            "new_price": new_price,
            "include": 1,
        })
    
    doc.save()
    
    return {
        "success": True,
        "items_count": len(doc.prev_items),
        "message": f"{len(doc.prev_items)} کالا از لیست قیمت قبلی وارد شد"
    }


@frappe.whitelist()
def update_prev_item(name, item_code, data):
    """Update a single prev_item"""
    if isinstance(data, str):
        data = json.loads(data)
    
    doc = frappe.get_doc("Auto Price List", name)
    check_editable(doc)
    
    import math
    
    for item in doc.prev_items:
        if item.item_code == item_code:
            if "increase_percent" in data:
                item.increase_percent = flt(data["increase_percent"])
            if "rounding_amount" in data:
                item.rounding_amount = flt(data["rounding_amount"])
            if "include" in data:
                item.include = cint(data["include"])
            if "new_price" in data:
                item.new_price = flt(data["new_price"])
            else:
                # Recalculate new_price
                new_price = flt(item.prev_price) * (1 + flt(item.increase_percent) / 100)
                if item.rounding_amount and item.rounding_amount > 0:
                    new_price = math.ceil(new_price / item.rounding_amount) * item.rounding_amount
                item.new_price = new_price
            break
    
    doc.save()
    
    return {"success": True}


@frappe.whitelist()
def apply_prev_prices_to_price_list(name):
    """Apply prev_items prices to the actual price list"""
    doc = frappe.get_doc("Auto Price List", name)
    
    updated_count = 0
    for item in doc.prev_items:
        if not item.include:
            continue
        
        if item.new_price and item.new_price > 0:
            # Check if item price exists
            existing = frappe.db.get_value("Item Price", {
                "item_code": item.item_code,
                "price_list": doc.price_list,
            }, "name")
            
            if existing:
                frappe.db.set_value("Item Price", existing, "price_list_rate", item.new_price)
            else:
                item_price = frappe.new_doc("Item Price")
                item_price.item_code = item.item_code
                item_price.price_list = doc.price_list
                item_price.price_list_rate = item.new_price
                item_price.insert()
            
            updated_count += 1
    
    frappe.db.commit()
    
    return {
        "success": True,
        "updated_count": updated_count,
        "message": f"{updated_count} قیمت به لیست قیمت اضافه شد"
    }


@frappe.whitelist()
def get_missing_materials(name):
    """Get materials without prices"""
    doc = frappe.get_doc("Auto Price List", name)
    
    return {
        "missing_materials": [
            {
                "item_code": mp.item_code if hasattr(mp, 'item_code') else None,
                "item_name": mp.item_name if hasattr(mp, 'item_name') else None,
            }
            for mp in (doc.missing_material_prices or [])
        ]
    }


@frappe.whitelist()
def delete_price_list(name):
    """Delete a draft price list"""
    doc = frappe.get_doc("Auto Price List", name)
    
    if doc.docstatus != 0:
        frappe.throw(_("فقط لیست‌های پیش‌نویس قابل حذف هستند"))
    
    doc.delete()
    
    return {"success": True, "message": "لیست قیمت حذف شد"}


@frappe.whitelist()
def duplicate_price_list(name):
    """Duplicate a price list"""
    doc = frappe.get_doc("Auto Price List", name)
    
    new_doc = frappe.copy_doc(doc)
    new_doc.docstatus = 0
    new_doc.insert()
    
    return {"success": True, "name": new_doc.name, "message": "لیست قیمت کپی شد"}


# ==================== Reports & Analytics APIs ====================

@frappe.whitelist()
def get_raw_materials_report(name):
    """Get raw materials report for a price list"""
    doc = frappe.get_doc("Auto Price List", name)
    
    if hasattr(doc, 'get_raw_materials_report'):
        return doc.get_raw_materials_report()
    
    # Manual implementation
    raw_materials = {}
    detailed_breakdown = []
    
    for item in doc.items:
        if not item.item_code:
            continue
            
        # Get BOM for item
        bom = frappe.db.get_value("BOM", {
            "item": item.item_code,
            "is_active": 1,
            "is_default": 1
        }, "name")
        
        if not bom:
            continue
            
        # Get exploded items
        exploded = frappe.get_all("BOM Explosion Item", 
            filters={"parent": bom},
            fields=["item_code", "item_name", "qty_consumed_per_unit", "stock_uom", "rate"]
        )
        
        item_breakdown = {
            "item_code": item.item_code,
            "item_name": item.item_name,
            "raw_materials": [],
            "total_raw_cost": 0
        }
        
        for exp in exploded:
            # Check if has manual price
            manual_price = None
            for mp in (doc.manual_material_prices or []):
                if mp.item_code == exp.item_code:
                    manual_price = mp.manual_price
                    break
            
            unit_cost = manual_price or exp.rate or 0
            total_cost = flt(exp.qty_consumed_per_unit) * flt(unit_cost)
            
            raw_mat_info = {
                "item_code": exp.item_code,
                "item_name": exp.item_name,
                "required_qty": exp.qty_consumed_per_unit,
                "uom": exp.stock_uom,
                "unit_cost": unit_cost,
                "total_cost": total_cost,
                "manual_price_available": manual_price is not None
            }
            
            item_breakdown["raw_materials"].append(raw_mat_info)
            item_breakdown["total_raw_cost"] += total_cost
            
            # Aggregate
            if exp.item_code not in raw_materials:
                raw_materials[exp.item_code] = {
                    "item_name": exp.item_name,
                    "total_required_qty": 0,
                    "uom": exp.stock_uom,
                    "unit_cost": unit_cost,
                    "manual_price_available": manual_price is not None,
                    "used_in_items": []
                }
            
            raw_materials[exp.item_code]["total_required_qty"] += exp.qty_consumed_per_unit
            if item.item_code not in raw_materials[exp.item_code]["used_in_items"]:
                raw_materials[exp.item_code]["used_in_items"].append(item.item_code)
        
        detailed_breakdown.append(item_breakdown)
    
    # Calculate summary
    total_cost = sum(flt(rm["total_required_qty"]) * flt(rm["unit_cost"]) for rm in raw_materials.values())
    materials_with_manual = sum(1 for rm in raw_materials.values() if rm["manual_price_available"])
    
    return {
        "success": True,
        "summary": {
            "total_items_analyzed": len(doc.items),
            "total_raw_materials": len(raw_materials),
            "materials_with_manual_prices": materials_with_manual,
            "total_raw_materials_cost": total_cost
        },
        "raw_materials_summary": raw_materials,
        "detailed_breakdown": detailed_breakdown
    }


@frappe.whitelist()
def get_purchase_analysis(name, item_code):
    """Get purchase analysis for an item"""
    # Get recent purchase invoices
    purchases = frappe.db.sql("""
        SELECT 
            pi.posting_date,
            pi.name as invoice_name,
            pi.supplier,
            pii.rate,
            pii.qty,
            pii.amount
        FROM `tabPurchase Invoice Item` pii
        INNER JOIN `tabPurchase Invoice` pi ON pii.parent = pi.name
        WHERE pii.item_code = %(item_code)s
          AND pi.docstatus = 1
        ORDER BY pi.posting_date DESC
        LIMIT 20
    """, {"item_code": item_code}, as_dict=True)
    
    if not purchases:
        return {"message": "No purchase data found"}
    
    total_qty = sum(p.qty for p in purchases)
    total_amount = sum(p.amount for p in purchases)
    rates = [p.rate for p in purchases]
    suppliers = list(set(p.supplier for p in purchases))
    
    return {
        "total_purchases": len(purchases),
        "total_quantity": total_qty,
        "total_amount": total_amount,
        "average_rate": total_amount / total_qty if total_qty else 0,
        "latest_rate": purchases[0].rate if purchases else 0,
        "min_rate": min(rates) if rates else 0,
        "max_rate": max(rates) if rates else 0,
        "rate_variance": ((max(rates) - min(rates)) / min(rates) * 100) if rates and min(rates) > 0 else 0,
        "suppliers": suppliers,
        "recent_purchases": purchases[:10]
    }


@frappe.whitelist()
def get_cost_analysis(name):
    """Get cost analysis data"""
    doc = frappe.get_doc("Auto Price List", name)
    
    cost_breakdown = {
        "raw_material": 0,
        "operation": 0,
        "overhead": 0,
        "labor": 0,
        "subcontracting": 0,
        "electricity": 0,
        "rent": 0,
        "consumable": 0
    }
    
    for item in doc.items:
        cost_breakdown["raw_material"] += flt(item.raw_material_cost or 0)
        cost_breakdown["operation"] += flt(item.operation_cost or 0)
        cost_breakdown["overhead"] += flt(item.overhead_cost or 0)
        cost_breakdown["labor"] += flt(item.labor_cost or 0)
        cost_breakdown["subcontracting"] += flt(item.subcontracting_cost or 0)
        cost_breakdown["electricity"] += flt(item.electricity_cost or 0)
        cost_breakdown["rent"] += flt(item.rent_cost or 0)
        cost_breakdown["consumable"] += flt(item.consumable_cost or 0)
    
    total_cost = sum(cost_breakdown.values())
    
    # Calculate percentages
    percentages = {}
    for key, value in cost_breakdown.items():
        percentages[key] = (value / total_cost * 100) if total_cost > 0 else 0
    
    return {
        "breakdown": cost_breakdown,
        "percentages": percentages,
        "total_cost": total_cost,
        "items_count": len(doc.items)
    }


@frappe.whitelist()
def get_break_even_analysis(name):
    """Get break-even analysis"""
    doc = frappe.get_doc("Auto Price List", name)
    
    total_fixed_costs = flt(doc.monthly_fixed_costs or 0)
    total_variable_cost = sum(flt(item.total_cost or 0) for item in doc.items)
    total_selling = sum(flt(item.final_selected_price or item.selling_price or 0) for item in doc.items)
    
    contribution_margin = total_selling - total_variable_cost
    contribution_margin_ratio = contribution_margin / total_selling if total_selling > 0 else 0
    
    break_even_revenue = total_fixed_costs / contribution_margin_ratio if contribution_margin_ratio > 0 else 0
    break_even_units = break_even_revenue / (total_selling / len(doc.items)) if doc.items and total_selling > 0 else 0
    
    return {
        "fixed_costs": total_fixed_costs,
        "variable_costs": total_variable_cost,
        "total_selling": total_selling,
        "contribution_margin": contribution_margin,
        "contribution_margin_ratio": contribution_margin_ratio * 100,
        "break_even_revenue": break_even_revenue,
        "break_even_units": break_even_units,
        "profit_at_target": total_selling - total_variable_cost - total_fixed_costs
    }


# ==================== Currency Conversion ====================

@frappe.whitelist()
def get_currency_rates():
    """Get available currencies and exchange rates"""
    currencies = frappe.get_all("Currency", 
        filters={"enabled": 1},
        fields=["name", "symbol"]
    )
    
    # Get exchange rates
    rates = {}
    for curr in currencies:
        rate = frappe.db.get_value("Currency Exchange", {
            "from_currency": "IRR",
            "to_currency": curr.name
        }, "exchange_rate")
        rates[curr.name] = flt(rate) if rate else 0
    
    return {
        "currencies": currencies,
        "rates": rates,
        "base_currency": "IRR"
    }


@frappe.whitelist()
def convert_prices(name, target_currency, exchange_rate=None):
    """Convert prices to another currency"""
    doc = frappe.get_doc("Auto Price List", name)
    
    if not exchange_rate:
        exchange_rate = frappe.db.get_value("Currency Exchange", {
            "from_currency": "IRR",
            "to_currency": target_currency
        }, "exchange_rate") or 1
    
    exchange_rate = flt(exchange_rate)
    
    converted_items = []
    for item in doc.items:
        converted_items.append({
            "item_code": item.item_code,
            "item_name": item.item_name,
            "total_cost": flt(item.total_cost or 0) * exchange_rate,
            "selling_price": flt(item.selling_price or 0) * exchange_rate,
            "final_selected_price": flt(item.final_selected_price or 0) * exchange_rate,
            "profit_amount": flt(item.profit_amount or 0) * exchange_rate,
        })
    
    return {
        "currency": target_currency,
        "exchange_rate": exchange_rate,
        "items": converted_items,
        "total_selling": sum(i["final_selected_price"] or i["selling_price"] for i in converted_items),
        "total_cost": sum(i["total_cost"] for i in converted_items),
        "total_profit": sum(i["profit_amount"] for i in converted_items)
    }


# ==================== Search APIs (for Autocomplete) ====================

@frappe.whitelist()
def search_items(query, limit=20):
    """Search items for autocomplete"""
    items = frappe.get_all("Item",
        filters=[
            ["Item", "disabled", "=", 0],
            ["Item", "item_name", "like", f"%{query}%"]
        ],
        or_filters=[
            ["Item", "item_code", "like", f"%{query}%"]
        ],
        fields=["item_code", "item_name", "item_group", "brand"],
        limit=limit
    )
    return items


@frappe.whitelist()
def search_item_groups(query, limit=20):
    """Search item groups for autocomplete"""
    groups = frappe.get_all("Item Group",
        filters=[["Item Group", "name", "like", f"%{query}%"]],
        fields=["name", "parent_item_group", "is_group"],
        limit=limit
    )
    return groups


@frappe.whitelist()
def search_brands(query, limit=20):
    """Search brands for autocomplete"""
    brands = frappe.get_all("Brand",
        filters=[["Brand", "name", "like", f"%{query}%"]],
        fields=["name"],
        limit=limit
    )
    return brands


# ==================== Wizard Step APIs ====================

@frappe.whitelist()
def wizard_step_1_save(name, data):
    """Save wizard step 1 - Basic settings"""
    if isinstance(data, str):
        data = json.loads(data)
    
    doc = frappe.get_doc("Auto Price List", name)
    check_editable(doc)
    
    # Update basic settings
    for field in ["price_list", "valid_from", "valid_until", "profit_margin", 
                  "commission_percentage", "price_rounding_amount"]:
        if field in data:
            setattr(doc, field, data[field])
    
    doc.save()
    return {"success": True, "step": 1}


@frappe.whitelist()
def wizard_step_2_fetch_items(name, filters=None):
    """Wizard step 2 - Fetch items based on filters"""
    if isinstance(filters, str):
        filters = json.loads(filters)
    
    doc = frappe.get_doc("Auto Price List", name)
    
    # Set filters
    if filters:
        doc.item_group = filters.get("item_group", "")
        doc.brand = filters.get("brand", "")
        doc.item_name_filter = filters.get("item_name_filter", "")
    
    # Call fetch_items method
    doc.fetch_items()
    doc.save()
    
    return {
        "success": True,
        "step": 2,
        "items_count": len(doc.items),
        "items": [
            {
                "item_code": i.item_code,
                "item_name": i.item_name,
                "item_group": i.item_group,
                "brand": i.brand
            } for i in doc.items
        ]
    }


@frappe.whitelist()
def wizard_step_3_calculate(name):
    """Wizard step 3 - Calculate prices"""
    doc = frappe.get_doc("Auto Price List", name)
    
    doc.calculate_item_prices_internal()
    doc.save()
    
    return {
        "success": True,
        "step": 3,
        "items": [
            {
                "item_code": i.item_code,
                "item_name": i.item_name,
                "raw_material_cost": i.raw_material_cost,
                "operation_cost": i.operation_cost,
                "overhead_cost": i.overhead_cost,
                "total_cost": i.total_cost,
                "selling_price": i.selling_price,
                "profit_amount": i.profit_amount,
                "final_selected_price": i.final_selected_price
            } for i in doc.items
        ],
        "total_profit": doc.total_profit
    }


@frappe.whitelist()
def wizard_step_4_review(name):
    """Wizard step 4 - Review and finalize"""
    doc = frappe.get_doc("Auto Price List", name)
    
    # Get analytics summary
    total_cost = sum(flt(i.total_cost or 0) for i in doc.items)
    total_selling = sum(flt(i.final_selected_price or i.selling_price or 0) for i in doc.items)
    total_profit = sum(flt(i.profit_amount or 0) for i in doc.items)
    
    return {
        "success": True,
        "step": 4,
        "summary": {
            "items_count": len(doc.items),
            "total_cost": total_cost,
            "total_selling": total_selling,
            "total_profit": total_profit,
            "avg_profit_margin": (total_profit / total_cost * 100) if total_cost > 0 else 0
        },
        "ready_to_submit": len(doc.items) > 0
    }


@frappe.whitelist()
def wizard_apply_prices(name):
    """Apply calculated prices to the price list"""
    doc = frappe.get_doc("Auto Price List", name)
    
    updated_count = 0
    for item in doc.items:
        if item.final_selected_price and item.final_selected_price > 0:
            existing = frappe.db.get_value("Item Price", {
                "item_code": item.item_code,
                "price_list": doc.price_list,
            }, "name")
            
            if existing:
                frappe.db.set_value("Item Price", existing, "price_list_rate", item.final_selected_price)
            else:
                item_price = frappe.new_doc("Item Price")
                item_price.item_code = item.item_code
                item_price.price_list = doc.price_list
                item_price.price_list_rate = item.final_selected_price
                item_price.insert()
            
            updated_count += 1
    
    frappe.db.commit()
    
    return {
        "success": True,
        "updated_count": updated_count,
        "message": f"{updated_count} قیمت به لیست قیمت اعمال شد"
    }
