// ==================== ادامه نمودارهای پیشرفته ====================

function render_sales_forecast(frm) {
    /**
     * پیش‌بینی فروش ماهانه
     */
    
    const items = frm.doc.items || [];
    const total_selling_price = items.reduce((sum, item) => sum + (item.selling_price || 0), 0);
    
    // پیش‌بینی بر اساس روند فعلی
    const monthly_forecast = [];
    const base_monthly = total_selling_price * 0.1; // فرض 10% فروش ماهانه
    
    for (let i = 1; i <= 12; i++) {
        const seasonal_factor = 1 + Math.sin((i - 1) * Math.PI / 6) * 0.2; // تغییرات فصلی
        const growth_factor = 1 + (i * 0.02); // رشد 2% ماهانه
        monthly_forecast.push({
            month: i,
            forecast: base_monthly * seasonal_factor * growth_factor
        });
    }
    
    const html = `
        <div class="forecast-container" style="background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
            <h5 style="text-align: center; margin-bottom: 20px; color: #2c3e50;">پیش‌بینی فروش 12 ماه آینده</h5>
            <canvas id="forecast-chart" width="600" height="400"></canvas>
        </div>
    `;
    
    frm.fields_dict.sales_forecast_html.$wrapper.html(html);
    
    setTimeout(() => {
        render_forecast_chartjs(monthly_forecast);
    }, 100);
}

function render_roi_analysis(frm) {
    /**
     * تحلیل ROI محصولات
     */
    
    const items = frm.doc.items || [];
    
    // محاسبه ROI برای هر محصول
    const roi_data = items.map(item => {
        const investment = item.total_cost || 0;
        const profit = (item.selling_price || 0) - investment;
        const roi = investment > 0 ? (profit / investment) * 100 : 0;
        
        return {
            item_name: item.item_name || item.item_code,
            roi: roi,
            profit: profit,
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
                <td class="text-right">${format_currency(item.investment)}</td>
                <td class="text-right">${format_currency(item.profit)}</td>
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
                <td class="text-right">${format_currency(item.current_price)}</td>
                <td class="text-right" style="color: ${margin_color}; font-weight: bold;">${item.margin.toFixed(1)}%</td>
                <td class="text-right" style="color: ${opportunity_color}; font-weight: bold;">${format_currency(item.price_opportunity)}</td>
                <td class="text-right">${format_currency(item.potential_price)}</td>
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
                            return `قیمت: ${format_currency(context.parsed.x)} - حاشیه: ${context.parsed.y.toFixed(1)}%`;
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
                            return format_currency(value);
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
     * رندر نمودار پیش‌بینی فروش
     */
    
    const canvas = document.getElementById('forecast-chart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    
    if (window.forecastChart) {
        window.forecastChart.destroy();
    }
    
    const months = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 
                   'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'];
    
    window.forecastChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: months,
            datasets: [{
                label: 'پیش‌بینی فروش',
                data: forecast_data.map(d => d.forecast),
                borderColor: '#27ae60',
                backgroundColor: 'rgba(39, 174, 96, 0.1)',
                borderWidth: 3,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            plugins: {
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `پیش‌بینی: ${format_currency(context.parsed.y)} ریال`;
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
