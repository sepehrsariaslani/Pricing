// گزارش مواد اولیه خام
// Raw Materials Report Functions

// Helper function to show better success messages for manual prices
function show_manual_prices_success_message(result) {
    if (result.selected_field && result.cost_amount) {
        const formatted_amount = format_currency(result.cost_amount);
        frappe.show_alert({
            message: '✅ ' + result.selected_field + ' به مبلغ ' + formatted_amount + ' اضافه شد - ' + 
                    result.updated_count + ' به‌روزرسانی، ' + result.added_count + ' جدید',
            indicator: 'green'
        });
    } else {
        frappe.show_alert({
            message: result.message,
            indicator: 'green'
        });
    }
}

function show_raw_materials_report(frm) {
    /**
     * نمایش گزارش کامل مواد اولیه خام
     */
    
    frappe.show_alert({
        message: '📊 در حال تهیه گزارش مواد اولیه خام...',
        indicator: 'blue'
    });
    
    frm.call('get_raw_materials_report').then((response) => {
        if (response && response.message) {
            const result = response.message;
            
            if (!result.success) {
                frappe.msgprint({
                    title: '❌ خطا',
                    message: result.message,
                    indicator: 'red'
                });
                return;
            }
            
            show_raw_materials_dialog(result);
        }
    }).catch((error) => {
        frappe.msgprint({
            title: '❌ خطا',
            message: 'خطا در تهیه گزارش مواد اولیه: ' + (error.message || error),
            indicator: 'red'
        });
    });
}

function show_raw_materials_dialog(data) {
    /**
     * نمایش دیالوگ گزارش مواد اولیه
     */
    
    const summary = data.summary;
    const raw_materials = data.raw_materials_summary;
    const detailed_breakdown = data.detailed_breakdown;
    
    // تهیه HTML خلاصه
    let summary_html = '<div class="row mb-3">';
    summary_html += '<div class="col-md-3"><div class="card text-center border-primary"><div class="card-body">';
    summary_html += '<h4 class="card-title text-primary">' + summary.total_items_analyzed + '</h4>';
    summary_html += '<p class="card-text">محصولات تحلیل شده</p></div></div></div>';
    
    summary_html += '<div class="col-md-3"><div class="card text-center border-success"><div class="card-body">';
    summary_html += '<h4 class="card-title text-success">' + summary.total_raw_materials + '</h4>';
    summary_html += '<p class="card-text">مواد اولیه خام</p></div></div></div>';
    
    summary_html += '<div class="col-md-3"><div class="card text-center border-warning"><div class="card-body">';
    summary_html += '<h4 class="card-title text-warning">' + summary.materials_with_manual_prices + '</h4>';
    summary_html += '<p class="card-text">با قیمت دستی</p></div></div></div>';
    
    summary_html += '<div class="col-md-3"><div class="card text-center border-info"><div class="card-body">';
    summary_html += '<h4 class="card-title text-info">' + format_currency(summary.total_raw_materials_cost) + '</h4>';
    summary_html += '<p class="card-text">کل هزینه مواد</p></div></div></div>';
    summary_html += '</div>';
    
    // تهیه جدول خلاصه مواد اولیه
    let materials_table = '<h5 class="mt-4">📋 خلاصه مواد اولیه خام:</h5>';
    materials_table += '<div class="table-responsive">';
    materials_table += '<table class="table table-bordered table-striped table-hover">';
    materials_table += '<thead class="table-dark"><tr>';
    materials_table += '<th>کد ماده</th><th>نام ماده</th><th>مقدار کل</th><th>واحد</th>';
    materials_table += '<th>قیمت واحد</th><th>هزینه کل</th><th>منبع قیمت</th><th>استفاده در</th>';
    materials_table += '</tr></thead><tbody>';
    
    for (const [item_code, material] of Object.entries(raw_materials)) {
        const total_cost = material.total_required_qty * material.unit_cost;
        const price_badge = material.manual_price_available ? 
            '<span class="badge bg-success">دستی</span>' : 
            '<span class="badge bg-secondary">سیستم</span>';
        
        materials_table += '<tr>';
        materials_table += '<td><strong>' + item_code + '</strong></td>';
        materials_table += '<td>' + material.item_name + '</td>';
        materials_table += '<td class="text-end">' + material.total_required_qty.toLocaleString() + '</td>';
        materials_table += '<td>' + material.uom + '</td>';
        materials_table += '<td class="text-end">' + format_currency(material.unit_cost) + '</td>';
        materials_table += '<td class="text-end"><strong>' + format_currency(total_cost) + '</strong></td>';
        materials_table += '<td class="text-center">' + price_badge + '</td>';
        materials_table += '<td class="text-center"><small>' + material.used_in_items.length + ' محصول</small></td>';
        materials_table += '</tr>';
    }
    materials_table += '</tbody></table></div>';
    
    // تهیه جدول تفصیلی
    let detailed_table = '<h5 class="mt-4">🔍 تفکیک تفصیلی به تفکیک محصول:</h5>';
    detailed_table += '<div class="accordion" id="detailedAccordion">';
    
    detailed_breakdown.forEach((item, index) => {
        detailed_table += '<div class="accordion-item">';
        detailed_table += '<h2 class="accordion-header" id="heading' + index + '">';
        detailed_table += '<button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" ';
        detailed_table += 'data-bs-target="#collapse' + index + '" aria-expanded="false">';
        detailed_table += '<strong>' + item.item_code + '</strong> - ' + item.item_name;
        detailed_table += ' <span class="badge bg-primary ms-2">' + format_currency(item.total_raw_cost) + '</span>';
        detailed_table += '</button></h2>';
        detailed_table += '<div id="collapse' + index + '" class="accordion-collapse collapse" ';
        detailed_table += 'data-bs-parent="#detailedAccordion">';
        detailed_table += '<div class="accordion-body">';
        
        detailed_table += '<div class="table-responsive">';
        detailed_table += '<table class="table table-sm table-striped">';
        detailed_table += '<thead><tr><th>کد ماده خام</th><th>نام ماده</th><th>مقدار مورد نیاز</th><th>قیمت واحد</th><th>هزینه کل</th><th>منبع قیمت</th></tr></thead>';
        detailed_table += '<tbody>';
        
        item.raw_materials.forEach(raw_mat => {
            const price_badge = raw_mat.manual_price_available ? 
                '<span class="badge bg-success">دستی</span>' : 
                '<span class="badge bg-secondary">سیستم</span>';
            
            detailed_table += '<tr>';
            detailed_table += '<td><strong>' + raw_mat.item_code + '</strong></td>';
            detailed_table += '<td>' + raw_mat.item_name + '</td>';
            detailed_table += '<td class="text-end">' + raw_mat.required_qty.toLocaleString() + ' ' + raw_mat.uom + '</td>';
            detailed_table += '<td class="text-end">' + format_currency(raw_mat.unit_cost) + '</td>';
            detailed_table += '<td class="text-end"><strong>' + format_currency(raw_mat.total_cost) + '</strong></td>';
            detailed_table += '<td class="text-center">' + price_badge + '</td>';
            detailed_table += '</tr>';
        });
        
        detailed_table += '</tbody></table></div>';
        detailed_table += '</div></div></div>';
    });
    detailed_table += '</div>';
    
    // نمایش دیالوگ
    let dialog = new frappe.ui.Dialog({
        title: '🧱 گزارش کامل مواد اولیه خام',
        size: 'extra-large',
        fields: [
            {
                fieldtype: 'HTML',
                fieldname: 'summary_section',
                options: summary_html
            },
            {
                fieldtype: 'HTML',
                fieldname: 'materials_table',
                options: materials_table
            },
            {
                fieldtype: 'HTML',
                fieldname: 'detailed_table',
                options: detailed_table
            }
        ],
        primary_action_label: '📊 صادرات Excel',
        primary_action: function() {
            export_raw_materials_to_excel(data);
        },
        secondary_action_label: '🔄 به‌روزرسانی قیمت‌ها',
        secondary_action: function() {
            update_missing_raw_materials_prices(data, cur_frm);
        }
    });
    
    dialog.show();
    
    frappe.show_alert({
        message: '✅ گزارش مواد اولیه آماده شد - ' + summary.total_raw_materials + ' ماده خام یافت شد',
        indicator: 'green'
    });
}

function export_raw_materials_to_excel(data) {
    /**
     * صادرات گزارش به Excel
     */
    
    const raw_materials = data.raw_materials_summary;
    let csv_content = 'کد ماده,نام ماده,مقدار کل,واحد,قیمت واحد,هزینه کل,منبع قیمت,تعداد استفاده\n';
    
    for (const [item_code, material] of Object.entries(raw_materials)) {
        const total_cost = material.total_required_qty * material.unit_cost;
        const price_source = material.manual_price_available ? 'دستی' : 'سیستم';
        
        csv_content += '"' + item_code + '","' + material.item_name + '",' + 
                      material.total_required_qty + ',"' + material.uom + '",' +
                      material.unit_cost + ',' + total_cost + ',"' +
                      price_source + '",' + material.used_in_items.length + '\n';
    }
    
    // دانلود فایل
    const blob = new Blob(['\uFEFF' + csv_content], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', 'raw_materials_report_' + frappe.datetime.now_date() + '.csv');
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    frappe.show_alert({
        message: '📊 گزارش به فرمت Excel صادر شد',
        indicator: 'green'
    });
}

function update_missing_raw_materials_prices(data, frm) {
    /**
     * به‌روزرسانی قیمت‌های مواد اولیه که قیمت دستی ندارند
     */
    
    const raw_materials = data.raw_materials_summary;
    const materials_without_manual_prices = Object.entries(raw_materials)
        .filter(([code, material]) => !material.manual_price_available && material.unit_cost > 0);
    
    if (materials_without_manual_prices.length === 0) {
        frappe.msgprint({
            title: '✅ اطلاعات',
            message: 'همه مواد اولیه دارای قیمت دستی هستند یا قیمت سیستمی ندارند',
            indicator: 'green'
        });
        return;
    }
    
    let materials_list = '<ul>';
    materials_without_manual_prices.forEach(([code, material]) => {
        materials_list += '<li><strong>' + code + '</strong> - ' + material.item_name + 
                         ' (قیمت: ' + format_currency(material.unit_cost) + ')</li>';
    });
    materials_list += '</ul>';
    
    frappe.confirm(
        '<p>آیا می‌خواهید <strong>' + materials_without_manual_prices.length + '</strong> ماده اولیه زیر را با قیمت‌های سیستمی به جدول manual_item_prices اضافه کنید؟</p>' +
        '<div style="max-height: 200px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; margin: 10px 0;">' +
        materials_list + '</div>' +
        '<small class="text-muted">این عمل قیمت‌های سیستمی را به عنوان قیمت دستی ثبت می‌کند</small>',
        function() {
            // اضافه مواد به manual_item_prices
            frappe.show_alert({
                message: '🔄 در حال اضافه ' + materials_without_manual_prices.length + ' ماده اولیه...',
                indicator: 'blue'
            });
            
            // ایجاد رکوردهای جدید
            materials_without_manual_prices.forEach(([code, material]) => {
                const new_row = frm.add_child('manual_item_prices');
                new_row.item_code = code;
                new_row.item_name = material.item_name;
                new_row.manual_raw_material_cost = material.unit_cost;
                new_row.manual_operation_cost = 0;
                new_row.manual_overhead_cost = 0;
                new_row.effective_date = frappe.datetime.now_date();
                new_row.notes = 'اضافه شده از گزارش مواد اولیه در ' + frappe.datetime.now();
                new_row.created_by = frappe.session.user;
                new_row.last_updated = frappe.datetime.now();
            });
            
            frm.refresh_field('manual_item_prices');
            frm.dirty();
            
            frappe.show_alert({
                message: '✅ ' + materials_without_manual_prices.length + ' ماده اولیه به جدول قیمت‌های دستی اضافه شد',
                indicator: 'green'
            });
            
            frappe.msgprint({
                title: '✅ تکمیل شد',
                message: 'مواد اولیه اضافه شدند. برای ذخیره تغییرات، دکمه Save را بزنید.',
                indicator: 'green'
            });
        }
    );
}
