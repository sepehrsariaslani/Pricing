#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
تست سیستم کراولر نهایی
"""

import sys
import os
sys.path.append('/Users/sepehr/frappe-bench/apps/pricing')

# Mock frappe for testing
class MockFrappe:
    class MockCache:
        def __init__(self):
            self.data = {}
        
        def get_value(self, key):
            return self.data.get(key, False)
        
        def set_value(self, key, value):
            self.data[key] = value
        
        def delete_value(self, key):
            if key in self.data:
                del self.data[key]
    
    def __init__(self):
        self._cache = MockFrappe.MockCache()
    
    def cache(self):
        return self._cache
    
    def publish_realtime(self, event, data, user=None):
        print(f"📡 Realtime: {event} -> {data}")
    
    def log_error(self, message):
        print(f"❌ Error: {message}")
    
    def enqueue(self, func, **kwargs):
        print(f"🔄 Enqueued: {func.__name__}")
        return func()
    
    def whitelist(self):
        def decorator(func):
            return func
        return decorator
    
    def get_doc(self, doctype, name):
        return MockCompetitor(name)

class MockCompetitor:
    def __init__(self, name):
        self.name = name
        self.competitor_name = f"Test Competitor {name}"
        self.website_url = "https://example.com"
        self.max_products = 100
        self.last_crawl_date = None
        self.total_products_found = 0
        self.products = []
    
    def append(self, field, data):
        if field == 'products':
            self.products.append(data)
    
    def save(self):
        print(f"💾 Saved competitor: {self.name}")

# Mock frappe utilities
def now_datetime():
    from datetime import datetime
    return datetime.now()

def flt(value, precision=2):
    try:
        return float(value)
    except:
        return 0.0

def cint(value):
    try:
        return int(value)
    except:
        return 0

# Setup mock environment
import builtins
builtins.frappe = MockFrappe()

# Import the crawler
from pricing.pricing.doctype.competitor_analysis.final_enhanced_crawler import FinalEnhancedCrawler

def test_crawler_initialization():
    """تست راه‌اندازی کراولر"""
    print("🧪 تست راه‌اندازی کراولر...")
    
    competitor = MockCompetitor("test-competitor")
    crawler = FinalEnhancedCrawler(competitor)
    
    assert crawler.competitor.name == "test-competitor"
    assert crawler.max_products == 100
    assert crawler.timeout == 30
    assert crawler.retry_attempts == 3
    
    print("✅ راه‌اندازی کراولر موفق بود")

def test_site_type_detection():
    """تست تشخیص نوع سایت"""
    print("🧪 تست تشخیص نوع سایت...")
    
    competitor = MockCompetitor("test-competitor")
    crawler = FinalEnhancedCrawler(competitor)
    
    # Mock response for site type detection
    import requests
    from unittest.mock import Mock, patch
    
    mock_response = Mock()
    mock_response.text = "welcome to our ecommerce store with shopping cart and buy now buttons"
    mock_response.status_code = 200
    
    with patch.object(crawler.session, 'get', return_value=mock_response):
        site_type = crawler.detect_site_type()
        assert site_type == 'ecommerce'
    
    print("✅ تشخیص نوع سایت موفق بود")

def test_product_url_validation():
    """تست اعتبارسنجی URL محصول"""
    print("🧪 تست اعتبارسنجی URL محصول...")
    
    competitor = MockCompetitor("test-competitor")
    crawler = FinalEnhancedCrawler(competitor)
    
    # URLs that should be valid
    valid_urls = [
        "https://example.com/product/test-item",
        "https://example.com/products/another-item",
        "https://example.com/محصول/تست"
    ]
    
    # URLs that should be invalid
    invalid_urls = [
        "https://example.com/cart",
        "https://example.com/checkout",
        "https://example.com/account",
        ""
    ]
    
    for url in valid_urls:
        assert crawler.is_product_url(url), f"URL should be valid: {url}"
    
    for url in invalid_urls:
        assert not crawler.is_product_url(url), f"URL should be invalid: {url}"
    
    print("✅ اعتبارسنجی URL محصول موفق بود")

def test_price_parsing():
    """تست پارس قیمت"""
    print("🧪 تست پارس قیمت...")
    
    competitor = MockCompetitor("test-competitor")
    crawler = FinalEnhancedCrawler(competitor)
    
    test_prices = [
        ("$19.99", 19.99),
        ("1,250,000 تومان", 1250000),
        ("€45.50", 45.50),
        ("Price: 123.45", 123.45),
        ("invalid", 0),
        ("", 0)
    ]
    
    for price_text, expected in test_prices:
        result = crawler.parse_price(price_text)
        assert result == expected, f"Price parsing failed for '{price_text}': got {result}, expected {expected}"
    
    print("✅ پارس قیمت موفق بود")

def test_control_flags():
    """تست کنترل‌های pause/stop"""
    print("🧪 تست کنترل‌های pause/stop...")
    
    competitor = MockCompetitor("test-competitor")
    crawler = FinalEnhancedCrawler(competitor)
    
    # Test initial state
    crawler.check_control_flags()
    assert not crawler.is_paused
    assert not crawler.should_stop
    
    # Test pause
    frappe.cache().set_value(f"crawler_pause_{crawler.competitor_name}", True)
    crawler.check_control_flags()
    assert crawler.is_paused
    
    # Test stop
    frappe.cache().set_value(f"crawler_stop_{crawler.competitor_name}", True)
    crawler.check_control_flags()
    assert crawler.should_stop
    
    print("✅ کنترل‌های pause/stop موفق بود")

def test_progress_tracking():
    """تست ردیابی پیشرفت"""
    print("🧪 تست ردیابی پیشرفت...")
    
    competitor = MockCompetitor("test-competitor")
    crawler = FinalEnhancedCrawler(competitor)
    
    # Test initial progress
    progress = crawler.get_progress_data()
    assert progress['status'] == 'pending'
    assert progress['total_discovered'] == 0
    assert progress['progress_percentage'] == 0
    
    # Test progress update
    crawler.update_progress(
        total_discovered=100,
        total_crawled=50,
        status=crawler.progress.status.__class__.CRAWLING
    )
    
    progress = crawler.get_progress_data()
    assert progress['total_discovered'] == 100
    assert progress['total_crawled'] == 50
    assert progress['progress_percentage'] == 50.0
    
    print("✅ ردیابی پیشرفت موفق بود")

def test_logging_system():
    """تست سیستم لاگ"""
    print("🧪 تست سیستم لاگ...")
    
    competitor = MockCompetitor("test-competitor")
    crawler = FinalEnhancedCrawler(competitor)
    
    # Test logging
    crawler.log("Test message", 'info', send_realtime=False)
    assert len(crawler.log_messages) == 1
    assert "Test message" in crawler.log_messages[0]
    
    # Test error logging
    crawler.log("Error message", 'error', send_realtime=False)
    assert len(crawler.log_messages) == 2
    
    print("✅ سیستم لاگ موفق بود")

def run_all_tests():
    """اجرای تمام تست‌ها"""
    print("🚀 شروع تست‌های سیستم کراولر نهایی...")
    print("=" * 60)
    
    try:
        test_crawler_initialization()
        test_site_type_detection()
        test_product_url_validation()
        test_price_parsing()
        test_control_flags()
        test_progress_tracking()
        test_logging_system()
        
        print("=" * 60)
        print("🎉 تمام تست‌ها با موفقیت انجام شد!")
        return True
        
    except Exception as e:
        print("=" * 60)
        print(f"❌ خطا در تست‌ها: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
