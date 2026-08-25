// ==================== ادامه نمودارهای پیشرفته ====================

function render_sales_forecast(frm) {
    /**
     * پیش‌بینی فروش و سود بر اساس داده‌های واقعی
     */
    
    // دریافت آیتم‌های فروخته شده از Sales Invoice Items
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Sales Invoice Item',
            filters: {
                docstatus: 1
            },
            fields: ['item_code', 'item_name', 'qty', 'rate', 'amount', 'parent', 'creation'],
            limit: 50000
        },
        callback: function(r) {
            let item_sales_history = {};
            let monthly_totals = {};
            
            // جمع‌آوری تاریخچه فروش هر محصول
            if (r.message && r.message.length > 0) {
                r.message.forEach(item => {
                    const month_key = item.creation.slice(0, 7);
                    
                    if (!item_sales_history[item.item_code]) {
                        item_sales_history[item.item_code] = {
                            item_name: item.item_name,
                            monthly_qty: {},
                            total_qty: 0,
                            total_amount: 0
                        };
                    }
                    
                    item_sales_history[item.item_code].monthly_qty[month_key] = 
                        (item_sales_history[item.item_code].monthly_qty[month_key] || 0) + (item.qty || 0);
                    item_sales_history[item.item_code].total_qty += (item.qty || 0);
                    item_sales_history[item.item_code].total_amount += (item.amount || 0);
                    
                    monthly_totals[month_key] = (monthly_totals[month_key] || 0) + (item.amount || 0);
                });
            }
            
            const months_count = Object.keys(monthly_totals).length || 1;
            
            // محاسبه پیش‌بینی سود بر اساس قیمت‌های جدید
            let next_month_forecast = {
                total_revenue: 0,
                total_cost: 0,
                total_profit: 0,
                items: []
            };
            
            const current_items = frm.doc.items || [];
            current_items.forEach(current_item => {
                const history = item_sales_history[current_item.item_code];
                if (history) {
                    // میانگین تعداد فروش ماهانه
                    const avg_monthly_qty = history.total_qty / months_count;
                    
                    // پیش‌بینی فروش با قیمت جدید
                    const new_price = current_item.final_selected_price || current_item.selling_price || 0;
                    const forecasted_revenue = avg_monthly_qty * new_price;
                    const forecasted_cost = avg_monthly_qty * (current_item.total_cost || 0);
                    const forecasted_profit = forecasted_revenue - forecasted_cost - (avg_monthly_qty * (current_item.required_markup_amount || 0));
                    
                    next_month_forecast.total_revenue += forecasted_revenue;
                    next_month_forecast.total_cost += forecasted_cost;
                    next_month_forecast.total_profit += forecasted_profit;
                    
                    next_month_forecast.items.push({
                        item_code: current_item.item_code,
                        item_name: current_item.item_name,
                        avg_monthly_qty: avg_monthly_qty,
                        new_price: new_price,
                        forecasted_revenue: forecasted_revenue,
                        forecasted_profit: forecasted_profit
                    });
                }
            });
            
            // مرتب‌سازی بر اساس سود
            next_month_forecast.items.sort((a, b) => b.forecasted_profit - a.forecasted_profit);
            
            // ساخت HTML
            let items_table = '';
            next_month_forecast.items.slice(0, 10).forEach((item, idx) => {
                items_table += `
                    <tr>
                        <td>${idx + 1}</td>
                        <td>${item.item_name}</td>
                        <td class="text-right">${item.avg_monthly_qty.toFixed(0)}</td>
                        <td class="text-right">${format_currency(item.new_price)} ریال</td>
                        <td class="text-right">${format_currency(item.forecasted_revenue)} ریال</td>
                        <td class="text-right" style="color: ${item.forecasted_profit > 0 ? '#27ae60' : '#e74c3c'}; font-weight: bold;">
                            ${format_currency(item.forecasted_profit)} ریال
                        </td>
                    </tr>
                `;
            });
            
            const profit_margin = next_month_forecast.total_cost > 0 ? 
                (next_month_forecast.total_profit / next_month_forecast.total_cost * 100) : 0;
            
            const html = `
                <div class="forecast-container" style="background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                    <h5 style="text-align: center; margin-bottom: 15px; color: #2c3e50;">پیش‌بینی سود ماه آینده با قیمت‌های جدید</h5>
                    
                    <div style="display: flex; justify-content: space-around; margin-bottom: 20px; padding: 15px; background: #f8f9fa; border-radius: 8px;">
                        <div style="text-align: center;">
                            <div style="color: #7f8c8d; font-size: 12px;">فروش پیش‌بینی</div>
                            <div style="color: #3498db; font-size: 18px; font-weight: bold;">${format_currency(next_month_forecast.total_revenue)} ریال</div>
                        </div>
                        <div style="text-align: center;">
                            <div style="color: #7f8c8d; font-size: 12px;">هزینه کل</div>
                            <div style="color: #e74c3c; font-size: 18px; font-weight: bold;">${format_currency(next_month_forecast.total_cost)} ریال</div>
                        </div>
                        <div style="text-align: center;">
                            <div style="color: #7f8c8d; font-size: 12px;">سود پیش‌بینی</div>
                            <div style="color: #27ae60; font-size: 18px; font-weight: bold;">${format_currency(next_month_forecast.total_profit)} ریال</div>
                        </div>
                        <div style="text-align: center;">
                            <div style="color: #7f8c8d; font-size: 12px;">حاشیه سود</div>
                            <div style="color: #9b59b6; font-size: 18px; font-weight: bold;">${profit_margin.toFixed(1)}%</div>
                        </div>
                    </div>
                    
                    <p style="text-align: center; color: #7f8c8d; font-size: 13px; margin-bottom: 15px;">
                        بر اساس میانگین فروش ${months_count} ماه گذشته
                    </p>
                    
                    <table class="table table-striped" style="margin-top: 20px;">
                        <thead>
                            <tr style="background-color: #f8f9fa;">
                                <th>رتبه</th>
                                <th>محصول</th>
                                <th class="text-right">میانگین فروش/ماه</th>
                                <th class="text-right">قیمت جدید</th>
                                <th class="text-right">فروش پیش‌بینی</th>
                                <th class="text-right">سود پیش‌بینی</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${items_table}
                        </tbody>
                    </table>
                    
                    <div style="margin-top: 30px;">
                        <h6 style="text-align: center; margin-bottom: 15px; color: #2c3e50;">پیش‌بینی سود 12 ماه آینده</h6>
                        <canvas id="forecast-chart" width="600" height="300"></canvas>
                    </div>
                </div>
            `;
            
            frm.fields_dict.sales_forecast_html.$wrapper.html(html);
            
            // رندر نمودار 12 ماهه
            setTimeout(() => {
                const monthly_profit_forecast = [];
                const month_names = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'];
                
                for (let i = 1; i <= 12; i++) {
                    const seasonal_factor = 1 + Math.sin((i - 1) * Math.PI / 6) * 0.15;
                    const growth_factor = 1 + (i * 0.01);
                    monthly_profit_forecast.push({
                        month: month_names[i - 1],
                        forecast: next_month_forecast.total_profit * seasonal_factor * growth_factor
                    });
                }
                render_forecast_chartjs(monthly_profit_forecast);
            }, 100);
        }
    });
}

function render_roi_analysis(frm) {
    /**
     * تحلیل ROI محصولات
     */
    
    const items = frm.doc.items || [];
    
    // محاسبه ROI برای هر محصول با استفاده از سود واقعی
    const roi_data = items.map(item => {
        const investment = item.total_cost || 0;
        // سود واقعی = قیمت نهایی - هزینه - افزایش برای تخفیف
        const real_profit = (item.final_selected_price || item.selling_price || 0) - investment - (item.required_markup_amount || 0);
        const roi = investment > 0 ? (real_profit / investment) * 100 : 0;
        
        return {
            item_name: item.item_name || item.item_code,
            roi: roi,
            profit: real_profit,
            investment: investment
        };
    }).sort((a, b) => b.roi - a.roi);
    
    let table_rows = '';
    roi_data.slice(0, 10).forEach((item, index) => {
        const roi_color = item.roi > 20 ? '#27ae60' : item.roi > 10 ? '#f39c12' : '#e74c3c';
        table_rows += `
            <tr>
                <td>${index + 1}</td>
                <td>${item.item_name}</td>
                <td class="text-right">${format_currency(item.investment)} ریال</td>
                <td class="text-right">${format_currency(item.profit)} ریال</td>
                <td class="text-right" style="color: ${roi_color}; font-weight: bold;">${item.roi.toFixed(1)}%</td>
            </tr>
        `;
    });
    
    const html = `
        <div class="roi-container" style="background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
            <h5 style="text-align: center; margin-bottom: 20px; color: #2c3e50;">تحلیل ROI محصولات (بالاترین 10)</h5>
            <table class="table table-striped">
                <thead>
                    <tr style="background-color: #f8f9fa;">
                        <th>رتبه</th>
                        <th>نام محصول</th>
                        <th class="text-right">سرمایه‌گذاری</th>
                        <th class="text-right">سود</th>
                        <th class="text-right">ROI</th>
                    </tr>
                </thead>
                <tbody>
                    ${table_rows}
                </tbody>
            </table>
        </div>
    `;
    
    frm.fields_dict.roi_analysis_html.$wrapper.html(html);
}

function render_product_ranking(frm) {
    /**
     * رنکینگ محصولات و فرصت‌های افزایش قیمت
     */
    
    const items = frm.doc.items || [];
    
    // رنکینگ بر اساس حاشیه سود
    const ranking_data = items.map(item => {
        const cost = item.total_cost || 0;
        const price = item.selling_price || 0;
        const margin = cost > 0 ? ((price - cost) / cost) * 100 : 0;
        const profit = price - cost;
        
        // تخمین فرصت افزایش قیمت (بر اساس حاشیه سود پایین)
        let price_opportunity = 0;
        if (margin < 15) {
            price_opportunity = (cost * 0.2) - profit; // هدف 20% حاشیه سود
        }
        
        return {
            item_name: item.item_name || item.item_code,
            current_price: price,
            margin: margin,
            profit: profit,
            price_opportunity: Math.max(0, price_opportunity),
            potential_price: price + Math.max(0, price_opportunity)
        };
    }).sort((a, b) => b.price_opportunity - a.price_opportunity);
    
    let ranking_rows = '';
    ranking_data.slice(0, 10).forEach((item, index) => {
        const margin_color = item.margin > 20 ? '#27ae60' : item.margin > 10 ? '#f39c12' : '#e74c3c';
        const opportunity_color = item.price_opportunity > 0 ? '#e74c3c' : '#27ae60';
        
        ranking_rows += `
            <tr>
                <td>${index + 1}</td>
                <td>${item.item_name}</td>
                <td class="text-right">${format_currency(item.current_price)} ریال</td>
                <td class="text-right" style="color: ${margin_color}; font-weight: bold;">${item.margin.toFixed(1)}%</td>
                <td class="text-right" style="color: ${opportunity_color}; font-weight: bold;">${format_currency(item.price_opportunity)} ریال</td>
                <td class="text-right">${format_currency(item.potential_price)} ریال</td>
            </tr>
        `;
    });
    
    const html = `
        <div class="ranking-container" style="background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
            <h5 style="text-align: center; margin-bottom: 20px; color: #2c3e50;">رنکینگ فرصت‌های افزایش قیمت</h5>
            <table class="table table-striped">
                <thead>
                    <tr style="background-color: #f8f9fa;">
                        <th>رتبه</th>
                        <th>نام محصول</th>
                        <th class="text-right">قیمت فعلی</th>
                        <th class="text-right">حاشیه سود</th>
                        <th class="text-right">فرصت افزایش</th>
                        <th class="text-right">قیمت پیشنهادی</th>
                    </tr>
                </thead>
                <tbody>
                    ${ranking_rows}
                </tbody>
            </table>
            <div class="alert alert-info" style="margin-top: 15px;">
                <small><strong>نکته:</strong> فرصت‌های افزایش قیمت بر اساس هدف 20% حاشیه سود محاسبه شده‌اند.</small>
            </div>
        </div>
    `;
    
    frm.fields_dict.product_ranking_html.$wrapper.html(html);
}

// ==================== توابع رندر Chart.js ====================

function render_waterfall_chartjs(costs, selling_price) {
    /**
     * رندر نمودار آبشاری با Chart.js
     */
    
    const canvas = document.getElementById('waterfall-chart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    if (window.waterfallChart) {
        window.waterfallChart.destroy();
    }
    
    const data_points = [
        { label: 'مواد اولیه', value: costs.material, color: '#3498db' },
        { label: 'نیروی کار', value: costs.labor, color: '#e74c3c' },
        { label: 'سربار', value: costs.overhead, color: '#f39c12' },
        { label: 'برق', value: costs.electricity, color: '#9b59b6' },
        { label: 'اجاره', value: costs.rent, color: '#1abc9c' },
        { label: 'پیمانکاری', value: costs.subcontracting, color: '#34495e' }
    ];
    
    let cumulative = 0;
    const chart_data = [];
    
    data_points.forEach(point => {
        chart_data.push({
            x: point.label,
            y: [cumulative, cumulative + point.value],
            backgroundColor: point.color
        });
        cumulative += point.value;
    });
    
    // اضافه کردن قیمت فروش
    chart_data.push({
        x: 'قیمت فروش',
        y: [0, selling_price],
        backgroundColor: '#27ae60'
    });
    
    window.waterfallChart = new Chart(ctx, {
        type: 'bar',
        data: {
            datasets: [{
                label: 'هزینه‌ها',
                data: chart_data,
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const value = context.parsed.y[1] - context.parsed.y[0];
                            return `${context.label}: ${format_currency(value)} ریال`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return format_currency(value) + ' ریال';
                        }
                    }
                }
            }
        }
    });
}

function render_bubble_chartjs(items) {
    /**
     * رندر نمودار حبابی با Chart.js
     */
    
    const canvas = document.getElementById('bubble-chart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    if (window.bubbleChart) {
        window.bubbleChart.destroy();
    }
    
    const bubble_data = items.map(item => {
        const profit_margin = ((item.selling_price || 0) - (item.total_cost || 0)) / (item.total_cost || 1) * 100;
        return {
            x: item.selling_price || 0,
            y: profit_margin,
            r: Math.sqrt((item.total_cost || 0) / 1000000) // اندازه حباب بر اساس هزینه
        };
    });
    
    window.bubbleChart = new Chart(ctx, {
        type: 'bubble',
        data: {
            datasets: [{
                label: 'محصولات',
                data: bubble_data,
                backgroundColor: 'rgba(52, 152, 219, 0.6)',
                borderColor: 'rgba(52, 152, 219, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            plugins: {
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `قیمت: ${format_currency(context.parsed.x)} ریال - حاشیه: ${context.parsed.y.toFixed(1)}%`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'قیمت فروش (ریال)'
                    },
                    ticks: {
                        callback: function(value) {
                            return format_currency(value) + ' ریال';
                        }
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'حاشیه سود (%)'
                    }
                }
            }
        }
    });
}

function render_forecast_chartjs(forecast_data) {
    /**
     * رندر نمودار پیش‌بینی سود
     */
    
    const canvas = document.getElementById('forecast-chart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    if (window.forecastChart) {
        window.forecastChart.destroy();
    }
    
    const months = forecast_data.map(d => d.month);
    
    window.forecastChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: months,
            datasets: [{
                label: 'پیش‌بینی سود',
                data: forecast_data.map(d => d.forecast),
                borderColor: '#27ae60',
                backgroundColor: 'rgba(39, 174, 96, 0.1)',
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointRadius: 5,
                pointHoverRadius: 7
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `سود پیش‌بینی: ${format_currency(context.parsed.y)} ریال`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return format_currency(value) + ' ریال';
                        }
                    }
                }
            }
        }
    });
}
