# -*- coding: utf-8 -*-

import frappe
import redis
import json
import asyncio
from celery import Celery
from datetime import datetime, timedelta
import uuid
from loguru import logger

# Celery configuration
celery_app = Celery('competitor_analysis')
celery_app.conf.update(
    broker_url='redis://localhost:6379/0',
    result_backend='redis://localhost:6379/0',
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Tehran',
    enable_utc=True,
)

class CrawlQueueManager:
    """مدیریت صف کرال‌های همزمان"""
    
    def __init__(self):
        self.redis_client = redis.Redis(host='localhost', port=6379, db=1)
        self.queue_key = 'competitor_crawl_queue'
        self.processing_key = 'competitor_crawl_processing'
        self.results_key = 'competitor_crawl_results'
        
    def add_to_queue(self, competitor_name, urls, priority='normal', crawl_type='smart'):
        """اضافه کردن کرال به صف"""
        try:
            task_id = str(uuid.uuid4())
            task_data = {
                'task_id': task_id,
                'competitor_name': competitor_name,
                'urls': urls if isinstance(urls, list) else [urls],
                'priority': priority,
                'crawl_type': crawl_type,
                'created_at': datetime.now().isoformat(),
                'status': 'queued'
            }
            
            # Add to queue based on priority
            if priority == 'high':
                self.redis_client.lpush(self.queue_key, json.dumps(task_data))
            else:
                self.redis_client.rpush(self.queue_key, json.dumps(task_data))
            
            logger.info(f"کرال {task_id} به صف اضافه شد")
            return task_id
            
        except Exception as e:
            logger.error(f"خطا در اضافه کردن به صف: {str(e)}")
            return None
    
    def get_next_task(self):
        """دریافت کار بعدی از صف"""
        try:
            task_json = self.redis_client.lpop(self.queue_key)
            if task_json:
                task_data = json.loads(task_json)
                # Move to processing
                self.redis_client.hset(
                    self.processing_key, 
                    task_data['task_id'], 
                    json.dumps(task_data)
                )
                return task_data
            return None
        except Exception as e:
            logger.error(f"خطا در دریافت کار: {str(e)}")
            return None
    
    def complete_task(self, task_id, result):
        """تکمیل کار و ذخیره نتیجه"""
        try:
            # Remove from processing
            self.redis_client.hdel(self.processing_key, task_id)
            
            # Store result
            result_data = {
                'task_id': task_id,
                'result': result,
                'completed_at': datetime.now().isoformat()
            }
            self.redis_client.hset(
                self.results_key, 
                task_id, 
                json.dumps(result_data)
            )
            
            # Set expiry for result (7 days)
            self.redis_client.expire(f"{self.results_key}:{task_id}", 604800)
            
            logger.info(f"کار {task_id} تکمیل شد")
            
        except Exception as e:
            logger.error(f"خطا در تکمیل کار: {str(e)}")
    
    def get_task_status(self, task_id):
        """دریافت وضعیت کار"""
        try:
            # Check if in processing
            processing_data = self.redis_client.hget(self.processing_key, task_id)
            if processing_data:
                return {'status': 'processing', 'data': json.loads(processing_data)}
            
            # Check if completed
            result_data = self.redis_client.hget(self.results_key, task_id)
            if result_data:
                return {'status': 'completed', 'data': json.loads(result_data)}
            
            # Check if in queue
            queue_items = self.redis_client.lrange(self.queue_key, 0, -1)
            for item in queue_items:
                task_data = json.loads(item)
                if task_data['task_id'] == task_id:
                    return {'status': 'queued', 'data': task_data}
            
            return {'status': 'not_found'}
            
        except Exception as e:
            logger.error(f"خطا در دریافت وضعیت: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def get_queue_stats(self):
        """آمار صف"""
        try:
            queue_length = self.redis_client.llen(self.queue_key)
            processing_count = self.redis_client.hlen(self.processing_key)
            
            return {
                'queue_length': queue_length,
                'processing_count': processing_count,
                'total_active': queue_length + processing_count
            }
        except Exception as e:
            logger.error(f"خطا در دریافت آمار: {str(e)}")
            return {}

# Celery tasks
@celery_app.task(bind=True)
def process_crawl_task(self, task_data):
    """پردازش کار کرال در Celery"""
    try:
        from .advanced_crawler import AdvancedCompetitorCrawler
        
        competitor = frappe.get_doc("Competitor Analysis", task_data['competitor_name'])
        crawler = AdvancedCompetitorCrawler(competitor)
        
        if task_data['crawl_type'] == 'smart':
            result = asyncio.run(crawler.smart_crawl_product(task_data['urls'][0]))
        elif task_data['crawl_type'] == 'batch':
            result = asyncio.run(crawler.batch_crawl_products(task_data['urls']))
        
        # Update task progress
        self.update_state(
            state='SUCCESS',
            meta={'result': result, 'completed_at': datetime.now().isoformat()}
        )
        
        return result
        
    except Exception as e:
        self.update_state(
            state='FAILURE',
            meta={'error': str(e), 'failed_at': datetime.now().isoformat()}
        )
        raise

@celery_app.task
def cleanup_old_results():
    """پاک‌سازی نتایج قدیمی"""
    try:
        redis_client = redis.Redis(host='localhost', port=6379, db=1)
        
        # Clean results older than 7 days
        cutoff_date = datetime.now() - timedelta(days=7)
        
        all_results = redis_client.hgetall('competitor_crawl_results')
        for task_id, result_json in all_results.items():
            result_data = json.loads(result_json)
            completed_at = datetime.fromisoformat(result_data['completed_at'])
            
            if completed_at < cutoff_date:
                redis_client.hdel('competitor_crawl_results', task_id)
                logger.info(f"نتیجه قدیمی {task_id} پاک شد")
        
    except Exception as e:
        logger.error(f"خطا در پاک‌سازی: {str(e)}")

# Frappe API functions
@frappe.whitelist()
def queue_crawl_task(competitor_name, urls, priority='normal', crawl_type='smart'):
    """اضافه کردن کرال به صف"""
    try:
        queue_manager = CrawlQueueManager()
        task_id = queue_manager.add_to_queue(competitor_name, urls, priority, crawl_type)
        
        if task_id:
            # Start Celery task
            process_crawl_task.delay({
                'task_id': task_id,
                'competitor_name': competitor_name,
                'urls': urls if isinstance(urls, list) else [urls],
                'crawl_type': crawl_type
            })
            
            return {
                'success': True,
                'task_id': task_id,
                'message': 'کرال به صف اضافه شد'
            }
        else:
            return {
                'success': False,
                'message': 'خطا در اضافه کردن به صف'
            }
            
    except Exception as e:
        return {
            'success': False,
            'message': str(e)
        }

@frappe.whitelist()
def get_crawl_status(task_id):
    """دریافت وضعیت کرال"""
    try:
        queue_manager = CrawlQueueManager()
        status = queue_manager.get_task_status(task_id)
        
        return {
            'success': True,
            'status': status
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': str(e)
        }

@frappe.whitelist()
def get_queue_dashboard():
    """داشبورد صف کرال"""
    try:
        queue_manager = CrawlQueueManager()
        stats = queue_manager.get_queue_stats()
        
        return {
            'success': True,
            'stats': stats
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': str(e)
        }
