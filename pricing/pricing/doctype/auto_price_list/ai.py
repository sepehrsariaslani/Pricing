"""
AI and Advanced Analytics Functions for Auto Price List
هوش مصنوعی و تحلیل‌های پیشرفته برای لیست قیمت خودکار

This module contains AI-powered pricing optimization, market analysis,
and demand forecasting functions separated from the main DocType for better maintainability.
"""

import frappe
from frappe.utils import flt, getdate, add_months, nowdate
import json
import math

# Check for optional ML libraries
try:
    import pandas as pd
    import numpy as np
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_squared_error
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False


class PricingAI:
    """AI-powered pricing optimization and analytics"""
    
    def __init__(self, doc):
        self.doc = doc
        
    def auto_optimize_pricing(self):
        """Automatically optimize pricing based on market conditions"""
        for item in self.doc.items:
            if item.total_cost > 0:
                # Get market price if available
                market_price = 0
                if self.doc.compare_with_price_list:
                    market_price = frappe.db.get_value(
                        "Item Price", 
                        {
                            "item_code": item.item_code, 
                            "price_list": self.doc.compare_with_price_list
                        }, 
                        "price_list_rate"
                    ) or 0
                
                # Calculate optimal price using AI
                optimal_price = self.ai_optimize_pricing(item)
                
                # Apply optimization if it's profitable
                if optimal_price > item.total_cost * 1.1:  # At least 10% profit
                    item.selling_price = optimal_price
                    item.profit_amount = optimal_price - item.total_cost
                    
                    # Update final price
                    item.final_selected_price = optimal_price
                    
                    # Add optimization note
                    if not item.notes:
                        item.notes = ""
                    item.notes += f"\n🤖 AI Optimized: {optimal_price:,.0f} ریال"

    def ai_optimize_pricing(self, item):
        """AI-powered pricing optimization using advanced machine learning"""
        if not item.total_cost or item.total_cost <= 0:
            return item.selling_price
            
        if SKLEARN_AVAILABLE:
            return self.ml_optimize_pricing(item)
        else:
            return self.rule_based_optimize_pricing(item)

    def ml_optimize_pricing(self, item):
        """Machine Learning based price optimization"""
        try:
            # Prepare features for ML model
            features = self.prepare_ml_features(item)
            
            # Get training data
            training_data = self.get_training_data_for_item(item.item_code)
            
            if len(training_data) < 10:  # Not enough data for ML
                return self.rule_based_optimize_pricing(item)
            
            # Train model and predict
            optimal_price = self.train_and_predict_price(training_data, features)
            
            return optimal_price
            
        except Exception as e:
            frappe.log_error(f"ML optimization error for {item.item_code}: {str(e)}")
            return self.rule_based_optimize_pricing(item)

    def clean_and_validate_data(self, data, data_type="price"):
        """Clean and validate data by removing outliers and noise"""
        try:
            if not data or len(data) < 3:
                return data
            
            # Convert to numpy array for processing
            import numpy as np
            values = np.array([flt(d) for d in data if d is not None and flt(d) > 0])
            
            if len(values) < 3:
                return data
            
            # Remove outliers using IQR method
            Q1 = np.percentile(values, 25)
            Q3 = np.percentile(values, 75)
            IQR = Q3 - Q1
            
            # Define outlier bounds
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            
            # For prices, ensure minimum reasonable bounds
            if data_type == "price":
                lower_bound = max(lower_bound, np.median(values) * 0.3)  # Not less than 30% of median
                upper_bound = min(upper_bound, np.median(values) * 3.0)  # Not more than 300% of median
            
            # Filter out outliers
            cleaned_values = values[(values >= lower_bound) & (values <= upper_bound)]
            
            return cleaned_values.tolist() if len(cleaned_values) > 0 else [np.median(values)]
            
        except Exception as e:
            frappe.log_error(f"Data cleaning error: {str(e)}")
            return data

    def calculate_price_volatility(self, item_code):
        """Calculate price volatility over the last 6 months"""
        try:
            price_data = frappe.db.sql("""
                SELECT sii.rate, si.posting_date
                FROM `tabSales Invoice Item` sii
                JOIN `tabSales Invoice` si ON si.name = sii.parent
                WHERE sii.item_code = %s 
                AND si.posting_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
                AND si.docstatus = 1
                AND sii.rate > 0
                ORDER BY si.posting_date
            """, (item_code,), as_dict=True)
            
            if len(price_data) < 5:
                return 0.1  # Low volatility for items with little data
            
            # Clean price data
            prices = self.clean_and_validate_data([d.rate for d in price_data], "price")
            
            if len(prices) < 3:
                return 0.1
            
            # Calculate coefficient of variation (std/mean)
            import numpy as np
            mean_price = np.mean(prices)
            std_price = np.std(prices)
            
            volatility = (std_price / mean_price) if mean_price > 0 else 0
            return min(volatility, 1.0)  # Cap at 100%
            
        except Exception as e:
            frappe.log_error(f"Price volatility calculation error for {item_code}: {str(e)}")
            return 0.1

    def calculate_competitor_gap(self, item_code, current_price):
        """Calculate gap from nearest competitor prices"""
        try:
            market_data = self.get_market_data(item_code)
            competitors = market_data.get('competitors', [])
            
            if not competitors:
                return 0.0  # No competitor data
            
            # Clean competitor prices
            competitor_prices = self.clean_and_validate_data(
                [c.get('price', 0) for c in competitors if c.get('price', 0) > 0], 
                "price"
            )
            
            if not competitor_prices:
                return 0.0
            
            # Find nearest competitor price
            import numpy as np
            current = flt(current_price)
            nearest_price = min(competitor_prices, key=lambda x: abs(x - current))
            
            # Calculate percentage gap
            gap = ((current - nearest_price) / nearest_price * 100) if nearest_price > 0 else 0
            return max(-50, min(50, gap))  # Cap between -50% and +50%
            
        except Exception as e:
            frappe.log_error(f"Competitor gap calculation error for {item_code}: {str(e)}")
            return 0.0

    def calculate_demand_trend(self, item_code):
        """Calculate demand trend slope over time"""
        try:
            # Get monthly sales data for last 12 months
            sales_data = frappe.db.sql("""
                SELECT 
                    DATE_FORMAT(si.posting_date, '%%Y-%%m') as month,
                    SUM(sii.qty) as total_qty
                FROM `tabSales Invoice Item` sii
                JOIN `tabSales Invoice` si ON si.name = sii.parent
                WHERE sii.item_code = %s 
                AND si.posting_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
                AND si.docstatus = 1
                GROUP BY DATE_FORMAT(si.posting_date, '%%Y-%%m')
                ORDER BY month
            """, (item_code,), as_dict=True)
            
            if len(sales_data) < 3:
                return 0.0  # Neutral trend
            
            # Clean quantity data
            quantities = self.clean_and_validate_data([d.total_qty for d in sales_data], "quantity")
            
            if len(quantities) < 3:
                return 0.0
            
            # Calculate linear trend slope
            import numpy as np
            x = np.arange(len(quantities))
            y = np.array(quantities)
            
            # Simple linear regression slope
            slope = np.polyfit(x, y, 1)[0]
            
            # Normalize slope relative to average quantity
            avg_qty = np.mean(quantities)
            normalized_slope = (slope / avg_qty) if avg_qty > 0 else 0
            
            return max(-1.0, min(1.0, normalized_slope))  # Cap between -1 and 1
            
        except Exception as e:
            frappe.log_error(f"Demand trend calculation error for {item_code}: {str(e)}")
            return 0.0

    def prepare_ml_features(self, item):
        """Prepare advanced features for ML model with data cleaning"""
        try:
            # Get market data
            market_data = self.get_market_data(item.item_code)
            
            # Calculate advanced features
            current_price = flt(item.selling_price or item.total_cost)
            
            features = {
                # Basic features
                'total_cost': flt(item.total_cost),
                'current_price': current_price,
                'profit_margin': flt(self.doc.profit_margin or 0),
                'commission_percentage': flt(self.doc.commission_percentage or 0),
                
                # Market features
                'market_price': flt(market_data.get('price', 0)),
                'competitor_count': len(market_data.get('competitors', [])),
                'demand_score': flt(market_data.get('demand_score', 50)),
                
                # Advanced features
                'price_volatility': self.calculate_price_volatility(item.item_code),
                'competitor_gap': self.calculate_competitor_gap(item.item_code, current_price),
                'demand_trend': self.calculate_demand_trend(item.item_code),
                'seasonality_factor': self.get_seasonality_factor(item.item_code),
                'inventory_turnover': self.get_inventory_turnover(item.item_code),
                'price_elasticity': self.estimate_price_elasticity(item.item_code),
                
                # Interaction features
                'cost_margin_ratio': (flt(item.total_cost) * flt(self.doc.profit_margin or 0)) / 100,
                'market_position': (current_price / flt(market_data.get('price', current_price))) if market_data.get('price', 0) > 0 else 1.0,
                'demand_volatility_score': self.calculate_demand_trend(item.item_code) * self.calculate_price_volatility(item.item_code)
            }
            
            return pd.DataFrame([features])
            
        except Exception as e:
            frappe.log_error(f"Feature preparation error for {item.item_code}: {str(e)}")
            return pd.DataFrame([{
                'total_cost': flt(item.total_cost),
                'current_price': flt(item.selling_price or item.total_cost),
                'profit_margin': flt(self.doc.profit_margin or 0),
                'commission_percentage': 0,
                'market_price': 0,
                'competitor_count': 0,
                'demand_score': 50,
                'seasonality_factor': 1.0,
                'inventory_turnover': 1.0,
                'price_elasticity': 1.0
            }])

    def get_training_data_for_item(self, item_code):
        """Get historical pricing data with time-series features for ML model"""
        try:
            # Get sales data from last 18 months for better time-series analysis
            sales_data = frappe.db.sql("""
                SELECT 
                    si.posting_date,
                    sii.rate as selling_price,
                    sii.qty,
                    si.total as invoice_total,
                    DATE_FORMAT(si.posting_date, '%%Y-%%m') as month_year
                FROM `tabSales Invoice Item` sii
                JOIN `tabSales Invoice` si ON si.name = sii.parent
                WHERE sii.item_code = %s 
                AND si.posting_date >= DATE_SUB(CURDATE(), INTERVAL 18 MONTH)
                AND si.docstatus = 1
                ORDER BY si.posting_date ASC
            """, (item_code,), as_dict=True)
            
            # Get purchase data for cost analysis
            purchase_data = frappe.db.sql("""
                SELECT 
                    pi.posting_date,
                    pii.rate as cost_price,
                    pii.qty
                FROM `tabPurchase Invoice Item` pii
                JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
                WHERE pii.item_code = %s 
                AND pi.posting_date >= DATE_SUB(CURDATE(), INTERVAL 18 MONTH)
                AND pi.docstatus = 1
                ORDER BY pi.posting_date ASC
            """, (item_code,), as_dict=True)
            
            if len(sales_data) < 5:
                return []
            
            # Clean the data
            cleaned_prices = self.clean_and_validate_data([s.selling_price for s in sales_data], "price")
            
            # Group by month for time-series analysis
            monthly_data = {}
            for sale in sales_data:
                month = sale.month_year
                if month not in monthly_data:
                    monthly_data[month] = {
                        'prices': [],
                        'quantities': [],
                        'costs': [],
                        'dates': []
                    }
                monthly_data[month]['prices'].append(sale.selling_price)
                monthly_data[month]['quantities'].append(sale.qty)
                monthly_data[month]['dates'].append(sale.posting_date)
                
                # Find matching cost
                cost_price = 0
                for purchase in purchase_data:
                    if purchase.posting_date <= sale.posting_date:
                        cost_price = purchase.cost_price
                        break
                monthly_data[month]['costs'].append(cost_price if cost_price > 0 else sale.selling_price * 0.7)
            
            # Sort months chronologically
            sorted_months = sorted(monthly_data.keys())
            
            # Create training data with time-series features
            training_data = []
            
            for i, month in enumerate(sorted_months):
                current_data = monthly_data[month]
                
                # Current month aggregates
                avg_price = sum(current_data['prices']) / len(current_data['prices'])
                avg_qty = sum(current_data['quantities']) / len(current_data['quantities'])
                avg_cost = sum(current_data['costs']) / len(current_data['costs'])
                
                # Time-series lag features
                price_lag_1 = avg_price  # Default to current
                price_lag_2 = avg_price
                qty_lag_1 = avg_qty
                qty_lag_2 = avg_qty
                
                if i >= 1:  # Has 1-month lag
                    lag_1_data = monthly_data[sorted_months[i-1]]
                    price_lag_1 = sum(lag_1_data['prices']) / len(lag_1_data['prices'])
                    qty_lag_1 = sum(lag_1_data['quantities']) / len(lag_1_data['quantities'])
                
                if i >= 2:  # Has 2-month lag
                    lag_2_data = monthly_data[sorted_months[i-2]]
                    price_lag_2 = sum(lag_2_data['prices']) / len(lag_2_data['prices'])
                    qty_lag_2 = sum(lag_2_data['quantities']) / len(lag_2_data['quantities'])
                
                # Calculate trends and momentum
                price_trend = (avg_price - price_lag_1) / price_lag_1 if price_lag_1 > 0 else 0
                qty_trend = (avg_qty - qty_lag_1) / qty_lag_1 if qty_lag_1 > 0 else 0
                price_momentum = (price_lag_1 - price_lag_2) / price_lag_2 if price_lag_2 > 0 else 0
                
                profit_margin = ((avg_price - avg_cost) / avg_cost) * 100 if avg_cost > 0 else 0
                
                training_data.append({
                    'date': current_data['dates'][0],
                    'selling_price': avg_price,
                    'cost_price': avg_cost,
                    'profit_margin': profit_margin,
                    'quantity_sold': avg_qty,
                    'revenue': avg_price * avg_qty,
                    
                    # Time-series features
                    'price_lag_1': price_lag_1,
                    'price_lag_2': price_lag_2,
                    'qty_lag_1': qty_lag_1,
                    'qty_lag_2': qty_lag_2,
                    
                    # Trend features
                    'price_trend': max(-1, min(1, price_trend)),  # Cap trends
                    'qty_trend': max(-1, min(1, qty_trend)),
                    'price_momentum': max(-1, min(1, price_momentum)),
                    
                    # Advanced features
                    'price_volatility': self.calculate_price_volatility(item_code) if i == len(sorted_months) - 1 else 0.1,
                    'competitor_gap': 0,  # Will be calculated in features
                    'demand_trend': qty_trend,
                    
                    # Seasonal features
                    'month': int(month.split('-')[1]),
                    'quarter': (int(month.split('-')[1]) - 1) // 3 + 1,
                    'is_peak_season': 1 if int(month.split('-')[1]) in [5, 6, 12] else 0
                })
            
            return training_data
            
        except Exception as e:
            frappe.log_error(f"Enhanced training data retrieval error for {item_code}: {str(e)}")
            return []

    def train_ensemble_models(self, training_data, features):
        """Train multiple models and create ensemble prediction with confidence intervals"""
        try:
            # Convert to DataFrame and clean data
            df = pd.DataFrame(training_data)
            
            if len(df) < 5:
                return {
                    'price': features['current_price'].iloc[0],
                    'confidence': 0.3,
                    'model_used': 'fallback'
                }
            
            # Prepare enhanced training features
            feature_columns = [
                'cost_price', 'profit_margin', 'quantity_sold', 
                'price_volatility', 'competitor_gap', 'demand_trend'
            ]
            
            # Fill missing columns with defaults
            for col in feature_columns:
                if col not in df.columns:
                    df[col] = 0
            
            X = df[feature_columns].fillna(0)
            y = df['selling_price']
            
            # Clean target variable
            y_cleaned = self.clean_and_validate_data(y.tolist(), "price")
            if len(y_cleaned) < len(y) * 0.7:  # If too much data removed
                y_cleaned = y.tolist()
            
            y = pd.Series(y_cleaned[:len(X)])
            X = X.iloc[:len(y)]
            
            # Prepare current features for prediction
            current_features = np.array([[
                features['total_cost'].iloc[0],
                features['profit_margin'].iloc[0],
                1,  # Default quantity
                features.get('price_volatility', pd.Series([0.1])).iloc[0],
                features.get('competitor_gap', pd.Series([0])).iloc[0],
                features.get('demand_trend', pd.Series([0])).iloc[0]
            ]])
            
            predictions = []
            model_scores = []
            
            # Model 1: Random Forest (baseline)
            try:
                rf_model = RandomForestRegressor(
                    n_estimators=100,
                    random_state=42,
                    max_depth=15,
                    min_samples_split=5
                )
                
                if len(X) > 10:
                    X_train, X_test, y_train, y_test = train_test_split(
                        X, y, test_size=0.3, random_state=42
                    )
                    rf_model.fit(X_train, y_train)
                    rf_score = rf_model.score(X_test, y_test)
                    model_scores.append(('RandomForest', rf_score))
                else:
                    rf_model.fit(X, y)
                    rf_score = 0.7  # Default score
                
                rf_pred = rf_model.predict(current_features)[0]
                predictions.append(('RandomForest', rf_pred, rf_score))
                
            except Exception as e:
                frappe.log_error(f"Random Forest model error: {str(e)}")
            
            # Model 2: Linear Regression (interpretable)
            try:
                from sklearn.linear_model import LinearRegression
                lr_model = LinearRegression()
                
                if len(X) > 5:
                    if len(X) > 10:
                        lr_model.fit(X_train, y_train)
                        lr_score = lr_model.score(X_test, y_test)
                    else:
                        lr_model.fit(X, y)
                        lr_score = 0.6
                    
                    lr_pred = lr_model.predict(current_features)[0]
                    predictions.append(('LinearRegression', lr_pred, lr_score))
                    model_scores.append(('LinearRegression', lr_score))
                
            except Exception as e:
                frappe.log_error(f"Linear Regression model error: {str(e)}")
            
            # Model 3: Gradient Boosting (if available)
            try:
                from sklearn.ensemble import GradientBoostingRegressor
                gb_model = GradientBoostingRegressor(
                    n_estimators=50,
                    learning_rate=0.1,
                    max_depth=6,
                    random_state=42
                )
                
                if len(X) > 15:
                    gb_model.fit(X_train, y_train)
                    gb_score = gb_model.score(X_test, y_test)
                    gb_pred = gb_model.predict(current_features)[0]
                    predictions.append(('GradientBoosting', gb_pred, gb_score))
                    model_scores.append(('GradientBoosting', gb_score))
                
            except Exception as e:
                frappe.log_error(f"Gradient Boosting model error: {str(e)}")
            
            # Ensemble prediction with weighted average
            if predictions:
                total_weight = sum(score for _, _, score in predictions)
                if total_weight > 0:
                    weighted_pred = sum(pred * score for _, pred, score in predictions) / total_weight
                    confidence = min(0.95, max(0.3, total_weight / len(predictions)))
                else:
                    weighted_pred = sum(pred for _, pred, _ in predictions) / len(predictions)
                    confidence = 0.5
                
                # Calculate prediction variance for confidence
                pred_values = [pred for _, pred, _ in predictions]
                if len(pred_values) > 1:
                    import numpy as np
                    pred_std = np.std(pred_values)
                    pred_mean = np.mean(pred_values)
                    cv = pred_std / pred_mean if pred_mean > 0 else 0
                    confidence *= (1 - min(0.5, cv))  # Reduce confidence if high variance
                
                return {
                    'price': flt(weighted_pred),
                    'confidence': confidence,
                    'model_used': 'ensemble',
                    'individual_predictions': predictions,
                    'model_scores': model_scores
                }
            else:
                return {
                    'price': features['current_price'].iloc[0],
                    'confidence': 0.3,
                    'model_used': 'fallback'
                }
            
        except Exception as e:
            frappe.log_error(f"Ensemble model training error: {str(e)}")
            return {
                'price': features['current_price'].iloc[0],
                'confidence': 0.3,
                'model_used': 'error_fallback'
            }

    def apply_risk_management(self, predicted_price, current_price, item_code, confidence):
        """Apply risk management rules and constraints"""
        try:
            base_cost = flt(predicted_price) / (1 + flt(self.doc.profit_margin or 20) / 100)
            
            # Risk constraints
            min_margin = 10  # Minimum 10% profit margin
            max_change_per_update = 25  # Maximum 25% price change
            min_confidence_threshold = 0.4
            
            # Calculate constraints
            min_price = base_cost * (1 + min_margin / 100)
            max_increase = current_price * (1 + max_change_per_update / 100)
            max_decrease = current_price * (1 - max_change_per_update / 100)
            
            # Apply constraints
            risk_adjusted_price = predicted_price
            risk_notes = []
            
            # Minimum margin constraint
            if risk_adjusted_price < min_price:
                risk_adjusted_price = min_price
                risk_notes.append(f"حداقل حاشیه سود {min_margin}% اعمال شد")
            
            # Maximum change constraint
            if risk_adjusted_price > max_increase:
                risk_adjusted_price = max_increase
                risk_notes.append(f"حداکثر افزایش {max_change_per_update}% اعمال شد")
            elif risk_adjusted_price < max_decrease:
                risk_adjusted_price = max_decrease
                risk_notes.append(f"حداکثر کاهش {max_change_per_update}% اعمال شد")
            
            # Confidence-based adjustment
            if confidence < min_confidence_threshold:
                # Reduce change magnitude for low confidence predictions
                change_ratio = (risk_adjusted_price - current_price) / current_price
                reduced_change = change_ratio * confidence / min_confidence_threshold
                risk_adjusted_price = current_price * (1 + reduced_change)
                risk_notes.append("تعدیل بر اساس اطمینان پایین مدل")
            
            return {
                'price': flt(risk_adjusted_price),
                'risk_notes': risk_notes,
                'constraints_applied': len(risk_notes) > 0
            }
            
        except Exception as e:
            frappe.log_error(f"Risk management error for {item_code}: {str(e)}")
            return {
                'price': flt(predicted_price),
                'risk_notes': [],
                'constraints_applied': False
            }

    def train_and_predict_price(self, training_data, features):
        """Enhanced ML prediction with ensemble and risk management"""
        try:
            # Get ensemble prediction
            ensemble_result = self.train_ensemble_models(training_data, features)
            predicted_price = ensemble_result['price']
            confidence = ensemble_result['confidence']
            
            # Apply risk management
            current_price = features['current_price'].iloc[0]
            risk_result = self.apply_risk_management(
                predicted_price, current_price, 
                features.get('item_code', 'unknown'), confidence
            )
            
            final_price = risk_result['price']
            
            # Log prediction details
            frappe.logger().info(f"ML Prediction - Original: {predicted_price:.0f}, "
                               f"Risk Adjusted: {final_price:.0f}, "
                               f"Confidence: {confidence:.2f}, "
                               f"Model: {ensemble_result['model_used']}")
            
            return flt(final_price)
            
        except Exception as e:
            frappe.log_error(f"Enhanced ML prediction error: {str(e)}")
            return features['current_price'].iloc[0]

    def rule_based_optimize_pricing(self, item):
        """Fallback rule-based pricing optimization"""
        # Get market data
        market_data = self.get_market_data(item.item_code)
        
        base_price = flt(item.total_cost)
        if base_price <= 0:
            return flt(item.selling_price or 0)
        
        # Apply profit margin
        if self.doc.profit_margin:
            base_price *= (1 + flt(self.doc.profit_margin) / 100)
        
        # Market adjustment
        market_price = flt(market_data.get('price', 0))
        if market_price > 0:
            # If market price is significantly higher, increase our price
            if market_price > base_price * 1.2:
                base_price = market_price * 0.95  # Price slightly below market
            # If market price is lower, stay competitive
            elif market_price < base_price * 0.8:
                base_price = max(market_price * 1.05, item.total_cost * 1.1)
        
        # Demand adjustment
        demand_score = flt(market_data.get('demand_score', 50))
        if demand_score > 70:  # High demand
            base_price *= 1.1
        elif demand_score < 30:  # Low demand
            base_price *= 0.95
        
        # Seasonality adjustment
        seasonality_factor = self.get_seasonality_factor(item.item_code)
        base_price *= seasonality_factor
        
        return base_price

    def get_seasonality_factor(self, item_code):
        """Calculate seasonality factor for pricing adjustment"""
        try:
            current_month = frappe.utils.nowdate().month
            
            # Default seasonal factors (can be customized per business)
            seasonal_factors = {
                1: 0.9,   # January - low season
                2: 0.95,  # February
                3: 1.0,   # March - normal
                4: 1.05,  # April
                5: 1.1,   # May - high season
                6: 1.15,  # June - peak
                7: 1.1,   # July
                8: 1.05,  # August
                9: 1.0,   # September
                10: 0.95, # October
                11: 0.9,  # November
                12: 1.2   # December - holiday season
            }
            
            return seasonal_factors.get(current_month, 1.0)
            
        except Exception as e:
            frappe.log_error(f"Seasonality factor error for {item_code}: {str(e)}")
            return 1.0

    def get_inventory_turnover(self, item_code):
        """Calculate inventory turnover rate"""
        try:
            # Get sales data for last 12 months
            sales_data = frappe.db.sql("""
                SELECT SUM(sii.qty) as total_sold
                FROM `tabSales Invoice Item` sii
                JOIN `tabSales Invoice` si ON si.name = sii.parent
                WHERE sii.item_code = %s 
                AND si.posting_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
                AND si.docstatus = 1
            """, (item_code,), as_dict=True)
            
            # Get average inventory
            avg_inventory = frappe.db.sql("""
                SELECT AVG(actual_qty) as avg_qty
                FROM `tabBin`
                WHERE item_code = %s
            """, (item_code,), as_dict=True)
            
            if sales_data and avg_inventory and avg_inventory[0].avg_qty:
                total_sold = flt(sales_data[0].total_sold or 0)
                avg_qty = flt(avg_inventory[0].avg_qty or 1)
                turnover = total_sold / avg_qty if avg_qty > 0 else 0
                return min(turnover, 50)  # Cap at reasonable level
            
            return 1.0  # Default turnover
            
        except Exception as e:
            frappe.log_error(f"Inventory turnover error for {item_code}: {str(e)}")
            return 1.0

    def estimate_price_elasticity(self, item_code):
        """Estimate price elasticity from historical data"""
        try:
            # Get price and quantity data for last 6 months
            price_qty_data = frappe.db.sql("""
                SELECT 
                    DATE_FORMAT(si.posting_date, '%%Y-%%m') as month,
                    AVG(sii.rate) as avg_price,
                    SUM(sii.qty) as total_qty
                FROM `tabSales Invoice Item` sii
                JOIN `tabSales Invoice` si ON si.name = sii.parent
                WHERE sii.item_code = %s 
                AND si.posting_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
                AND si.docstatus = 1
                GROUP BY DATE_FORMAT(si.posting_date, '%%Y-%%m')
                HAVING COUNT(*) >= 2
                ORDER BY month
            """, (item_code,), as_dict=True)
            
            if len(price_qty_data) < 3:
                return 1.0  # Neutral elasticity
            
            # Simple elasticity calculation
            prices = [flt(d.avg_price) for d in price_qty_data if d.avg_price > 0]
            quantities = [flt(d.total_qty) for d in price_qty_data if d.total_qty > 0]
            
            if len(prices) >= 3 and len(quantities) >= 3:
                # Calculate simple correlation as proxy for elasticity
                if SKLEARN_AVAILABLE:
                    import numpy as np
                    correlation = np.corrcoef(prices, quantities)[0, 1]
                    # Convert correlation to elasticity estimate
                    elasticity = abs(correlation) if not math.isnan(correlation) else 1.0
                    return max(0.1, min(3.0, elasticity))
            
            return 1.0
            
        except Exception as e:
            frappe.log_error(f"Price elasticity estimation error for {item_code}: {str(e)}")
            return 1.0

    def get_market_data(self, item_code, force_refresh=False):
        """Get real-time market data for item pricing"""
        cache_key = f"market_data_{item_code}"
        
        if not force_refresh and hasattr(self.doc, '_market_data_cache'):
            cached_data = self.doc._market_data_cache.get(cache_key)
            if cached_data:
                return cached_data
        
        # Initialize market data
        market_data = {
            'price': 0,
            'competitors': [],
            'demand_score': 50,
            'trend': 'stable'
        }
        
        try:
            # Get competitor prices from other price lists
            competitor_prices = frappe.db.sql("""
                SELECT ip.price_list_rate, pl.price_list_name
                FROM `tabItem Price` ip
                JOIN `tabPrice List` pl ON pl.name = ip.price_list
                WHERE ip.item_code = %s 
                AND ip.price_list != %s
                AND pl.enabled = 1
                ORDER BY ip.price_list_rate
            """, (item_code, self.doc.compare_with_price_list or ''), as_dict=True)
            
            if competitor_prices:
                prices = [flt(cp.price_list_rate) for cp in competitor_prices if cp.price_list_rate > 0]
                if prices:
                    market_data['price'] = sum(prices) / len(prices)  # Average price
                    market_data['competitors'] = competitor_prices
            
            # Get demand score from sales history
            recent_sales = frappe.db.sql("""
                SELECT COUNT(*) as sale_count, SUM(qty) as total_qty
                FROM `tabSales Invoice Item` sii
                JOIN `tabSales Invoice` si ON si.name = sii.parent
                WHERE sii.item_code = %s 
                AND si.posting_date >= DATE_SUB(CURDATE(), INTERVAL 3 MONTH)
                AND si.docstatus = 1
            """, (item_code,), as_dict=True)
            
            if recent_sales and recent_sales[0].sale_count:
                # Simple demand scoring based on sales frequency
                sale_count = recent_sales[0].sale_count
                if sale_count > 10:
                    market_data['demand_score'] = min(90, 50 + sale_count * 2)
                elif sale_count > 5:
                    market_data['demand_score'] = 60
                else:
                    market_data['demand_score'] = max(20, 50 - (5 - sale_count) * 5)
            
            # Cache the result
            if not hasattr(self.doc, '_market_data_cache'):
                self.doc._market_data_cache = {}
            self.doc._market_data_cache[cache_key] = market_data
            
        except Exception as e:
            frappe.log_error(f"Market data error for {item_code}: {str(e)}")
        
        return market_data

    def get_external_market_data(self, item_code):
        """Get market data from external APIs (placeholder for future integration)"""
        external_data = {
            'price': 0,
            'availability': 'unknown',
            'trend': 'stable',
            'last_updated': nowdate()
        }
        
        # Placeholder for external API integration
        # This could integrate with:
        # - Industry price databases
        # - Competitor websites
        # - Market research APIs
        # - Economic indicators
        
        try:
            # Example: Get data from a hypothetical API
            # response = requests.get(f"https://api.marketdata.com/items/{item_code}")
            # if response.status_code == 200:
            #     data = response.json()
            #     external_data['price'] = data.get('average_price', 0)
            #     external_data['trend'] = data.get('trend', 'stable')
            pass
        except:
            pass
        
        return external_data

    def calculate_competitor_analysis(self):
        """Analyze competitor pricing and market positioning"""
        if not self.doc.items:
            return
        
        competitor_analysis = []
        
        for item in self.doc.items:
            if not item.item_code:
                continue
                
            # Get market data
            market_data = self.get_market_data(item.item_code)
            
            analysis = {
                'item_code': item.item_code,
                'our_price': flt(item.selling_price or 0),
                'market_avg_price': flt(market_data.get('price', 0)),
                'competitor_count': len(market_data.get('competitors', [])),
                'position': 'unknown',
                'recommendation': ''
            }
            
            # Determine market position
            if analysis['market_avg_price'] > 0 and analysis['our_price'] > 0:
                price_ratio = analysis['our_price'] / analysis['market_avg_price']
                
                if price_ratio > 1.1:
                    analysis['position'] = 'premium'
                    analysis['recommendation'] = 'Consider reducing price for competitiveness'
                elif price_ratio < 0.9:
                    analysis['position'] = 'budget'
                    analysis['recommendation'] = 'Opportunity to increase price'
                else:
                    analysis['position'] = 'competitive'
                    analysis['recommendation'] = 'Price is well positioned'
            
            competitor_analysis.append(analysis)
        
        # Store analysis results
        self.doc.competitor_analysis_data = json.dumps(competitor_analysis, indent=2)

    def predict_demand_forecast(self, item_code, periods=12):
        """Predict demand forecast using time series analysis"""
        if not STATSMODELS_AVAILABLE:
            return self.simple_demand_forecast(item_code, periods)
        
        try:
            # Get historical sales data
            sales_data = frappe.db.sql("""
                SELECT 
                    DATE_FORMAT(si.posting_date, '%%Y-%%m') as month,
                    SUM(sii.qty) as total_qty
                FROM `tabSales Invoice Item` sii
                JOIN `tabSales Invoice` si ON si.name = sii.parent
                WHERE sii.item_code = %s 
                AND si.posting_date >= DATE_SUB(CURDATE(), INTERVAL 24 MONTH)
                AND si.docstatus = 1
                GROUP BY DATE_FORMAT(si.posting_date, '%%Y-%%m')
                ORDER BY month
            """, (item_code,), as_dict=True)
            
            if len(sales_data) < 6:  # Need at least 6 months of data
                return self.simple_demand_forecast(item_code, periods)
            
            # Prepare time series data
            df = pd.DataFrame(sales_data)
            df['month'] = pd.to_datetime(df['month'])
            df.set_index('month', inplace=True)
            df = df.asfreq('M', fill_value=0)  # Monthly frequency
            
            # Apply Exponential Smoothing
            model = ExponentialSmoothing(
                df['total_qty'],
                trend='add',
                seasonal='add',
                seasonal_periods=12
            )
            
            fitted_model = model.fit()
            forecast = fitted_model.forecast(periods)
            
            # Convert to list with dates
            forecast_data = []
            current_date = df.index[-1]
            
            for i, value in enumerate(forecast):
                forecast_date = current_date + pd.DateOffset(months=i+1)
                forecast_data.append({
                    'date': forecast_date.strftime('%Y-%m'),
                    'predicted_demand': max(0, flt(value)),
                    'confidence': 'medium'
                })
            
            return forecast_data
            
        except Exception as e:
            frappe.log_error(f"Demand forecast error for {item_code}: {str(e)}")
            return self.simple_demand_forecast(item_code, periods)

    def simple_demand_forecast(self, item_code, periods=12):
        """Simple demand forecast using moving average"""
        try:
            # Get last 12 months average
            avg_sales = frappe.db.sql("""
                SELECT AVG(monthly_qty) as avg_demand
                FROM (
                    SELECT SUM(sii.qty) as monthly_qty
                    FROM `tabSales Invoice Item` sii
                    JOIN `tabSales Invoice` si ON si.name = sii.parent
                    WHERE sii.item_code = %s 
                    AND si.posting_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
                    AND si.docstatus = 1
                    GROUP BY DATE_FORMAT(si.posting_date, '%%Y-%%m')
                ) as monthly_sales
            """, (item_code,))[0][0] or 0
            
            # Simple forecast with seasonal adjustment
            forecast_data = []
            base_demand = flt(avg_sales)
            
            for i in range(periods):
                # Simple seasonality (higher in certain months)
                month = ((getdate().month + i - 1) % 12) + 1
                seasonal_factor = 1.0
                
                # Example seasonality (adjust based on business)
                if month in [11, 12, 1]:  # Winter months
                    seasonal_factor = 1.2
                elif month in [6, 7, 8]:  # Summer months
                    seasonal_factor = 0.8
                
                predicted_demand = base_demand * seasonal_factor
                
                forecast_data.append({
                    'date': add_months(getdate(), i+1).strftime('%Y-%m'),
                    'predicted_demand': max(0, predicted_demand),
                    'confidence': 'low'
                })
            
            return forecast_data
            
        except Exception as e:
            frappe.log_error(f"Simple demand forecast error for {item_code}: {str(e)}")
            return []

    def get_seasonality_factor(self, item_code):
        """Calculate seasonality factor for current month"""
        try:
            current_month = getdate().month
            
            # Get sales data by month for last 2 years
            monthly_sales = frappe.db.sql("""
                SELECT 
                    MONTH(si.posting_date) as month,
                    AVG(sii.qty) as avg_qty
                FROM `tabSales Invoice Item` sii
                JOIN `tabSales Invoice` si ON si.name = sii.parent
                WHERE sii.item_code = %s 
                AND si.posting_date >= DATE_SUB(CURDATE(), INTERVAL 24 MONTH)
                AND si.docstatus = 1
                GROUP BY MONTH(si.posting_date)
            """, (item_code,), as_dict=True)
            
            if not monthly_sales:
                return 1.0
            
            # Calculate average and current month factor
            total_avg = sum(flt(ms.avg_qty) for ms in monthly_sales) / len(monthly_sales)
            current_month_avg = next((flt(ms.avg_qty) for ms in monthly_sales if ms.month == current_month), total_avg)
            
            if total_avg > 0:
                return current_month_avg / total_avg
            else:
                return 1.0
                
        except Exception as e:
            frappe.log_error(f"Seasonality calculation error for {item_code}: {str(e)}")
            return 1.0

    def get_inventory_turnover(self, item_code):
        """Calculate inventory turnover ratio"""
        try:
            # Get average inventory and COGS
            inventory_data = frappe.db.sql("""
                SELECT 
                    AVG(actual_qty) as avg_inventory,
                    (SELECT SUM(sii.qty * sii.rate) 
                     FROM `tabSales Invoice Item` sii
                     JOIN `tabSales Invoice` si ON si.name = sii.parent
                     WHERE sii.item_code = %s 
                     AND si.posting_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
                     AND si.docstatus = 1) as cogs
                FROM `tabBin`
                WHERE item_code = %s
                AND actual_qty > 0
            """, (item_code, item_code), as_dict=True)
            
            if inventory_data and inventory_data[0].avg_inventory and inventory_data[0].cogs:
                turnover = flt(inventory_data[0].cogs) / flt(inventory_data[0].avg_inventory)
                return max(0.1, min(10.0, turnover))  # Limit between 0.1 and 10
            else:
                return 1.0
                
        except Exception as e:
            frappe.log_error(f"Inventory turnover calculation error for {item_code}: {str(e)}")
            return 1.0

    def estimate_price_elasticity(self, item_code):
        """Estimate price elasticity of demand"""
        try:
            # Get price and quantity data over time
            price_qty_data = frappe.db.sql("""
                SELECT 
                    DATE_FORMAT(si.posting_date, '%%Y-%%m') as month,
                    AVG(sii.rate) as avg_price,
                    SUM(sii.qty) as total_qty
                FROM `tabSales Invoice Item` sii
                JOIN `tabSales Invoice` si ON si.name = sii.parent
                WHERE sii.item_code = %s 
                AND si.posting_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
                AND si.docstatus = 1
                GROUP BY DATE_FORMAT(si.posting_date, '%%Y-%%m')
                HAVING COUNT(*) >= 3
                ORDER BY month
            """, (item_code,), as_dict=True)
            
            if len(price_qty_data) < 3:
                return 1.0  # Neutral elasticity
            
            # Simple elasticity calculation
            prices = [flt(d.avg_price) for d in price_qty_data if d.avg_price > 0]
            quantities = [flt(d.total_qty) for d in price_qty_data if d.total_qty > 0]
            
            if len(prices) >= 3 and len(quantities) >= 3:
                # Calculate correlation coefficient as proxy for elasticity
                if SKLEARN_AVAILABLE:
                    correlation = np.corrcoef(prices, quantities)[0, 1]
                    # Convert correlation to elasticity estimate
                    elasticity = abs(correlation) if not math.isnan(correlation) else 1.0
                    return max(0.1, min(3.0, elasticity))
            
            return 1.0
            
        except Exception as e:
            frappe.log_error(f"Price elasticity calculation error for {item_code}: {str(e)}")
            return 1.0
    
    def ai_optimize_all_items(self):
        """AI optimization for all items"""
        try:
            items_results = []
            for item in self.doc.items:
                if item.item_code and item.total_cost > 0:
                    optimized_price = self.ai_optimize_pricing(item)
                    change_percent = ((optimized_price - item.selling_price) / item.selling_price * 100) if item.selling_price > 0 else 0
                    
                    # Determine reason for change
                    reason = "بهینه‌سازی AI"
                    if change_percent > 5:
                        reason = "افزایش قیمت توصیه شده"
                    elif change_percent < -5:
                        reason = "کاهش قیمت توصیه شده"
                    else:
                        reason = "قیمت مناسب"
                    
                    items_results.append({
                        'item_code': item.item_code,
                        'old_price': item.selling_price,
                        'new_price': optimized_price,
                        'change': change_percent,
                        'reason': reason
                    })
            
            return {
                'items': items_results,
                'total_items': len(items_results),
                'status': 'success'
            }
        except Exception as e:
            frappe.log_error(f"AI optimize all items error: {str(e)}")
            return {
                'items': [],
                'total_items': 0,
                'status': 'error',
                'message': str(e)
            }
    
    def get_real_time_market_data(self, item_codes=None):
        """Get real-time market data for items"""
        try:
            if not item_codes:
                item_codes = [item.item_code for item in self.doc.items if item.item_code]
            
            market_data = {}
            for item_code in item_codes:
                market_data[item_code] = self.get_market_data(item_code, force_refresh=True)
            
            return market_data
        except Exception as e:
            frappe.log_error(f"Real-time market data error: {str(e)}")
            return {}
    
    def calculate_all_seasonal_factors(self):
        """Calculate seasonal factors for all items"""
        try:
            results = []
            for item in self.doc.items:
                if item.item_code:
                    seasonal_factor = self.calculate_dynamic_seasonal_factor(item.item_code)
                    results.append({
                        'item_code': item.item_code,
                        'seasonal_factor': seasonal_factor,
                        'recommendation': 'increase_price' if seasonal_factor > 10 else 'decrease_price' if seasonal_factor < -10 else 'maintain_price'
                    })
            return results
        except Exception as e:
            frappe.log_error(f"Calculate all seasonal factors error: {str(e)}")
            return []
    
    def get_ml_pricing_insights(self):
        """Get ML-based pricing insights"""
        try:
            insights = {
                'total_items': len(self.doc.items),
                'ai_recommendations': [],
                'market_analysis': {},
                'risk_assessment': []
            }
            
            for item in self.doc.items:
                if item.item_code and item.total_cost > 0:
                    # Get AI recommendation
                    ai_price = self.ai_optimize_pricing(item)
                    current_margin = ((item.selling_price - item.total_cost) / item.total_cost * 100) if item.total_cost > 0 else 0
                    ai_margin = ((ai_price - item.total_cost) / item.total_cost * 100) if item.total_cost > 0 else 0
                    
                    insights['ai_recommendations'].append({
                        'item_code': item.item_code,
                        'current_price': item.selling_price,
                        'ai_price': ai_price,
                        'current_margin': current_margin,
                        'ai_margin': ai_margin,
                        'confidence': 'high' if abs(ai_price - item.selling_price) < item.selling_price * 0.1 else 'medium'
                    })
            
            return insights
        except Exception as e:
            frappe.log_error(f"ML pricing insights error: {str(e)}")
            return {'error': str(e)}
    
    def get_demand_forecast(self, item_code, periods=12):
        """Get demand forecast for specific item"""
        return self.predict_demand_forecast(item_code, periods)
    
    def get_inventory_optimization(self, item_code):
        """Get inventory optimization suggestions"""
        try:
            # Get historical sales data
            sales_data = frappe.db.sql("""
                SELECT 
                    AVG(sii.qty) as avg_monthly_sales,
                    STDDEV(sii.qty) as sales_volatility,
                    COUNT(*) as order_frequency
                FROM `tabSales Invoice Item` sii
                JOIN `tabSales Invoice` si ON si.name = sii.parent
                WHERE sii.item_code = %s 
                AND si.posting_date >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
                AND si.docstatus = 1
            """, (item_code,), as_dict=True)
            
            if sales_data and sales_data[0].avg_monthly_sales:
                avg_sales = flt(sales_data[0].avg_monthly_sales)
                volatility = flt(sales_data[0].sales_volatility) or avg_sales * 0.2
                
                # Simple inventory optimization
                safety_stock = volatility * 2  # 2 standard deviations
                reorder_point = avg_sales * 1.5 + safety_stock
                optimal_order_qty = avg_sales * 3  # 3 months supply
                
                return {
                    'item_code': item_code,
                    'avg_monthly_sales': avg_sales,
                    'safety_stock': safety_stock,
                    'reorder_point': reorder_point,
                    'optimal_order_qty': optimal_order_qty,
                    'recommendation': f"Maintain {optimal_order_qty:.0f} units, reorder at {reorder_point:.0f} units"
                }
            
            return {'item_code': item_code, 'recommendation': 'Insufficient data for optimization'}
            
        except Exception as e:
            frappe.log_error(f"Inventory optimization error for {item_code}: {str(e)}")
            return {'error': str(e)}
    
    def run_price_elasticity_analysis(self, item_code):
        """Run price elasticity analysis for item"""
        try:
            elasticity = self.calculate_price_elasticity(item_code)
            
            # Interpret elasticity
            if elasticity > 1.5:
                interpretation = "Highly elastic - customers very sensitive to price changes"
                recommendation = "Consider competitive pricing strategy"
            elif elasticity > 1.0:
                interpretation = "Elastic - customers moderately sensitive to price changes"
                recommendation = "Balance between margin and volume"
            elif elasticity > 0.5:
                interpretation = "Inelastic - customers less sensitive to price changes"
                recommendation = "Opportunity for premium pricing"
            else:
                interpretation = "Highly inelastic - customers not sensitive to price changes"
                recommendation = "Strong pricing power - maximize margins"
            
            return {
                'item_code': item_code,
                'elasticity': elasticity,
                'interpretation': interpretation,
                'recommendation': recommendation
            }
            
        except Exception as e:
            frappe.log_error(f"Price elasticity analysis error for {item_code}: {str(e)}")
            return {'error': str(e)}
    
    def get_advanced_competitor_analysis(self):
        """Get advanced competitor analysis"""
        try:
            analysis = {
                'competitive_position': 'unknown',
                'price_gaps': [],
                'market_opportunities': [],
                'threats': []
            }
            
            competitive_items = 0
            total_items = len(self.doc.items)
            
            for item in self.doc.items:
                if item.item_code:
                    market_data = self.get_market_data(item.item_code)
                    if market_data.get('market_average', 0) > 0:
                        price_ratio = item.selling_price / market_data['market_average']
                        
                        if price_ratio < 0.9:
                            competitive_items += 1
                            analysis['market_opportunities'].append({
                                'item_code': item.item_code,
                                'opportunity': 'Price increase potential',
                                'current_price': item.selling_price,
                                'market_average': market_data['market_average'],
                                'potential_increase': market_data['market_average'] * 0.95 - item.selling_price
                            })
                        elif price_ratio > 1.2:
                            analysis['threats'].append({
                                'item_code': item.item_code,
                                'threat': 'Above market pricing',
                                'current_price': item.selling_price,
                                'market_average': market_data['market_average'],
                                'risk_level': 'high' if price_ratio > 1.5 else 'medium'
                            })
            
            # Determine competitive position
            if competitive_items > total_items * 0.7:
                analysis['competitive_position'] = 'highly_competitive'
            elif competitive_items > total_items * 0.4:
                analysis['competitive_position'] = 'competitive'
            else:
                analysis['competitive_position'] = 'premium'
            
            return analysis
            
        except Exception as e:
            frappe.log_error(f"Advanced competitor analysis error: {str(e)}")
            return {'error': str(e)}
    
    def integrate_real_data_for_pricing(self):
        """Integrate real purchase invoice data into pricing"""
        try:
            results = []
            
            for item in self.doc.items:
                if item.item_code:
                    # Get recent purchase data
                    purchase_data = frappe.db.sql("""
                        SELECT 
                            AVG(pii.rate) as avg_purchase_rate,
                            MAX(pi.posting_date) as last_purchase_date,
                            COUNT(*) as purchase_count
                        FROM `tabPurchase Invoice Item` pii
                        JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
                        WHERE pii.item_code = %s 
                        AND pi.posting_date >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
                        AND pi.docstatus = 1
                    """, (item.item_code,), as_dict=True)
                    
                    if purchase_data and purchase_data[0].avg_purchase_rate:
                        real_cost = flt(purchase_data[0].avg_purchase_rate)
                        current_cost = flt(item.total_cost)
                        cost_variance = ((real_cost - current_cost) / current_cost * 100) if current_cost > 0 else 0
                        
                        results.append({
                            'item_code': item.item_code,
                            'current_cost': current_cost,
                            'real_cost': real_cost,
                            'cost_variance': cost_variance,
                            'last_purchase': purchase_data[0].last_purchase_date,
                            'purchase_count': purchase_data[0].purchase_count,
                            'recommendation': 'update_cost' if abs(cost_variance) > 10 else 'cost_accurate'
                        })
            
            return results
            
        except Exception as e:
            frappe.log_error(f"Real data integration error: {str(e)}")
            return {'error': str(e)}
