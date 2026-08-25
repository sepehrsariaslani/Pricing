#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
راه‌اندازی Celery برای سیستم تحلیل رقبا
"""

import os
import sys
from celery import Celery

# Add frappe to path
sys.path.append('/Users/sepehr/frappe-bench')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'frappe.conf')

# Initialize Celery
app = Celery('competitor_analysis')

# Configuration
app.conf.update(
    broker_url='redis://localhost:6379/0',
    result_backend='redis://localhost:6379/0',
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Tehran',
    enable_utc=True,
    
    # Task routing
    task_routes={
        'competitor_analysis.crawl_task': {'queue': 'crawl'},
        'competitor_analysis.ai_task': {'queue': 'ai'},
        'competitor_analysis.report_task': {'queue': 'reports'},
    },
    
    # Worker configuration
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
    
    # Task time limits
    task_soft_time_limit=300,  # 5 minutes
    task_time_limit=600,       # 10 minutes
    
    # Retry configuration
    task_default_retry_delay=60,
    task_max_retries=3,
    
    # Beat schedule for periodic tasks
    beat_schedule={
        'cleanup-old-results': {
            'task': 'competitor_analysis.cleanup_old_results',
            'schedule': 3600.0,  # Every hour
        },
        'auto-crawl-competitors': {
            'task': 'competitor_analysis.auto_crawl_competitors',
            'schedule': 86400.0,  # Daily
        },
        'generate-daily-reports': {
            'task': 'competitor_analysis.generate_daily_reports',
            'schedule': 86400.0,  # Daily at midnight
        },
    },
)

# Auto-discover tasks
app.autodiscover_tasks([
    'pricing.pricing.doctype.competitor_analysis'
])

if __name__ == '__main__':
    app.start()
