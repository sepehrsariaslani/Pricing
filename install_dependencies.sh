#!/bin/bash

# Advanced Competitor Analysis System - Installation Script
# این اسکریپت تمام وابستگی‌های مورد نیاز را نصب می‌کند

echo "🚀 شروع نصب وابستگی‌های سیستم تحلیل رقبا پیشرفته..."

# Update system packages
echo "📦 به‌روزرسانی پکیج‌های سیستم..."
sudo apt-get update

# Install system dependencies
echo "🔧 نصب وابستگی‌های سیستم..."
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
    build-essential

# Install Python dependencies
echo "🐍 نصب کتابخانه‌های Python..."
pip install -r requirements.txt

# Install Playwright browsers
echo "🎭 نصب مرورگرهای Playwright..."
playwright install

# Install spaCy language models
echo "🧠 نصب مدل‌های زبانی spaCy..."
python -m spacy download en_core_web_sm
python -m spacy download en_core_web_lg

# Download NLTK data
echo "📚 دانلود داده‌های NLTK..."
python -c "
import nltk
nltk.download('punkt')
nltk.download('stopwords')
nltk.download('vader_lexicon')
nltk.download('wordnet')
"

# Setup Redis
echo "🔴 راه‌اندازی Redis..."
sudo systemctl enable redis-server
sudo systemctl start redis-server

# Install Ollama (for local AI models)
echo "🤖 نصب Ollama برای مدل‌های AI محلی..."
curl -fsSL https://ollama.ai/install.sh | sh

# Pull useful models
echo "📥 دانلود مدل‌های AI..."
ollama pull llama2:7b
ollama pull codellama:7b
ollama pull mistral:7b

# Create necessary directories
echo "📁 ایجاد پوشه‌های مورد نیاز..."
mkdir -p /tmp/competitor_cache
mkdir -p /tmp/crawl_queue
mkdir -p logs/competitor_analysis

# Set permissions
chmod -R 755 /tmp/competitor_cache
chmod -R 755 /tmp/crawl_queue
chmod -R 755 logs/

echo "✅ نصب با موفقیت کامل شد!"
echo "🔄 لطفاً سرور را ری‌استارت کنید: bench restart"
