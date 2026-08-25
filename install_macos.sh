#!/bin/bash
# 🍎 اسکریپت نصب کتابخانه‌های سیستم تحلیل رقبا برای macOS
# macOS Installation Script for Competitor Analysis System

set -e  # خروج در صورت خطا

echo "🚀 شروع نصب کتابخانه‌های سیستم تحلیل رقبا برای macOS..."

# رنگ‌ها برای نمایش بهتر
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# بررسی وجود Homebrew
print_status "بررسی وجود Homebrew..."
if ! command -v brew &> /dev/null; then
    print_warning "Homebrew یافت نشد. در حال نصب..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # اضافه کردن Homebrew به PATH
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
    eval "$(/opt/homebrew/bin/brew shellenv)"
else
    print_success "Homebrew موجود است"
fi

# به‌روزرسانی Homebrew
print_status "به‌روزرسانی Homebrew..."
brew update

# نصب وابستگی‌های سیستم
print_status "نصب وابستگی‌های سیستم..."
brew install \
    python@3.11 \
    redis \
    postgresql \
    tesseract \
    tesseract-lang \
    poppler \
    opencv \
    ffmpeg \
    git \
    curl \
    wget \
    node \
    npm

# نصب Chrome (اگر موجود نباشد)
print_status "بررسی وجود Google Chrome..."
if [ ! -d "/Applications/Google Chrome.app" ]; then
    print_warning "Google Chrome یافت نشد. در حال نصب..."
    brew install --cask google-chrome
else
    print_success "Google Chrome موجود است"
fi

# راه‌اندازی Redis
print_status "راه‌اندازی Redis..."
brew services start redis
print_success "Redis راه‌اندازی شد"

# رفتن به پوشه اپ
cd /Users/sepehr/frappe-bench/apps/pricing

# ایجاد محیط مجازی Python (اختیاری)
print_status "بررسی محیط مجازی Python..."
if [ ! -d "venv" ]; then
    print_status "ایجاد محیط مجازی..."
    python3 -m venv venv
    source venv/bin/activate
else
    print_status "فعال‌سازی محیط مجازی موجود..."
    source venv/bin/activate
fi

# به‌روزرسانی pip
print_status "به‌روزرسانی pip..."
pip install --upgrade pip setuptools wheel

# نصب کتابخانه‌های Python
print_status "نصب کتابخانه‌های Python از requirements.txt..."
pip install -r requirements.txt

# نصب کتابخانه‌های اضافی برای macOS
print_status "نصب کتابخانه‌های اضافی برای macOS..."
pip install \
    psycopg2-binary \
    pillow \
    lxml \
    cffi \
    cryptography

# نصب Playwright و مرورگرها
print_status "نصب Playwright و مرورگرها..."
playwright install
playwright install-deps

# تست Playwright
print_status "تست Playwright..."
python -c "
from playwright.sync_api import sync_playwright
print('✅ Playwright نصب شده و آماده استفاده است')
"

# نصب و راه‌اندازی Ollama
print_status "نصب Ollama..."
if ! command -v ollama &> /dev/null; then
    curl -fsSL https://ollama.ai/install.sh | sh
else
    print_success "Ollama قبلاً نصب شده"
fi

# راه‌اندازی Ollama در پس‌زمینه
print_status "راه‌اندازی Ollama..."
ollama serve &
sleep 5

# دانلود مدل‌های AI (این کار زمان‌بر است)
print_status "دانلود مدل‌های AI محلی..."
print_warning "این مرحله ممکن است چندین دقیقه طول بکشد..."

# دانلود مدل‌های کوچک‌تر برای شروع
ollama pull llama2:7b-chat &
ollama pull codellama:7b-instruct &
ollama pull mistral:7b-instruct &

# منتظر ماندن برای تکمیل دانلود
wait

print_success "مدل‌های AI دانلود شدند"

# نصب spaCy و مدل‌های آن
print_status "نصب مدل‌های spaCy..."
python -m spacy download en_core_web_sm
python -m spacy download en_core_web_lg

# دانلود داده‌های NLTK
print_status "دانلود داده‌های NLTK..."
python -c "
import nltk
import ssl
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

nltk.download('punkt')
nltk.download('stopwords')
nltk.download('vader_lexicon')
nltk.download('wordnet')
nltk.download('omw-1.4')
print('✅ داده‌های NLTK دانلود شدند')
"

# نصب Celery
print_status "نصب Celery..."
pip install celery[redis]

# ایجاد پوشه‌های مورد نیاز
print_status "ایجاد پوشه‌های مورد نیاز..."
mkdir -p logs/celery
mkdir -p logs/competitor_analysis
mkdir -p /tmp/competitor_cache
mkdir -p /tmp/crawl_queue
mkdir -p data/exports

# تنظیم مجوزها
chmod -R 755 logs/
chmod -R 755 /tmp/competitor_cache
chmod -R 755 /tmp/crawl_queue
chmod -R 755 data/

# تست Redis
print_status "تست اتصال Redis..."
redis-cli ping > /dev/null && print_success "Redis در حال اجرا است" || print_error "مشکل در اتصال به Redis"

# تست کتابخانه‌های Python
print_status "تست کتابخانه‌های Python..."
python -c "
try:
    import selenium
    import requests
    import bs4
    import transformers
    import spacy
    import cv2
    import easyocr
    import celery
    import redis
    import ollama
    print('✅ تمام کتابخانه‌های اصلی با موفقیت وارد شدند')
except ImportError as e:
    print(f'❌ خطا در وارد کردن کتابخانه: {e}')
    exit(1)
"

# تست OCR
print_status "تست OCR..."
python -c "
try:
    import easyocr
    reader = easyocr.Reader(['en', 'fa'])
    print('✅ OCR راه‌اندازی شد')
except Exception as e:
    print(f'⚠️  هشدار OCR: {e}')
"

# تست Ollama
print_status "تست Ollama..."
ollama list > /dev/null && print_success "Ollama در حال اجرا است" || print_warning "Ollama ممکن است نیاز به راه‌اندازی مجدد داشته باشد"

# ایجاد فایل راه‌اندازی سریع
print_status "ایجاد اسکریپت راه‌اندازی سریع..."
cat > start_services.sh << 'EOF'
#!/bin/bash
# اسکریپت راه‌اندازی سریع سرویس‌ها

echo "🚀 راه‌اندازی سرویس‌های سیستم تحلیل رقبا..."

# راه‌اندازی Redis
brew services start redis

# راه‌اندازی Ollama
ollama serve &

# فعال‌سازی محیط مجازی
source venv/bin/activate

echo "✅ سرویس‌ها آماده استفاده هستند"
echo ""
echo "برای شروع Celery Worker:"
echo "celery -A pricing.pricing.doctype.competitor_analysis.queue_manager worker --loglevel=info"
echo ""
echo "برای شروع Celery Beat:"
echo "celery -A pricing.pricing.doctype.competitor_analysis.queue_manager beat --loglevel=info"
echo ""
echo "برای مانیتورینگ Celery:"
echo "pip install flower && celery -A pricing.pricing.doctype.competitor_analysis.queue_manager flower"
EOF

chmod +x start_services.sh

# ایجاد فایل تست سیستم
print_status "ایجاد اسکریپت تست سیستم..."
cat > test_system.py << 'EOF'
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
تست کامل سیستم تحلیل رقبا
"""

import sys
import traceback

def test_imports():
    """تست وارد کردن کتابخانه‌ها"""
    print("🔍 تست وارد کردن کتابخانه‌ها...")
    
    try:
        import selenium
        print("✅ Selenium")
        
        import requests
        print("✅ Requests")
        
        import bs4
        print("✅ BeautifulSoup")
        
        import transformers
        print("✅ Transformers")
        
        import spacy
        print("✅ spaCy")
        
        import cv2
        print("✅ OpenCV")
        
        import easyocr
        print("✅ EasyOCR")
        
        import celery
        print("✅ Celery")
        
        import redis
        print("✅ Redis")
        
        import ollama
        print("✅ Ollama")
        
        return True
        
    except ImportError as e:
        print(f"❌ خطا در وارد کردن کتابخانه: {e}")
        return False

def test_services():
    """تست سرویس‌ها"""
    print("\n🔍 تست سرویس‌ها...")
    
    # تست Redis
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        print("✅ Redis")
    except Exception as e:
        print(f"❌ Redis: {e}")
        return False
    
    # تست Ollama
    try:
        import ollama
        models = ollama.list()
        print(f"✅ Ollama ({len(models.get('models', []))} مدل)")
    except Exception as e:
        print(f"⚠️  Ollama: {e}")
    
    return True

def test_crawler():
    """تست کرالر"""
    print("\n🔍 تست کرالر...")
    
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        driver = webdriver.Chrome(options=options)
        driver.get("https://httpbin.org/html")
        title = driver.title
        driver.quit()
        
        print(f"✅ کرالر Selenium (عنوان: {title[:30]}...)")
        return True
        
    except Exception as e:
        print(f"❌ کرالر: {e}")
        return False

def main():
    """تست اصلی"""
    print("🧪 تست کامل سیستم تحلیل رقبا")
    print("=" * 50)
    
    success = True
    
    success &= test_imports()
    success &= test_services()
    success &= test_crawler()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 تمام تست‌ها موفقیت‌آمیز بودند!")
        print("سیستم آماده استفاده است.")
    else:
        print("❌ برخی تست‌ها ناموفق بودند.")
        print("لطفاً خطاها را بررسی کنید.")
        sys.exit(1)

if __name__ == "__main__":
    main()
EOF

chmod +x test_system.py

print_success "نصب کامل شد! 🎉"
print_status "فایل‌های ایجاد شده:"
print_status "  - start_services.sh: راه‌اندازی سریع سرویس‌ها"
print_status "  - test_system.py: تست کامل سیستم"

print_status "برای تست سیستم اجرا کنید:"
print_status "  python test_system.py"

print_status "برای راه‌اندازی سرویس‌ها:"
print_status "  ./start_services.sh"

print_status "برای شروع ERPNext:"
print_status "  cd /Users/sepehr/frappe-bench"
print_status "  bench migrate"
print_status "  bench restart"

print_success "سیستم تحلیل رقبا آماده استفاده است! 🚀"
