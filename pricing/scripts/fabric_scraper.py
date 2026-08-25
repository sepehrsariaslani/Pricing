
import frappe
import requests
from bs4 import BeautifulSoup
import re

def update_fabric_prices():
    """
    Weekly Job:
    1. Find items with 'پارچه' in name and a set custom_url.
    2. Scrape price and stock status from custom_url.
    3. Update Item custom_stock_status.
    4. Create/Update Item Price.
    """
    print("Starting fabric price update...")
    
    # 1. Find Items
    items = frappe.get_all("Item", 
        filters={
            "item_name": ["like", "%پارچه%"],
            "custom_url": ["is", "set"]
        },
        fields=["name", "item_name", "custom_url"]
    )
    
    if not items:
        # Fallback: Check specifically for our test item in case 'like' filter fails or name doesn't match exactly
        test_item = frappe.db.get_value("Item", "پارچه-منتون-507", ["name", "item_name", "custom_url"], as_dict=True)
        if test_item and test_item.get("custom_url"):
             items = [test_item]
        else:
             print("No items found with 'پارچه' and custom_url.")
             return

    print(f"Found {len(items)} items to process.")

    for item in items:
        process_item(item)

    frappe.db.commit()
    print("Fabric price update completed.")

def process_item(item):
    url = item.custom_url
    print(f"Processing {item.name} - {url}")
    
    try:
        # 2. Scrape
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Prepare data
        price = 0.0
        stock_status = 0 # Default to 0 (Unchecked/Out of Stock)
        
        if "laramob.com" in url:
            # 1. Try JSON-LD (Structured Data) - Preferred
            json_ld = soup.find('script', type='application/ld+json')
            if json_ld:
                try:
                    import json
                    data = json.loads(json_ld.string)
                    # Handle multiple JSON-LD blocks (list) or single object
                    if isinstance(data, list):
                        product_data = next((item for item in data if item.get('@type') == 'Product'), None)
                    else:
                        product_data = data if data.get('@type') == 'Product' else None
                    
                    if product_data:
                        offers = product_data.get('offers', {})
                        
                        # Extract Price
                        if offers.get('@type') == 'AggregateOffer':
                            price = float(offers.get('lowPrice') or offers.get('price') or 0)
                        elif offers.get('@type') == 'Offer':
                            price = float(offers.get('price') or 0)
                        
                        # Extract Availability
                        availability = offers.get('availability') or ""
                        
                        # Check deep structure for availability if missing
                        inner_offers = offers.get('offers')
                        if not availability:
                            if isinstance(inner_offers, dict):
                                availability = inner_offers.get('availability') or availability
                            elif isinstance(inner_offers, list):
                                availability = inner_offers[0].get('availability') or availability

                        # Check deep structure for price if missing
                        if not price:
                            if isinstance(inner_offers, dict):
                                 price = float(inner_offers.get('price') or 0)
                            elif isinstance(inner_offers, list):
                                 price = float(inner_offers[0].get('price') or 0)

                            elif isinstance(inner_offers, list):
                                 price = float(inner_offers[0].get('price') or 0)

                        if "InStock" in str(availability):
                            stock_status = 1
                        elif "OutOfStock" in str(availability) or "Discontinued" in str(availability):
                             stock_status = 0
                        
                        print(f"JSON-LD Scraped Price: {price}, Availability: {availability} -> Status: {stock_status}")
                except Exception as json_err:
                    print(f"JSON-LD parsing failed: {json_err}")

            # 2. Fallback to HTML/Regex if JSON-LD failed/missing
            if price == 0:
                # ... existing regex logic or simplified ...
                pass
            
            # Stock Status Fallback
            if stock_status == "Unknown":
                page_text = soup.get_text()
                if "ناموجود" in page_text and "موجود" not in page_text:
                    stock_status = 0
                elif "موجود" in page_text:
                    stock_status = 1
                else:
                    stock_status = 0 # Default to 0 if unknown

            # Apply Pricing Rule
            if price > 0:
                price = apply_price_rule(price)

            print(f"Final Scraped Price: {price}, Status: {stock_status}")
            
            # 3. Update Item
            frappe.db.set_value("Item", item.name, "custom_stock_status", stock_status)
            
            # 4. Update Item Price
            if price > 0:
                update_item_price(item.name, price)

        elif "savadecor.com" in url:
            # Savadecor Logic
            # Price in Tomans, e.g. "428,000 تومان"
            # Stock: check for "ناموجود"
            
            # 1. Price
            price = 0.0
            price_els = soup.select('.woocommerce-Price-amount, .price, .amount')
            if price_els:
                 # Get the first visible price, usually the main product price
                 for el in price_els:
                     text = el.get_text(strip=True)
                     if any(char.isdigit() for char in text):
                         # clean
                         clean_text = text.replace('تومان', '').replace(',', '').strip()
                         try:
                             price_toman = float(clean_text)
                             if price_toman > 0:
                                 price = price_toman * 10 # Convert to Rials
                                 break
                         except:
                             continue

            # 2. Stock Status
            stock_status = 0 # Default Out
            page_text = soup.get_text()
            if "موجود" in page_text and "ناموجود" not in page_text:
                 stock_status = 1
            # Some sites have "موجود در انبار" or just "موجود"
            # If "ناموجود" is present, it overrides "موجود" usually (e.g. "کالای مورد نظر ناموجود است")
            
            print(f"Savadecor Scraped Price: {price} Rials, Status: {stock_status}")

            # Apply Pricing Rule
            if price > 0:
                price = apply_price_rule(price)

            # 3. Update Item
            frappe.db.set_value("Item", item.name, "custom_stock_status", stock_status)
            
            # 4. Update Item Price
            if price > 0:
                update_item_price(item.name, price)
                
    except Exception as e:
        print(f"Error processing {item.name}: {e}")
        frappe.log_error(f"Fabric Scraper Error: {item.name}", str(e))

def apply_price_rule(price):
    """
    Applies the standar pricing rule:
    1. Add 10% Markup
    2. Round UP to nearest 10,000 Tomans (100,000 Rials)
    """
    import math
    price_with_markup = price * 1.10
    rounding_base = 100000 # 10,000 Tomans
    final_price = math.ceil(price_with_markup / rounding_base) * rounding_base
    
    print(f"Pricing Rule: {price} -> +10%: {price_with_markup} -> Rounded: {final_price}")
    return final_price

@frappe.whitelist()
def update_single_item(item_code):
    """Wraps process_item for UI button"""
    if not frappe.has_permission("Item", "write"):
        frappe.throw("Permission Denied")
        
    item = frappe.get_doc("Item", item_code)
    if not item.custom_url:
        frappe.throw("Please set 'Supplier URL' first.")
        
    process_item(item)
    return "Price updated successfully."

@frappe.whitelist()
def trigger_update_all():
    """Triggers the background job for updating all fabric prices"""
    frappe.enqueue('pricing.scripts.fabric_scraper.update_fabric_prices', queue='long', timeout=3600)
    return "Fabric price update started in the background."

def get_or_create_price_list(price_list_name, buying=1, selling=0):
    if not frappe.db.exists("Price List", price_list_name):
        frappe.get_doc({
            "doctype": "Price List",
            "price_list_name": price_list_name,
            "enabled": 1,
            "buying": buying,
            "selling": selling,
            "currency": "ریال"
        }).insert(ignore_permissions=True)
        print(f"Created Price List: {price_list_name}")
    return price_list_name

def update_item_price(item_code, new_price):
    # Determine Price List
    # Priority: Standard Selling -> Standard Buying
    price_list = "Standard Selling"
    if frappe.db.exists("Price List", price_list):
        pass
    elif frappe.db.exists("Price List", "Standard Buying"):
        price_list = "Standard Buying"
    else:
        # Create Standard Selling if neither exists
        price_list = get_or_create_price_list("Standard Selling", buying=0, selling=1)
    
    # Check if Item Price exists
    name = frappe.db.exists("Item Price", {"item_code": item_code, "price_list": price_list})
    
    if name:
        doc = frappe.get_doc("Item Price", name)
        doc.price_list_rate = new_price
        doc.save()
        print(f"Updated Item Price for {item_code} in {price_list}: {new_price}")
    else:
        doc = frappe.new_doc("Item Price")
        doc.item_code = item_code
        doc.price_list = price_list
        doc.price_list_rate = new_price
        doc.currency = "ریال" 
        doc.insert()
        print(f"Created Item Price for {item_code} in {price_list}: {new_price}")

