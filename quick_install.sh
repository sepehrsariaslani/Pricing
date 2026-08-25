#!/bin/bash
# 🚀 نصب سریع کتابخانه‌های ضروری - macOS

echo "🚀 نصب سریع کتابخانه‌های ضروری..."

# رفتن به پوشه اپ
cd /Users/sepehr/frappe-bench/apps/pricing

# نصب کتابخانه‌های اصلی
echo "📦 نصب کتابخانه‌های Python..."
pip install --upgrade pip

# کتابخانه‌های ضروری
pip install \
    selenium==4.15.0 \
    undetected-chromedriver==3.5.4 \
    requests==2.31.0 \
    beautifulsoup4==4.12.2 \
    lxml==4.9.3 \
    fake-useragent==1.4.0 \
    celery==5.3.4 \
    redis==5.0.1 \
    diskcache==5.6.3 \
    loguru==0.7.2

# AI و NLP
pip install \
    transformers==4.35.0 \
    torch==2.1.0 \
    sentence-transformers==2.2.2 \
    spacy==3.7.2 \
    nltk==3.8.1 \
    textblob==0.17.1

# Computer Vision و OCR  
pip install \
    opencv-python==4.8.1.78 \
    easyocr==1.7.0 \
    pytesseract==0.3.10 \
    pillow==10.1.0

# Web و API
pip install \
    playwright==1.40.0 \
    requests-html==0.10.0 \
    httpx==0.25.2 \
    aiohttp==3.9.1

echo "✅ کتابخانه‌های اصلی نصب شدند"

# نصب مرورگرهای Playwright
echo "🌐 نصب مرورگرهای Playwright..."
playwright install chromium

# دانلود مدل spaCy
echo "🧠 دانلود مدل spaCy..."
python -m spacy download en_core_web_sm

# دانلود داده‌های NLTK
echo "📚 دانلود داده‌های NLTK..."
python -c "
import nltk
nltk.download('punkt')
nltk.download('stopwords')
nltk.download('vader_lexicon')
print('✅ NLTK داده‌ها دانلود شدند')
"

# تست سریع
echo "🧪 تست سریع..."
python -c "
import selenium
import requests
import bs4
import transformers
import spacy
import cv2
import easyocr
print('✅ تمام کتابخانه‌های اصلی آماده هستند')
"

echo "🎉 نصب سریع تکمیل شد!"
echo "برای نصب کامل اجرا کنید: ./install_macos.sh"
