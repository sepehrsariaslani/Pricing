import frappe
from frappe.model.document import Document
from frappe.utils import flt, cint, today, add_days, getdate, now_datetime
import json
from datetime import datetime, timedelta

# Temporary hard-off switch for crawler load/performance testing.
WEB_CRAWLER_ENABLED = False

# Try to import web crawler only when it is enabled.
if WEB_CRAWLER_ENABLED:
    try:
        from .web_crawler import CompetitorWebCrawler
        WEB_CRAWLER_AVAILABLE = True
    except ImportError as e:
        frappe.log_error(f"Web crawler dependencies not available: {e}", "Competitor Analysis Import")
        WEB_CRAWLER_AVAILABLE = False
        
        class CompetitorWebCrawler:
            def __init__(self, *args, **kwargs):
                pass
            
            def crawl_competitor_website(self, *args, **kwargs):
                return {"status": "error", "message": "Web crawler dependencies are not installed."}
            
            def update_product_prices(self, *args, **kwargs):
                return {"status": "error", "message": "Web crawler dependencies are not installed."}
else:
    WEB_CRAWLER_AVAILABLE = False

    class CompetitorWebCrawler:
        def __init__(self, *args, **kwargs):
            pass
        
        def crawl_competitor_website(self, *args, **kwargs):
            return {"status": "disabled", "message": "Web crawler is disabled."}
        
        def update_product_prices(self, *args, **kwargs):
            return {"status": "disabled", "message": "Web crawler is disabled."}

class CompetitorAnalysis(Document):
    def validate(self):
        """Validate competitor analysis data"""
        self.validate_dates()
        self.calculate_product_comparisons()
        self.set_title()
        
    def validate_dates(self):
        """Validate analysis and review dates"""
        if self.analysis_date and getdate(self.analysis_date) > getdate(today()):
            frappe.throw("Analysis date cannot be in the future")
            
        if self.next_review_date and self.analysis_date:
            if getdate(self.next_review_date) <= getdate(self.analysis_date):
                frappe.throw("Next review date must be after analysis date")
    
    def set_title(self):
        """Set document title"""
        if not self.title:
            self.title = f"{self.competitor_name} - {self.competitor_type}"
    
    def calculate_product_comparisons(self):
        """Calculate price differences for competitor products"""
        for product in self.products:
            if product.item_code and product.competitor_price:
                # Get our current price
                our_price = self.get_our_item_price(product.item_code)
                if product.competitor_price and product.our_price:
                    price_difference = flt(product.competitor_price) - flt(product.our_price)
                    price_difference_percent = (price_difference / product.our_price) * 100
                    
                    product.price_difference = price_difference
                    product.price_difference_percent = price_difference_percent
                    
                    # تعیین موقعیت بازار
                    if price_difference_percent > 20:
                        product.market_position = "گران‌تر"
                    elif price_difference_percent > 5:
                        product.market_position = "پریمیوم"
                    elif price_difference_percent < -20:
                        product.market_position = "ارزان‌تر"
                    else:
                        product.market_position = "مشابه"
                
                product.last_updated = today()
    
    def get_our_item_price(self, item_code):
        """Get our current selling price for an item"""
        try:
            # Try to get from Item Price first
            item_price = frappe.get_value("Item Price", 
                {"item_code": item_code, "selling": 1}, 
                "price_list_rate")
            
            if item_price:
                return item_price
            
            # Fallback to standard rate from Item
            standard_rate = frappe.get_value("Item", item_code, "standard_rate")
            return standard_rate or 0
            
        except Exception:
            return 0
    
    @frappe.whitelist()
    def generate_competitive_analysis_report(self):
        """Generate comprehensive competitive analysis report"""
        try:
            analysis_data = {
                'competitor_overview': self.get_competitor_overview(),
                'pricing_analysis': self.get_pricing_analysis(),
                'market_position_analysis': self.get_market_position_analysis(),
                'swot_analysis': self.get_swot_analysis(),
                'financial_analysis': self.get_financial_analysis(),
                'strategic_insights': self.get_strategic_insights(),
                'recommendations': self.get_recommendations()
            }
            
            return analysis_data
            
        except Exception as e:
            frappe.log_error(f"Competitive analysis report error: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def get_competitor_overview(self):
        """Get competitor overview data"""
        return {
            'name': self.competitor_name,
            'type': self.competitor_type,
            'market_segment': self.market_segment,
            'company_size': self.company_size,
            'annual_revenue': self.annual_revenue,
            'market_share': self.market_share,
            'geographic_presence': self.geographic_presence,
            'market_position': self.market_position
        }
    
    def get_pricing_analysis(self):
        """Analyze pricing strategies and patterns"""
        pricing_data = {
            'pricing_model': self.pricing_model,
            'average_discount': self.average_discount,
            'price_elasticity': self.price_elasticity,
            'seasonal_pricing': self.seasonal_pricing,
            'promotional_frequency': self.promotional_frequency,
            'bundling_strategy': self.bundling_strategy,
            'loyalty_programs': self.loyalty_programs
        }
        
        # Analyze product price comparisons
        if self.products:
            total_products = len(self.products)
            cheaper_count = len([p for p in self.products if p.market_position == "ارزان‌تر"])
            expensive_count = len([p for p in self.products if p.market_position == "گران‌تر"])
            similar_count = len([p for p in self.products if p.market_position == "مشابه"])
            
            pricing_data['product_comparison'] = {
                'total_products': total_products,
                'cheaper_products': cheaper_count,
                'expensive_products': expensive_count,
                'similar_products': similar_count,
                'cheaper_percentage': (cheaper_count / total_products * 100) if total_products > 0 else 0,
                'expensive_percentage': (expensive_count / total_products * 100) if total_products > 0 else 0
            }
            
            # Calculate average price difference
            price_differences = [flt(p.price_difference_percent) for p in self.products if p.price_difference_percent]
            if price_differences:
                pricing_data['average_price_difference'] = sum(price_differences) / len(price_differences)
        
        return pricing_data
    
    def get_market_position_analysis(self):
        """Analyze market position and competitive standing"""
        return {
            'market_position': self.market_position,
            'customer_satisfaction': self.customer_satisfaction,
            'brand_strength': self.brand_strength,
            'innovation_index': self.innovation_index,
            'digital_presence': self.digital_presence,
            'social_media_score': self.social_media_score,
            'online_reviews_rating': self.online_reviews_rating,
            'website_traffic_rank': self.website_traffic_rank
        }
    
    def get_swot_analysis(self):
        """Get SWOT analysis data"""
        return {
            'strengths': self.strengths,
            'weaknesses': self.weaknesses,
            'opportunities': self.opportunities,
            'threats': self.threats
        }
    
    def get_financial_analysis(self):
        """Analyze financial performance"""
        return {
            'revenue_growth': self.revenue_growth,
            'profit_margin': self.profit_margin,
            'debt_to_equity': self.debt_to_equity,
            'current_ratio': self.current_ratio,
            'inventory_turnover': self.inventory_turnover,
            'return_on_assets': self.return_on_assets,
            'return_on_equity': self.return_on_equity,
            'cash_flow_ratio': self.cash_flow_ratio
        }
    
    def get_strategic_insights(self):
        """Generate strategic insights"""
        insights = {
            'competitive_advantages': self.competitive_advantages,
            'key_partnerships': self.key_partnerships,
            'distribution_channels': self.distribution_channels,
            'technology_adoption': self.technology_adoption,
            'regulatory_compliance': self.regulatory_compliance,
            'sustainability_initiatives': self.sustainability_initiatives,
            'future_plans': self.future_plans,
            'risk_factors': self.risk_factors
        }
        
        # Generate automated insights
        automated_insights = []
        
        # Price positioning insights
        if self.products:
            avg_price_diff = sum([flt(p.price_difference_percent) for p in self.products if p.price_difference_percent]) / len(self.products)
            if avg_price_diff > 15:
                automated_insights.append("Competitor generally prices higher than us - opportunity for premium positioning")
            elif avg_price_diff < -15:
                automated_insights.append("Competitor generally prices lower than us - need to review cost structure")
            else:
                automated_insights.append("Pricing is competitive - focus on value differentiation")
        
        # Market position insights
        if self.market_share and flt(self.market_share) > 25:
            automated_insights.append("Strong market presence - monitor for defensive strategies")
        elif self.market_share and flt(self.market_share) < 5:
            automated_insights.append("Niche player - potential acquisition target or specialized threat")
        
        # Financial health insights
        if self.profit_margin and flt(self.profit_margin) > 20:
            automated_insights.append("High profitability - strong competitive position")
        elif self.profit_margin and flt(self.profit_margin) < 5:
            automated_insights.append("Low margins - potential pricing pressure or efficiency issues")
        
        insights['automated_insights'] = automated_insights
        return insights
    
    def get_recommendations(self):
        """Get strategic and pricing recommendations"""
        return {
            'strategic_recommendations': self.strategic_recommendations,
            'pricing_recommendations': self.pricing_recommendations,
            'action_items': self.action_items,
            'monitoring_kpis': self.monitoring_kpis
        }
    
    @frappe.whitelist()
    def update_product_prices(self):
        """به‌روزرسانی قیمت محصولات رقیب از منابع خارجی"""
        updated_count = 0
        
        for product in self.products:
            if product.item_code:
                # به‌روزرسانی قیمت ما
                our_price = self.get_our_item_price(product.item_code)
                if our_price != product.our_price:
                    product.our_price = our_price
                    updated_count += 1
                
                # محاسبه مجدد مقایسه‌ها
                if product.competitor_price and our_price:
                    product.price_difference = flt(product.competitor_price) - flt(our_price)
                    product.price_difference_percent = (product.price_difference / our_price) * 100
                
                product.last_updated = today()
        
        if updated_count > 0:
            self.save()
            
        return {
            'status': 'success',
            'message': f'{updated_count} قیمت محصول به‌روزرسانی شد',
            'updated_count': updated_count
        }
    
    @frappe.whitelist()
    def start_intelligent_crawl(self):
        """شروع کرال هوشمند وب‌سایت رقیب"""
        try:
            if not WEB_CRAWLER_AVAILABLE:
                return {'status': 'disabled', 'message': 'Web crawler is disabled'}

            if not self.website_url:
                return {'status': 'error', 'message': 'آدرس وب‌سایت مشخص نشده است'}
            
            crawler = CompetitorWebCrawler(self)
            result = crawler.crawl_competitor_website()
            
            if result['status'] == 'success':
                self.save()
            
            return result
            
        except Exception as e:
            frappe.log_error(f"خطا در کرال هوشمند: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @frappe.whitelist()
    def analyze_seo_performance(self):
        """تحلیل عملکرد SEO رقیب"""
        try:
            seo_analysis = {
                'domain_score': self.calculate_domain_score(),
                'content_quality': self.analyze_content_quality(),
                'technical_seo': self.check_technical_seo(),
                'backlink_profile': self.analyze_backlink_profile(),
                'keyword_performance': self.analyze_keyword_performance()
            }
            
            return {
                'status': 'success',
                'seo_analysis': seo_analysis,
                'recommendations': self.generate_seo_recommendations(seo_analysis)
            }
            
        except Exception as e:
            frappe.log_error(f"خطا در تحلیل SEO: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def calculate_domain_score(self):
        """محاسبه امتیاز دامنه"""
        score = 0
        
        if self.domain_authority:
            score += min(self.domain_authority, 100) * 0.4
        
        if self.backlinks_count:
            # امتیاز بر اساس تعداد بک‌لینک
            backlink_score = min(self.backlinks_count / 1000 * 20, 40)
            score += backlink_score
        
        if self.monthly_traffic:
            # امتیاز بر اساس ترافیک ماهانه
            traffic_score = min(self.monthly_traffic / 10000 * 20, 20)
            score += traffic_score
        
        return min(score, 100)
    
    def analyze_content_quality(self):
        """تحلیل کیفیت محتوا"""
        quality_indicators = {
            'meta_description_quality': len(self.meta_description or '') > 120,
            'keyword_optimization': len(self.top_keywords or '') > 50,
            'content_freshness': self.last_crawl_date and 
                                (now_datetime() - self.last_crawl_date).days < 30
        }
        
        return quality_indicators
    
    def check_technical_seo(self):
        """بررسی SEO فنی"""
        # این بخش می‌تواند با ابزارهای خارجی تکمیل شود
        return {
            'mobile_friendly': True,  # فرضی
            'page_speed': 'متوسط',
            'ssl_certificate': True,
            'structured_data': bool(self.meta_description)
        }
    
    def analyze_backlink_profile(self):
        """تحلیل پروفایل بک‌لینک"""
        if not self.backlinks_count:
            return {'quality': 'نامشخص', 'diversity': 'نامشخص'}
        
        # تحلیل کیفیت بر اساس نسبت DA به تعداد بک‌لینک
        if self.domain_authority and self.backlinks_count:
            quality_ratio = self.domain_authority / (self.backlinks_count / 100)
            if quality_ratio > 5:
                quality = 'بالا'
            elif quality_ratio > 2:
                quality = 'متوسط'
            else:
                quality = 'پایین'
        else:
            quality = 'نامشخص'
        
        return {
            'quality': quality,
            'total_backlinks': self.backlinks_count,
            'diversity': 'متوسط'  # فرضی
        }
    
    def analyze_keyword_performance(self):
        """تحلیل عملکرد کلمات کلیدی"""
        if not self.organic_keywords:
            return {'performance': 'نامشخص'}
        
        if self.organic_keywords > 1000:
            performance = 'عالی'
        elif self.organic_keywords > 500:
            performance = 'خوب'
        elif self.organic_keywords > 100:
            performance = 'متوسط'
        else:
            performance = 'ضعیف'
        
        return {
            'performance': performance,
            'total_keywords': self.organic_keywords,
            'trend': self.traffic_trend or 'نامشخص'
        }
    
    def generate_seo_recommendations(self, seo_analysis):
        """تولید توصیه‌های SEO"""
        recommendations = []
        
        if seo_analysis['domain_score'] < 50:
            recommendations.append('تقویت اعتبار دامنه از طریق بک‌لینک‌سازی')
        
        if not seo_analysis['content_quality']['meta_description_quality']:
            recommendations.append('بهبود کیفیت متا توضیحات')
        
        if not seo_analysis['content_quality']['keyword_optimization']:
            recommendations.append('بهینه‌سازی کلمات کلیدی')
        
        if seo_analysis['keyword_performance']['performance'] == 'ضعیف':
            recommendations.append('گسترش استراتژی کلمات کلیدی')
        
        return recommendations
    
    @frappe.whitelist()
    def setup_price_monitoring(self):
        """راه‌اندازی نظارت بر قیمت‌ها"""
        try:
            if not WEB_CRAWLER_AVAILABLE:
                return {'status': 'disabled', 'message': 'Web crawler is disabled'}

            if not self.enable_price_monitoring:
                return {'status': 'error', 'message': 'نظارت بر قیمت فعال نیست'}
            
            # ایجاد job برای نظارت دوره‌ای
            frappe.enqueue(
                'pricing.pricing.doctype.competitor_analysis.competitor_analysis.monitor_price_changes',
                competitor_name=self.name,
                queue='long',
                timeout=3600
            )
            
            return {
                'status': 'success',
                'message': 'نظارت بر قیمت‌ها راه‌اندازی شد'
            }
            
        except Exception as e:
            frappe.log_error(f"خطا در راه‌اندازی نظارت قیمت: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @frappe.whitelist()
    def schedule_next_review(self, days=90):
        """زمان‌بندی بررسی بعدی"""
        self.next_review_date = add_days(today(), cint(days))
        self.save()
        
        return {
            'status': 'success',
            'message': f'بررسی بعدی برای {self.next_review_date} زمان‌بندی شد',
            'next_review_date': self.next_review_date
        }

@frappe.whitelist()
def get_competitor_analysis_dashboard():
    """دریافت داده‌های داشبورد تحلیل رقبا"""
    try:
        # دریافت رقبای فعال
        active_competitors = frappe.get_all("Competitor Analysis",
            filters={"status": "فعال"},
            fields=["name", "competitor_name", "competitor_type", "market_segment", "priority"])
        
        # توزیع انواع رقبا
        competitor_types = frappe.get_all("Competitor Analysis",
            filters={"status": "فعال"},
            fields=["competitor_type"],
            group_by="competitor_type")
        
        # توزیع بخش‌های بازار
        market_segments = frappe.get_all("Competitor Analysis",
            filters={"status": "فعال"},
            fields=["market_segment"],
            group_by="market_segment")
        
        # بررسی‌های سررسید
        reviews_due = frappe.get_all("Competitor Analysis",
            filters={
                "status": "فعال",
                "next_review_date": ["<=", add_days(today(), 7)]
            },
            fields=["name", "competitor_name", "next_review_date"])
        
        return {
            'active_competitors': len(active_competitors),
            'competitor_types': competitor_types,
            'market_segments': market_segments,
            'reviews_due': reviews_due,
            'competitor_list': active_competitors
        }
        
    except Exception as e:
        frappe.log_error(f"خطا در داشبورد رقبا: {str(e)}")
        return {'status': 'error', 'message': str(e)}

@frappe.whitelist()
def bulk_update_competitor_prices():
    """به‌روزرسانی گروهی قیمت تمام محصولات رقبا"""
    try:
        updated_analyses = 0
        total_products_updated = 0
        
        active_analyses = frappe.get_all("Competitor Analysis",
            filters={"status": "فعال"},
            fields=["name"])
        
        for analysis in active_analyses:
            doc = frappe.get_doc("Competitor Analysis", analysis.name)
            result = doc.update_product_prices()
            
            if result.get('updated_count', 0) > 0:
                updated_analyses += 1
                total_products_updated += result['updated_count']
        
        return {
            'status': 'success',
            'message': f'{total_products_updated} محصول در {updated_analyses} تحلیل رقیب به‌روزرسانی شد',
            'updated_analyses': updated_analyses,
            'total_products_updated': total_products_updated
        }
        
    except Exception as e:
        frappe.log_error(f"خطا در به‌روزرسانی گروهی: {str(e)}")
        return {'status': 'error', 'message': str(e)}

@frappe.whitelist()
def monitor_price_changes(competitor_name):
    """نظارت بر تغییرات قیمت رقیب"""
    try:
        if not WEB_CRAWLER_AVAILABLE:
            return {'status': 'disabled', 'message': 'Web crawler is disabled'}

        competitor = frappe.get_doc("Competitor Analysis", competitor_name)
        
        if not competitor.enable_price_monitoring:
            return {'status': 'skipped', 'message': 'نظارت بر قیمت غیرفعال است'}
        
        # شروع کرال برای به‌روزرسانی قیمت‌ها
        crawler = CompetitorWebCrawler(competitor)
        result = crawler.update_product_prices()
        
        if result['status'] == 'success':
            competitor.save()
        
        return result
        
    except Exception as e:
        frappe.log_error(f"خطا در نظارت قیمت {competitor_name}: {str(e)}")
        return {'status': 'error', 'message': str(e)}

@frappe.whitelist()
def get_competitor_intelligence_dashboard():
    """دریافت داده‌های داشبورد هوش رقابتی"""
    try:
        # آمار کلی
        total_competitors = frappe.db.count("Competitor Analysis", {"status": "فعال"})
        
        # رقبای با کرال فعال
        auto_crawl_competitors = frappe.db.count("Competitor Analysis", {
            "status": "فعال",
            "enable_auto_crawling": 1
        })
        
        # رقبای نیازمند به‌روزرسانی
        outdated_competitors = frappe.get_all("Competitor Analysis",
            filters={
                "status": "فعال",
                "last_crawl_date": ["<", add_days(today(), -7)]
            },
            fields=["name", "competitor_name", "last_crawl_date"])
        
        # آمار SEO
        seo_stats = frappe.db.sql("""
            SELECT 
                AVG(domain_authority) as avg_da,
                AVG(monthly_traffic) as avg_traffic,
                COUNT(*) as total_with_seo
            FROM `tabCompetitor Analysis`
            WHERE status = 'فعال' AND domain_authority IS NOT NULL
        """, as_dict=True)[0]
        
        # تحلیل موقعیت بازار
        market_positions = frappe.get_all("Competitor Analysis",
            filters={"status": "فعال"},
            fields=["market_position"],
            group_by="market_position")
        
        return {
            'status': 'success',
            'total_competitors': total_competitors,
            'auto_crawl_competitors': auto_crawl_competitors,
            'outdated_competitors': outdated_competitors,
            'seo_stats': seo_stats,
            'market_positions': market_positions
        }
        
    except Exception as e:
        frappe.log_error(f"خطا در داشبورد هوش رقابتی: {str(e)}")
        return {'status': 'error', 'message': str(e)}

@frappe.whitelist()
def generate_competitive_intelligence_report(competitor_name=None):
    """تولید گزارش جامع هوش رقابتی"""
    try:
        filters = {"status": "فعال"}
        if competitor_name:
            filters["name"] = competitor_name
        
        competitors = frappe.get_all("Competitor Analysis",
            filters=filters,
            fields=["*"])
        
        report_data = {
            'summary': {
                'total_competitors': len(competitors),
                'market_leaders': len([c for c in competitors if c.get('market_position') == 'رهبر بازار']),
                'direct_competitors': len([c for c in competitors if c.get('competitor_type') == 'رقیب مستقیم'])
            },
            'seo_analysis': analyze_competitors_seo(competitors),
            'pricing_analysis': analyze_competitors_pricing(competitors),
            'market_analysis': analyze_market_positioning(competitors),
            'recommendations': generate_strategic_recommendations(competitors)
        }
        
        return {
            'status': 'success',
            'report_data': report_data
        }
        
    except Exception as e:
        frappe.log_error(f"خطا در تولید گزارش هوش رقابتی: {str(e)}")
        return {'status': 'error', 'message': str(e)}

def analyze_competitors_seo(competitors):
    """تحلیل SEO رقبا"""
    seo_data = []
    
    for comp in competitors:
        if comp.get('domain_authority') or comp.get('monthly_traffic'):
            seo_data.append({
                'name': comp.get('competitor_name'),
                'domain_authority': comp.get('domain_authority', 0),
                'monthly_traffic': comp.get('monthly_traffic', 0),
                'organic_keywords': comp.get('organic_keywords', 0),
                'backlinks': comp.get('backlinks_count', 0)
            })
    
    # رتبه‌بندی بر اساس DA
    seo_data.sort(key=lambda x: x['domain_authority'], reverse=True)
    
    return {
        'top_performers': seo_data[:5],
        'average_da': sum(c['domain_authority'] for c in seo_data) / len(seo_data) if seo_data else 0,
        'total_analyzed': len(seo_data)
    }

def analyze_competitors_pricing(competitors):
    """تحلیل قیمت‌گذاری رقبا"""
    pricing_strategies = {}
    
    for comp in competitors:
        strategy = comp.get('pricing_model')
        if strategy:
            pricing_strategies[strategy] = pricing_strategies.get(strategy, 0) + 1
    
    return {
        'pricing_strategies': pricing_strategies,
        'most_common_strategy': max(pricing_strategies.items(), key=lambda x: x[1])[0] if pricing_strategies else None
    }

def analyze_market_positioning(competitors):
    """تحلیل موقعیت‌یابی بازار"""
    positions = {}
    segments = {}
    
    for comp in competitors:
        # موقعیت بازار
        position = comp.get('market_position')
        if position:
            positions[position] = positions.get(position, 0) + 1
        
        # بخش بازار
        segment = comp.get('market_segment')
        if segment:
            segments[segment] = segments.get(segment, 0) + 1
    
    return {
        'market_positions': positions,
        'market_segments': segments
    }

def generate_strategic_recommendations(competitors):
    """تولید توصیه‌های استراتژیک"""
    recommendations = []
    
    # تحلیل رقبای قوی
    strong_competitors = [c for c in competitors 
                         if c.get('market_position') == 'رهبر بازار' or 
                         c.get('domain_authority', 0) > 70]
    
    if strong_competitors:
        recommendations.append({
            'type': 'تهدید',
            'title': 'رقبای قوی شناسایی شدند',
            'description': f'{len(strong_competitors)} رقیب قوی در بازار وجود دارد که نیاز به نظارت دقیق دارند.'
        })
    
    # تحلیل فرصت‌ها
    weak_segments = [c for c in competitors if c.get('customer_satisfaction', 0) < 3]
    if weak_segments:
        recommendations.append({
            'type': 'فرصت',
            'title': 'رقبای ضعیف شناسایی شدند',
            'description': f'{len(weak_segments)} رقیب با رضایت مشتری پایین وجود دارد که فرصت رقابت است.'
        })
    
    return recommendations
