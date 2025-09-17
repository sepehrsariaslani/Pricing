import frappe
from frappe.model.document import Document
from frappe.utils import flt, cint, today, add_days, getdate, now
import json
from datetime import datetime, timedelta

class RawMaterialPricing(Document):
    def validate(self):
        """Validate raw material pricing data"""
        self.validate_dates()
        self.set_material_details()
        self.calculate_price_changes()
        self.calculate_cost_impact()
        self.set_title()
        
    def validate_dates(self):
        """Validate effective and expiry dates"""
        if self.effective_date and getdate(self.effective_date) > getdate(today()):
            frappe.throw("Effective date cannot be in the future")
            
        if self.expiry_date and self.effective_date:
            if getdate(self.expiry_date) <= getdate(self.effective_date):
                frappe.throw("Expiry date must be after effective date")
    
    def set_material_details(self):
        """Set material details from Item master"""
        if self.material_code:
            item = frappe.get_doc("Item", self.material_code)
            self.material_name = item.item_name
            self.uom = item.stock_uom
            if not self.material_category:
                self.material_category = item.item_group
            if not self.currency:
                self.currency = frappe.defaults.get_global_default("currency")
    
    def set_title(self):
        """Set document title"""
        if not self.title and self.material_name:
            self.title = f"{self.material_name} - {self.effective_date}"
    
    def calculate_price_changes(self):
        """Calculate price changes from previous price"""
        if self.current_price and self.previous_price:
            self.price_change = flt(self.current_price) - flt(self.previous_price)
            if self.previous_price > 0:
                self.price_change_percent = (self.price_change / self.previous_price) * 100
        
        # Update price history
        self.update_price_history()
    
    def update_price_history(self):
        """Update price history table"""
        if self.current_price:
            # Check if entry for today already exists
            existing_entry = None
            for history in self.price_history:
                if history.date == today():
                    existing_entry = history
                    break
            
            if existing_entry:
                # Update existing entry
                existing_entry.price = self.current_price
                existing_entry.price_change = self.price_change
                existing_entry.price_change_percent = self.price_change_percent
            else:
                # Add new entry
                self.append('price_history', {
                    'date': today(),
                    'price': self.current_price,
                    'price_change': self.price_change,
                    'price_change_percent': self.price_change_percent,
                    'source': 'Manual Entry'
                })
    
    def calculate_cost_impact(self):
        """Calculate cost impact on affected items"""
        self.affected_items = []
        total_impact = 0
        
        # Find all BOMs that use this material
        boms = frappe.get_all("BOM Item",
            filters={"item_code": self.material_code},
            fields=["parent", "qty", "amount"])
        
        for bom_item in boms:
            bom = frappe.get_doc("BOM", bom_item.parent)
            if bom.is_active and bom.is_default:
                # Calculate impact for this BOM
                old_cost = bom_item.amount or 0
                new_cost = flt(self.current_price) * flt(bom_item.qty)
                cost_impact = new_cost - old_cost
                
                # Determine impact severity
                impact_severity = self.get_impact_severity(cost_impact, old_cost)
                recommended_action = self.get_recommended_action(impact_severity, cost_impact)
                
                self.append('affected_items', {
                    'item_code': bom.item,
                    'item_name': frappe.get_value("Item", bom.item, "item_name"),
                    'bom_no': bom.name,
                    'material_qty_required': bom_item.qty,
                    'current_cost_per_unit': old_cost / bom_item.qty if bom_item.qty > 0 else 0,
                    'new_cost_per_unit': self.current_price,
                    'cost_impact_per_unit': cost_impact / bom_item.qty if bom_item.qty > 0 else 0,
                    'total_cost_impact': cost_impact,
                    'impact_severity': impact_severity,
                    'recommended_action': recommended_action
                })
                
                total_impact += cost_impact
        
        self.total_cost_impact = total_impact
    
    def get_impact_severity(self, cost_impact, old_cost):
        """Determine impact severity based on cost change"""
        if old_cost == 0:
            return "Medium"
        
        impact_percent = abs(cost_impact / old_cost * 100)
        
        if impact_percent > 20:
            return "Critical"
        elif impact_percent > 10:
            return "High"
        elif impact_percent > 5:
            return "Medium"
        else:
            return "Low"
    
    def get_recommended_action(self, severity, cost_impact):
        """Get recommended action based on impact"""
        if severity == "Critical":
            return "Find Alternative" if cost_impact > 0 else "Stock Up"
        elif severity == "High":
            return "Negotiate" if cost_impact > 0 else "Adjust Pricing"
        elif severity == "Medium":
            return "Adjust Pricing"
        else:
            return "Monitor"
    
    def before_save(self):
        """Actions before saving"""
        # Store previous price for comparison
        if not self.is_new():
            old_doc = frappe.get_doc(self.doctype, self.name)
            if old_doc.current_price != self.current_price:
                self.previous_price = old_doc.current_price
        
        # Set last price update
        self.last_price_update = now()
    
    def after_save(self):
        """Actions after saving"""
        # Send notifications if price changed significantly
        if self.price_change_percent and abs(self.price_change_percent) >= flt(self.price_alert_threshold or 5):
            self.send_price_change_notifications()
        
        # Update related Auto Price Lists if auto update is enabled
        if self.auto_update_pricing:
            self.update_related_price_lists()
    
    def send_price_change_notifications(self):
        """Send notifications to users about price changes"""
        for user in self.notification_users:
            if self.should_notify_user(user):
                self.send_notification_to_user(user)
    
    def should_notify_user(self, user):
        """Check if user should be notified based on their preferences"""
        if not user.threshold_percent:
            return True
        
        return abs(self.price_change_percent) >= flt(user.threshold_percent)
    
    def send_notification_to_user(self, user):
        """Send notification to specific user"""
        subject = f"Raw Material Price Alert: {self.material_name}"
        message = f"""
        Material: {self.material_name} ({self.material_code})
        Previous Price: {frappe.format(self.previous_price, {'fieldtype': 'Currency'})}
        Current Price: {frappe.format(self.current_price, {'fieldtype': 'Currency'})}
        Change: {self.price_change_percent:.2f}%
        
        Total Cost Impact: {frappe.format(self.total_cost_impact, {'fieldtype': 'Currency'})}
        Affected Items: {len(self.affected_items)}
        """
        
        if user.email_enabled:
            frappe.sendmail(
                recipients=[user.user],
                subject=subject,
                message=message
            )
        
        # Create notification
        frappe.get_doc({
            'doctype': 'Notification Log',
            'subject': subject,
            'for_user': user.user,
            'type': 'Alert',
            'document_type': self.doctype,
            'document_name': self.name
        }).insert(ignore_permissions=True)
    
    def update_related_price_lists(self):
        """Update related Auto Price Lists with new material costs"""
        try:
            updated_price_lists = []
            
            # Find Auto Price Lists that might be affected
            price_lists = frappe.get_all("Auto Price List",
                filters={"docstatus": 0},
                fields=["name", "title"])
            
            for price_list in price_lists:
                try:
                    doc = frappe.get_doc("Auto Price List", price_list.name)
                    items_updated = False
                    
                    # Check if any items in the price list use this material
                    for item in doc.items:
                        if item.item_code in [ai.item_code for ai in self.affected_items]:
                            # Update the raw material cost with new price
                            affected_item = next((ai for ai in self.affected_items if ai.item_code == item.item_code), None)
                            if affected_item:
                                # Apply the cost impact
                                old_cost = flt(item.raw_material_cost)
                                new_cost = old_cost + flt(affected_item.total_cost_impact)
                                item.raw_material_cost = new_cost
                                items_updated = True
                    
                    if items_updated:
                        # Recalculate all item prices
                        doc.calculate_item_prices()
                        doc.save()
                        updated_price_lists.append(price_list.name)
                        
                except Exception as e:
                    frappe.log_error(f"Error updating price list {price_list.name}: {str(e)}")
                    continue
            
            return updated_price_lists
            
        except Exception as e:
            frappe.log_error(f"Error in update_related_price_lists: {str(e)}")
            return []
    
    @frappe.whitelist()
    def update_market_data(self):
        """Update market data from external sources"""
        try:
            # Placeholder for external API integration
            import random
            
            # Simulate market price (±10% of current price)
            if self.current_price:
                variation = random.uniform(-0.1, 0.1)
                self.market_price = self.current_price * (1 + variation)
            
            # Set market trend based on price comparison
            if self.market_price and self.current_price:
                diff_percent = ((self.market_price - self.current_price) / self.current_price) * 100
                if diff_percent > 5:
                    self.market_trend = "Rising"
                elif diff_percent < -5:
                    self.market_trend = "Falling"
                else:
                    self.market_trend = "Stable"
            
            # Update volatility index
            self.volatility_index = random.uniform(0.1, 2.0)
            self.last_verified_date = today()
            self.save()
            
            return {
                'status': 'success',
                'message': 'Market data updated successfully',
                'market_price': self.market_price,
                'market_trend': self.market_trend
            }
            
        except Exception as e:
            frappe.log_error(f"Market data update error: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    @frappe.whitelist()
    def generate_impact_report(self):
        """Generate comprehensive impact analysis report"""
        try:
            report_data = {
                'material_info': {
                    'code': self.material_code,
                    'name': self.material_name,
                    'category': self.material_category,
                    'current_price': self.current_price,
                    'previous_price': self.previous_price,
                    'price_change': self.price_change,
                    'price_change_percent': self.price_change_percent,
                    'market_trend': self.market_trend,
                    'volatility_index': self.volatility_index
                },
                'cost_impact': {
                    'total_impact': self.total_cost_impact,
                    'affected_items_count': len(self.affected_items),
                    'high_impact_items': len([item for item in self.affected_items if item.impact_severity == 'Critical']),
                    'medium_impact_items': len([item for item in self.affected_items if item.impact_severity == 'High']),
                    'low_impact_items': len([item for item in self.affected_items if item.impact_severity in ['Medium', 'Low']])
                },
                'supplier_analysis': {
                    'total_suppliers': len(self.suppliers),
                    'best_supplier': self.get_best_supplier(),
                    'price_variance': self.get_supplier_price_variance()
                },
                'recommendations': self.get_strategic_recommendations(),
                'affected_items': [
                    {
                        'item_code': item.item_code,
                        'item_name': item.item_name,
                        'current_cost': item.current_cost_per_unit,
                        'new_cost': item.new_cost_per_unit,
                        'impact': item.total_cost_impact,
                        'severity': item.impact_severity,
                        'action': item.recommended_action
                    } for item in self.affected_items
                ]
            }
            
            return report_data
            
        except Exception as e:
            frappe.log_error(f"Error generating impact report: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    def get_best_supplier(self):
        """Get the best supplier based on price and rating"""
        if not self.suppliers:
            return None
        
        best_supplier = None
        best_score = 0
        
        for supplier in self.suppliers:
            # Calculate score based on price and rating
            price_score = 50  # Base score
            if supplier.quoted_price and self.current_price:
                price_ratio = supplier.quoted_price / self.current_price
                price_score = max(0, (2 - price_ratio) * 50)
            
            rating_score = (supplier.supplier_rating or 3) * 20  # Convert 1-5 to 0-100
            
            total_score = (price_score + rating_score) / 2
            
            if total_score > best_score:
                best_score = total_score
                best_supplier = {
                    'supplier': supplier.supplier,
                    'supplier_name': supplier.supplier_name,
                    'quoted_price': supplier.quoted_price,
                    'rating': supplier.supplier_rating,
                    'score': total_score
                }
        
        return best_supplier
    
    def get_supplier_price_variance(self):
        """Calculate price variance among suppliers"""
        if not self.suppliers:
            return 0
        
        prices = [s.quoted_price for s in self.suppliers if s.quoted_price]
        if len(prices) < 2:
            return 0
        
        min_price = min(prices)
        max_price = max(prices)
        
        return ((max_price - min_price) / max_price * 100) if max_price > 0 else 0
    
    def get_strategic_recommendations(self):
        """Generate strategic recommendations based on analysis"""
        recommendations = []
        
        # Price change recommendations
        if self.price_change_percent:
            if abs(self.price_change_percent) > 20:
                recommendations.append({
                    'type': 'Critical',
                    'title': 'Significant Price Change',
                    'description': f'Material price changed by {self.price_change_percent:.1f}%. Consider alternative suppliers or materials.',
                    'priority': 'High'
                })
            elif abs(self.price_change_percent) > 10:
                recommendations.append({
                    'type': 'Warning',
                    'title': 'Notable Price Change',
                    'description': f'Material price changed by {self.price_change_percent:.1f}%. Monitor closely and negotiate with suppliers.',
                    'priority': 'Medium'
                })
        
        # Supplier recommendations
        if len(self.suppliers) < 2:
            recommendations.append({
                'type': 'Improvement',
                'title': 'Supplier Diversification',
                'description': 'Consider adding more suppliers to reduce dependency and improve negotiation power.',
                'priority': 'Medium'
            })
        
        # Market trend recommendations
        if self.market_trend == 'Rising':
            recommendations.append({
                'type': 'Action',
                'title': 'Rising Market Trend',
                'description': 'Market prices are rising. Consider bulk purchasing or long-term contracts.',
                'priority': 'High'
            })
        elif self.market_trend == 'Falling':
            recommendations.append({
                'type': 'Opportunity',
                'title': 'Falling Market Trend',
                'description': 'Market prices are falling. Good time to renegotiate contracts.',
                'priority': 'Medium'
            })
        
        # Volatility recommendations
        if self.volatility_index and self.volatility_index > 1.5:
            recommendations.append({
                'type': 'Risk',
                'title': 'High Price Volatility',
                'description': 'Material shows high price volatility. Consider hedging strategies or alternative materials.',
                'priority': 'High'
            })
        
        return recommendations

@frappe.whitelist()
def get_raw_material_dashboard():
    """Get dashboard data for raw material pricing"""
    try:
        # Get active materials
        active_materials = frappe.get_all("Raw Material Pricing",
            filters={"status": "Active"},
            fields=["name", "material_name", "current_price", "price_change_percent", "total_cost_impact"])
        
        # Get materials with high price volatility
        volatile_materials = frappe.get_all("Raw Material Pricing",
            filters={"status": "Active", "volatility_index": [">", 1.5]},
            fields=["name", "material_name", "volatility_index"])
        
        # Get materials needing attention
        attention_materials = frappe.get_all("Raw Material Pricing",
            filters={
                "status": "Active",
                "price_change_percent": [">", 10]
            },
            fields=["name", "material_name", "price_change_percent"])
        
        return {
            'active_materials': len(active_materials),
            'volatile_materials': len(volatile_materials),
            'attention_materials': len(attention_materials),
            'material_list': active_materials[:10],
            'volatile_list': volatile_materials,
            'attention_list': attention_materials
        }
        
    except Exception as e:
        frappe.log_error(f"Raw material dashboard error: {str(e)}")
        return {'status': 'error', 'message': str(e)}
