# -*- coding: utf-8 -*-

import frappe
import json
import requests
import asyncio
from datetime import datetime
import numpy as np
import pandas as pd
from transformers import pipeline, AutoTokenizer, AutoModel
import torch
from sentence_transformers import SentenceTransformer
import spacy
from textblob import TextBlob
import ollama
from loguru import logger
import cv2
from PIL import Image
import io
import base64

class AICompetitorAnalyzer:
    """تحلیلگر هوشمند رقبا با استفاده از AI محلی"""
    
    def __init__(self):
        self.setup_models()
        
    def setup_models(self):
        """راه‌اندازی مدل‌های AI"""
        try:
            # Local sentence transformer for embeddings
            self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
            
            # NLP pipelines
            self.sentiment_pipeline = pipeline("sentiment-analysis", 
                                              model="cardiffnlp/twitter-roberta-base-sentiment-latest")
            
            # Load spaCy model
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except OSError:
                logger.warning("spaCy model not found, using basic processing")
                self.nlp = None
            
            logger.info("مدل‌های AI محلی با موفقیت بارگذاری شدند")
            
        except Exception as e:
            logger.error(f"خطا در بارگذاری مدل‌های AI: {str(e)}")
            self.sentence_model = None
            self.sentiment_pipeline = None
            self.nlp = None
    
    def analyze_product_text(self, text):
        """تحلیل متن محصول با NLP"""
        try:
            analysis = {
                'sentiment': None,
                'keywords': [],
                'entities': [],
                'summary': '',
                'features': []
            }
            
            if not text:
                return analysis
            
            # Sentiment analysis
            if self.sentiment_pipeline:
                sentiment_result = self.sentiment_pipeline(text[:512])
                analysis['sentiment'] = sentiment_result[0]
            
            # Keyword extraction with spaCy
            if self.nlp:
                doc = self.nlp(text)
                
                # Extract entities
                analysis['entities'] = [
                    {'text': ent.text, 'label': ent.label_} 
                    for ent in doc.ents
                ]
                
                # Extract keywords (nouns and adjectives)
                keywords = [
                    token.lemma_.lower() 
                    for token in doc 
                    if token.pos_ in ['NOUN', 'ADJ'] and len(token.text) > 2
                ]
                analysis['keywords'] = list(set(keywords))[:20]
            
            # Feature extraction using simple patterns
            features = self.extract_features_from_text(text)
            analysis['features'] = features
            
            # Generate summary using Ollama
            summary = self.generate_summary_with_ollama(text)
            analysis['summary'] = summary
            
            return analysis
            
        except Exception as e:
            logger.error(f"خطا در تحلیل متن: {str(e)}")
            return {}
    
    def extract_features_from_text(self, text):
        """استخراج ویژگی‌های محصول از متن"""
        features = []
        
        # Common feature patterns
        feature_patterns = [
            r'(\d+)\s*(GB|TB|MB)',  # Storage
            r'(\d+)\s*(inch|اینچ)',  # Size
            r'(\d+)\s*(MP|مگاپیکسل)',  # Camera
            r'(\d+)\s*(mAh|میلی‌آمپر)',  # Battery
            r'(\d+)\s*(Hz|هرتز)',  # Frequency
            r'(\d+)\s*(W|وات)',  # Power
        ]
        
        import re
        for pattern in feature_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    features.append(' '.join(match))
                else:
                    features.append(match)
        
        return features[:10]  # Limit to 10 features
    
    def generate_summary_with_ollama(self, text, max_length=200):
        """تولید خلاصه با Ollama"""
        try:
            prompt = f"""
            Summarize this product description in Persian, maximum {max_length} characters:
            
            {text[:1000]}
            
            Summary in Persian:
            """
            
            response = ollama.generate(
                model='llama2:7b',
                prompt=prompt,
                options={'temperature': 0.3, 'max_tokens': 100}
            )
            
            summary = response['response'].strip()
            return summary[:max_length] if summary else ''
            
        except Exception as e:
            logger.error(f"خطا در تولید خلاصه: {str(e)}")
            return ''
    
    def compare_products_with_ai(self, product1_data, product2_data):
        """مقایسه محصولات با AI"""
        try:
            comparison = {
                'similarity_score': 0,
                'price_difference': 0,
                'feature_comparison': {},
                'recommendation': ''
            }
            
            # Text similarity using sentence transformers
            if self.sentence_model:
                text1 = f"{product1_data.get('title', '')} {product1_data.get('description', '')}"
                text2 = f"{product2_data.get('title', '')} {product2_data.get('description', '')}"
                
                embeddings1 = self.sentence_model.encode([text1])
                embeddings2 = self.sentence_model.encode([text2])
                
                similarity = np.dot(embeddings1[0], embeddings2[0]) / (
                    np.linalg.norm(embeddings1[0]) * np.linalg.norm(embeddings2[0])
                )
                comparison['similarity_score'] = float(similarity)
            
            # Price comparison
            price1 = product1_data.get('price', 0)
            price2 = product2_data.get('price', 0)
            
            if price1 and price2:
                comparison['price_difference'] = ((price2 - price1) / price1) * 100
            
            # Feature comparison
            features1 = set(product1_data.get('features', []))
            features2 = set(product2_data.get('features', []))
            
            comparison['feature_comparison'] = {
                'common_features': list(features1.intersection(features2)),
                'unique_to_product1': list(features1 - features2),
                'unique_to_product2': list(features2 - features1)
            }
            
            # Generate recommendation
            recommendation = self.generate_comparison_recommendation(comparison)
            comparison['recommendation'] = recommendation
            
            return comparison
            
        except Exception as e:
            logger.error(f"خطا در مقایسه محصولات: {str(e)}")
            return {}
    
    def generate_comparison_recommendation(self, comparison):
        """تولید توصیه مقایسه"""
        try:
            similarity = comparison.get('similarity_score', 0)
            price_diff = comparison.get('price_difference', 0)
            
            if similarity > 0.8:
                if price_diff > 10:
                    return "محصول اول گران‌تر است اما شباهت زیادی دارند"
                elif price_diff < -10:
                    return "محصول دوم گران‌تر است اما شباهت زیادی دارند"
                else:
                    return "محصولات بسیار شبیه هم هستند"
            elif similarity > 0.6:
                return "محصولات تا حدودی شبیه هم هستند"
            else:
                return "محصولات متفاوتی هستند"
                
        except:
            return "تحلیل مقایسه ممکن نیست"
    
    def analyze_market_position(self, competitor_data, market_data):
        """تحلیل موقعیت بازار با AI"""
        try:
            analysis = {
                'market_share_estimate': 0,
                'competitive_advantage': [],
                'weaknesses': [],
                'opportunities': [],
                'threats': [],
                'strategic_recommendations': []
            }
            
            # Use Ollama for strategic analysis
            prompt = f"""
            Analyze this competitor data and provide strategic insights in Persian:
            
            Competitor: {competitor_data.get('name', 'Unknown')}
            Products: {len(competitor_data.get('products', []))}
            Average Price: {competitor_data.get('average_price', 0)}
            Website Traffic: {competitor_data.get('monthly_traffic', 0)}
            
            Provide analysis in JSON format with:
            - competitive_advantage: list of advantages
            - weaknesses: list of weaknesses  
            - opportunities: list of opportunities
            - threats: list of threats
            - strategic_recommendations: list of recommendations
            
            All in Persian language.
            """
            
            response = ollama.generate(
                model='llama2:7b',
                prompt=prompt,
                options={'temperature': 0.5}
            )
            
            # Parse AI response
            ai_analysis = self.parse_ai_json_response(response['response'])
            if ai_analysis:
                analysis.update(ai_analysis)
            
            return analysis
            
        except Exception as e:
            logger.error(f"خطا در تحلیل موقعیت بازار: {str(e)}")
            return {}
    
    def parse_ai_json_response(self, response):
        """پردازش پاسخ JSON از AI"""
        try:
            # Find JSON in response
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
            
            return None
        except:
            return None
    
    def analyze_pricing_strategy(self, competitor_products):
        """تحلیل استراتژی قیمت‌گذاری"""
        try:
            if not competitor_products:
                return {}
            
            prices = [p.get('price', 0) for p in competitor_products if p.get('price', 0) > 0]
            
            if not prices:
                return {}
            
            analysis = {
                'average_price': np.mean(prices),
                'median_price': np.median(prices),
                'price_range': {
                    'min': min(prices),
                    'max': max(prices)
                },
                'price_distribution': self.analyze_price_distribution(prices),
                'pricing_strategy': self.determine_pricing_strategy(prices)
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"خطا در تحلیل قیمت‌گذاری: {str(e)}")
            return {}
    
    def analyze_price_distribution(self, prices):
        """تحلیل توزیع قیمت‌ها"""
        try:
            prices_array = np.array(prices)
            
            # Calculate quartiles
            q1 = np.percentile(prices_array, 25)
            q2 = np.percentile(prices_array, 50)  # median
            q3 = np.percentile(prices_array, 75)
            
            return {
                'q1': float(q1),
                'q2': float(q2),
                'q3': float(q3),
                'iqr': float(q3 - q1),
                'std': float(np.std(prices_array))
            }
        except:
            return {}
    
    def determine_pricing_strategy(self, prices):
        """تعیین استراتژی قیمت‌گذاری"""
        try:
            prices_array = np.array(prices)
            cv = np.std(prices_array) / np.mean(prices_array)  # Coefficient of variation
            
            if cv < 0.2:
                return "قیمت‌گذاری یکنواخت"
            elif cv < 0.5:
                return "قیمت‌گذاری متوسط"
            else:
                return "قیمت‌گذاری متنوع"
        except:
            return "نامشخص"

# Frappe API functions
@frappe.whitelist()
def analyze_competitor_with_ai(competitor_name):
    """تحلیل رقیب با AI"""
    try:
        competitor = frappe.get_doc("Competitor Analysis", competitor_name)
        analyzer = AICompetitorAnalyzer()
        
        # Prepare competitor data
        competitor_data = {
            'name': competitor.competitor_name,
            'products': [
                {
                    'title': p.item_name,
                    'price': p.competitor_price,
                    'description': p.description,
                    'features': p.get('specifications', {})
                }
                for p in competitor.products
            ],
            'average_price': sum([p.competitor_price or 0 for p in competitor.products]) / len(competitor.products) if competitor.products else 0,
            'monthly_traffic': competitor.monthly_traffic or 0
        }
        
        # AI Analysis
        market_analysis = analyzer.analyze_market_position(competitor_data, {})
        pricing_analysis = analyzer.analyze_pricing_strategy(competitor_data['products'])
        
        # Analyze each product
        product_analyses = []
        for product in competitor_data['products']:
            if product.get('description'):
                analysis = analyzer.analyze_product_text(product['description'])
                product_analyses.append({
                    'product': product['title'],
                    'analysis': analysis
                })
        
        result = {
            'market_analysis': market_analysis,
            'pricing_analysis': pricing_analysis,
            'product_analyses': product_analyses,
            'summary': {
                'total_products': len(competitor_data['products']),
                'average_price': competitor_data['average_price'],
                'analysis_date': datetime.now().isoformat()
            }
        }
        
        return {
            'success': True,
            'analysis': result
        }
        
    except Exception as e:
        frappe.log_error(f"خطا در تحلیل AI: {str(e)}")
        return {
            'success': False,
            'message': str(e)
        }

@frappe.whitelist()
def compare_products_ai(product1_name, product2_name):
    """مقایسه محصولات با AI"""
    try:
        analyzer = AICompetitorAnalyzer()
        
        # Get product data (you'll need to implement this based on your data structure)
        product1_data = frappe.get_doc("Competitor Product", product1_name)
        product2_data = frappe.get_doc("Competitor Product", product2_name)
        
        # Convert to dict format
        p1_dict = {
            'title': product1_data.item_name,
            'price': product1_data.competitor_price,
            'description': product1_data.description,
            'features': product1_data.get('specifications', {})
        }
        
        p2_dict = {
            'title': product2_data.item_name,
            'price': product2_data.competitor_price,
            'description': product2_data.description,
            'features': product2_data.get('specifications', {})
        }
        
        comparison = analyzer.compare_products_with_ai(p1_dict, p2_dict)
        
        return {
            'success': True,
            'comparison': comparison
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': str(e)
        }
