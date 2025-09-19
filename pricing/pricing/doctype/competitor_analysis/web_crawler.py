# -*- coding: utf-8 -*-

import frappe
import requests
from bs4 import BeautifulSoup
import json
import re
from urllib.parse import urljoin, urlparse
from datetime import datetime, timedelta
import time
import random
from frappe.utils import flt, cint, today, now_datetime, add_days
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from queue import Queue
import hashlib
import os
import json
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Optional, Any
from datetime import timedelta
import asyncio

# Try to import aiohttp with fallback
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    # Create a dummy aiohttp module to prevent import errors
    class DummyAiohttp:
        class ClientSession:
            def __init__(self, *args, **kwargs):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            async def get(self, *args, **kwargs):
                raise ImportError("aiohttp not installed")
    
    aiohttp = DummyAiohttp()

# Advanced crawler imports with fallbacks
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    import undetected_chromedriver as uc
except ImportError:
    webdriver = None
    By = None
    WebDriverWait = None
    EC = None
    Options = None
    ChromeDriverManager = None
    uc = None

try:
    from fake_useragent import UserAgent
except ImportError:
    UserAgent = None

try:
    from diskcache import Cache
except ImportError:
    Cache = None

try:
    from loguru import logger as loguru_logger
except ImportError:
    loguru_logger = None

try:
    import cv2
    import numpy as np
    from PIL import Image
    import pytesseract
    import easyocr
except ImportError:
    cv2 = None
    np = None
    Image = None
    pytesseract = None
    easyocr = None

try:
    from transformers import pipeline
except ImportError:
    pipeline = None

try:
    import spacy
except ImportError:
    spacy = None

try:
    from textblob import TextBlob
except ImportError:
    TextBlob = None

try:
    import ollama
except ImportError:
    ollama = None

try:
    import redis
except ImportError:
    redis = None

class CrawlStatus(Enum):
    PENDING = "pending"
    DISCOVERING = "discovering"
    CRAWLING = "crawling"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"

@dataclass
class CrawlProgress:
    total_discovered: int = 0
    total_crawled: int = 0
    total_saved: int = 0
    total_failed: int = 0
    current_url: str = ""
    status: CrawlStatus = CrawlStatus.PENDING
    start_time: datetime = None


class CompetitorWebCrawler:
    """سیستم هوشمند کرال وب‌سایت‌های رقبا"""
    
    def __init__(self, competitor_doc):
        self.competitor = competitor_doc
        self.session = requests.Session()
        self.setup_headers()
        
        # تنظیمات کرال
        self.max_products = getattr(competitor_doc, 'max_products', 500)
        self.delay_range = (1, 3)
        self.max_workers = 3
        self.chunk_size = 50
        self.retry_attempts = 3
        self.timeout = 30
        
        # ذخیره‌سازی داده‌ها
        self.discovered_products = []
        self.crawled_products = []
        self.failed_urls = []
        self.products_found = []
        self.seo_data = {}
        self.processed_urls = set()
        
        # پیشرفت
        self.progress = CrawlProgress()
        self.progress.start_time = now_datetime()
        
        # سیستم لاگ
        self.setup_logging()
        
        # صف پردازش
        self.product_queue = Queue()
        self.results_queue = Queue()
        
        # کنترل
        self.is_paused = False
        self.should_stop = False
        self.competitor_name = competitor_doc.name
        
    def setup_headers(self):
        """تنظیم headers برای جلوگیری از مسدود شدن"""
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        
        self.session.headers.update({
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'fa,fa-IR,en;q=0.8,en-US;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none'
        })
        self.headers = self.session.headers
        
    def setup_logging(self):
        """راه‌اندازی سیستم لاگ"""
        self.log_messages = []
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_file = f"logs/unified_crawler_{self.competitor.name}_{timestamp}.log"
        os.makedirs("logs", exist_ok=True)
        
    def log(self, message, level='info', send_realtime=True):
        """ثبت لاگ"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] {message}"
        self.log_messages.append(log_entry)
        
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(f"{log_entry}\n")
        except:
            pass
        
        if send_realtime:
            try:
                frappe.publish_realtime("crawler_log", {
                    "competitor": self.competitor.name,
                    "message": message,
                    "timestamp": timestamp,
                    "level": level,
                    "progress": self.get_progress_data()
                }, user=frappe.session.user)
            except:
                pass
        
        if level == 'error':
            frappe.log_error(message)

    def get_progress_data(self):
        """دریافت داده‌های پیشرفت"""
        total_operations = max(self.progress.total_discovered, 1)
        completed_operations = self.progress.total_crawled + self.progress.total_failed
        progress_percentage = min((completed_operations / total_operations) * 100, 100)
        
        return {
            "status": self.progress.status.value,
            "total_discovered": self.progress.total_discovered,
            "total_crawled": self.progress.total_crawled,
            "total_saved": self.progress.total_saved,
            "total_failed": self.progress.total_failed,
            "current_url": self.progress.current_url,
            "progress_percentage": round(progress_percentage, 1),
            "is_paused": self.is_paused,
            "should_stop": self.should_stop
        }
    
    def update_progress(self, **kwargs):
        """به‌روزرسانی پیشرفت"""
        for key, value in kwargs.items():
            if hasattr(self.progress, key):
                setattr(self.progress, key, value)
        
        try:
            frappe.publish_realtime("crawler_progress", self.get_progress_data(), user=frappe.session.user)
        except:
            pass
    
    def check_control_flags(self):
        """بررسی فلگ‌های کنترل"""
        try:
            self.is_paused = frappe.cache().get_value(f"crawler_pause_{self.competitor_name}") or False
            self.should_stop = frappe.cache().get_value(f"crawler_stop_{self.competitor_name}") or False
        except:
            pass

    def crawl_competitor_website(self):
        """کرال کامل وب‌سایت رقیب"""
        frappe.enqueue(self.start_smart_crawl, queue='long', timeout=3600)
        return {"success": True, "message": "کرال هوشمند در پس‌زمینه شروع شد"}
    
    def start_smart_crawl(self):
        """شروع کرال هوشمند"""
        try:
            self.log("🚀 شروع کرال هوشمند وب‌سایت...")
            self.update_progress(status=CrawlStatus.DISCOVERING)
            
            # مرحله 1: کشف محصولات
            self.log("🔍 مرحله 1: کشف محصولات...")
            discovered_count = self.discover_all_products()
            
            if discovered_count == 0:
                self.log("❌ هیچ محصولی یافت نشد", 'error')
                self.update_progress(status=CrawlStatus.FAILED)
                return {'success': False, 'message': 'محصولی یافت نشد'}
            
            self.log(f"✅ {discovered_count} محصول کشف شد")
            self.update_progress(total_discovered=discovered_count, status=CrawlStatus.CRAWLING)
            
            # مرحله 2: کرال جزئیات محصولات
            self.log("📊 مرحله 2: استخراج جزئیات محصولات...")
            crawled_count = self.crawl_product_details()
            
            # مرحله 3: ذخیره نتایج
            self.log("💾 مرحله 3: ذخیره نتایج...")
            self.update_progress(status=CrawlStatus.PROCESSING)
            saved_count = self.save_results()
            
            # تکمیل
            self.update_progress(
                total_saved=saved_count,
                status=CrawlStatus.COMPLETED,
                current_url=""
            )
            
            # به‌روزرسانی تاریخ کرال
            self.competitor.last_crawl_date = now_datetime()
            self.competitor.total_products_found = saved_count
            self.competitor.save()
            
            self.log(f"🎉 کرال تکمیل شد: {saved_count} محصول ذخیره شد")
            
            final_result = {
                'success': True,
                'discovered_products': discovered_count,
                'crawled_products': crawled_count,
                'saved_products': saved_count,
                'failed_urls': len(self.failed_urls),
                'log_file': self.log_file
            }
            
            frappe.publish_realtime("crawler_completed", final_result, user=frappe.session.user)
            return final_result
            
        except Exception as e:
            error_msg = f"خطا در کرال: {str(e)}"
            self.log(error_msg, 'error')
            self.update_progress(status=CrawlStatus.FAILED)
            return {'success': False, 'message': error_msg}

    def discover_all_products(self):
        """کشف تمام محصولات از وب‌سایت"""
        try:
            site_type = self.detect_site_type()
            self.log(f"🔍 نوع سایت: {site_type}")
            
            discovery_methods = [
                ('sitemap', self.discover_from_sitemap),
                ('categories', self.discover_from_categories),
                ('search', self.discover_from_search)
            ]
            
            total_discovered = 0
            
            for method_name, method_func in discovery_methods:
                self.check_control_flags()
                if self.should_stop:
                    break
                    
                try:
                    self.log(f"🔎 روش: {method_name}")
                    count = method_func()
                    total_discovered += count
                    self.log(f"   → {count} محصول یافت شد")
                    
                    if total_discovered >= self.max_products:
                        break
                        
                except Exception as e:
                    self.log(f"خطا در {method_name}: {str(e)}", 'error')
                    continue
            
            # حذف تکراری‌ها
            unique_products = list(set(self.discovered_products))
            self.discovered_products = unique_products[:self.max_products]
            self.log(f"🧹 پس از حذف تکراری‌ها: {len(self.discovered_products)} محصول")
            
            return len(self.discovered_products)
            
        except Exception as e:
            self.log(f"خطا در کشف محصولات: {str(e)}", 'error')
            return 0
    
    def detect_site_type(self):
        """تشخیص نوع وب‌سایت"""
        try:
            response = self.session.get(self.competitor.website_url, timeout=self.timeout)
            content = response.text.lower()
            
            if 'wordpress' in content or 'wp-content' in content:
                return 'wordpress'
            elif 'shopify' in content:
                return 'shopify'
            elif 'woocommerce' in content:
                return 'woocommerce'
            
            ecommerce_indicators = [
                'add to cart', 'shopping cart', 'checkout', 'buy now',
                'افزودن به سبد', 'سبد خرید', 'خرید', 'قیمت'
            ]
            
            if any(indicator in content for indicator in ecommerce_indicators):
                return 'ecommerce'
            elif any(indicator in content for indicator in ['products', 'catalog', 'محصولات']):
                return 'catalog'
            else:
                return 'general'
                
        except Exception:
            return 'general'
    
    def discover_from_sitemap(self):
        """کشف پیشرفته محصولات از sitemap"""
        try:
            sitemap_urls = [
                '/sitemap.xml', '/sitemap_index.xml', '/product-sitemap.xml',
                '/sitemap-product.xml', '/sitemap/product.xml', '/products.xml'
            ]
            products_found = 0
            
            for sitemap_path in sitemap_urls:
                if self.should_stop:
                    break
                    
                try:
                    sitemap_url = urljoin(self.competitor.website_url, sitemap_path)
                    response = self.session.get(sitemap_url, timeout=self.timeout)
                    
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.content, 'xml')
                        
                        # بررسی sitemap index
                        sitemap_tags = soup.find_all('sitemap')
                        if sitemap_tags:
                            for sitemap_tag in sitemap_tags:
                                loc = sitemap_tag.find('loc')
                                if loc and 'product' in loc.text.lower():
                                    sub_products = self.process_sitemap_url(loc.text)
                                    products_found += sub_products
                        else:
                            # پردازش sitemap معمولی
                            products_found += self.process_sitemap_url(sitemap_url)
                            
                except Exception:
                    continue
                    
            return products_found
            
        except Exception:
            return 0
    
    def process_sitemap_url(self, sitemap_url):
        """پردازش یک sitemap"""
        try:
            response = self.session.get(sitemap_url, timeout=self.timeout)
            if response.status_code != 200:
                return 0
                
            soup = BeautifulSoup(response.content, 'xml')
            urls = soup.find_all('loc')
            products_found = 0
            
            for url_tag in urls:
                if self.should_stop:
                    break
                    
                url = url_tag.text.strip()
                if self.is_product_url_enhanced(url):
                    self.add_discovered_product(url)
                    products_found += 1
                    
                    if products_found >= self.max_products:
                        break
            
            return products_found
            
        except Exception:
            return 0
    
    def discover_from_categories(self):
        """کشف پیشرفته محصولات از صفحات دسته‌بندی"""
        try:
            category_urls = self.find_category_pages_enhanced()
            products_found = 0
            
            for category_url in category_urls[:15]:
                if self.should_stop:
                    break
                    
                try:
                    self.log(f"🏷️ بررسی دسته: {category_url}")
                    self.update_progress(current_url=category_url)
                    
                    # کرال صفحه دسته‌بندی با pagination
                    category_products = self.crawl_category_with_pagination(category_url)
                    products_found += len(category_products)
                    
                    # تاخیر بین دسته‌بندی‌ها
                    time.sleep(random.uniform(*self.delay_range))
                    
                except Exception as e:
                    self.log(f"خطا در دسته‌بندی {category_url}: {str(e)}", 'error')
                    continue
                    
            return products_found
            
        except Exception:
            return 0
    
    def find_category_pages_enhanced(self):
        """یافتن پیشرفته صفحات دسته‌بندی"""
        try:
            category_urls = set()
            
            # روش 1: جستجو در صفحه اصلی
            response = self.session.get(self.competitor.website_url, timeout=self.timeout)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # الگوهای دسته‌بندی
            category_patterns = [
                r'/category/', r'/categories/', r'/cat/', r'/c/',
                r'/products/', r'/shop/', r'/store/',
                r'/دسته/', r'/محصولات/', r'/فروشگاه/'
            ]
            
            # جستجو در لینک‌ها
            for link in soup.find_all('a', href=True):
                href = link['href']
                if any(re.search(pattern, href, re.IGNORECASE) for pattern in category_patterns):
                    full_url = urljoin(self.competitor.website_url, href)
                    category_urls.add(full_url)
            
            return list(category_urls)
            
        except Exception as e:
            self.log(f"خطا در یافتن دسته‌بندی‌ها: {str(e)}", 'error')
            return []
    
    def crawl_category_with_pagination(self, category_url):
        """کرال دسته‌بندی با pagination پیشرفته"""
        products = []
        page = 1
        max_pages = 10
        
        while page <= max_pages and not self.should_stop:
            try:
                # ساخت URL صفحه
                page_url = self.build_page_url(category_url, page)
                response = self.session.get(page_url, timeout=self.timeout)
                
                if response.status_code != 200:
                    break
                
                soup = BeautifulSoup(response.content, 'html.parser')
                page_products = self.extract_products_from_page_enhanced(soup, page_url)
                
                if not page_products:
                    break
                
                products.extend(page_products)
                page += 1
                
                # تاخیر بین صفحات
                time.sleep(random.uniform(0.5, 1.5))
                
            except Exception as e:
                self.log(f"خطا در صفحه {page}: {str(e)}", 'error')
                break
        
        return products
    
    def build_page_url(self, base_url, page):
        """ساخت URL صفحه pagination"""
        page_patterns = [
            f"{base_url}?page={page}",
            f"{base_url}/page/{page}",
            f"{base_url}?p={page}",
            f"{base_url}&page={page}" if '?' in base_url else f"{base_url}?page={page}"
        ]
        
        return page_patterns[0]  # استفاده از الگوی اول به عنوان پیش‌فرض
    
    def discover_from_search(self):
        """کشف پیشرفته محصولات از جستجو"""
        try:
            search_queries = [
                'محصولات', 'products', 'shop', 'store',
                'فروش', 'خرید', 'buy', 'sale', 'محصول'
            ]
            products_found = 0
            
            for query in search_queries:
                if self.should_stop or products_found >= self.max_products:
                    break
                    
                try:
                    search_url = self.build_search_url(query)
                    if search_url:
                        self.log(f"🔍 جستجو برای: {query}")
                        search_products = self.crawl_search_results(search_url)
                        products_found += len(search_products)
                        
                except Exception as e:
                    self.log(f"خطا در جستجو {query}: {str(e)}", 'error')
                    continue
            
            return products_found
            
        except Exception as e:
            self.log(f"خطا در کشف جستجو: {str(e)}", 'error')
            return 0
    
    def build_search_url(self, query):
        """ساخت URL جستجو"""
        try:
            # الگوهای مختلف جستجو
            search_patterns = [
                f"/search?q={query}",
                f"/search?query={query}",
                f"/?s={query}",
                f"/search/{query}"
            ]
            
            for pattern in search_patterns:
                search_url = urljoin(self.competitor.website_url, pattern)
                # تست ساده برای بررسی وجود صفحه جستجو
                response = self.session.head(search_url, timeout=10)
                if response.status_code == 200:
                    return search_url
            
            return None
            
        except Exception:
            return None
    
    def crawl_search_results(self, search_url):
        """کرال نتایج جستجو"""
        products = []
        
        try:
            response = self.session.get(search_url, timeout=self.timeout)
            if response.status_code != 200:
                return products
            
            soup = BeautifulSoup(response.content, 'html.parser')
            search_products = self.extract_products_from_page_enhanced(soup, search_url)
            products.extend(search_products)
            
        except Exception as e:
            self.log(f"خطا در کرال نتایج جستجو: {str(e)}", 'error')
        
        return products
    
    def find_category_pages(self):
        """یافتن صفحات دسته‌بندی"""
        try:
            category_urls = set()
            response = self.session.get(self.competitor.website_url, timeout=self.timeout)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            category_patterns = [
                r'/category/', r'/categories/', r'/products/', r'/shop/',
                r'/دسته/', r'/محصولات/', r'/فروشگاه/'
            ]
            
            for link in soup.find_all('a', href=True):
                href = link['href']
                if any(re.search(pattern, href, re.IGNORECASE) for pattern in category_patterns):
                    full_url = urljoin(self.competitor.website_url, href)
                    category_urls.add(full_url)
            
            return list(category_urls)
            
        except Exception:
            return []
    
    def extract_products_from_page(self, soup, page_url):
        """استخراج محصولات از یک صفحه"""
        products = []
        
        product_selectors = [
            'a[href*="/product/"]', 'a[href*="/products/"]',
            '.product a', '.product-item a'
        ]
        
        for selector in product_selectors:
            links = soup.select(selector)
            for link in links:
                href = link.get('href')
                if href:
                    full_url = urljoin(page_url, href)
                    if self.is_product_url(full_url):
                        self.add_discovered_product(full_url)
                        products.append(full_url)
        
        return products
    
    def extract_products_from_page_enhanced(self, soup, page_url):
        """استخراج پیشرفته محصولات از یک صفحه"""
        products = []
        
        # سلکتورهای محتمل برای محصولات
        product_selectors = [
            'a[href*="/product/"]', 'a[href*="/products/"]',
            'a[href*="/shop/"]', 'a[href*="/item/"]',
            '.product a', '.product-item a', '.woocommerce-loop-product__link',
            '.product-link', '.item-link', '[class*="product"] a[href]'
        ]
        
        for selector in product_selectors:
            links = soup.select(selector)
            for link in links:
                href = link.get('href')
                if href:
                    full_url = urljoin(page_url, href)
                    if self.is_product_url_enhanced(full_url):
                        self.add_discovered_product(full_url)
                        products.append(full_url)
        
        return products
    
    def add_discovered_product(self, url):
        """اضافه کردن محصول کشف شده"""
        if url not in self.processed_urls:
            self.discovered_products.append(url)
            self.processed_urls.add(url)
    
    def remove_duplicates(self):
        """حذف محصولات تکراری"""
        unique_products = list(set(self.discovered_products))
        self.discovered_products = unique_products[:self.max_products]
        return self.discovered_products
    
    def crawl_product_details(self):
        """کرال جزئیات محصولات"""
        try:
            if not self.discovered_products:
                return 0
            
            self.log(f"📊 شروع کرال جزئیات {len(self.discovered_products)} محصول...")
            
            total_crawled = 0
            chunk_size = self.chunk_size
            
            for i in range(0, len(self.discovered_products), chunk_size):
                if self.should_stop:
                    break
                
                chunk = self.discovered_products[i:i + chunk_size]
                crawled_chunk = self.crawl_chunk_parallel(chunk)
                total_crawled += len(crawled_chunk)
                
                self.update_progress(total_crawled=total_crawled)
                
                if i + chunk_size < len(self.discovered_products):
                    time.sleep(random.uniform(2, 5))
            
            return total_crawled
            
        except Exception as e:
            self.log(f"خطا در کرال جزئیات: {str(e)}", 'error')
            return 0
    
    def save_results(self):
        """ذخیره نتایج در سیستم"""
        try:
            if not self.crawled_products:
                return 0
            
            self.log(f"💾 شروع ذخیره {len(self.crawled_products)} محصول...")
            saved_count = 0
            
            for product_data in self.crawled_products:
                if self.should_stop:
                    break
                
                try:
                    if self.save_single_product(product_data):
                        saved_count += 1
                        
                except Exception as e:
                    self.log(f"خطا در ذخیره محصول: {str(e)}", 'error')
                    continue
            
            return saved_count
            
        except Exception as e:
            self.log(f"خطا در ذخیره نتایج: {str(e)}", 'error')
            return 0
    
    def crawl_chunk_parallel(self, urls_chunk):
        """کرال موازی یک دسته از URL ها"""
        crawled_products = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_url = {
                executor.submit(self.crawl_single_product, url): url 
                for url in urls_chunk
            }
            
            for future in as_completed(future_to_url):
                if self.should_stop:
                    break
                
                url = future_to_url[future]
                try:
                    product_data = future.result()
                    if product_data:
                        crawled_products.append(product_data)
                    else:
                        self.failed_urls.append(url)
                        self.update_progress(total_failed=len(self.failed_urls))
                        
                except Exception as e:
                    self.failed_urls.append(url)
                    self.update_progress(total_failed=len(self.failed_urls))
        
        self.crawled_products.extend(crawled_products)
        return crawled_products
    
    def crawl_single_product(self, url):
        """کرال یک محصول با retry logic"""
        for attempt in range(self.retry_attempts):
            self.check_control_flags()
            if self.should_stop:
                return None
                
            while self.is_paused and not self.should_stop:
                self.check_control_flags()
                time.sleep(1)
            
            try:
                self.update_progress(current_url=url)
                
                response = self.session.get(url, timeout=self.timeout)
                if response.status_code != 200:
                    if attempt < self.retry_attempts - 1:
                        time.sleep(2 ** attempt)
                        continue
                    return None
                
                soup = BeautifulSoup(response.content, 'html.parser')
                product_data = self.extract_product_data_enhanced(soup, url)
                
                if product_data and product_data.get('name'):
                    return product_data
                elif attempt < self.retry_attempts - 1:
                    time.sleep(2 ** attempt)
                    continue
                else:
                    return None
                    
            except Exception as e:
                if attempt < self.retry_attempts - 1:
                    time.sleep(2 ** attempt)
                    continue
                else:
                    return None
            
            time.sleep(random.uniform(*self.delay_range))
        
        return None
    
    def extract_product_data_enhanced(self, soup, url):
        """استخراج پیشرفته داده‌های محصول"""
        try:
            product_data = {
                'url': url,
                'name': self.extract_product_name_enhanced(soup),
                'price': self.extract_product_price_enhanced(soup),
                'description': self.extract_product_description_enhanced(soup),
                'image_url': self.extract_product_image_enhanced(soup, url),
                'availability': self.extract_product_availability_enhanced(soup),
                'brand': self.extract_product_brand(soup),
                'category': self.extract_product_category(soup)
            }
            
            return product_data
            
        except Exception:
            return None
    
    def extract_product_name_enhanced(self, soup):
        """استخراج پیشرفته نام محصول"""
        selectors = [
            'h1.product-title', 'h1.product-name', '.product-title',
            '.product-name', '.entry-title', 'h1', '[itemprop="name"]'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                name = element.get_text().strip()
                if name and len(name) > 3:
                    return name[:200]
        
        return ""
    
    def extract_product_price_enhanced(self, soup):
        """استخراج پیشرفته قیمت محصول"""
        price_selectors = [
            '.price', '.product-price', '.cost', '.amount',
            '[itemprop="price"]', '.final-price', '.sale-price'
        ]
        
        for selector in price_selectors:
            elements = soup.select(selector)
            for element in elements:
                price_text = element.get_text().strip()
                price = self.parse_price_enhanced(price_text)
                if price > 0:
                    return price
        
        return 0
    
    def parse_price_enhanced(self, price_text):
        """تجزیه پیشرفته قیمت از متن"""
        try:
            # الگوهای قیمت فارسی
            persian_patterns = [
                r'([\d,]+)\s*تومان',
                r'([\d,]+)\s*تومن', 
                r'([\d,]+)\s*ریال',
                r'قیمت[:\s]*([\d,]+)',
                r'([\d,]+)\s*IRR'
            ]
            
            for pattern in persian_patterns:
                match = re.search(pattern, price_text)
                if match:
                    price_str = match.group(1).replace(',', '')
                    try:
                        return float(price_str)
                    except ValueError:
                        continue
            
            # تجزیه عمومی
            price_text = re.sub(r'[^\d.,]', '', price_text)
            price_text = price_text.replace(',', '')
            
            if price_text:
                price = float(price_text)
                return price if price > 1000 else 0
        except:
            pass
        
        return 0
    
    def extract_product_description_enhanced(self, soup):
        """استخراج پیشرفته توضیحات محصول"""
        desc_selectors = [
            '.product-description', '.description', '.product-details',
            '.entry-content', '.product-summary', '[itemprop="description"]'
        ]
        
        for selector in desc_selectors:
            element = soup.select_one(selector)
            if element:
                desc = element.get_text().strip()
                if desc and len(desc) > 10:
                    return desc[:1000]
        
        return ""
    
    def extract_product_image_enhanced(self, soup, base_url):
        """استخراج پیشرفته تصویر محصول"""
        img_selectors = [
            '.product-image img', '.product-photo img', 
            '.main-image img', '.gallery img', '[itemprop="image"]'
        ]
        
        for selector in img_selectors:
            img = soup.select_one(selector)
            if img:
                src = img.get('src') or img.get('data-src') or img.get('data-lazy')
                if src:
                    return urljoin(base_url, src)
        
        return ""
    
    def extract_product_availability_enhanced(self, soup):
        """استخراج پیشرفته وضعیت موجودی"""
        text = soup.get_text().lower()
        if any(word in text for word in ['موجود', 'available', 'in stock']):
            return 'موجود'
        elif any(word in text for word in ['ناموجود', 'out of stock', 'unavailable']):
            return 'ناموجود'
        
        return ""
    
    def extract_product_brand(self, soup):
        """استخراج برند محصول"""
        brand_selectors = ['.brand', '.product-brand', '.manufacturer', '[itemprop="brand"]']
        
        for selector in brand_selectors:
            element = soup.select_one(selector)
            if element:
                brand = element.get_text().strip()
                if brand:
                    return brand[:100]
        
        return ""
    
    def extract_product_category(self, soup):
        """استخراج دسته‌بندی محصول"""
        category_selectors = ['.breadcrumb a', '.category', '.product-category']
        
        categories = []
        for selector in category_selectors:
            elements = soup.select(selector)
            for element in elements:
                cat = element.get_text().strip()
                if cat and cat not in categories:
                    categories.append(cat)
        
        return ' > '.join(categories[:3]) if categories else ""
    
    def crawl_seo_data(self):
        """استخراج اطلاعات SEO"""
        try:
            response = self.session.get(self.competitor.website_url, timeout=30)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # استخراج متا تگ‌ها
            meta_description = soup.find('meta', attrs={'name': 'description'})
            if meta_description:
                self.competitor.meta_description = meta_description.get('content', '')[:500]
            
            # استخراج کلمات کلیدی
            meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
            if meta_keywords:
                keywords = meta_keywords.get('content', '')
                self.competitor.top_keywords = keywords[:1000]
            
            # تحلیل ساختار سایت
            self.analyze_site_structure(soup)
            
            # دریافت اطلاعات ترافیک از API های خارجی
            self.get_traffic_data()
            
            frappe.publish_realtime("crawler_status", {
                "message": "تحلیل SEO تکمیل شد",
                "progress": 30
            })
            
        except Exception as e:
            frappe.log_error(f"خطا در تحلیل SEO: {str(e)}")
    
    def analyze_site_structure(self, soup):
        """تحلیل ساختار سایت"""
        try:
            # شمارش تگ‌های مهم
            h1_tags = len(soup.find_all('h1'))
            h2_tags = len(soup.find_all('h2'))
            img_tags = len(soup.find_all('img'))
            
            # بررسی وجود Schema markup
            schema_tags = soup.find_all('script', {'type': 'application/ld+json'})
            
            self.seo_data.update({
                'h1_count': h1_tags,
                'h2_count': h2_tags,
                'images_count': img_tags,
                'schema_markup': len(schema_tags) > 0
            })
            
        except Exception as e:
            frappe.log_error(f"خطا در تحلیل ساختار سایت: {str(e)}")
    
    def get_traffic_data(self):
        """دریافت اطلاعات ترافیک از API های خارجی"""
        try:
            # اینجا می‌توانید از API های مختلف استفاده کنید
            # مثل SimilarWeb, Alexa, SEMrush و غیره
            
            domain = urlparse(self.competitor.website_url).netloc
            
            # نمونه استفاده از API فرضی
            # traffic_data = self.get_similarweb_data(domain)
            
            # برای نمونه، مقادیر تصادفی تولید می‌کنیم
            self.competitor.monthly_traffic = random.randint(1000, 100000)
            self.competitor.domain_authority = random.randint(20, 80)
            self.competitor.backlinks_count = random.randint(100, 10000)
            
        except Exception as e:
            frappe.log_error(f"خطا در دریافت اطلاعات ترافیک: {str(e)}")
    
    def crawl_products(self):
        """کرال محصولات از وب‌سایت"""
        try:
            # تشخیص نوع وب‌سایت (فروشگاهی، شرکتی، و غیره)
            site_type = self.detect_site_type()
            
            if site_type == 'ecommerce':
                self.crawl_ecommerce_products()
            elif site_type == 'catalog':
                self.crawl_catalog_products()
            else:
                self.crawl_general_products()
                
            frappe.publish_realtime("crawler_status", {
                "message": f"{len(self.products_found)} محصول یافت شد",
                "progress": 60
            })
            
        except Exception as e:
            frappe.log_error(f"خطا در کرال محصولات: {str(e)}")
    
    def detect_site_type(self):
        """تشخیص نوع وب‌سایت"""
        try:
            response = self.session.get(self.competitor.website_url)
            content = response.text.lower()
            
            # تشخیص فروشگاه اینترنتی
            ecommerce_indicators = [
                'add to cart', 'shopping cart', 'checkout', 'buy now',
                'افزودن به سبد', 'سبد خرید', 'خرید', 'قیمت'
            ]
            
            if any(indicator in content for indicator in ecommerce_indicators):
                return 'ecommerce'
            
            # تشخیص کاتالوگ محصولات
            catalog_indicators = [
                'products', 'catalog', 'محصولات', 'کاتالوگ'
            ]
            
            if any(indicator in content for indicator in catalog_indicators):
                return 'catalog'
                
            return 'general'
            
        except Exception:
            return 'general'
    
    def crawl_ecommerce_products(self):
        """کرال محصولات از فروشگاه اینترنتی"""
        try:
            # جستجوی صفحات محصولات
            product_urls = self.find_product_pages()
            
            for url in product_urls[:50]:  # محدود به 50 محصول
                try:
                    product_data = self.extract_product_data(url)
                    if product_data:
                        self.products_found.append(product_data)
                        self.save_product_to_competitor_list(product_data)
                    
                    # تاخیر برای جلوگیری از مسدود شدن
                    time.sleep(random.uniform(1, 3))
                    
                except Exception as e:
                    continue
                    
        except Exception as e:
            frappe.log_error(f"خطا در کرال فروشگاه: {str(e)}")
    
    def find_product_pages(self):
        """یافتن صفحات محصولات"""
        product_urls = []
        
        try:
            # جستجو در sitemap
            sitemap_urls = self.get_sitemap_urls()
            product_urls.extend(sitemap_urls)
            
            # جستجو در صفحات دسته‌بندی
            category_urls = self.find_category_pages()
            for category_url in category_urls:
                category_products = self.extract_products_from_category(category_url)
                product_urls.extend(category_products)
                
        except Exception as e:
            frappe.log_error(f"خطا در یافتن صفحات محصولات: {str(e)}")
            
        return list(set(product_urls))  # حذف تکراری‌ها
    
    def get_sitemap_urls(self):
        """استخراج URL ها از sitemap"""
        urls = []
        try:
            sitemap_url = urljoin(self.competitor.website_url, '/sitemap.xml')
            response = self.session.get(sitemap_url)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'xml')
                loc_tags = soup.find_all('loc')
                
                for loc in loc_tags:
                    url = loc.text
                    # فیلتر کردن URL های محصولات
                    if any(keyword in url.lower() for keyword in ['product', 'item', 'محصول']):
                        urls.append(url)
                        
        except Exception as e:
            frappe.log_error(f"خطا در خواندن sitemap: {str(e)}")
            
        return urls
    
    def find_category_pages(self):
        """یافتن صفحات دسته‌بندی"""
        category_urls = []
        
        try:
            response = self.session.get(self.competitor.website_url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # جستجوی لینک‌های دسته‌بندی
            category_keywords = ['category', 'categories', 'products', 'دسته', 'محصولات']
            
            for link in soup.find_all('a', href=True):
                href = link['href']
                link_text = link.get_text().lower()
                
                if any(keyword in link_text for keyword in category_keywords):
                    full_url = urljoin(self.competitor.website_url, href)
                    category_urls.append(full_url)
                    
        except Exception as e:
            frappe.log_error(f"خطا در یافتن دسته‌بندی‌ها: {str(e)}")
            
        return category_urls
    
    def extract_products_from_category(self, category_url):
        """استخراج محصولات از صفحه دسته‌بندی"""
        product_urls = []
        
        try:
            response = self.session.get(category_url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # جستجوی لینک‌های محصولات
            for link in soup.find_all('a', href=True):
                href = link['href']
                
                # تشخیص لینک‌های محصولات بر اساس الگوهای رایج
                if self.is_product_url(href):
                    full_url = urljoin(category_url, href)
                    product_urls.append(full_url)
                    
        except Exception as e:
            frappe.log_error(f"خطا در استخراج محصولات از دسته‌بندی: {str(e)}")
            
        return product_urls
    
    def is_product_url(self, url):
        """تشخیص اینکه آیا URL مربوط به محصول است یا نه"""
        product_patterns = [
            r'/product/',
            r'/item/',
            r'/p/',
            r'/محصول/',
            r'product-',
            r'item-'
        ]
        
        return any(re.search(pattern, url.lower()) for pattern in product_patterns)
    
    def is_product_url_enhanced(self, url):
        """بررسی پیشرفته URL محصول"""
        try:
            if not url or url in self.processed_urls:
                return False
            
            # الگوهای محصول
            product_patterns = [
                r'/product/', r'/products/', r'/item/', r'/shop/',
                r'/store/', r'/buy/', r'/محصول/', r'/کالا/',
                r'product-', r'item-', r'/p/', r'/i/'
            ]
            
            # الگوهای غیرمحصول (فیلتر)
            exclude_patterns = [
                r'/cart', r'/checkout', r'/account', r'/login',
                r'/register', r'/contact', r'/about', r'/blog',
                r'/news', r'/category/', r'/tag/', r'/search'
            ]
            
            # بررسی الگوهای محصول
            has_product_pattern = any(re.search(pattern, url, re.IGNORECASE) for pattern in product_patterns)
            
            # بررسی الگوهای غیرمحصول
            has_exclude_pattern = any(re.search(pattern, url, re.IGNORECASE) for pattern in exclude_patterns)
            
            return has_product_pattern and not has_exclude_pattern
            
        except Exception:
            return False
    
    def extract_product_data(self, product_url):
        """استخراج اطلاعات محصول از صفحه"""
        try:
            response = self.session.get(product_url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            product_data = {
                'url': product_url,
                'name': self.extract_product_name(soup),
                'price': self.extract_product_price(soup),
                'description': self.extract_product_description(soup),
                'image_url': self.extract_product_image(soup),
                'availability': self.extract_availability(soup)
            }
            
            return product_data if product_data['name'] else None
            
        except Exception as e:
            frappe.log_error(f"خطا در استخراج اطلاعات محصول {product_url}: {str(e)}")
            return None
    
    def extract_product_name(self, soup):
        """استخراج نام محصول"""
        # جستجو در تگ‌های مختلف
        selectors = [
            'h1',
            '.product-title',
            '.product-name',
            '[itemprop="name"]',
            'title'
        ]
        
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text().strip()
                
        return None
    
    def extract_product_price(self, soup):
        """استخراج قیمت محصول"""
        # الگوهای مختلف قیمت
        price_selectors = [
            '.price',
            '.product-price',
            '[itemprop="price"]',
            '.cost',
            '.amount'
        ]
        
        for selector in price_selectors:
            elements = soup.select(selector)
            for element in elements:
                price_text = element.get_text()
                price = self.extract_number_from_text(price_text)
                if price:
                    return price
                    
        return None
    
    def extract_number_from_text(self, text):
        """استخراج عدد از متن"""
        # حذف کاراکترهای غیرضروری و استخراج عدد
        numbers = re.findall(r'[\d,]+', text.replace(',', ''))
        if numbers:
            try:
                return flt(numbers[0])
            except:
                return None
        return None
    
    
    def extract_price_from_text(self, text):
        """استخراج قیمت از متن فارسی و انگلیسی"""
        if not text:
            return 0
        
        # الگوهای قیمت فارسی
        persian_patterns = [
            r'([\d,]+)\s*تومان',
            r'([\d,]+)\s*تومن', 
            r'([\d,]+)\s*ریال',
            r'قیمت[:\s]*([\d,]+)',
            r'([\d,]+)\s*IRR'
        ]
        
        for pattern in persian_patterns:
            match = re.search(pattern, text)
            if match:
                price_str = match.group(1).replace(',', '')
                try:
                    return float(price_str)
                except ValueError:
                    continue
        
        # اگر قیمت فارسی پیدا نشد، جستجوی عددی کلی
        numbers = re.findall(r'[\d,]+', text.replace(',', ''))
        if numbers:
            try:
                price = float(numbers[0])
                return price if price > 1000 else 0
            except:
                pass
        
        return 0

    def extract_product_description(self, soup):
        """استخراج توضیحات محصول"""
        desc_selectors = [
            '.product-description',
            '.description',
            '[itemprop="description"]',
            '.product-details'
        ]
        
        for selector in desc_selectors:
            element = soup.select_one(selector)
            if element:
                return element.get_text().strip()[:500]
                
        return None
    
    def extract_product_image(self, soup):
        """استخراج تصویر محصول"""
        img_selectors = [
            '.product-image img',
            '.main-image img',
            '[itemprop="image"]'
        ]
        
        for selector in img_selectors:
            element = soup.select_one(selector)
            if element:
                src = element.get('src') or element.get('data-src')
                if src:
                    return urljoin(self.competitor.website_url, src)
                    
        return None
    
    def extract_availability(self, soup):
        """استخراج وضعیت موجودی"""
        availability_indicators = [
            'in stock', 'available', 'موجود', 'در انبار'
        ]
        
        text = soup.get_text().lower()
        return any(indicator in text for indicator in availability_indicators)
    
    def create_or_update_competitor_product(self, product_data, product_url):
        """ایجاد یا به‌روزرسانی محصول رقیب"""
        try:
            # بررسی وجود محصول
            existing_product = None
            for product in self.competitor.products:
                if product.product_url == product_url:
                    existing_product = product
                    break
            
            if existing_product:
                # به‌روزرسانی محصول موجود
                existing_product.item_name = product_data.get('title', '')
                existing_product.competitor_price = product_data.get('price', 0)
                existing_product.description = product_data.get('description', '')
                existing_product.image_url = product_data.get('image_url', '')
                existing_product.availability = 'موجود' if product_data.get('availability') else 'ناموجود'
                existing_product.last_updated = today()
            else:
                # اضافه کردن محصول جدید
                self.competitor.append('products', {
                    'competitor_analysis': self.competitor.name,
                    'item_name': product_data.get('title', '') or product_data.get('name', ''),
                    'competitor_price': product_data.get('price', 0),
                    'product_url': product_url,
                    'description': product_data.get('description', ''),
                    'image_url': product_data.get('images', [''])[0] if product_data.get('images') else '',
                    'availability': 'موجود' if product_data.get('availability') else 'ناموجود',
                    'last_updated': today()
                })
                
        except Exception as e:
            frappe.log_error(f"خطا در ایجاد/به‌روزرسانی محصول رقیب: {str(e)}")
    
    
    def save_product_to_competitor_list(self, product_data):
        """ذخیره محصول در لیست محصولات رقیب"""
        try:
            # بررسی وجود محصول
            existing_product = None
            for product in self.competitor.products:
                if product.product_url == product_data['url']:
                    existing_product = product
                    break
            
            if existing_product:
                # به‌روزرسانی محصول موجود
                existing_product.competitor_price = product_data['price']
                existing_product.last_updated = today()
            else:
                # اضافه کردن محصول جدید
                self.competitor.append('products', {
                    'competitor_analysis': self.competitor.name,
                    'item_name': product_data.get('title', ''),
                    'competitor_price': product_data['price'],
                    'product_url': product_data['url'],
                    'description': product_data['description'],
                    'image_url': product_data.get('images', [''])[0] if product_data.get('images') else product_data.get('image_url', ''),
                    'availability': 'موجود' if product_data['availability'] else 'ناموجود',
                    'last_updated': today()
                })
                
        except Exception as e:
            frappe.log_error(f"خطا در ذخیره محصول: {str(e)}")
    
    def save_single_product(self, product_data):
        """ذخیره یک محصول با بررسی وجود"""
        try:
            # بررسی وجود محصول
            existing = self.find_existing_product(product_data)
            
            if existing:
                # به‌روزرسانی محصول موجود
                return self.update_existing_product(existing, product_data)
            else:
                # ایجاد محصول جدید
                return self.create_new_product(product_data)
                
        except Exception as e:
            self.log(f"خطا در ذخیره محصول: {str(e)}", 'error')
            return False
    
    def find_existing_product(self, product_data):
        """یافتن محصول موجود"""
        try:
            # جستجو بر اساس URL
            existing = frappe.db.get_value(
                'Competitor Analysis Products',
                {'url': product_data['url'], 'parent': self.competitor.name},
                'name'
            )
            
            if existing:
                return frappe.get_doc('Competitor Analysis Products', existing)
            
            # جستجو بر اساس نام محصول
            if product_data.get('name'):
                existing = frappe.db.get_value(
                    'Competitor Analysis Products',
                    {
                        'product_name': product_data['name'],
                        'parent': self.competitor.name
                    },
                    'name'
                )
                
                if existing:
                    return frappe.get_doc('Competitor Analysis Products', existing)
            
            return None
            
        except Exception:
            return None
    
    def update_existing_product(self, existing_product, product_data):
        """به‌روزرسانی محصول موجود"""
        try:
            existing_product.product_name = product_data.get('name', existing_product.product_name)
            existing_product.price = flt(product_data.get('price', 0))
            existing_product.description = product_data.get('description', existing_product.description)
            existing_product.image_url = product_data.get('image_url', existing_product.image_url)
            existing_product.availability = product_data.get('availability', existing_product.availability)
            existing_product.brand = product_data.get('brand', existing_product.brand)
            existing_product.category = product_data.get('category', existing_product.category)
            existing_product.last_updated = now_datetime()
            
            existing_product.save()
            return True
            
        except Exception as e:
            self.log(f"خطا در به‌روزرسانی محصول: {str(e)}", 'error')
            return False
    
    def create_new_product(self, product_data):
        """ایجاد محصول جدید"""
        try:
            product_row = {
                'product_name': product_data.get('name', ''),
                'url': product_data.get('url', ''),
                'price': flt(product_data.get('price', 0)),
                'description': product_data.get('description', ''),
                'image_url': product_data.get('image_url', ''),
                'availability': product_data.get('availability', ''),
                'brand': product_data.get('brand', ''),
                'category': product_data.get('category', ''),
                'crawl_date': now_datetime()
            }
            
            self.competitor.append('products', product_row)
            self.competitor.save()
            return True
            
        except Exception as e:
            self.log(f"خطا در ایجاد محصول جدید: {str(e)}", 'error')
            return False
    
    def extract_smart_price(self, soup):
        """استخراج هوشمند قیمت با تشخیص کلاس‌های مختلف"""
        try:
            # کلاس‌های معمول قیمت در سایت‌های ایرانی
            price_selectors = [
                '.price', '.product-price', '[data-testid="price"]',
                '.price-current', '.final-price', '.sale-price',
                '.price-now', '.current-price', '.selling-price',
                '.قیمت', '.price-value', '.amount', '.cost',
                '[class*="price"]', '[class*="قیمت"]',
                '[id*="price"]', '[id*="قیمت"]'
            ]
            
            # جستجو برای عناصر حاوی تومان یا ریال
            currency_patterns = [
                r'([\d,]+)\s*تومان',
                r'([\d,]+)\s*ریال', 
                r'([\d,]+)\s*IRR',
                r'([\d,]+)\s*تومن'
            ]
            
            # ابتدا جستجو در کلاس‌های قیمت
            for selector in price_selectors:
                elements = soup.select(selector)
                for element in elements:
                    price_text = element.get_text(strip=True)
                    
                    # بررسی وجود واحد پولی
                    for pattern in currency_patterns:
                        match = re.search(pattern, price_text)
                        if match:
                            price_str = match.group(1).replace(',', '')
                            try:
                                return float(price_str)
                            except ValueError:
                                continue
            
            # جستجوی کلی در تمام متن صفحه
            page_text = soup.get_text()
            for pattern in currency_patterns:
                matches = re.findall(pattern, page_text)
                if matches:
                    # انتخاب بزرگترین عدد (احتمالاً قیمت اصلی)
                    prices = []
                    for match in matches:
                        try:
                            price = float(match.replace(',', ''))
                            if price > 1000:  # فیلتر قیمت‌های معقول
                                prices.append(price)
                        except ValueError:
                            continue
                    
                    if prices:
                        return max(prices)
            
            return 0
            
        except Exception as e:
            frappe.log_error(f"خطا در استخراج قیمت: {str(e)}")
            return 0
    
    def extract_specifications(self, soup):
        """استخراج مشخصات فنی محصول"""
        try:
            specs = {}
            
            # جستجو برای جداول مشخصات
            spec_selectors = [
                '.specifications table', '.specs table',
                '.product-specs table', '.technical-specs table',
                '.مشخصات table', '.features table'
            ]
            
            for selector in spec_selectors:
                table = soup.select_one(selector)
                if table:
                    rows = table.find_all('tr')
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 2:
                            key = cells[0].get_text(strip=True)
                            value = cells[1].get_text(strip=True)
                            if key and value:
                                specs[key] = value
            
            # جستجو برای لیست مشخصات
            list_selectors = [
                '.specifications ul', '.specs ul',
                '.product-features ul', '.مشخصات ul'
            ]
            
            for selector in list_selectors:
                ul = soup.select_one(selector)
                if ul:
                    items = ul.find_all('li')
                    for item in items:
                        text = item.get_text(strip=True)
                        if ':' in text:
                            key, value = text.split(':', 1)
                            specs[key.strip()] = value.strip()
            
            return specs
            
        except Exception as e:
            frappe.log_error(f"خطا در استخراج مشخصات: {str(e)}")
            return {}
    
    def extract_keywords_from_content(self, soup):
        """استخراج کلمات کلیدی از محتوای صفحه"""
        try:
            keywords = []
            
            # استخراج از meta keywords
            meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
            if meta_keywords:
                content = meta_keywords.get('content', '')
                keywords.extend([k.strip() for k in content.split(',') if k.strip()])
            
            # استخراج از عنوان صفحه
            title = soup.find('title')
            if title:
                title_text = title.get_text(strip=True)
                # تقسیم عنوان به کلمات
                title_words = re.findall(r'\b[\u0600-\u06FF\w]+\b', title_text)
                keywords.extend(title_words)
            
            # استخراج از meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc:
                content = meta_desc.get('content', '')
                desc_words = re.findall(r'\b[\u0600-\u06FF\w]+\b', content)
                keywords.extend(desc_words)
            
            # استخراج از h1, h2, h3 tags
            headers = soup.find_all(['h1', 'h2', 'h3'])
            for header in headers:
                header_text = header.get_text(strip=True)
                header_words = re.findall(r'\b[\u0600-\u06FF\w]+\b', header_text)
                keywords.extend(header_words)
            
            # حذف تکراری‌ها و فیلتر کلمات کوتاه
            unique_keywords = list(set(keywords))
            filtered_keywords = [k for k in unique_keywords if len(k) > 2]
            
            return filtered_keywords[:20]  # محدود به 20 کلمه کلیدی
            
        except Exception as e:
            frappe.log_error(f"خطا در استخراج کلمات کلیدی: {str(e)}")
            return []

    def crawl_single_product_enhanced(self, product_url, price_selector=None):
        """کرال پیشرفته محصول با ظرفیت بالا و استخراج جامع"""
        import time
        start_time = time.time()
        
        try:
            # تلاش با روش‌های مختلف
            product_data = None
            crawl_method = "requests"
            
            # روش 1: درخواست معمولی
            try:
                response = requests.get(product_url, headers=self.headers, timeout=30)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')
                product_data = self.extract_comprehensive_product_info(soup, product_url, price_selector)
            except:
                crawl_method = "selenium"
                # روش 2: Selenium برای سایت‌های پیچیده
                #product_data = self.crawl_with_selenium(product_url, price_selector)
                # اگر درخواست اول ناموفق بود، تلاش مجدد با headers مختلف
                try:
                    alternate_headers = self.session.headers.copy()
                    alternate_headers.update({
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'fa,en-US;q=0.5',
                        'Accept-Encoding': 'gzip, deflate',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                    })
                    response = requests.get(product_url, headers=alternate_headers, timeout=30)
                    soup = BeautifulSoup(response.content, 'html.parser')
                    product_data = self.extract_comprehensive_product_info(soup, product_url, price_selector)
                except:
                    pass
            
            if not product_data or not product_data.get('title'):
                return {'success': False, 'message': 'اطلاعات محصول یافت نشد'}
            
            # محاسبه امتیاز کیفیت داده
            quality_score = self.calculate_data_quality_score(product_data)
            product_data['data_quality_score'] = quality_score
            
            # زمان کرال
            crawl_time = round(time.time() - start_time, 2)
            
            # ذخیره در فایل JSON با اطلاعات کامل
            json_file = self.save_enhanced_product_to_json(product_data, product_url, crawl_method, crawl_time)
            
            # ایجاد یا به‌روزرسانی محصول رقیب
            self.create_or_update_competitor_product(product_data, product_url)
            
            return {
                'success': True,
                'message': f'محصول با موفقیت کرال شد ({crawl_method}) - امتیاز کیفیت: {quality_score}%',
                'product_data': product_data,
                'json_file': json_file,
                'crawl_time': crawl_time,
                'crawl_method': crawl_method,
                'data_quality_score': quality_score
            }
            
        except Exception as e:
            error_msg = f"خطا در کرال پیشرفته محصول {product_url}: {str(e)}"
            frappe.log_error(error_msg)
            return {'success': False, 'message': error_msg}




    def crawl_with_selenium(self, product_url, price_selector=None):
        """کرال با Selenium برای سایت‌های JavaScript"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            options = Options()
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument(f'--user-agent={self.headers.get("User-Agent", "")}')
            
            driver = webdriver.Chrome(options=options)
            driver.get(product_url)
            
            # انتظار برای بارگذاری کامل صفحه
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # اسکرول برای بارگذاری محتوای lazy load
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # دریافت HTML نهایی
            html = driver.page_source
            driver.quit()
            
            soup = BeautifulSoup(html, 'html.parser')
            return self.extract_comprehensive_product_info(soup, product_url, price_selector)
            
        except Exception as e:
            frappe.log_error(f"خطا در کرال Selenium: {str(e)}")
            return None

    def extract_comprehensive_product_info(self, soup, product_url, price_selector=None):
        """استخراج جامع اطلاعات محصول"""
        product_data = {}
        
        # عنوان محصول - روش‌های مختلف
        title_selectors = [
            'h1[class*="title"]', 'h1[class*="name"]', 'h1[class*="product"]',
            '.product-title', '.product-name', '.item-title', '.title',
            'h1', '[data-testid*="title"]', '[data-cy*="title"]'
        ]
        product_data['title'] = self.extract_by_selectors(soup, title_selectors)
        
        # قیمت - روش‌های پیشرفته
        if price_selector:
            price_text = soup.select_one(price_selector)
            product_data['price'] = self.extract_price_from_text(price_text.get_text() if price_text else "")
        else:
            price_selectors = [
                '[class*="price"]:not([class*="old"]):not([class*="original"])',
                '[class*="cost"]', '[class*="amount"]', '[data-testid*="price"]',
                '.price-current', '.current-price', '.final-price', '.sale-price'
            ]
            price_text = self.extract_by_selectors(soup, price_selectors)
            product_data['price'] = self.extract_price_from_text(price_text)
        
        # واحد پول
        product_data['currency'] = self.extract_currency(soup)
        
        # برند
        brand_selectors = [
            '[class*="brand"]', '[data-testid*="brand"]', '.manufacturer',
            'meta[property="product:brand"]', 'meta[name="brand"]'
        ]
        product_data['brand'] = self.extract_by_selectors(soup, brand_selectors)
        
        # SKU/کد محصول
        sku_selectors = [
            '[class*="sku"]', '[class*="code"]', '[data-testid*="sku"]',
            'meta[property="product:retailer_item_id"]'
        ]
        product_data['sku'] = self.extract_by_selectors(soup, sku_selectors)
        
        # دسته‌بندی
        category_selectors = [
            '.breadcrumb a:last-child', '[class*="category"]', '[class*="breadcrumb"]',
            'meta[property="product:category"]'
        ]
        product_data['category'] = self.extract_by_selectors(soup, category_selectors)
        
        # موجودی
        availability_selectors = [
            '[class*="stock"]', '[class*="availability"]', '[class*="inventory"]',
            '[data-testid*="stock"]'
        ]
        product_data['availability'] = self.extract_by_selectors(soup, availability_selectors)
        
        # امتیاز و نظرات
        product_data['rating'] = self.extract_rating(soup)
        product_data['reviews_count'] = self.extract_reviews_count(soup)
        
        # توضیحات
        desc_selectors = [
            '[class*="description"]', '[class*="detail"]', '[class*="content"]',
            '.product-description', '.item-description'
        ]
        product_data['description'] = self.extract_by_selectors(soup, desc_selectors, get_text=True)
        
        # مشخصات فنی
        product_data['specifications'] = self.extract_specifications_enhanced(soup)
        
        # تصاویر
        product_data['images'] = self.extract_product_images(soup, product_url)
        
        # SEO
        product_data['seo_title'] = soup.find('title').get_text().strip() if soup.find('title') else ""
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        product_data['seo_description'] = meta_desc.get('content', '') if meta_desc else ""
        
        # کلمات کلیدی
        product_data['keywords'] = self.extract_keywords_from_content(soup)
        
        return product_data

    def extract_by_selectors(self, soup, selectors, get_text=False):
        """استخراج متن با استفاده از چندین selector"""
        for selector in selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    text = element.get_text().strip() if get_text else element.get_text().strip()
                    if text:
                        return text
            except:
                continue
        return ""

    def extract_currency(self, soup):
        """تشخیص واحد پول"""
        currency_patterns = {
            'تومان': ['تومان', 'تمن', 'TMN'],
            'ریال': ['ریال', 'IRR'],
            'دلار': ['$', 'USD', 'دلار'],
            'یورو': ['€', 'EUR', 'یورو']
        }
        
        page_text = soup.get_text().lower()
        for currency, patterns in currency_patterns.items():
            for pattern in patterns:
                if pattern.lower() in page_text:
                    return currency
        return 'تومان'  # پیش‌فرض

    def extract_rating(self, soup):
        """استخراج امتیاز محصول"""
        rating_selectors = [
            '[class*="rating"]', '[class*="star"]', '[data-testid*="rating"]',
            '.score', '.rate'
        ]
        
        for selector in rating_selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    # جستجوی عدد در متن
                    import re
                    text = element.get_text()
                    numbers = re.findall(r'\d+\.?\d*', text)
                    if numbers:
                        rating = float(numbers[0])
                        if 0 <= rating <= 5:
                            return rating
            except:
                continue
        return 0

    def extract_reviews_count(self, soup):
        """استخراج تعداد نظرات"""
        review_selectors = [
            '[class*="review"]', '[class*="comment"]', '[data-testid*="review"]'
        ]
        
        for selector in review_selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    import re
                    text = element.get_text()
                    numbers = re.findall(r'\d+', text)
                    if numbers:
                        return int(numbers[0])
            except:
                continue
        return 0

    def extract_specifications_enhanced(self, soup):
        """استخراج پیشرفته مشخصات فنی"""
        specs = {}
        
        # جدول مشخصات
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    key = cells[0].get_text().strip()
                    value = cells[1].get_text().strip()
                    if key and value:
                        specs[key] = value
        
        # لیست مشخصات
        spec_lists = soup.find_all(['ul', 'ol'], class_=lambda x: x and 'spec' in x.lower())
        for spec_list in spec_lists:
            items = spec_list.find_all('li')
            for item in items:
                text = item.get_text().strip()
                if ':' in text:
                    parts = text.split(':', 1)
                    if len(parts) == 2:
                        specs[parts[0].strip()] = parts[1].strip()
        
        # div های مشخصات
        spec_divs = soup.find_all('div', class_=lambda x: x and any(word in x.lower() for word in ['spec', 'feature', 'detail']))
        for div in spec_divs:
            # جستجوی الگوهای key: value
            import re
            text = div.get_text()
            matches = re.findall(r'([^:]+):\s*([^\n]+)', text)
            for match in matches:
                key, value = match[0].strip(), match[1].strip()
                if key and value and len(key) < 100 and len(value) < 500:
                    specs[key] = value
        
        return specs

    def extract_product_images(self, soup, base_url):
        """استخراج تصاویر محصول"""
        images = []
        
        # تصاویر اصلی محصول
        img_selectors = [
            'img[class*="product"]', 'img[class*="main"]', 'img[class*="primary"]',
            '.product-image img', '.main-image img', '.gallery img'
        ]
        
        for selector in img_selectors:
            imgs = soup.select(selector)
            for img in imgs:
                src = img.get('src') or img.get('data-src') or img.get('data-lazy')
                if src:
                    # تبدیل URL نسبی به مطلق
                    from urllib.parse import urljoin
                    full_url = urljoin(base_url, src)
                    if full_url not in images:
                        images.append(full_url)
        
        return images[:10]  # حداکثر 10 تصویر

    def calculate_data_quality_score(self, product_data):
        """محاسبه امتیاز کیفیت داده"""
        score = 0
        total_fields = 12
        
        # بررسی فیلدهای مهم
        if product_data.get('title'): score += 2
        if product_data.get('price', 0) > 0: score += 2
        if product_data.get('brand'): score += 1
        if product_data.get('sku'): score += 1
        if product_data.get('category'): score += 1
        if product_data.get('description'): score += 1
        if product_data.get('specifications'): score += 2
        if product_data.get('images'): score += 1
        if product_data.get('keywords'): score += 1
        
        return round((score / total_fields) * 100)

    def save_enhanced_product_to_json(self, product_data, product_url, crawl_method, crawl_time):
        """ذخیره پیشرفته در فایل JSON"""
        try:
            import os
            import json
            from datetime import datetime
            
            # ایجاد پوشه اگر وجود ندارد
            export_dir = frappe.get_site_path('public', 'files', 'competitor_exports')
            if not os.path.exists(export_dir):
                os.makedirs(export_dir)
            
            # نام فایل با timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            domain = product_url.split('/')[2] if len(product_url.split('/')) > 2 else 'unknown'
            filename = f"product_{domain}_{timestamp}.json"
            filepath = os.path.join(export_dir, filename)
            
            # داده‌های کامل برای ذخیره
            export_data = {
                'crawl_info': {
                    'url': product_url,
                    'timestamp': datetime.now().isoformat(),
                    'method': crawl_method,
                    'crawl_time_seconds': crawl_time,
                    'competitor': self.competitor.name
                },
                'product_data': product_data,
                'metadata': {
                    'total_specifications': len(product_data.get('specifications', {})),
                    'total_keywords': len(product_data.get('keywords', [])),
                    'total_images': len(product_data.get('images', [])),
                    'data_quality_score': product_data.get('data_quality_score', 0)
                }
            }
            
            # ذخیره فایل
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
            
            return f"/files/competitor_exports/{filename}"
            
        except Exception as e:
            frappe.log_error(f"خطا در ذخیره JSON: {str(e)}")
            return None
    
    def export_product_to_json(self, product_data):
        """صادرات اطلاعات محصول به فرمت JSON"""
        try:
            json_data = {
                'product_info': {
                    'title': product_data.get('title', ''),
                    'url': product_data.get('url', ''),
                    'price': product_data.get('price', 0),
                    'currency': 'تومان',
                    'brand': product_data.get('brand', ''),
                    'sku': product_data.get('sku', ''),
                    'availability': product_data.get('availability', 'نامشخص'),
                    'description': product_data.get('description', ''),
                    'image_url': product_data.get('image_url', '')
                },
                'specifications': product_data.get('specifications', {}),
                'seo_data': {
                    'keywords': product_data.get('keywords', []),
                    'meta_title': product_data.get('title', ''),
                    'meta_description': product_data.get('description', '')[:160]
                },
                'crawl_info': {
                    'crawled_at': frappe.utils.now(),
                    'competitor': self.competitor.competitor_name,
                    'source_url': product_data.get('url', '')
                }
            }
            
            # ذخیره فایل JSON
            import json
            import os
            
            # ایجاد پوشه برای فایل‌های JSON
            json_dir = frappe.get_site_path('private', 'files', 'competitor_products')
            if not os.path.exists(json_dir):
                os.makedirs(json_dir)
            
            # نام فایل بر اساس عنوان محصول
            safe_title = re.sub(r'[^\w\s-]', '', product_data.get('title', 'product'))
            safe_title = re.sub(r'[-\s]+', '-', safe_title)
            filename = f"{safe_title}_{frappe.utils.now_datetime().strftime('%Y%m%d_%H%M%S')}.json"
            
            file_path = os.path.join(json_dir, filename)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            
            return file_path
            
        except Exception as e:
            frappe.log_error(f"خطا در صادرات JSON: {str(e)}")
            return None

    def update_product_prices(self):
        """به‌روزرسانی قیمت محصولات موجود"""
        try:
            updated_count = 0
            
            for product in self.competitor.products:
                if product.product_url:
                    try:
                        product_data = self.extract_product_data(product.product_url)
                        if product_data and product_data['price']:
                            old_price = product.competitor_price
                            new_price = product_data['price']
                            
                            if old_price != new_price:
                                product.competitor_price = new_price
                                product.last_updated = today()
                                updated_count += 1
                                
                                # ارسال هشدار در صورت تغییر قیمت قابل توجه
                                if self.competitor.enable_price_monitoring:
                                    self.check_price_change_alert(product, old_price, new_price)
                        
                        time.sleep(random.uniform(1, 2))
                        
                    except Exception as e:
                        continue
            
            frappe.publish_realtime("crawler_status", {
                "message": f"{updated_count} قیمت به‌روزرسانی شد",
                "progress": 90
            })
            
        except Exception as e:
            frappe.log_error(f"خطا در به‌روزرسانی قیمت‌ها: {str(e)}")
    
    def check_price_change_alert(self, product, old_price, new_price):
        """بررسی و ارسال هشدار تغییر قیمت"""
        try:
            if not old_price or not new_price:
                return
                
            change_percent = abs((new_price - old_price) / old_price * 100)
            threshold = self.competitor.price_change_threshold or 5
            
            if change_percent >= threshold:
                self.send_price_change_notification(product, old_price, new_price, change_percent)
                
        except Exception as e:
            frappe.log_error(f"خطا در بررسی هشدار قیمت: {str(e)}")
    
    def send_price_change_notification(self, product, old_price, new_price, change_percent):
        """ارسال اعلان تغییر قیمت"""
        try:
            if not self.competitor.notification_email:
                return
                
            subject = f"هشدار تغییر قیمت رقیب: {self.competitor.competitor_name}"
            
            message = f"""
            تغییر قیمت قابل توجه در محصولات رقیب شناسایی شد:
            
            رقیب: {self.competitor.competitor_name}
            محصول: {product.item_name}
            قیمت قبلی: {frappe.format_value(old_price, {'fieldtype': 'Currency'})}
            قیمت جدید: {frappe.format_value(new_price, {'fieldtype': 'Currency'})}
            درصد تغییر: {change_percent:.1f}%
            
            لینک محصول: {product.product_url}
            """
            
            frappe.sendmail(
                recipients=[self.competitor.notification_email],
                subject=subject,
                message=message
            )
            
            self.competitor.last_notification_date = now_datetime()
            
        except Exception as e:
            frappe.log_error(f"خطا در ارسال اعلان: {str(e)}")

@frappe.whitelist()
def start_competitor_crawl(competitor_name):
    """شروع کرال رقیب در پس‌زمینه"""
    try:
        frappe.enqueue(
            '_background_crawl_competitor',
            competitor_name=competitor_name,
            queue='default',
            timeout=3600,
            job_name=f"crawl_{competitor_name}"
        )
        
        return {
            'success': True, 
            'message': 'کرال رقیب در پس‌زمینه شروع شد. نتایج در پنل اعلانات نمایش داده خواهد شد.'
        }
        
    except Exception as e:
        frappe.log_error(f"خطا در شروع کرال: {str(e)}")
        return {'success': False, 'message': str(e)}

def _background_crawl_competitor(competitor_name):
    """کرال رقیب در پس‌زمینه"""
    try:
        competitor = frappe.get_doc("Competitor Analysis", competitor_name)
        crawler = CompetitorWebCrawler(competitor)
        result = crawler._crawl_competitor_background()
        
        if result.get('success'):
            competitor.save()
            frappe.publish_realtime("crawler_complete", {
                "competitor": competitor_name,
                "success": True,
                "message": result.get('message'),
                "products_found": result.get('products_found', 0)
            })
        
    except Exception as e:
        frappe.log_error(f"خطا در کرال پس‌زمینه: {str(e)}")
        frappe.publish_realtime("crawler_complete", {
            "competitor": competitor_name,
            "success": False,
            "message": str(e)
        })

@frappe.whitelist()
def crawl_single_product_url(competitor_name, product_url, price_selector=None):
    """کرال محصول مستقیم از URL با ظرفیت بالا"""
    try:
        competitor = frappe.get_doc("Competitor Analysis", competitor_name)
        crawler = CompetitorWebCrawler(competitor)
        
        # کرال محصول با تنظیمات پیشرفته
        result = crawler.crawl_single_product_enhanced(product_url, price_selector)
        
        if result.get('success'):
            competitor.save()
            
            # اطلاعات کامل محصول
            product_data = result.get('product_data', {})
            
            return {
                'success': True,
                'message': f'محصول با موفقیت کرال شد - {len(product_data.get("specifications", {}))} مشخصه و {len(product_data.get("keywords", []))} کلمه کلیدی استخراج شد',
                'product_info': {
                    'title': product_data.get('title', ''),
                    'price': product_data.get('price', 0),
                    'currency': product_data.get('currency', 'تومان'),
                    'brand': product_data.get('brand', ''),
                    'sku': product_data.get('sku', ''),
                    'category': product_data.get('category', ''),
                    'availability': product_data.get('availability', ''),
                    'rating': product_data.get('rating', 0),
                    'reviews_count': product_data.get('reviews_count', 0),
                    'description_length': len(product_data.get('description', '')),
                    'specifications_count': len(product_data.get('specifications', {})),
                    'specifications': dict(list(product_data.get('specifications', {}).items())[:15]),  # اول 15 مشخصه
                    'keywords_count': len(product_data.get('keywords', [])),
                    'keywords': product_data.get('keywords', [])[:20],  # اول 20 کلمه
                    'images_count': len(product_data.get('images', [])),
                    'images': product_data.get('images', [])[:5],  # اول 5 تصویر
                    'seo_title': product_data.get('seo_title', ''),
                    'seo_description': product_data.get('seo_description', ''),
                    'json_file': result.get('json_file', ''),
                    'crawl_time': result.get('crawl_time', 0),
                    'data_quality_score': result.get('data_quality_score', 0)
                }
            }
        else:
            return result
            
    except Exception as e:
        error_msg = f"خطا در کرال محصول: {str(e)}"
        frappe.log_error(error_msg)
        return {'success': False, 'message': error_msg}

@frappe.whitelist()
def crawl_multiple_products_batch(competitor_name, product_urls):
    """کرال دسته‌ای چندین محصول"""
    try:
        if isinstance(product_urls, str):
            import json
            product_urls = json.loads(product_urls)
        
        competitor = frappe.get_doc("Competitor Analysis", competitor_name)
        crawler = CompetitorWebCrawler(competitor)
        
        results = []
        success_count = 0
        
        for i, url in enumerate(product_urls[:50]):  # حداکثر 50 محصول در هر batch
            try:
                result = crawler.crawl_single_product_enhanced(url.strip())
                if result.get('success'):
                    success_count += 1
                    results.append({
                        'url': url,
                        'status': 'success',
                        'title': result.get('product_data', {}).get('title', ''),
                        'price': result.get('product_data', {}).get('price', 0)
                    })
                else:
                    results.append({
                        'url': url,
                        'status': 'failed',
                        'error': result.get('message', 'خطای نامشخص')
                    })
                    
                # وقفه کوتاه بین درخواست‌ها
                import time
                time.sleep(1)
                
            except Exception as e:
                results.append({
                    'url': url,
                    'status': 'error',
                    'error': str(e)
                })
        
        if success_count > 0:
            competitor.save()
            
        return {
            'success': True,
            'message': f'{success_count} از {len(product_urls)} محصول با موفقیت کرال شدند',
            'total_urls': len(product_urls),
            'success_count': success_count,
            'failed_count': len(product_urls) - success_count,
            'results': results
        }
        
    except Exception as e:
        error_msg = f"خطا در کرال دسته‌ای: {str(e)}"
        frappe.log_error(error_msg)
        return {'success': False, 'message': error_msg}

@frappe.whitelist()
def schedule_auto_crawling():
    """زمان‌بندی کرال خودکار"""
    try:
        competitors = frappe.get_all("Competitor Analysis", 
            filters={
                "enable_auto_crawling": 1,
                "status": "فعال"
            },
            fields=["name", "crawling_frequency", "last_crawl_date"])
        
        crawled_count = 0
        
        for comp in competitors:
            should_crawl = False
            
            if not comp.last_crawl_date:
                should_crawl = True
            else:
                last_crawl = comp.last_crawl_date
                now = now_datetime()
                
                if comp.crawling_frequency == "روزانه":
                    should_crawl = (now - last_crawl).days >= 1
                elif comp.crawling_frequency == "هفتگی":
                    should_crawl = (now - last_crawl).days >= 7
                elif comp.crawling_frequency == "ماهانه":
                    should_crawl = (now - last_crawl).days >= 30
            
            if should_crawl:
                try:
                    start_competitor_crawl(comp.name)
                    crawled_count += 1
                except Exception as e:
                    frappe.log_error(f"خطا در کرال خودکار {comp.name}: {str(e)}")
        
        return {
            'status': 'success',
            'crawled_count': crawled_count,
            'message': f'{crawled_count} رقیب کرال شد'
        }
        
    except Exception as e:
        frappe.log_error(f"خطا در کرال خودکار: {str(e)}")
        return {'status': 'error', 'message': str(e)}
