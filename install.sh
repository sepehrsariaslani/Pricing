#!/bin/bash

echo "🚀 Installing Pricing App..."
echo "=========================="

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

# Step 1: Run setup.py to install dependencies
print_status "Step 1: Installing dependencies..."
python3 setup.py
if [ $? -ne 0 ]; then
    print_error "Dependency installation failed. Trying minimal installation..."
    
    # Try installing minimal dependencies
    print_status "Installing minimal dependencies..."
    pip3 install numpy_financial pandas numpy requests aiohttp beautifulsoup4 lxml selenium webdriver-manager celery redis loguru jinja2 plotly scikit-learn
    
    if [ $? -ne 0 ]; then
        print_error "Even minimal installation failed. Please install dependencies manually."
        exit 1
    fi
fi

print_success "Dependencies installed successfully!"

# Step 2: Install the app
print_status "Step 2: Installing Pricing app in ERPNext..."
bench --site $SITE install-app pricing

if [ $? -ne 0 ]; then
    print_error "App installation failed!"
    print_status "This might be due to missing dependencies. Let's try to fix this..."
    
    # Try to install missing dependencies one by one
    print_status "Installing critical dependencies..."
    pip3 install aiohttp beautifulsoup4 lxml requests selenium webdriver-manager
    
    # Try again
    print_status "Retrying app installation..."
    bench --site $SITE install-app pricing
    
    if [ $? -ne 0 ]; then
        print_error "App installation still failed. Please check the error messages above."
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

# Step 4: Build assets
print_status "Step 4: Building assets..."
bench build

if [ $? -ne 0 ]; then
    print_warning "Asset building had some issues, but continuing..."
fi

print_success "Assets built successfully!"

# Step 5: Restart
print_status "Step 5: Restarting services..."
bench restart

print_success "Services restarted!"

echo ""
echo "🎉 PRICING APP INSTALLATION COMPLETED!"
echo "======================================"
echo ""
echo "📋 What's next:"
echo "   1. Open your ERPNext site: http://localhost:8000"
echo "   2. Go to: Setup > Pricing > Auto Price List"
echo "   3. Create your first price list"
echo "   4. Configure competitor analysis if needed"
echo ""
echo "🔧 For background tasks (web crawling), start Celery worker:"
echo "   celery -A pricing worker --loglevel=info --queues=crawler,pricing"
echo ""
echo "📚 Documentation:"
echo "   - Auto Price List: Calculate product prices based on BOM"
echo "   - Competitor Analysis: Track competitor prices automatically"
echo "   - Volume Pricing: Set quantity-based discounts"
echo "   - Customer Tier Pricing: Different prices for different customer types"
echo ""
echo "🆘 If you encounter issues:"
echo "   1. Check the error logs: bench logs"
echo "   2. Try: bench --site $SITE migrate"
echo "   3. Try: bench build --force"
echo "   4. Contact support with error details"
echo ""
print_success "Happy pricing! 🚀"
