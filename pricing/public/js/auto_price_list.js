frappe.provide('pricing.auto_price_list');

frappe.ui.form.on('Auto Price List', {
    refresh: function (frm) {
        // دکمه اعمال قیمت‌ها - برای هر دو حالت (قبل و بعد از Submit)
        if (frm.fields_dict.update_prices_button && frm.fields_dict.update_prices_button.$input) {
            frm.fields_dict.update_prices_button.$input.off('click.pricing').on('click.pricing', function () {
                frappe.confirm(
                    'آیا می‌خواهید قیمت‌های این لیست را در لیست قیمت "' + frm.doc.price_list + '" اعمال کنید؟',
                    function () {
                        frappe.call({
                            method: 'pricing.pricing.doctype.auto_price_list.auto_price_list.update_prices',
                            args: {
                                docname: frm.doc.name
                            },
                            freeze: true,
                            freeze_message: __('در حال اعمال قیمت‌ها...'),
                            callback: function (r) {
                                if (r.message && r.message.success) {
                                    frappe.show_alert({
                                        message: r.message.message,
                                        indicator: r.message.indicator
                                    });
                                } else if (r.message) {
                                    frappe.msgprint({
                                        title: 'خطا',
                                        message: r.message.message,
                                        indicator: 'red'
                                    });
                                }
                            }
                        });
                    }
                );
            });
        }

        // مخفی کردن تب‌های فرآیندها و عملیات‌ها بعد از Submit
        if (frm.doc.docstatus === 1) {
            frm.set_df_property('pricing_strategies_tab', 'hidden', 1);
            frm.set_df_property('pricing_processes_tab', 'hidden', 1);
            frm.set_df_property('bulk_pricing_tab', 'hidden', 1);
        }
    }
    // Removed auto-triggers: profit_margin, items_add, items_remove
    // These were calling calculate_prices() on every change, which called
    // update_item_prices_with_details + frm.reload_doc(), overwriting unsaved changes.
    // Use the manual "محاسبه بهای تمام شده" button instead.
});