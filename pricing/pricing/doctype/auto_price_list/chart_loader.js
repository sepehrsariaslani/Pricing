// ==================== بارگذاری Chart.js ====================

function load_chartjs_library() {
    /**
     * بارگذاری کتابخانه Chart.js اگر لود نشده باشد
     */
    
    if (typeof Chart !== 'undefined') {
        console.log('Chart.js already loaded');
        return Promise.resolve();
    }
    
    return new Promise((resolve, reject) => {
        console.log('Loading Chart.js library...');
        
        // بارگذاری Chart.js از CDN
        const script = document.createElement('script');
        script.src = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.js';
        script.onload = function() {
            console.log('Chart.js loaded successfully');
            resolve();
        };
        script.onerror = function() {
            console.error('Failed to load Chart.js');
            // سعی در بارگذاری از CDN دیگر
            const fallback_script = document.createElement('script');
            fallback_script.src = 'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.js';
            fallback_script.onload = function() {
                console.log('Chart.js loaded from fallback CDN');
                resolve();
            };
            fallback_script.onerror = function() {
                console.error('Failed to load Chart.js from fallback CDN');
                reject(new Error('Chart.js could not be loaded'));
            };
            document.head.appendChild(fallback_script);
        };
        document.head.appendChild(script);
    });
}

// بارگذاری خودکار Chart.js هنگام لود صفحه
$(document).ready(function() {
    load_chartjs_library();
});

// اضافه کردن به window برای دسترسی سراسری
window.load_chartjs_library = load_chartjs_library;
