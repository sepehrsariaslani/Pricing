# نصب Pricing App روی هاست

این راهنما برای نصب اپ Pricing روی هاست‌های مختلف (shared hosting, VPS, dedicated server) طراحی شده.

## 🚀 نصب سریع

### روش 1: نصب خودکار (توصیه شده)

```bash
# در پوشه pricing app
chmod +x host_install.sh
./host_install.sh
```

### روش 2: نصب دستی

```bash
# 1. نصب وابستگی‌های ضروری
python3 -m pip install --user numpy_financial requests aiohttp beautifulsoup4 lxml jinja2 loguru

# 2. نصب اپ
bench --site [site-name] install-app pricing

# 3. اجرای migration
bench --site [site-name] migrate

# 4. build کردن assets
bench build

# 5. restart
bench restart
```

## 📋 پیش‌نیازها

### سیستم‌عامل
- Ubuntu 18.04+ / CentOS 7+ / Debian 9+
- Python 3.8+
- ERPNext v13+

### دسترسی‌های مورد نیاز
- دسترسی SSH به سرور
- دسترسی pip برای نصب پکیج‌های Python
- دسترسی bench commands

### پکیج‌های سیستمی (اختیاری)
```bash
# برای Ubuntu/Debian
sudo apt-get install python3-dev build-essential libxml2-dev libxslt1-dev

# برای CentOS/RHEL
sudo yum install python3-devel gcc libxml2-devel libxslt-devel
```

## 🔧 حل مشکلات رایج

### خطای "No module named 'aiohttp'"

```bash
python3 -m pip install --user aiohttp
bench --site [site-name] install-app pricing
```

### خطای "Permission denied"

```bash
# استفاده از --user flag
python3 -m pip install --user [package-name]
```

### خطای "Failed building wheel"

```bash
# نصب پکیج‌های سیستمی مورد نیاز
sudo apt-get install python3-dev build-essential
# یا
sudo yum install python3-devel gcc
```

### خطای "bench command not found"

```bash
# اضافه کردن bench به PATH
export PATH=$PATH:~/.local/bin
# یا
source ~/.bashrc
```

## 📦 سطوح نصب

### سطح 1: حداقل (Essential)
فقط قابلیت‌های اصلی قیمت‌گذاری

```bash
pip install --user numpy_financial requests aiohttp beautifulsoup4 lxml jinja2 loguru
```

**قابلیت‌های فعال:**
- ✅ محاسبه قیمت بر اساس BOM
- ✅ قیمت‌گذاری دستی مواد
- ✅ محاسبه سود و کمیسیون
- ✅ مقایسه با price list موجود

### سطح 2: استاندارد (Standard)
شامل تحلیل داده و نمودارها

```bash
pip install --user -r requirements_host.txt
```

**قابلیت‌های اضافی:**
- ✅ نمودارها و داشبورد
- ✅ تحلیل داده‌ها
- ✅ گزارش‌گیری پیشرفته
- ⚠️ وب کراولینگ (نیاز به Chrome)

### سطح 3: کامل (Full)
تمام قابلیت‌ها شامل ML و AI

```bash
pip install --user -r requirements.txt
```

**قابلیت‌های اضافی:**
- ✅ هوش مصنوعی برای قیمت‌گذاری
- ✅ پیش‌بینی تقاضا
- ✅ تحلیل رقبا
- ✅ بهینه‌سازی قیمت

## 🏢 راهنمای هاست‌های مختلف

### Shared Hosting
```bash
# فقط سطح 1 (Essential) توصیه می‌شود
./host_install.sh
```

**محدودیت‌ها:**
- عدم دسترسی sudo
- محدودیت منابع
- عدم امکان نصب Chrome/Chromium

### VPS / Cloud Server
```bash
# نصب کامل امکان‌پذیر
python3 setup.py
./install.sh
```

### Dedicated Server
```bash
# تمام قابلیت‌ها قابل استفاده
python3 setup.py
./install.sh
```

## 🔍 تست نصب

بعد از نصب، این مراحل را انجام دهید:

1. **ورود به ERPNext**
2. **رفتن به Setup > Pricing**
3. **ایجاد Auto Price List جدید**
4. **تست محاسبه قیمت**

### تست Python Dependencies

```python
# در bench console
python3 -c "
import numpy_financial
import requests
import aiohttp
import bs4
import lxml
print('✅ Essential packages OK')

try:
    import pandas
    import numpy
    import plotly
    print('✅ Standard packages OK')
except ImportError as e:
    print(f'⚠️ Standard packages missing: {e}')

try:
    import sklearn
    import selenium
    print('✅ Advanced packages OK')
except ImportError as e:
    print(f'⚠️ Advanced packages missing: {e}')
"
```

## 📞 پشتیبانی

### مشکلات رایج و راه‌حل

| مشکل | راه‌حل |
|------|--------|
| خطای import | `pip install --user [package]` |
| خطای permission | استفاده از `--user` flag |
| خطای build | نصب `python3-dev build-essential` |
| خطای Chrome | نصب `chromium-browser` یا غیرفعال کردن web crawling |
| خطای Redis | نصب `redis-server` یا غیرفعال کردن Celery |

### اطلاعات مورد نیاز برای پشتیبانی

1. نوع هاست (shared/VPS/dedicated)
2. سیستم‌عامل و نسخه
3. نسخه Python
4. نسخه ERPNext
5. پیام خطای کامل
6. نتیجه `pip list | grep -E "(aiohttp|beautifulsoup4|lxml)"`

### تماس با پشتیبانی

- 📧 Email: support@yourcompany.com
- 💬 Telegram: @yoursupport
- 🌐 Website: https://yourwebsite.com

## 📚 مستندات بیشتر

- [راهنمای کاربری](USER_GUIDE.md)
- [مستندات API](API_DOCS.md)
- [نمونه‌های کاربردی](EXAMPLES.md)
- [FAQ](FAQ.md)

---

**نکته:** این اپ برای محیط‌های مختلف بهینه‌سازی شده و حتی در صورت عدم نصب برخی پکیج‌ها، قابلیت‌های اصلی کار خواهند کرد.
