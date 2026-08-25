frappe.ui.form.on('Competitor Product', {
    refresh: function(frm) {
        if (frm.doc.docstatus === 0) {
            // دکمه کرال محصول
            if (frm.doc.product_url) {
                frm.add_custom_button(__('کرال محصول'), function() {
                    crawl_single_product(frm);
                }, __('عملیات'));
            }
            
            // دکمه گزارش مقایسه
            if (frm.doc.competitor_price && frm.doc.our_price) {
                frm.add_custom_button(__('گزارش مقایسه'), function() {
                    generate_comparison_report(frm);
                }, __('گزارش‌ها'));
            }
            
            // دکمه تحلیل روند قیمت
            if (frm.doc.price_history) {
                frm.add_custom_button(__('تحلیل روند قیمت'), function() {
                    show_price_trend_analysis(frm);
                }, __('گزارش‌ها'));
            }
            
            // دکمه مشاهده تاریخچه قیمت
            if (frm.doc.price_history) {
                frm.add_custom_button(__('تاریخچه قیمت'), function() {
                    show_price_history(frm);
                }, __('گزارش‌ها'));
            }
        }
    },
    
    item_code: function(frm) {
        if (frm.doc.item_code) {
            // دریافت قیمت فعلی کالای ما
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Item Price',
                    filters: {
                        item_code: frm.doc.item_code,
                        selling: 1
                    },
                    fieldname: 'price_list_rate'
                },
                callback: function(r) {
                    if (r.message && r.message.price_list_rate) {
                        frm.set_value('our_price', r.message.price_list_rate);
                        calculate_price_differences(frm);
                    } else {
                        // در صورت عدم وجود از نرخ استاندارد استفاده کن
                        frappe.call({
                            method: 'frappe.client.get_value',
                            args: {
                                doctype: 'Item',
                                filters: {name: frm.doc.item_code},
                                fieldname: 'standard_rate'
                            },
                            callback: function(r) {
                                if (r.message && r.message.standard_rate) {
                                    frm.set_value('our_price', r.message.standard_rate);
                                    calculate_price_differences(frm);
                                }
                            }
                        });
                    }
                }
            });
        }
    },
    
    competitor_price: function(frm) {
        calculate_price_differences(frm);
    },
    
    our_price: function(frm) {
        calculate_price_differences(frm);
    }
});

function calculate_price_differences(frm) {
    if (frm.doc.competitor_price && frm.doc.our_price) {
        let price_difference = flt(frm.doc.competitor_price) - flt(frm.doc.our_price);
        let price_difference_percent = (price_difference / frm.doc.our_price) * 100;
        
        frm.set_value('price_difference', price_difference);
        frm.set_value('price_difference_percent', price_difference_percent);
        
        // تعیین موقعیت بازار
        let market_position;
        if (price_difference_percent > 20) {
            market_position = "گران‌تر";
        } else if (price_difference_percent > 5) {
            market_position = "پریمیوم";
        } else if (price_difference_percent < -20) {
            market_position = "ارزان‌تر";
        } else {
            market_position = "مشابه";
        }
        
        frm.set_value('market_position', market_position);
        frm.set_value('last_updated', frappe.datetime.now_datetime());
    }
}

function crawl_single_product(frm) {
    frappe.show_alert({
        message: __('در حال کرال اطلاعات محصول...'),
        indicator: 'blue'
    });
    
    frappe.call({
        method: 'crawl_product_data',
        doc: frm.doc,
        callback: function(r) {
            if (r.message && r.message.success) {
                frappe.show_alert({
                    message: r.message.message,
                    indicator: 'green'
                });
                frm.reload_doc();
            } else {
                frappe.show_alert({
                    message: r.message ? r.message.message : __('خطا در کرال محصول'),
                    indicator: 'red'
                });
            }
        }
    });
}

function generate_comparison_report(frm) {
    frappe.show_alert({
        message: __('در حال تولید گزارش مقایسه...'),
        indicator: 'blue'
    });
    
    frappe.call({
        method: 'generate_comparison_report',
        doc: frm.doc,
        callback: function(r) {
            if (r.message && !r.message.error) {
                show_comparison_report_dialog(r.message);
            } else {
                frappe.msgprint({
                    title: __('خطا'),
                    message: r.message ? r.message.error : __('خطا در تولید گزارش'),
                    indicator: 'red'
                });
            }
        }
    });
}

function show_comparison_report_dialog(report_data) {
    let dialog = new frappe.ui.Dialog({
        title: __('گزارش مقایسه محصول'),
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'report_html'
            }
        ]
    });
    
    let html = `
        <div class="comparison-report" style="padding: 15px;">
            <div class="row">
                <div class="col-md-6">
                    <h4>اطلاعات پایه</h4>
                    <table class="table table-bordered">
                        <tr><td><strong>نام محصول:</strong></td><td>${report_data.product_name || ''}</td></tr>
                        <tr><td><strong>کد محصول ما:</strong></td><td>${report_data.our_item_code || ''}</td></tr>
                        <tr><td><strong>آدرس محصول:</strong></td><td><a href="${report_data.product_url || ''}" target="_blank">مشاهده</a></td></tr>
                        <tr><td><strong>آخرین به‌روزرسانی:</strong></td><td>${report_data.last_updated || ''}</td></tr>
                    </table>
                </div>
                <div class="col-md-6">
                    <h4>مقایسه قیمت</h4>
                    <table class="table table-bordered">
                        <tr><td><strong>قیمت رقیب:</strong></td><td>${format_currency(report_data.pricing?.competitor_price || 0)}</td></tr>
                        <tr><td><strong>قیمت ما:</strong></td><td>${format_currency(report_data.pricing?.our_price || 0)}</td></tr>
                        <tr><td><strong>اختلاف قیمت:</strong></td><td style="color: ${(report_data.pricing?.price_difference || 0) > 0 ? 'red' : 'green'}">${format_currency(report_data.pricing?.price_difference || 0)}</td></tr>
                        <tr><td><strong>درصد اختلاف:</strong></td><td>${(report_data.pricing?.price_difference_percent || 0).toFixed(1)}%</td></tr>
                        <tr><td><strong>موقعیت بازار:</strong></td><td><span class="label label-info">${report_data.pricing?.market_position || ''}</span></td></tr>
                    </table>
                </div>
            </div>
            
            <div class="row" style="margin-top: 20px;">
                <div class="col-md-6">
                    <h4>تحلیل روند قیمت</h4>
                    <table class="table table-bordered">
                        <tr><td><strong>روند هفتگی:</strong></td><td><span class="label ${get_trend_class(report_data.price_trends?.weekly?.trend)}">${report_data.price_trends?.weekly?.trend || ''}</span></td></tr>
                        <tr><td><strong>تغییر هفتگی:</strong></td><td>${(report_data.price_trends?.weekly?.change_percent || 0).toFixed(1)}%</td></tr>
                        <tr><td><strong>روند ماهانه:</strong></td><td><span class="label ${get_trend_class(report_data.price_trends?.monthly?.trend)}">${report_data.price_trends?.monthly?.trend || ''}</span></td></tr>
                        <tr><td><strong>تغییر ماهانه:</strong></td><td>${(report_data.price_trends?.monthly?.change_percent || 0).toFixed(1)}%</td></tr>
                    </table>
                </div>
                <div class="col-md-6">
                    <h4>وضعیت موجودی</h4>
                    <table class="table table-bordered">
                        <tr><td><strong>وضعیت:</strong></td><td><span class="label ${get_availability_class(report_data.availability?.status)}">${report_data.availability?.status || ''}</span></td></tr>
                        <tr><td><strong>جزئیات:</strong></td><td>${report_data.availability?.stock_details || 'ندارد'}</td></tr>
                    </table>
                    
                    <h4>امتیاز کیفیت</h4>
                    <table class="table table-bordered">
                        <tr><td><strong>امتیاز:</strong></td><td>${'★'.repeat(report_data.quality?.rating || 0)}${'☆'.repeat(5 - (report_data.quality?.rating || 0))}</td></tr>
                    </table>
                </div>
            </div>
            
            <div class="row" style="margin-top: 20px;">
                <div class="col-md-12">
                    <h4>توصیه‌های استراتژیک</h4>
                    <div class="recommendations">
                        ${(report_data.recommendations || []).map(rec => `
                            <div class="alert alert-${get_priority_class(rec.priority)}" style="margin-bottom: 10px;">
                                <strong>${rec.type}:</strong> ${rec.message}
                            </div>
                        `).join('')}
                    </div>
                </div>
            </div>
        </div>
    `;
    
    dialog.fields_dict.report_html.$wrapper.html(html);
    dialog.show();
}

function show_price_trend_analysis(frm) {
    frappe.call({
        method: 'get_price_trend',
        doc: frm.doc,
        args: {days: 30},
        callback: function(r) {
            if (r.message) {
                let trend_data = r.message;
                frappe.msgprint({
                    title: __('تحلیل روند قیمت (30 روز اخیر)'),
                    message: `
                        <div style="padding: 15px;">
                            <p><strong>روند کلی:</strong> <span class="label ${get_trend_class(trend_data.trend)}">${trend_data.trend}</span></p>
                            <p><strong>درصد تغییر:</strong> ${trend_data.change_percent.toFixed(1)}%</p>
                            <p><strong>تعداد نقاط داده:</strong> ${trend_data.data_points}</p>
                            ${trend_data.first_price ? `<p><strong>قیمت اولیه:</strong> ${format_currency(trend_data.first_price)}</p>` : ''}
                            ${trend_data.last_price ? `<p><strong>قیمت فعلی:</strong> ${format_currency(trend_data.last_price)}</p>` : ''}
                        </div>
                    `,
                    indicator: 'blue'
                });
            }
        }
    });
}

function show_price_history(frm) {
    if (!frm.doc.price_history) {
        frappe.msgprint(__('تاریخچه قیمت موجود نیست'));
        return;
    }
    
    try {
        let price_history = JSON.parse(frm.doc.price_history);
        
        let dialog = new frappe.ui.Dialog({
            title: __('تاریخچه قیمت محصول'),
            size: 'large',
            fields: [
                {
                    fieldtype: 'HTML',
                    fieldname: 'history_html'
                }
            ]
        });
        
        let html = `
            <div style="padding: 15px;">
                <table class="table table-striped">
                    <thead>
                        <tr>
                            <th>تاریخ</th>
                            <th>قیمت</th>
                            <th>تغییر نسبت به قبل</th>
                        </tr>
                    </thead>
                    <tbody>
        `;
        
        for (let i = 0; i < price_history.length; i++) {
            let entry = price_history[i];
            let change = '';
            
            if (i > 0) {
                let prev_price = price_history[i-1].price;
                let change_amount = entry.price - prev_price;
                let change_percent = (change_amount / prev_price) * 100;
                let color = change_amount > 0 ? 'red' : (change_amount < 0 ? 'green' : 'gray');
                change = `<span style="color: ${color}">${change_amount > 0 ? '+' : ''}${format_currency(change_amount)} (${change_percent.toFixed(1)}%)</span>`;
            }
            
            html += `
                <tr>
                    <td>${entry.date}</td>
                    <td>${format_currency(entry.price)}</td>
                    <td>${change}</td>
                </tr>
            `;
        }
        
        html += `
                    </tbody>
                </table>
            </div>
        `;
        
        dialog.fields_dict.history_html.$wrapper.html(html);
        dialog.show();
        
    } catch (e) {
        frappe.msgprint(__('خطا در نمایش تاریخچه قیمت'));
    }
}

// Helper functions
function get_trend_class(trend) {
    switch(trend) {
        case 'صعودی': return 'label-danger';
        case 'نزولی': return 'label-success';
        case 'ثابت': return 'label-info';
        default: return 'label-default';
    }
}

function get_availability_class(status) {
    switch(status) {
        case 'موجود': return 'label-success';
        case 'ناموجود': return 'label-danger';
        case 'محدود': return 'label-warning';
        case 'متوقف شده': return 'label-default';
        default: return 'label-info';
    }
}

function get_priority_class(priority) {
    switch(priority) {
        case 'بالا': return 'danger';
        case 'متوسط': return 'warning';
        case 'پایین': return 'info';
        default: return 'info';
    }
}

function format_currency(amount) {
    return new Intl.NumberFormat('fa-IR').format(amount) + ' ریال';
}
