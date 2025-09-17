import frappe

def get_context(context):
    """تنظیم context برای صفحه داشبورد کراولر"""
    
    # بررسی دسترسی کاربر
    if not frappe.has_permission("Competitor Analysis", "read"):
        frappe.throw("شما دسترسی لازم برای مشاهده این صفحه را ندارید")
    
    # دریافت لیست رقبا
    competitors = frappe.get_all(
        "Competitor Analysis",
        fields=["name", "competitor_name", "website_url", "last_crawl_date", "total_products_found"],
        order_by="creation desc"
    )
    
    context.competitors = competitors
    context.title = "داشبورد کراولر"
    context.no_cache = 1
    
    return context
