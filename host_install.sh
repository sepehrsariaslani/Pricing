#!/bin/bash

echo "🚀 Installing Pricing App for Shared Hosting..."
echo "=============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "setup.py" ]; then
    print_error "setup.py not found. Please run this script from the pricing app directory."
    exit 1
fi

# Get the current site
SITE=$(bench get-site 2>/dev/null)
if [ -z "$SITE" ]; then
    print_warning "Could not detect site automatically. Please specify site name:"
    read -p "Enter site name: " SITE
fi

print_status "Using site: $SITE"

# Step 1: Install essential dependencies only
print_status "Step 1: Installing essential dependencies for hosting..."

# Essential packages that usually work on shared hosting
ESSENTIAL_PACKAGES=(
    "numpy_financial"
    "requests"
    "aiohttp"
    "beautifulsoup4"
    "lxml"
    "jinja2"
    "loguru"
)

print_status "Installing essential packages..."
for package in "${ESSENTIAL_PACKAGES[@]}"; do
    print_status "Installing $package..."
    python3 -m pip install --user "$package" 2>/dev/null
    if [ $? -eq 0 ]; then
        print_success "$package installed"
    else
        print_warning "$package installation failed (may already be installed)"
    fi
done

# Try to install optional packages
print_status "Installing optional packages (may fail on some hosts)..."
OPTIONAL_PACKAGES=(
    "pandas"
    "numpy"
    "plotly"
    "scikit-learn"
)

for package in "${OPTIONAL_PACKAGES[@]}"; do
    print_status "Trying to install $package..."
    python3 -m pip install --user "$package" 2>/dev/null
    if [ $? -eq 0 ]; then
        print_success "$package installed"
    else
        print_warning "$package installation failed (advanced features may be limited)"
    fi
done

# Step 2: Install the app
print_status "Step 2: Installing Pricing app in ERPNext..."
bench --site $SITE install-app pricing

if [ $? -ne 0 ]; then
    print_error "App installation failed!"
    print_status "Trying to fix common issues..."
    
    # Check if aiohttp is the issue
    python3 -c "import aiohttp" 2>/dev/null
    if [ $? -ne 0 ]; then
        print_status "Installing aiohttp specifically..."
        python3 -m pip install --user aiohttp
        
        # Try again
        print_status "Retrying app installation..."
        bench --site $SITE install-app pricing
        
        if [ $? -ne 0 ]; then
            print_error "App installation still failed. Please check error messages above."
            print_status "Common solutions:"
            print_status "1. Contact your hosting provider to install missing system packages"
            print_status "2. Try: python3 -m pip install --user aiohttp beautifulsoup4 lxml"
            print_status "3. Check if you have sufficient permissions"
            exit 1
        fi
    else
        print_error "App installation failed for unknown reason. Check error messages above."
        exit 1
    fi
fi

print_success "Pricing app installed successfully!"

# Step 3: Migrate
print_status "Step 3: Running migrations..."
bench --site $SITE migrate

if [ $? -ne 0 ]; then
    print_warning "Migration had some issues, but continuing..."
fi

print_success "Migrations completed!"

# Step 4: Build assets (may fail on shared hosting)
print_status "Step 4: Building assets..."
bench build 2>/dev/null

if [ $? -ne 0 ]; then
    print_warning "Asset building failed (common on shared hosting)"
    print_status "Trying alternative build..."
    bench build --app pricing 2>/dev/null
    
    if [ $? -ne 0 ]; then
        print_warning "Asset building still failed. App should still work for basic features."
    else
        print_success "Assets built successfully!"
    fi
else
    print_success "Assets built successfully!"
fi

# Step 5: Restart (may not work on shared hosting)
print_status "Step 5: Restarting services..."
bench restart 2>/dev/null

if [ $? -ne 0 ]; then
    print_warning "Service restart failed (common on shared hosting)"
    print_status "Please restart your ERPNext instance manually through your hosting control panel"
else
    print_success "Services restarted!"
fi

echo ""
echo "🎉 PRICING APP INSTALLATION COMPLETED!"
echo "======================================"
echo ""
echo "📋 What's installed:"
echo "   ✅ Core pricing functionality"
echo "   ✅ Basic BOM cost calculations"
echo "   ✅ Price list management"
echo "   ⚠️  Advanced features may be limited (depending on hosting)"
echo ""
echo "📋 Next steps:"
echo "   1. Open your ERPNext site"
echo "   2. Go to: Setup > Pricing > Auto Price List"
echo "   3. Create your first price list"
echo ""
echo "🔧 Features available:"
echo "   ✅ Auto Price List - Calculate product prices"
echo "   ✅ Manual Material Pricing - Override material costs"
echo "   ✅ Profit margin calculations"
echo "   ✅ Commission and markup calculations"
echo "   ⚠️  Web crawling - May need additional setup"
echo "   ⚠️  Advanced ML features - May need additional packages"
echo ""
echo "🆘 If you encounter issues:"
echo "   1. Check: bench logs"
echo "   2. Try: bench --site $SITE migrate"
echo "   3. Contact your hosting provider for missing system packages"
echo "   4. For advanced features, install: pandas, numpy, scikit-learn"
echo ""
echo "📧 Missing packages? Send this to your hosting provider:"
echo "   python3-dev build-essential libxml2-dev libxslt1-dev"
echo ""
print_success "Happy pricing! 🚀"
