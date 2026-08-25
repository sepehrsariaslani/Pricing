// Copyright (c) 2024, Your Company and contributors
// For license information, please see license.txt

frappe.ui.form.on('Manual Material Price', {
    refresh: function(frm) {
        // اضافه کردن دکمه پیش‌نمایش تأثیر قیمت
        if (!frm.is_new()) {
            frm.add_custom_button(__('پیش‌نمایش تأثیر قیمت'), function() {
                preview_price_impact(frm);
            }, __('ابزارها'));
            
            frm.add_custom_button(__('به‌روزرسانی قیمت‌ها'), function() {
                update_affected_prices(frm);
            }, __('ابزارها'));
        }
        
        // نمایش اطلاعات ماده اولیه
        if (frm.doc.item_code) {
            show_material_info(frm);
        }
    },
    
    item_code: function(frm) {
        if (frm.doc.item_code) {
            // دریافت اطلاعات ماده اولیه
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Item',
                    filters: {name: frm.doc.item_code},
                    fieldname: ['item_name', 'stock_uom', 'standard_rate']
                },
                callback: function(r) {
                    if (r.message) {
                        frm.set_value('item_name', r.message.item_name);
                        frm.set_value('uom', r.message.stock_uom);
                        
                        // نمایش قیمت فعلی
                        if (r.message.standard_rate) {
                            frm.dashboard.add_comment(
                                `قیمت فعلی: ${format_currency(r.message.standard_rate)}`,
                                'blue'
                            );
                        }
                    }
                }
            });
            
            // نمایش محصولات متأثر
            show_affected_products(frm);
        }
    },
    
    manual_price: function(frm) {
        if (frm.doc.item_code && frm.doc.manual_price) {
            // محاسبه real-time تأثیر قیمت
            calculate_price_impact_preview(frm);
        }
    }
});

function show_material_info(frm) {
    if (!frm.doc.item_code) return;
    
    frappe.call({
        method: 'frappe.client.get_value',
        args: {
            doctype: 'Item',
            filters: {name: frm.doc.item_code},
            fieldname: ['item_name', 'stock_uom', 'standard_rate', 'item_group']
        },
        callback: function(r) {
            if (r.message) {
                let info_html = `
                    <div class="alert alert-info">
                        <h5>📦 اطلاعات ماده اولیه</h5>
                        <p><strong>نام:</strong> ${r.message.item_name}</p>
                        <p><strong>گروه:</strong> ${r.message.item_group}</p>
                        <p><strong>واحد:</strong> ${r.message.stock_uom}</p>
                        <p><strong>قیمت استاندارد:</strong> ${format_currency(r.message.standard_rate || 0)}</p>
                    </div>
                `;
                
                frm.dashboard.add_comment(info_html, 'blue', true);
            }
        }
    });
}

function show_affected_products(frm) {
    if (!frm.doc.item_code) return;
    
    frappe.call({
        method: 'frappe.db.sql',
        args: {
            query: `
                SELECT DISTINCT b.item, b.item_name, COUNT(*) as bom_count
                FROM \`tabBOM\` b
                INNER JOIN \`tabBOM Item\` bi ON b.name = bi.parent
                WHERE bi.item_code = %s 
                AND b.is_active = 1
                GROUP BY b.item, b.item_name
                ORDER BY b.item_name
            `,
            values: [frm.doc.item_code]
        },
        callback: function(r) {
            if (r.message && r.message.length > 0) {
                let products_html = `
                    <div class="alert alert-warning">
                        <h5>🏭 محصولات متأثر (${r.message.length} محصول)</h5>
                        <ul>
                `;
                
                r.message.forEach(function(product) {
                    products_html += `<li>${product[0]} - ${product[1]} (${product[2]} BOM)</li>`;
                });
                
                products_html += `
                        </ul>
                        <small>این محصولات از ماده اولیه ${frm.doc.item_code} استفاده می‌کنند</small>
                    </div>
                `;
                
                frm.dashboard.add_comment(products_html, 'orange', true);
            } else {
                frm.dashboard.add_comment(
                    `⚠️ هیچ محصولی که از ماده ${frm.doc.item_code} استفاده کند پیدا نشد`,
                    'red'
                );
            }
        }
    });
}

function calculate_price_impact_preview(frm) {
    if (!frm.doc.item_code || !frm.doc.manual_price) return;
    
    frappe.call({
        method: 'pricing.pricing.doctype.manual_material_price.manual_material_price.preview_price_impact',
        args: {
            item_code: frm.doc.item_code,
            new_price: frm.doc.manual_price
        },
        callback: function(r) {
            if (r.message) {
                let impact_html = `
                    <div class="alert alert-success">
                        <h5>💰 پیش‌نمایش تأثیر قیمت</h5>
                        <p><strong>قیمت جدید:</strong> ${format_currency(frm.doc.manual_price)}</p>
                        <p><strong>تعداد محصولات متأثر:</strong> ${r.message.affected_count}</p>
                        <p><strong>میانگین تغییر قیمت:</strong> ${r.message.avg_price_change}%</p>
                    </div>
                `;
                
                frm.dashboard.add_comment(impact_html, 'green', true);
            }
        }
    });
}

function preview_price_impact(frm) {
    frappe.call({
        method: 'pricing.pricing.doctype.manual_material_price.manual_material_price.get_detailed_price_impact',
        args: {
            item_code: frm.doc.item_code,
            new_price: frm.doc.manual_price
        },
        callback: function(r) {
            if (r.message) {
                let d = new frappe.ui.Dialog({
                    title: 'جزئیات تأثیر تغییر قیمت',
                    fields: [
                        {
                            fieldtype: 'HTML',
                            fieldname: 'impact_details',
                            options: r.message.html
                        }
                    ],
                    size: 'large'
                });
                d.show();
            }
        }
    });
}

function update_affected_prices(frm) {
    frappe.confirm(
        'آیا مطمئن هستید که می‌خواهید قیمت‌های تمام محصولات متأثر را به‌روزرسانی کنید؟',
        function() {
            frappe.call({
                method: 'pricing.pricing.doctype.manual_material_price.manual_material_price.force_update_prices',
                args: {
                    item_code: frm.doc.item_code,
                    new_price: frm.doc.manual_price
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.msgprint({
                            title: 'به‌روزرسانی موفق',
                            message: r.message.message,
                            indicator: 'green'
                        });
                        frm.refresh();
                    }
                }
            });
        }
    );
}
