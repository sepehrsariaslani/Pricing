// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Fixed Costs Settings', {
    refresh: function(frm) {
        // اضافه کردن دکمه محاسبه
        frm.add_custom_button(__('محاسبه هزینه‌های ثابت'), function() {
            calculate_fixed_costs(frm);
        }, __('عملیات'));
        
        // اضافه کردن دکمه نمایش تفکیک
        frm.add_custom_button(__('نمایش تفکیک حساب‌ها'), function() {
            show_account_breakdown(frm);
        }, __('گزارش‌ها'));
        
        // اضافه کردن دکمه پیشنهاد حساب‌ها
        frm.add_custom_button(__('پیشنهاد حساب‌های هزینه ثابت'), function() {
            suggest_fixed_cost_accounts(frm);
        }, __('کمک'));
    },
    
    calculation_method: function(frm) {
        // محاسبه مجدد هنگام تغییر روش محاسبه
        if (frm.doc.fixed_costs_accounts && frm.doc.fixed_costs_accounts.length > 0) {
            calculate_fixed_costs(frm);
        }
    },
    
    months_for_average: function(frm) {
        // محاسبه مجدد هنگام تغییر تعداد ماه
        if (frm.doc.calculation_method === 'میانگین چند ماه گذشته' && 
            frm.doc.fixed_costs_accounts && frm.doc.fixed_costs_accounts.length > 0) {
            calculate_fixed_costs(frm);
        }
    }
});

frappe.ui.form.on('Fixed Cost Account', {
    account: function(frm, cdt, cdn) {
        // به‌روزرسانی نام حساب هنگام انتخاب
        let row = locals[cdt][cdn];
        if (row.account) {
            frappe.db.get_value('Account', row.account, 'account_name')
                .then(r => {
                    if (r.message) {
                        frappe.model.set_value(cdt, cdn, 'account_name', r.message.account_name);
                    }
                });
        }
    },
    
    fixed_costs_accounts_add: function(frm, cdt, cdn) {
        // تنظیم پیش‌فرض برای ردیف جدید
        frappe.model.set_value(cdt, cdn, 'is_active', 1);
    }
});

function calculate_fixed_costs(frm) {
    /**
     * محاسبه هزینه‌های ثابت
     */
    
    if (!frm.doc.fixed_costs_accounts || frm.doc.fixed_costs_accounts.length === 0) {
        frappe.msgprint(__('لطفاً ابتدا حساب‌های هزینه ثابت را تعریف کنید'));
        return;
    }
    
    frappe.show_alert({
        message: 'در حال محاسبه هزینه‌های ثابت...',
        indicator: 'blue'
    });
    
    frappe.call({
        method: 'pricing.pricing.doctype.fixed_costs_settings.fixed_costs_settings.calculate_fixed_costs',
        callback: function(r) {
            if (r.message && r.message.success) {
                const result = r.message;
                
                // به‌روزرسانی فیلدها
                frm.set_value('current_monthly_fixed_costs', result.monthly_fixed_costs);
                frm.set_value('last_calculation_date', frappe.datetime.now_datetime());
                frm.set_value('last_updated_by', frappe.session.user);
                
                // نمایش پیام موفقیت
                const formatted_amount = format_currency(result.monthly_fixed_costs);
                frappe.show_alert({
                    message: `هزینه‌های ثابت محاسبه شد: ${formatted_amount} ریال`,
                    indicator: 'green'
                });
                
                // نمایش جزئیات
                show_calculation_details(frm, result);
                
            } else {
                const error = r.message ? r.message.error : 'خطای نامشخص';
                frappe.show_alert({
                    message: `خطا در محاسبه: ${error}`,
                    indicator: 'red'
                });
            }
        },
        error: function(err) {
            console.error('Error calculating fixed costs:', err);
            frappe.show_alert({
                message: 'خطا در ارتباط با سرور',
                indicator: 'red'
            });
        }
    });
}

function show_account_breakdown(frm) {
    /**
     * نمایش تفکیک حساب‌ها
     */
    
    frappe.call({
        method: 'pricing.pricing.doctype.fixed_costs_settings.fixed_costs_settings.get_fixed_costs_breakdown',
        callback: function(r) {
            if (r.message && r.message.length > 0) {
                show_breakdown_dialog(frm, r.message);
            } else {
                frappe.msgprint(__('ابتدا هزینه‌های ثابت را محاسبه کنید'));
            }
        }
    });
}

function suggest_fixed_cost_accounts(frm) {
    /**
     * پیشنهاد حساب‌های هزینه ثابت
     */
    
    frappe.call({
        method: 'frappe.desk.search.search_link',
        args: {
            doctype: 'Account',
            txt: '',
            filters: {
                'account_type': 'Expense',
                'is_group': 0
            }
        },
        callback: function(r) {
            if (r.results && r.results.length > 0) {
                show_account_suggestions_dialog(frm, r.results);
            } else {
                frappe.msgprint(__('هیچ حساب هزینه‌ای یافت نشد'));
            }
        }
    });
}

function show_calculation_details(frm, result) {
    /**
     * نمایش جزئیات محاسبه
     */
    
    const dialog = new frappe.ui.Dialog({
        title: __('جزئیات محاسبه هزینه‌های ثابت'),
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'details_html'
            }
        ]
    });
    
    const formatted_amount = format_currency(result.monthly_fixed_costs);
    
    const html = `
        <div style="padding: 20px;">
            <div class="alert alert-success">
                <h4><i class="fa fa-check-circle"></i> محاسبه با موفقیت انجام شد</h4>
                <h3 style="color: #27ae60;">${formatted_amount} ریال</h3>
            </div>
            
            <div class="row">
                <div class="col-md-6">
                    <h5>اطلاعات محاسبه:</h5>
                    <ul>
                        <li><strong>روش محاسبه:</strong> ${result.calculation_method}</li>
                        <li><strong>تعداد حساب‌ها:</strong> ${result.accounts_count}</li>
                        <li><strong>بازه زمانی:</strong> ${result.date_range}</li>
                    </ul>
                </div>
                <div class="col-md-6">
                    <h5>کاربرد:</h5>
                    <ul>
                        <li>محاسبه نقطه سر به سر</li>
                        <li>تحلیل سودآوری</li>
                        <li>برنامه‌ریزی مالی</li>
                        <li>قیمت‌گذاری محصولات</li>
                    </ul>
                </div>
            </div>
        </div>
    `;
    
    dialog.fields_dict.details_html.$wrapper.html(html);
    dialog.show();
}

function show_breakdown_dialog(frm, breakdown) {
    /**
     * نمایش تفکیک حساب‌ها
     */
    
    const dialog = new frappe.ui.Dialog({
        title: __('تفکیک هزینه‌های ثابت بر اساس حساب‌ها'),
        size: 'extra-large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'breakdown_html'
            }
        ]
    });
    
    let table_rows = '';
    let total_amount = 0;
    
    breakdown.forEach(item => {
        total_amount += item.amount;
        const formatted_amount = format_currency(item.amount);
        const percentage = item.percentage.toFixed(1);
        
        table_rows += `
            <tr>
                <td>${item.account}</td>
                <td>${item.account_name}</td>
                <td>${item.description || '-'}</td>
                <td class="text-right">${formatted_amount}</td>
                <td class="text-right">${percentage}%</td>
            </tr>
        `;
    });
    
    const formatted_total = format_currency(total_amount);
    
    const html = `
        <div style="padding: 20px;">
            <div class="alert alert-info">
                <h4>مجموع هزینه‌های ثابت ماهانه: ${formatted_total} ریال</h4>
            </div>
            
            <table class="table table-bordered table-striped">
                <thead>
                    <tr style="background-color: #f8f9fa;">
                        <th>کد حساب</th>
                        <th>نام حساب</th>
                        <th>توضیحات</th>
                        <th class="text-right">مبلغ (ریال)</th>
                        <th class="text-right">درصد</th>
                    </tr>
                </thead>
                <tbody>
                    ${table_rows}
                </tbody>
                <tfoot>
                    <tr style="background-color: #e9ecef; font-weight: bold;">
                        <td colspan="3">مجموع</td>
                        <td class="text-right">${formatted_total}</td>
                        <td class="text-right">100.0%</td>
                    </tr>
                </tfoot>
            </table>
        </div>
    `;
    
    dialog.fields_dict.breakdown_html.$wrapper.html(html);
    dialog.show();
}

function show_account_suggestions_dialog(frm, accounts) {
    /**
     * نمایش پیشنهادات حساب‌های هزینه ثابت
     */
    
    const dialog = new frappe.ui.Dialog({
        title: __('پیشنهاد حساب‌های هزینه ثابت'),
        size: 'large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'suggestions_html'
            }
        ],
        primary_action_label: __('اضافه کردن انتخاب شده‌ها'),
        primary_action: function() {
            const selected_accounts = [];
            dialog.$wrapper.find('input[type="checkbox"]:checked').each(function() {
                const account_code = $(this).val();
                const account_name = $(this).data('account-name');
                selected_accounts.push({
                    account: account_code,
                    account_name: account_name,
                    is_active: 1
                });
            });
            
            if (selected_accounts.length > 0) {
                // اضافه کردن به جدول
                selected_accounts.forEach(acc => {
                    const row = frm.add_child('fixed_costs_accounts');
                    row.account = acc.account;
                    row.account_name = acc.account_name;
                    row.is_active = acc.is_active;
                });
                
                frm.refresh_field('fixed_costs_accounts');
                
                frappe.show_alert({
                    message: `${selected_accounts.length} حساب اضافه شد`,
                    indicator: 'green'
                });
                
                dialog.hide();
            } else {
                frappe.msgprint(__('لطفاً حداقل یک حساب انتخاب کنید'));
            }
        }
    });
    
    // فیلتر حساب‌های مرتبط با هزینه ثابت
    const fixed_cost_keywords = [
        'اجاره', 'rent', 'حقوق', 'salary', 'دستمزد', 'بیمه', 'insurance',
        'استهلاک', 'depreciation', 'تلفن', 'اینترنت', 'آب', 'گاز', 'برق',
        'نگهبانی', 'نظافت', 'کارمزد', 'سود'
    ];
    
    const relevant_accounts = accounts.filter(acc => {
        const account_name = acc.description.toLowerCase();
        return fixed_cost_keywords.some(keyword => account_name.includes(keyword));
    });
    
    let suggestions_html = `
        <div style="padding: 15px;">
            <p><strong>حساب‌های پیشنهادی برای هزینه‌های ثابت:</strong></p>
            <div style="max-height: 400px; overflow-y: auto;">
    `;
    
    relevant_accounts.forEach(acc => {
        suggestions_html += `
            <div class="checkbox" style="margin: 8px 0;">
                <label>
                    <input type="checkbox" value="${acc.value}" data-account-name="${acc.description}">
                    <strong>${acc.value}</strong> - ${acc.description}
                </label>
            </div>
        `;
    });
    
    if (relevant_accounts.length === 0) {
        suggestions_html += '<p class="text-muted">هیچ حساب مرتبطی یافت نشد. می‌توانید به صورت دستی حساب‌ها را اضافه کنید.</p>';
    }
    
    suggestions_html += `
            </div>
            <div class="alert alert-info" style="margin-top: 15px;">
                <small>
                    <strong>نکته:</strong> این پیشنهادات بر اساس نام حساب‌ها و کلمات کلیدی مرتبط با هزینه‌های ثابت ارائه شده‌اند.
                    شما می‌توانید حساب‌های دیگری را نیز به صورت دستی اضافه کنید.
                </small>
            </div>
        </div>
    `;
    
    dialog.fields_dict.suggestions_html.$wrapper.html(suggestions_html);
    dialog.show();
}
