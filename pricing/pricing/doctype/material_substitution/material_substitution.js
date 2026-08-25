frappe.ui.form.on('Material Substitution', {
    original_item: function(frm) {
        if (frm.doc.original_item) {
            // محاسبه خودکار قیمت کالای اصلی
            calculate_item_price(frm, 'original_item', 'original_item_price');
        }
    },
    
    substitute_item: function(frm) {
        if (frm.doc.substitute_item) {
            // محاسبه خودکار قیمت کالای جایگزین
            calculate_item_price(frm, 'substitute_item', 'substitute_item_price');
        }
    }
});

function calculate_item_price(frm, item_field, price_field) {
    if (!frm.doc[item_field]) return;
    
    frappe.call({
        method: 'pricing.pricing.doctype.material_substitution.material_substitution.get_item_price_for_substitution',
        args: {
            item_code: frm.doc[item_field]
        },
        callback: function(r) {
            if (r.message) {
                frm.set_value(price_field, r.message);
                calculate_price_difference(frm);
            }
        }
    });
}

function calculate_price_difference(frm) {
    if (frm.doc.original_item_price && frm.doc.substitute_item_price) {
        // محاسبه تفاوت قیمت
        let price_diff = frm.doc.original_item_price - frm.doc.substitute_item_price;
        frm.set_value('price_difference', price_diff);
        
        // محاسبه درصد صرفه‌جویی
        if (frm.doc.original_item_price > 0) {
            let savings_percentage = (price_diff / frm.doc.original_item_price) * 100;
            frm.set_value('cost_savings_percentage', savings_percentage);
        }
        
        // رنگ‌آمیزی بر اساس صرفه‌جویی
        apply_savings_styling(frm);
    }
}

function apply_savings_styling(frm) {
    setTimeout(() => {
        if (frm.doc.cost_savings_percentage > 0) {
            // صرفه‌جویی مثبت - رنگ سبز
            frm.fields_dict.cost_savings_percentage.$wrapper.find('.control-input').css({
                'background-color': '#d4edda',
                'border-color': '#c3e6cb',
                'color': '#155724'
            });
        } else if (frm.doc.cost_savings_percentage < 0) {
            // هزینه بیشتر - رنگ قرمز
            frm.fields_dict.cost_savings_percentage.$wrapper.find('.control-input').css({
                'background-color': '#f8d7da',
                'border-color': '#f5c6cb',
                'color': '#721c24'
            });
        }
    }, 100);
}
