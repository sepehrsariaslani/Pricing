# 🚀 دستورات نصب سیستم تحلیل رقبا پیشرفته

## 1. نصب وابستگی‌های سیستم

```bash
# به‌روزرسانی سیستم
sudo apt-get update && sudo apt-get upgrade -y

# نصب وابستگی‌های اصلی
sudo apt-get install -y \
    chromium-browser \
    chromium-chromedriver \
    tesseract-ocr \
    tesseract-ocr-fas \
    poppler-utils \
    redis-server \
    postgresql-client \
    libpq-dev \
    python3-dev \
    build-essential \
    curl \
    wget \
    git

# راه‌اندازی Redis
sudo systemctl enable redis-server
sudo systemctl start redis-server
sudo systemctl status redis-server
```

## 2. نصب کتابخانه‌های Python

```bash
# رفتن به پوشه اپ
cd /Users/sepehr/frappe-bench/apps/pricing

# نصب requirements
pip install -r requirements.txt

# نصب کتابخانه‌های اضافی برای macOS
pip install --upgrade pip setuptools wheel
```

## 3. نصب Playwright و مرورگرها

```bash
# نصب مرورگرهای Playwright
playwright install
playwright install-deps

# تست Playwright
python -c "from playwright.sync_api import sync_playwright; print('Playwright OK')"
```

## 4. نصب و راه‌اندازی Ollama (AI محلی)

```bash
# نصب Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# شروع سرویس Ollama
ollama serve &

# دانلود مدل‌های AI (این کار زمان‌بر است)
ollama pull llama2:7b
ollama pull codellama:7b
ollama pull mistral:7b

# تست Ollama
ollama list
```

## 5. راه‌اندازی spaCy و NLTK

```bash
# دانلود مدل‌های spaCy
python -m spacy download en_core_web_sm
python -m spacy download en_core_web_lg

# دانلود داده‌های NLTK
python -c "
import nltk
nltk.download('punkt')
nltk.download('stopwords')
nltk.download('vader_lexicon')
nltk.download('wordnet')
nltk.download('omw-1.4')
print('NLTK data downloaded successfully')
"
```

## 6. راه‌اندازی Celery

```bash
# نصب Celery
pip install celery[redis]

# ایجاد پوشه‌های مورد نیاز
mkdir -p logs/celery
mkdir -p /tmp/competitor_cache
mkdir -p /tmp/crawl_queue

# تنظیم مجوزها
chmod -R 755 logs/
chmod -R 755 /tmp/competitor_cache
chmod -R 755 /tmp/crawl_queue

# شروع Celery Worker (در ترمینال جداگانه)
celery -A pricing.pricing.doctype.competitor_analysis.queue_manager worker --loglevel=info

# شروع Celery Beat (در ترمینال جداگانه)
celery -A pricing.pricing.doctype.competitor_analysis.queue_manager beat --loglevel=info
```

## 7. تست سیستم

```bash
# تست Redis
redis-cli ping

# تست کتابخانه‌های Python
python -c "
import selenium
import requests
import beautifulsoup4
import transformers
import spacy
import cv2
import easyocr
print('All libraries imported successfully!')
"

# تست OCR
python -c "
import easyocr
reader = easyocr.Reader(['en', 'fa'])
print('OCR initialized successfully!')
"
```

## 8. راه‌اندازی ERPNext

```bash
# رفتن به پوشه bench
cd /Users/sepehr/frappe-bench

# نصب اپ
bench install-app pricing

# مایگریت دیتابیس
bench migrate

# ری‌استارت سیستم
bench restart

# پاک کردن کش
bench clear-cache
bench clear-website-cache
```

## 9. تنظیمات امنیتی و بهینه‌سازی

```bash
# تنظیم محدودیت‌های Redis
echo "maxmemory 1gb" | sudo tee -a /etc/redis/redis.conf
echo "maxmemory-policy allkeys-lru" | sudo tee -a /etc/redis/redis.conf

# ری‌استارت Redis
sudo systemctl restart redis-server

# تنظیم فایروال (اختیاری)
sudo ufw allow 6379  # Redis
sudo ufw allow 5555  # Celery Flower (monitoring)
```

## 10. مانیتورینگ و نظارت

```bash
# نصب Flower برای مانیتورینگ Celery
pip install flower

# شروع Flower (در ترمینال جداگانه)
celery -A pricing.pricing.doctype.competitor_analysis.queue_manager flower

# دسترسی به Flower: http://localhost:5555
```

## 11. اسکریپت‌های خودکار

```bash
# اجرای اسکریپت نصب خودکار
chmod +x install_dependencies.sh
./install_dependencies.sh

# راه‌اندازی Celery به صورت سرویس
sudo cp setup_celery.py /etc/systemd/system/celery-competitor.service
sudo systemctl enable celery-competitor
sudo systemctl start celery-competitor
```

## 12. تست نهایی سیستم

```bash
# تست کرال ساده
python -c "
import frappe
frappe.init(site='your-site-name')
frappe.connect()
from pricing.pricing.doctype.competitor_analysis.web_crawler import crawl_single_product_url
result = crawl_single_product_url('Test Competitor', 'https://example.com/product')
print('Crawl test result:', result)
"
```

## 🔧 عیب‌یابی مشکلات رایج

### مشکل 1: خطای Chrome Driver
```bash
# حل مشکل Chrome Driver
sudo apt-get install --reinstall chromium-chromedriver
which chromedriver
```

### مشکل 2: خطای Redis Connection
```bash
# بررسی وضعیت Redis
sudo systemctl status redis-server
redis-cli ping

# ری‌استارت Redis
sudo systemctl restart redis-server
```

### مشکل 3: خطای Ollama
```bash
# بررسی وضعیت Ollama
ps aux | grep ollama
ollama list

# ری‌استارت Ollama
pkill ollama
ollama serve &
```

### مشکل 4: خطای مجوزها
```bash
# تنظیم مجوزهای صحیح
sudo chown -R $USER:$USER /tmp/competitor_cache
sudo chown -R $USER:$USER logs/
chmod -R 755 /tmp/competitor_cache
chmod -R 755 logs/
```

## 📊 بررسی عملکرد

```bash
# مانیتورینگ منابع سیستم
htop
free -h
df -h

# بررسی لاگ‌ها
tail -f logs/competitor_analysis/crawler_*.log
tail -f logs/celery/worker.log
```

## 🎯 نکات مهم

1. **حافظه**: سیستم حداقل 4GB RAM نیاز دارد
2. **فضای ذخیره**: حداقل 10GB فضای خالی
3. **اینترنت**: اتصال پایدار برای دانلود مدل‌های AI
4. **امنیت**: استفاده از VPN برای کرال سایت‌های محدود
5. **بک‌آپ**: پشتیبان‌گیری منظم از دیتابیس و کش

## 🚀 آماده برای استفاده!

پس از تکمیل این مراحل، سیستم تحلیل رقبا پیشرفته شما آماده استفاده است و شامل:

✅ کرال هوشمند با Selenium و Anti-Detection  
✅ پردازش AI محلی با Ollama  
✅ سیستم صف پیشرفته با Celery  
✅ کش هوشمند و بهینه‌سازی عملکرد  
✅ تحلیل تصاویر و OCR  
✅ مانیتورینگ و گزارش‌گیری خودکار  
