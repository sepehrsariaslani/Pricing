frappe.ui.form.on('Competitor Analysis', {
    refresh: function(frm) {
        // Add custom buttons
        if (frm.doc.docstatus === 0) {
            // دکمه‌های کرال هوشمند
            if (frm.doc.website_url) {
                frm.add_custom_button(__('شروع کرال هوشمند'), function() {
                    start_intelligent_crawl(frm);
                }, __('وب کرالر'));
                
                frm.add_custom_button(__('تحلیل SEO'), function() {
                    analyze_seo_data(frm);
                }, __('وب کرالر'));
                
                frm.add_custom_button(__('نظارت بر قیمت‌ها'), function() {
                    monitor_price_changes(frm);
                }, __('وب کرالر'));
                
                frm.add_custom_button(__('کرال محصول از لینک'), function() {
                    crawl_product_from_url(frm);
                }, __('وب کرالر'));
            }
            
            frm.add_custom_button(__('به‌روزرسانی قیمت محصولات'), function() {
                frm.call('update_product_prices').then(r => {
                    if (r.message && r.message.status === 'success') {
                        frappe.msgprint(r.message.message);
                        frm.refresh();
                    }
                });
            });
            
            frm.add_custom_button(__('تولید گزارش تحلیل'), function() {
                generate_competitor_analysis_report(frm);
            });
            
            frm.add_custom_button(__('زمان‌بندی بررسی بعدی'), function() {
                schedule_next_review_dialog(frm);
            });
            
            frm.add_custom_button(__('داشبورد رقبا'), function() {
                show_competitor_dashboard();
            }, __('گزارش‌ها'));
            
            frm.add_custom_button(__('نمودار مقایسه قیمت'), function() {
                show_price_comparison_chart(frm);
            }, __('گزارش‌ها'));
            
            frm.add_custom_button(__('تحلیل SWOT'), function() {
                show_swot_analysis(frm);
            }, __('تحلیل'));
            
            frm.add_custom_button(__('نقشه موقعیت بازار'), function() {
                show_market_position_map(frm);
            }, __('تحلیل'));
        }
        
        // Set default values
        if (frm.is_new()) {
            frm.set_value('analysis_date', frappe.datetime.get_today());
            frm.set_value('status', 'فعال');
            frm.set_value('analyst', frappe.session.user);
            frm.set_value('enable_auto_crawling', 0);
            frm.set_value('crawling_frequency', 'هفتگی');
            frm.set_value('enable_price_monitoring', 1);
            frm.set_value('price_change_threshold', 5);
        }
        
        // نمایش وضعیت کرال
        if (frm.doc.last_crawl_date) {
            let last_crawl = moment(frm.doc.last_crawl_date);
            let days_ago = moment().diff(last_crawl, 'days');
            
            if (days_ago > 7) {
                frm.dashboard.add_indicator(__('کرال قدیمی'), 'orange');
            } else if (days_ago <= 1) {
                frm.dashboard.add_indicator(__('کرال به‌روز'), 'green');
            }
        }
        
        // Highlight overdue reviews
        if (frm.doc.next_review_date && frappe.datetime.get_diff(frm.doc.next_review_date, frappe.datetime.get_today()) < 0) {
            frm.dashboard.add_indicator(__('Review Overdue'), 'red');
        } else if (frm.doc.next_review_date && frappe.datetime.get_diff(frm.doc.next_review_date, frappe.datetime.get_today()) <= 7) {
            frm.dashboard.add_indicator(__('Review Due Soon'), 'orange');
        }
    },
    
    competitor_name: function(frm) {
        if (frm.doc.competitor_name && !frm.doc.title) {
            frm.set_value('title', frm.doc.competitor_name + ' - ' + (frm.doc.competitor_type || 'تحلیل'));
        }
    },
    
    competitor_type: function(frm) {
        if (frm.doc.competitor_name && frm.doc.competitor_type) {
            frm.set_value('title', frm.doc.competitor_name + ' - ' + frm.doc.competitor_type);
        }
    },
    
    website_url: function(frm) {
        if (frm.doc.website_url) {
            // اعتبارسنجی URL
            if (!frm.doc.website_url.startsWith('http')) {
                frm.set_value('website_url', 'https://' + frm.doc.website_url);
            }
            
            // نمایش دکمه‌های کرال
            frm.refresh();
        }
    },
    
    enable_auto_crawling: function(frm) {
        if (frm.doc.enable_auto_crawling && !frm.doc.crawling_frequency) {
            frm.set_value('crawling_frequency', 'هفتگی');
        }
    }
});

frappe.ui.form.on('Competitor Product', {
    item_code: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.item_code) {
            // Get our current price for the item
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Item Price',
                    filters: {
                        item_code: row.item_code,
                        selling: 1
                    },
                    fieldname: 'price_list_rate'
                },
                callback: function(r) {
                    if (r.message && r.message.price_list_rate) {
                        frappe.model.set_value(cdt, cdn, 'our_price', r.message.price_list_rate);
                    } else {
                        // Fallback to standard rate
                        frappe.call({
                            method: 'frappe.client.get_value',
                            args: {
                                doctype: 'Item',
                                filters: {name: row.item_code},
                                fieldname: 'standard_rate'
                            },
                            callback: function(r) {
                                if (r.message && r.message.standard_rate) {
                                    frappe.model.set_value(cdt, cdn, 'our_price', r.message.standard_rate);
                                }
                            }
                        });
                    }
                }
            });
        }
    },
    
    competitor_price: function(frm, cdt, cdn) {
        calculate_price_differences(frm, cdt, cdn);
    },
    
    our_price: function(frm, cdt, cdn) {
        calculate_price_differences(frm, cdt, cdn);
    },
    
    products_add: function(frm, cdt, cdn) {
        // Add update button to new product row
        add_product_update_button(frm, cdt, cdn);
    }
});

// Add update button functionality to products table
function add_product_update_button(frm, cdt, cdn) {
    setTimeout(() => {
        let row = locals[cdt][cdn];
        let grid_row = frm.fields_dict.products.grid.grid_rows_by_docname[cdn];
        
        if (grid_row && row.product_url) {
            // Add update button to the row
            let update_btn = $(`<button class="btn btn-xs btn-primary" style="margin-left: 5px;">
                <i class="fa fa-refresh"></i> به‌روزرسانی
            </button>`);
            
            update_btn.click(() => {
                update_single_product_data(frm, cdt, cdn);
            });
            
            // Add button to the row
            grid_row.wrapper.find('.grid-row-check').after(update_btn);
        }
    }, 100);
}

function update_single_product_data(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    
    if (!row.product_url) {
        frappe.msgprint(__('لطفاً ابتدا URL محصول را وارد کنید'));
        return;
    }
    
    frappe.show_progress(__('در حال به‌روزرسانی اطلاعات محصول...'), 50);
    
    frappe.call({
        method: 'pricing.pricing.doctype.competitor_analysis.web_crawler.update_product_from_url',
        args: {
            competitor_name: frm.doc.name,
            product_url: row.product_url,
            row_name: cdn
        },
        callback: function(r) {
            frappe.hide_progress();
            
            if (r.message && r.message.success) {
                // Update the row with new data
                let product_data = r.message.product_data;
                
                frappe.model.set_value(cdt, cdn, 'product_name', product_data.title || row.product_name);
                frappe.model.set_value(cdt, cdn, 'competitor_price', product_data.price || row.competitor_price);
                frappe.model.set_value(cdt, cdn, 'description', product_data.description || row.description);
                frappe.model.set_value(cdt, cdn, 'availability', product_data.availability || row.availability);
                frappe.model.set_value(cdt, cdn, 'brand', product_data.brand || row.brand);
                frappe.model.set_value(cdt, cdn, 'last_updated', frappe.datetime.get_today());
                
                frappe.msgprint({
                    title: __('به‌روزرسانی موفق'),
                    message: __('اطلاعات محصول با موفقیت به‌روزرسانی شد'),
                    indicator: 'green'
                });
                
                frm.refresh_field('products');
            } else {
                frappe.msgprint({
                    title: __('خطا در به‌روزرسانی'),
                    message: r.message ? r.message.message : __('خطای نامشخص'),
                    indicator: 'red'
                });
            }
        },
        error: function(r) {
            frappe.hide_progress();
            frappe.msgprint({
                title: __('خطا در ارتباط'),
                message: __('خطا در ارتباط با سرور'),
                indicator: 'red'
            });
        }
    });
}

function calculate_price_differences(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    
    if (row.competitor_price && row.our_price) {
        let price_difference = flt(row.competitor_price) - flt(row.our_price);
        let price_difference_percent = (price_difference / row.our_price) * 100;
        
        frappe.model.set_value(cdt, cdn, 'price_difference', price_difference);
        frappe.model.set_value(cdt, cdn, 'price_difference_percent', price_difference_percent);
        
        // Set market position
        let market_position;
        if (price_difference_percent > 20) {
            market_position = "Expensive";
        } else if (price_difference_percent > 5) {
            market_position = "Premium";
        } else if (price_difference_percent < -20) {
            market_position = "Cheaper";
        } else {
            market_position = "Similar";
        }
        
        frappe.model.set_value(cdt, cdn, 'market_position', market_position);
        frappe.model.set_value(cdt, cdn, 'last_updated', frappe.datetime.get_today());
    }
}

function generate_competitor_analysis_report(frm) {
    frappe.call({
        method: 'generate_competitive_analysis_report',
        doc: frm.doc,
        callback: function(r) {
            if (r.message) {
                show_analysis_report_dialog(r.message);
            }
        }
    });
}

function show_analysis_report_dialog(analysis_data) {
    let dialog = new frappe.ui.Dialog({
        title: __('Competitive Analysis Report'),
        size: 'extra-large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'report_html'
            }
        ]
    });
    
    let html = generate_analysis_report_html(analysis_data);
    dialog.fields_dict.report_html.$wrapper.html(html);
    dialog.show();
}

function generate_analysis_report_html(data) {
    let html = `
        <div class="competitor-analysis-report">
            <h3>Competitive Analysis Report</h3>
            
            <!-- Competitor Overview -->
            <div class="section">
                <h4>Competitor Overview</h4>
                <div class="row">
                    <div class="col-md-6">
                        <table class="table table-bordered">
                            <tr><td><strong>Name:</strong></td><td>${data.competitor_overview.name || ''}</td></tr>
                            <tr><td><strong>Type:</strong></td><td>${data.competitor_overview.type || ''}</td></tr>
                            <tr><td><strong>Market Segment:</strong></td><td>${data.competitor_overview.market_segment || ''}</td></tr>
                            <tr><td><strong>Company Size:</strong></td><td>${data.competitor_overview.company_size || ''}</td></tr>
                        </table>
                    </div>
                    <div class="col-md-6">
                        <table class="table table-bordered">
                            <tr><td><strong>Annual Revenue:</strong></td><td>${frappe.format(data.competitor_overview.annual_revenue, {fieldtype: 'Currency'}) || 'N/A'}</td></tr>
                            <tr><td><strong>Market Share:</strong></td><td>${data.competitor_overview.market_share || 'N/A'}%</td></tr>
                            <tr><td><strong>Market Position:</strong></td><td>${data.competitor_overview.market_position || ''}</td></tr>
                        </table>
                    </div>
                </div>
            </div>
            
            <!-- Pricing Analysis -->
            <div class="section">
                <h4>Pricing Analysis</h4>
                <div class="row">
                    <div class="col-md-8">
                        <table class="table table-bordered">
                            <tr><td><strong>Pricing Model:</strong></td><td>${data.pricing_analysis.pricing_model || ''}</td></tr>
                            <tr><td><strong>Average Discount:</strong></td><td>${data.pricing_analysis.average_discount || 0}%</td></tr>
                            <tr><td><strong>Price Elasticity:</strong></td><td>${data.pricing_analysis.price_elasticity || ''}</td></tr>
                            <tr><td><strong>Promotional Frequency:</strong></td><td>${data.pricing_analysis.promotional_frequency || ''}</td></tr>
                        </table>
                    </div>
                    <div class="col-md-4">
                        ${data.pricing_analysis.product_comparison ? `
                            <div class="alert alert-info">
                                <h6>Product Comparison</h6>
                                <p>Total Products: ${data.pricing_analysis.product_comparison.total_products}</p>
                                <p>Cheaper: ${data.pricing_analysis.product_comparison.cheaper_percentage.toFixed(1)}%</p>
                                <p>Expensive: ${data.pricing_analysis.product_comparison.expensive_percentage.toFixed(1)}%</p>
                            </div>
                        ` : ''}
                    </div>
                </div>
            </div>
            
            <!-- SWOT Analysis -->
            <div class="section">
                <h4>SWOT Analysis</h4>
                <div class="row">
                    <div class="col-md-6">
                        <div class="card border-success">
                            <div class="card-header bg-success text-white"><h6>Strengths</h6></div>
                            <div class="card-body">${data.swot_analysis.strengths || 'Not specified'}</div>
                        </div>
                        <br>
                        <div class="card border-info">
                            <div class="card-header bg-info text-white"><h6>Opportunities</h6></div>
                            <div class="card-body">${data.swot_analysis.opportunities || 'Not specified'}</div>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="card border-warning">
                            <div class="card-header bg-warning text-white"><h6>Weaknesses</h6></div>
                            <div class="card-body">${data.swot_analysis.weaknesses || 'Not specified'}</div>
                        </div>
                        <br>
                        <div class="card border-danger">
                            <div class="card-header bg-danger text-white"><h6>Threats</h6></div>
                            <div class="card-body">${data.swot_analysis.threats || 'Not specified'}</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Strategic Insights -->
            <div class="section">
                <h4>Strategic Insights</h4>
                ${data.strategic_insights.automated_insights ? `
                    <div class="alert alert-primary">
                        <h6>Automated Insights:</h6>
                        <ul>
                            ${data.strategic_insights.automated_insights.map(insight => `<li>${insight}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}
            </div>
            
            <!-- Recommendations -->
            <div class="section">
                <h4>Recommendations</h4>
                <div class="row">
                    <div class="col-md-6">
                        <h6>Strategic Recommendations:</h6>
                        <p>${data.recommendations.strategic_recommendations || 'Not specified'}</p>
                    </div>
                    <div class="col-md-6">
                        <h6>Pricing Recommendations:</h6>
                        <p>${data.recommendations.pricing_recommendations || 'Not specified'}</p>
                    </div>
                </div>
            </div>
        </div>
        
        <style>
            .competitor-analysis-report .section { margin-bottom: 30px; }
            .competitor-analysis-report .card { margin-bottom: 10px; }
            .competitor-analysis-report h4 { color: #333; border-bottom: 2px solid #007bff; padding-bottom: 5px; }
        </style>
    `;
    
    return html;
}

function schedule_next_review_dialog(frm) {
    let dialog = new frappe.ui.Dialog({
        title: __('Schedule Next Review'),
        fields: [
            {
                fieldtype: 'Int',
                fieldname: 'days',
                label: __('Days from today'),
                default: 90,
                reqd: 1
            }
        ],
        primary_action_label: __('Schedule'),
        primary_action: function() {
            let values = dialog.get_values();
            frm.call('schedule_next_review', {
                days: values.days
            }).then(r => {
                if (r.message && r.message.status === 'success') {
                    frappe.msgprint(r.message.message);
                    frm.refresh();
                    dialog.hide();
                }
            });
        }
    });
    
    dialog.show();
}

function show_competitor_dashboard() {
    frappe.call({
        method: 'pricing.pricing.doctype.competitor_analysis.competitor_analysis.get_competitor_analysis_dashboard',
        callback: function(r) {
            if (r.message) {
                show_dashboard_dialog(r.message);
            }
        }
    });
}

function show_dashboard_dialog(dashboard_data) {
    let dialog = new frappe.ui.Dialog({
        title: __('Competitor Analysis Dashboard'),
        size: 'extra-large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'dashboard_html'
            }
        ]
    });
    
    let html = generate_dashboard_html(dashboard_data);
    dialog.fields_dict.dashboard_html.$wrapper.html(html);
    dialog.show();
}

function generate_dashboard_html(data) {
    let html = `
        <div class="competitor-dashboard">
            <div class="row">
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <h2 class="text-primary">${data.active_competitors}</h2>
                            <p>Active Competitors</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <h2 class="text-warning">${data.reviews_due.length}</h2>
                            <p>Reviews Due</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header"><h6>Recent Competitors</h6></div>
                        <div class="card-body">
                            ${data.competitor_list.slice(0, 5).map(comp => `
                                <div class="d-flex justify-content-between">
                                    <span>${comp.competitor_name}</span>
                                    <span class="badge badge-${comp.priority === 'High' ? 'danger' : comp.priority === 'Medium' ? 'warning' : 'secondary'}">${comp.priority || 'Low'}</span>
                                </div>
                            `).join('<hr>')}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    return html;
}

function show_price_comparison_chart(frm) {
    if (!frm.doc.products || frm.doc.products.length === 0) {
        frappe.msgprint(__('No products to compare'));
        return;
    }
    
    let dialog = new frappe.ui.Dialog({
        title: __('Price Comparison Chart'),
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'chart_html'
            }
        ]
    });
    
    let html = generate_price_comparison_chart_html(frm.doc.products);
    dialog.fields_dict.chart_html.$wrapper.html(html);
    dialog.show();
}

function generate_price_comparison_chart_html(products) {
    let html = `
        <div class="price-comparison-chart">
            <h4>Price Comparison</h4>
            <div class="table-responsive">
                <table class="table table-striped">
                    <thead>
                        <tr>
                            <th>Product</th>
                            <th>Our Price</th>
                            <th>Competitor Price</th>
                            <th>Difference</th>
                            <th>Position</th>
                        </tr>
                    </thead>
                    <tbody>
    `;
    
    products.forEach(product => {
        let position_class = product.market_position === 'Cheaper' ? 'success' : 
                           product.market_position === 'Expensive' ? 'danger' : 'info';
        
        html += `
            <tr>
                <td>${product.item_name || product.item_code}</td>
                <td>${frappe.format(product.our_price, {fieldtype: 'Currency'})}</td>
                <td>${frappe.format(product.competitor_price, {fieldtype: 'Currency'})}</td>
                <td class="text-${product.price_difference > 0 ? 'danger' : 'success'}">
                    ${frappe.format(product.price_difference, {fieldtype: 'Currency'})} 
                    (${product.price_difference_percent ? product.price_difference_percent.toFixed(1) : 0}%)
                </td>
                <td><span class="badge badge-${position_class}">${product.market_position}</span></td>
            </tr>
        `;
    });
    
    html += `
                    </tbody>
                </table>
            </div>
        </div>
    `;
    
    return html;
}

// توابع کرال هوشمند
function start_intelligent_crawl(frm) {
    if (!frm.doc.website_url) {
        frappe.msgprint(__('لطفاً آدرس وب‌سایت رقیب را وارد کنید'));
        return;
    }
    
    let progress_dialog = show_crawl_progress_dialog();
    
    frappe.call({
        method: 'pricing.pricing.doctype.competitor_analysis.web_crawler.start_competitor_crawl',
        args: {
            competitor_name: frm.doc.name
        },
        callback: function(r) {
            progress_dialog.hide();
            
            if (r.message && r.message.status === 'success') {
                frappe.msgprint({
                    title: __('کرال تکمیل شد'),
                    message: r.message.message,
                    indicator: 'green'
                });
                frm.reload_doc();
            } else {
                frappe.msgprint({
                    title: __('خطا در کرال'),
                    message: r.message.message || 'خطای نامشخص',
                    indicator: 'red'
                });
            }
        }
    });
}

function show_crawl_progress_dialog() {
    let dialog = new frappe.ui.Dialog({
        title: __('در حال کرال...'),
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'progress_html'
            }
        ],
        primary_action_label: __('لغو'),
        primary_action: function() {
            dialog.hide();
        }
    });
    
    let html = `
        <div class="text-center">
            <div class="progress mb-3">
                <div class="progress-bar progress-bar-striped progress-bar-animated" 
                     role="progressbar" style="width: 0%" id="crawl-progress"></div>
            </div>
            <p id="crawl-status">شروع کرال...</p>
        </div>
    `;
    
    dialog.fields_dict.progress_html.$wrapper.html(html);
    dialog.show();
    
    // گوش دادن به پیام‌های realtime
    frappe.realtime.on('crawler_status', function(data) {
        $('#crawl-progress').css('width', data.progress + '%');
        $('#crawl-status').text(data.message);
    });
    
    return dialog;
}

function analyze_seo_data(frm) {
    if (!frm.doc.website_url) {
        frappe.msgprint(__('لطفاً آدرس وب‌سایت رقیب را وارد کنید'));
        return;
    }
    
    let dialog = new frappe.ui.Dialog({
        title: __('تحلیل SEO'),
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'seo_html'
            }
        ]
    });
    
    let html = generate_seo_analysis_html(frm.doc);
    dialog.fields_dict.seo_html.$wrapper.html(html);
    dialog.show();
}

function generate_seo_analysis_html(doc) {
    return `
        <div class="seo-analysis">
            <div class="row">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <h6>اعتبار دامنه و صفحه</h6>
                        </div>
                        <div class="card-body">
                            <p><strong>اعتبار دامنه (DA):</strong> ${doc.domain_authority || 'نامشخص'}</p>
                            <p><strong>اعتبار صفحه (PA):</strong> ${doc.page_authority || 'نامشخص'}</p>
                            <p><strong>تعداد بک‌لینک:</strong> ${doc.backlinks_count || 'نامشخص'}</p>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <h6>ترافیک و کلمات کلیدی</h6>
                        </div>
                        <div class="card-body">
                            <p><strong>ترافیک ماهانه:</strong> ${doc.monthly_traffic ? format_number(doc.monthly_traffic) : 'نامشخص'}</p>
                            <p><strong>روند ترافیک:</strong> ${doc.traffic_trend || 'نامشخص'}</p>
                            <p><strong>کلمات کلیدی ارگانیک:</strong> ${doc.organic_keywords || 'نامشخص'}</p>
                        </div>
                    </div>
                </div>
            </div>
            <div class="row mt-3">
                <div class="col-md-12">
                    <div class="card">
                        <div class="card-header">
                            <h6>کلمات کلیدی برتر</h6>
                        </div>
                        <div class="card-body">
                            <p>${doc.top_keywords || 'اطلاعاتی موجود نیست'}</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function monitor_price_changes(frm) {
    let dialog = new frappe.ui.Dialog({
        title: __('نظارت بر تغییرات قیمت'),
        fields: [
            {
                fieldtype: 'Check',
                fieldname: 'enable_monitoring',
                label: __('فعال‌سازی نظارت'),
                default: frm.doc.enable_price_monitoring
            },
            {
                fieldtype: 'Percent',
                fieldname: 'threshold',
                label: __('آستانه تغییر قیمت (درصد)'),
                default: frm.doc.price_change_threshold || 5
            },
            {
                fieldtype: 'Data',
                fieldname: 'email',
                label: __('ایمیل هشدار'),
                options: 'Email',
                default: frm.doc.notification_email
            }
        ],
        primary_action_label: __('ذخیره'),
        primary_action: function() {
            let values = dialog.get_values();
            
            frm.set_value('enable_price_monitoring', values.enable_monitoring);
            frm.set_value('price_change_threshold', values.threshold);
            frm.set_value('notification_email', values.email);
            
            frm.save();
            dialog.hide();
        }
    });
    
    dialog.show();
}

function show_swot_analysis(frm) {
    let dialog = new frappe.ui.Dialog({
        title: __('تحلیل SWOT'),
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'swot_html'
            }
        ]
    });
    
    let html = `
        <div class="swot-analysis">
            <div class="row">
                <div class="col-md-6">
                    <div class="card border-success">
                        <div class="card-header bg-success text-white text-center">
                            <h5>نقاط قوت</h5>
                        </div>
                        <div class="card-body">
                            ${frm.doc.strengths || 'مشخص نشده'}
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card border-warning">
                        <div class="card-header bg-warning text-white text-center">
                            <h5>نقاط ضعف</h5>
                        </div>
                        <div class="card-body">
                            ${frm.doc.weaknesses || 'مشخص نشده'}
                        </div>
                    </div>
                </div>
            </div>
            <br>
            <div class="row">
                <div class="col-md-6">
                    <div class="card border-info">
                        <div class="card-header bg-info text-white text-center">
                            <h5>فرصت‌ها</h5>
                        </div>
                        <div class="card-body">
                            ${frm.doc.opportunities || 'مشخص نشده'}
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card border-danger">
                        <div class="card-header bg-danger text-white text-center">
                            <h5>تهدیدها</h5>
                        </div>
                        <div class="card-body">
                            ${frm.doc.threats || 'مشخص نشده'}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    dialog.fields_dict.swot_html.$wrapper.html(html);
    dialog.show();
}

function show_market_position_map(frm) {
    let dialog = new frappe.ui.Dialog({
        title: __('نقشه موقعیت بازار'),
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'map_html'
            }
        ]
    });
    
    let html = generate_market_position_map_html(frm.doc);
    dialog.fields_dict.map_html.$wrapper.html(html);
    dialog.show();
}

function generate_market_position_map_html(doc) {
    return `
        <div class="market-position-map">
            <div class="row">
                <div class="col-md-12 text-center">
                    <h4>موقعیت ${doc.competitor_name} در بازار</h4>
                    <div class="position-grid" style="position: relative; height: 400px; border: 1px solid #ddd; margin: 20px 0;">
                        <div class="position-marker" style="
                            position: absolute;
                            left: ${get_position_x(doc)}%;
                            top: ${get_position_y(doc)}%;
                            width: 20px;
                            height: 20px;
                            background: #007bff;
                            border-radius: 50%;
                            transform: translate(-50%, -50%);
                        "></div>
                        <div style="position: absolute; left: 0; bottom: 0; padding: 5px;">قیمت پایین</div>
                        <div style="position: absolute; right: 0; bottom: 0; padding: 5px;">قیمت بالا</div>
                        <div style="position: absolute; left: 0; top: 0; padding: 5px; transform: rotate(90deg); transform-origin: left top;">کیفیت بالا</div>
                        <div style="position: absolute; left: 0; bottom: 0; padding: 5px; transform: rotate(90deg); transform-origin: left bottom;">کیفیت پایین</div>
                    </div>
                </div>
            </div>
            <div class="row">
                <div class="col-md-6">
                    <h6>اطلاعات موقعیت:</h6>
                    <p><strong>موقعیت بازار:</strong> ${doc.market_position || 'نامشخص'}</p>
                    <p><strong>بخش بازار:</strong> ${doc.market_segment || 'نامشخص'}</p>
                    <p><strong>سهم بازار:</strong> ${doc.market_share || 'نامشخص'}%</p>
                </div>
                <div class="col-md-6">
                    <h6>امتیازات:</h6>
                    <p><strong>رضایت مشتری:</strong> ${doc.customer_satisfaction || 'نامشخص'}/5</p>
                    <p><strong>قدرت برند:</strong> ${doc.brand_strength || 'نامشخص'}/5</p>
                    <p><strong>شاخص نوآوری:</strong> ${doc.innovation_index || 'نامشخص'}/5</p>
                </div>
            </div>
        </div>
    `;
}

function get_position_x(doc) {
    // محاسبه موقعیت X بر اساس قیمت (فرضی)
    if (doc.market_segment === 'لوکس' || doc.market_segment === 'پریمیوم') return 80;
    if (doc.market_segment === 'اقتصادی') return 20;
    return 50;
}

function get_position_y(doc) {
    // محاسبه موقعیت Y بر اساس کیفیت (فرضی)
    let quality_score = (doc.customer_satisfaction || 3) + (doc.brand_strength || 3) + (doc.innovation_index || 3);
    return Math.max(10, Math.min(90, (quality_score / 15) * 100));
}

function format_number(num) {
    if (!num) return '0';
    return new Intl.NumberFormat('fa-IR').format(num);
}

function crawl_product_from_url(frm) {
    let d = new frappe.ui.Dialog({
        title: __('کرال پیشرفته محصول'),
        fields: [
            {
                label: __('نوع کرال'),
                fieldname: 'crawl_type',
                fieldtype: 'Select',
                options: 'تک محصول\nکرال دسته‌ای',
                default: 'تک محصول',
                reqd: 1
            },
            {
                label: __('لینک محصول'),
                fieldname: 'product_url',
                fieldtype: 'Long Text',
                depends_on: 'eval:doc.crawl_type=="تک محصول"',
                reqd: 1,
                description: __('لینک کامل صفحه محصول (بدون محدودیت طول)')
            },
            {
                label: __('لیست URL محصولات'),
                fieldname: 'batch_urls',
                fieldtype: 'Long Text',
                depends_on: 'eval:doc.crawl_type=="کرال دسته‌ای"',
                reqd: 1,
                description: __('هر URL در یک خط جداگانه (حداکثر 50 محصول)')
            },
            {
                label: __('CSS Selector قیمت (اختیاری)'),
                fieldname: 'price_selector',
                fieldtype: 'Data',
                description: __('مثال: .price, #product-price, .final-price')
            },
            {
                label: __('استفاده از Selenium'),
                fieldname: 'use_selenium',
                fieldtype: 'Check',
                description: __('برای سایت‌های پیچیده با JavaScript')
            }
        ],
        size: 'large',
        primary_action_label: __('شروع کرال پیشرفته'),
        primary_action(values) {
            if (values.crawl_type === 'تک محصول') {
                crawl_single_product_enhanced(frm, values);
            } else {
                crawl_batch_products(frm, values);
            }
            d.hide();
        }
    });
    
    d.show();
}

function crawl_single_product_enhanced(frm, values) {
    if (!values.product_url) {
        frappe.msgprint(__('لطفاً لینک محصول را وارد کنید'));
        return;
    }
    
    frappe.show_progress(__('در حال کرال پیشرفته محصول...'), 30);
    
    frappe.call({
        method: 'pricing.pricing.doctype.competitor_analysis.web_crawler.crawl_single_product_url',
        args: {
            competitor_name: frm.doc.name,
            product_url: values.product_url,
            price_selector: values.price_selector,
            use_selenium: values.use_selenium
        },
        callback: function(r) {
            frappe.hide_progress();
            
            if (r.message && r.message.success) {
                show_enhanced_product_results(r.message.product_info);
                frm.refresh();
            } else {
                frappe.msgprint({
                    title: __('خطا در کرال'),
                    message: r.message ? r.message.message : __('خطای نامشخص'),
                    indicator: 'red'
                });
            }
        },
        error: function(r) {
            frappe.hide_progress();
            frappe.msgprint({
                title: __('خطا در ارتباط'),
                message: __('خطا در ارتباط با سرور'),
                indicator: 'red'
            });
        }
    });
}

function crawl_batch_products(frm, values) {
    if (!values.batch_urls) {
        frappe.msgprint(__('لطفاً لیست URL ها را وارد کنید'));
        return;
    }
    
    let urls = values.batch_urls.split('\n').filter(url => url.trim());
    
    if (urls.length === 0) {
        frappe.msgprint(__('لطفاً حداقل یک URL وارد کنید'));
        return;
    }
    
    if (urls.length > 50) {
        frappe.msgprint(__('حداکثر 50 محصول در هر دسته قابل کرال است'));
        return;
    }
    
    frappe.show_progress(__(`در حال کرال ${urls.length} محصول...`), 30);
    
    frappe.call({
        method: 'pricing.pricing.doctype.competitor_analysis.web_crawler.crawl_multiple_products_batch',
        args: {
            competitor_name: frm.doc.name,
            product_urls: JSON.stringify(urls),
            price_selector: values.price_selector
        },
        callback: function(r) {
            frappe.hide_progress();
            
            if (r.message && r.message.success) {
                show_batch_crawl_results(r.message);
                frm.refresh();
            } else {
                frappe.msgprint({
                    title: __('خطا در کرال دسته‌ای'),
                    message: r.message ? r.message.message : __('خطای نامشخص'),
                    indicator: 'red'
                });
            }
        },
        error: function(r) {
            frappe.hide_progress();
            frappe.msgprint({
                title: __('خطا در ارتباط'),
                message: __('خطا در ارتباط با سرور'),
                indicator: 'red'
            });
        }
    });
}
function show_enhanced_product_results(product_info) {
    let result_html = `
        <div style="padding: 20px; max-height: 600px; overflow-y: auto;">
            <h3 style="color: #28a745;">✅ کرال محصول موفقیت‌آمیز بود!</h3>
            <hr>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;">
                <div>
                    <h5>📋 اطلاعات اصلی</h5>
                    <p><strong>عنوان:</strong> ${product_info.title || 'نامشخص'}</p>
                    <p><strong>قیمت:</strong> ${format_number(product_info.price)} ${product_info.currency || 'تومان'}</p>
                    <p><strong>برند:</strong> ${product_info.brand || 'نامشخص'}</p>
                    <p><strong>کد محصول:</strong> ${product_info.sku || 'نامشخص'}</p>
                    <p><strong>دسته‌بندی:</strong> ${product_info.category || 'نامشخص'}</p>
                    <p><strong>موجودی:</strong> ${product_info.availability || 'نامشخص'}</p>
                </div>
                
                <div>
                    <h5>⭐ امتیاز و نظرات</h5>
                    <p><strong>امتیاز:</strong> ${product_info.rating || 0}/5</p>
                    <p><strong>تعداد نظرات:</strong> ${format_number(product_info.reviews_count || 0)}</p>
                    <p><strong>طول توضیحات:</strong> ${format_number(product_info.description_length || 0)} کاراکتر</p>
                    <p><strong>امتیاز کیفیت داده:</strong> ${product_info.data_quality_score || 0}%</p>
                    <p><strong>زمان کرال:</strong> ${product_info.crawl_time || 0} ثانیه</p>
                </div>
            </div>
            
            <div style="margin-bottom: 20px;">
                <h5>🔧 مشخصات فنی (${product_info.specifications_count || 0} مورد)</h5>
                ${product_info.specifications && Object.keys(product_info.specifications).length > 0 ? 
                    `<div style="background: #f8f9fa; padding: 10px; border-radius: 5px; max-height: 200px; overflow-y: auto;">
                        ${Object.entries(product_info.specifications).map(([key, value]) => 
                            `<p style="margin: 5px 0;"><strong>${key}:</strong> ${value}</p>`
                        ).join('')}
                    </div>` 
                    : '<p style="color: #6c757d;">مشخصات فنی یافت نشد</p>'
                }
            </div>
            
            <div style="margin-bottom: 20px;">
                <h5>🏷️ کلمات کلیدی SEO (${product_info.keywords_count || 0} مورد)</h5>
                ${product_info.keywords && product_info.keywords.length > 0 ? 
                    `<div style="background: #e3f2fd; padding: 10px; border-radius: 5px;">
                        ${product_info.keywords.map(keyword => 
                            `<span style="background: #2196f3; color: white; padding: 3px 8px; margin: 2px; border-radius: 12px; font-size: 12px; display: inline-block;">${keyword}</span>`
                        ).join('')}
                    </div>` 
                    : '<p style="color: #6c757d;">کلمات کلیدی یافت نشد</p>'
                }
            </div>
            
            <div style="margin-bottom: 20px;">
                <h5>🖼️ تصاویر محصول (${product_info.images_count || 0} مورد)</h5>
                ${product_info.images && product_info.images.length > 0 ? 
                    `<div style="display: flex; gap: 10px; flex-wrap: wrap;">
                        ${product_info.images.map(img => 
                            `<img src="${img}" style="width: 80px; height: 80px; object-fit: cover; border-radius: 5px; border: 1px solid #ddd;" onerror="this.style.display='none'">`
                        ).join('')}
                    </div>` 
                    : '<p style="color: #6c757d;">تصاویر یافت نشد</p>'
                }
            </div>
            
            <div style="margin-bottom: 20px;">
                <h5>🔍 اطلاعات SEO</h5>
                <p><strong>عنوان SEO:</strong> ${product_info.seo_title || 'نامشخص'}</p>
                <p><strong>توضیحات SEO:</strong> ${product_info.seo_description || 'نامشخص'}</p>
            </div>
            
            ${product_info.json_file ? 
                `<div style="text-align: center; padding: 15px; background: #d4edda; border-radius: 5px;">
                    <h5 style="color: #155724;">📁 فایل JSON کامل</h5>
                    <a href="${product_info.json_file}" target="_blank" class="btn btn-success btn-sm">
                        دانلود اطلاعات کامل JSON
                    </a>
                </div>` 
                : ''
            }
        </div>
    `;
    
    let result_dialog = new frappe.ui.Dialog({
        title: __('نتیجه کرال پیشرفته محصول'),
        size: 'extra-large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'result_html',
                options: result_html
            }
        ],
        primary_action_label: __('بستن'),
        primary_action() {
            result_dialog.hide();
        }
    });
    
    result_dialog.show();
}

function show_batch_crawl_results(batch_result) {
    let result_html = `
        <div style="padding: 20px;">
            <h3 style="color: #28a745;">📊 نتیجه کرال دسته‌ای</h3>
            <hr>
            
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; margin-bottom: 20px;">
                <div style="text-align: center; padding: 15px; background: #e3f2fd; border-radius: 8px;">
                    <h4 style="color: #1976d2; margin: 0;">${format_number(batch_result.total_urls)}</h4>
                    <p style="margin: 5px 0;">کل محصولات</p>
                </div>
                <div style="text-align: center; padding: 15px; background: #e8f5e8; border-radius: 8px;">
                    <h4 style="color: #2e7d32; margin: 0;">${format_number(batch_result.success_count)}</h4>
                    <p style="margin: 5px 0;">موفق</p>
                </div>
                <div style="text-align: center; padding: 15px; background: #ffebee; border-radius: 8px;">
                    <h4 style="color: #c62828; margin: 0;">${format_number(batch_result.failed_count)}</h4>
                    <p style="margin: 5px 0;">ناموفق</p>
                </div>
            </div>
            
            <h5>📋 جزئیات نتایج:</h5>
            <div style="max-height: 400px; overflow-y: auto; border: 1px solid #ddd; border-radius: 5px;">
                <table class="table table-striped" style="margin: 0;">
                    <thead style="background: #f8f9fa;">
                        <tr>
                            <th>وضعیت</th>
                            <th>عنوان محصول</th>
                            <th>قیمت</th>
                            <th>URL</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${batch_result.results.map(result => `
                            <tr>
                                <td>
                                    ${result.status === 'success' ? 
                                        '<span style="color: #28a745;">✅ موفق</span>' : 
                                        '<span style="color: #dc3545;">❌ ناموفق</span>'
                                    }
                                </td>
                                <td>${result.title || 'نامشخص'}</td>
                                <td>${result.price ? format_number(result.price) + ' تومان' : '-'}</td>
                                <td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis;">
                                    <a href="${result.url}" target="_blank" title="${result.url}">
                                        ${result.url.substring(0, 50)}...
                                    </a>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>
    `;
    
    let batch_dialog = new frappe.ui.Dialog({
        title: __('نتیجه کرال دسته‌ای محصولات'),
        size: 'extra-large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'batch_result_html',
                options: result_html
            }
        ],
        primary_action_label: __('بستن'),
        primary_action() {
            batch_dialog.hide();
        }
    });
    
    batch_dialog.show();
}
