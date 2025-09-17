#!/usr/bin/env python3
"""
Setup script for Pricing App
This script handles installation of dependencies and initial setup
"""

import os
import sys
import subprocess
import json
from pathlib import Path

def run_command(command, description="", ignore_errors=False):
    """Run a shell command with proper error handling"""
    print(f"\n{'='*60}")
    print(f"🔧 {description}")
    print(f"{'='*60}")
    print(f"Running: {command}")
    
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            check=True, 
            capture_output=True, 
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        
        if result.stdout:
            print("✅ Output:")
            print(result.stdout)
        
        print(f"✅ {description} completed successfully!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error in {description}:")
        print(f"Exit code: {e.returncode}")
        if e.stdout:
            print("STDOUT:", e.stdout)
        if e.stderr:
            print("STDERR:", e.stderr)
        
        if not ignore_errors:
            print(f"❌ Setup failed at: {description}")
            sys.exit(1)
        else:
            print(f"⚠️  Warning: {description} failed but continuing...")
            return False

def check_frappe_bench():
    """Check if we're in a Frappe bench environment"""
    current_dir = Path.cwd()
    
    # Check if we're in apps directory
    if current_dir.name == "pricing" and current_dir.parent.name == "apps":
        bench_dir = current_dir.parent.parent
        return bench_dir
    
    # Check if we're in bench directory
    if (current_dir / "apps" / "frappe").exists():
        return current_dir
    
    print("❌ Error: This script must be run from a Frappe bench directory or the pricing app directory")
    sys.exit(1)

def install_system_dependencies():
    """Install system-level dependencies (Host-friendly version)"""
    print("\n🔧 Checking system dependencies...")
    
    # For shared hosting, we usually can't install system packages
    # So we'll just check and inform the user
    
    missing_deps = []
    
    # Check Python development headers
    try:
        import distutils.util
        print("✅ Python development tools available")
    except ImportError:
        missing_deps.append("Python development headers")
    
    # Check if we can compile C extensions
    try:
        import subprocess
        result = subprocess.run(['python3', '-c', 'import distutils.ccompiler; distutils.ccompiler.new_compiler()'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ C compiler available")
        else:
            missing_deps.append("C compiler (build-essential)")
    except:
        missing_deps.append("C compiler (build-essential)")
    
    if missing_deps:
        print("⚠️  Missing system dependencies (contact your hosting provider):")
        for dep in missing_deps:
            print(f"   - {dep}")
        print("\n📧 Send this to your hosting provider:")
        print("   Please install: python3-dev build-essential libxml2-dev libxslt1-dev")
        print("   For web crawling: chromium-browser or google-chrome")
        print("   For caching: redis-server (optional)")
    else:
        print("✅ All required system dependencies are available")

def install_python_dependencies():
    """Install Python dependencies from requirements.txt (Host-friendly version)"""
    requirements_file = Path(__file__).parent / "requirements.txt"
    
    if not requirements_file.exists():
        print("❌ requirements.txt not found!")
        sys.exit(1)
    
    # Check if we have pip access
    try:
        subprocess.run(["python3", "-m", "pip", "--version"], check=True, capture_output=True)
        print("✅ pip is available")
    except:
        print("❌ pip is not available or accessible")
        print("📧 Contact your hosting provider to enable pip or install packages manually")
        return False
    
    # Upgrade pip first (with user flag for shared hosting)
    run_command(
        "python3 -m pip install --user --upgrade pip",
        "Upgrading pip (user mode)"
    )
    
    # Essential dependencies only (for hosting compatibility)
    essential_deps = [
        "numpy_financial>=1.0.0",
        "requests>=2.31.0",
        "aiohttp>=3.8.0", 
        "beautifulsoup4>=4.12.0",
        "lxml>=4.9.0",
        "jinja2>=3.1.0",
        "loguru>=0.7.0",
    ]
    
    # Optional dependencies (install if possible)
    optional_deps = [
        "pandas>=2.0.0",
        "numpy>=1.24.0",
        "selenium>=4.15.0",
        "webdriver-manager>=4.0.0",
        "celery>=5.3.0",
        "redis>=5.0.0",
        "plotly>=5.15.0",
        "scikit-learn>=1.3.0",
    ]
    
    print("\n🔧 Installing essential dependencies...")
    failed_essential = []
    for dep in essential_deps:
        success = run_command(
            f"python3 -m pip install --user '{dep}'",
            f"Installing {dep.split('>=')[0]}",
            ignore_errors=True
        )
        if not success:
            failed_essential.append(dep)
    
    print("\n🔧 Installing optional dependencies...")
    failed_optional = []
    for dep in optional_deps:
        success = run_command(
            f"python3 -m pip install --user '{dep}'",
            f"Installing {dep.split('>=')[0]}",
            ignore_errors=True
        )
        if not success:
            failed_optional.append(dep)
    
    # Report results
    if failed_essential:
        print("\n❌ Failed to install essential dependencies:")
        for dep in failed_essential:
            print(f"   - {dep}")
        print("\n📧 Contact your hosting provider or try manual installation")
        return False
    
    if failed_optional:
        print("\n⚠️  Some optional features may not work due to missing dependencies:")
        for dep in failed_optional:
            print(f"   - {dep}")
        print("   (Advanced features like ML pricing and web crawling may be limited)")
    
    print("\n✅ Core dependencies installed successfully!")
    return True

def setup_celery():
    """Setup Celery for background tasks"""
    celery_setup_file = Path(__file__).parent / "setup_celery.py"
    
    celery_content = '''#!/usr/bin/env python3
"""
Celery setup for Pricing App background tasks
"""

import os
from celery import Celery

# Set default Django settings module for 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

app = Celery('pricing')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# Celery configuration
app.conf.update(
    broker_url='redis://localhost:6379/0',
    result_backend='redis://localhost:6379/0',
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Tehran',
    enable_utc=True,
    task_routes={
        'pricing.pricing.doctype.competitor_analysis.tasks.*': {'queue': 'crawler'},
        'pricing.pricing.doctype.auto_price_list.tasks.*': {'queue': 'pricing'},
    },
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=1000,
)

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
'''
    
    with open(celery_setup_file, 'w', encoding='utf-8') as f:
        f.write(celery_content)
    
    print("✅ Celery setup file created")

def create_install_script():
    """Create a convenient install script"""
    install_script = Path(__file__).parent / "install.sh"
    
    script_content = '''#!/bin/bash

echo "🚀 Installing Pricing App..."

# Run setup.py
python3 setup.py

# Install the app
echo "📦 Installing Pricing app in ERPNext..."
bench --site $(bench get-site) install-app pricing

# Migrate
echo "🔄 Running migrations..."
bench --site $(bench get-site) migrate

# Build assets
echo "🏗️  Building assets..."
bench build

# Restart
echo "🔄 Restarting services..."
bench restart

echo "✅ Pricing App installation completed!"
echo ""
echo "🎉 You can now access the Pricing features in your ERPNext site"
echo ""
echo "📋 Next steps:"
echo "   1. Go to Setup > Pricing > Auto Price List"
echo "   2. Create your first price list"
echo "   3. Configure competitor analysis if needed"
echo ""
echo "🔧 For background tasks (web crawling), start Celery worker:"
echo "   celery -A pricing worker --loglevel=info --queues=crawler,pricing"
'''
    
    with open(install_script, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    # Make it executable
    os.chmod(install_script, 0o755)
    
    print("✅ Install script created: install.sh")

def create_requirements_minimal():
    """Create a minimal requirements file for essential dependencies only"""
    minimal_deps = [
        "# Essential dependencies for Pricing App",
        "numpy_financial>=1.0.0",
        "pandas>=2.0.0",
        "numpy>=1.24.0",
        "requests>=2.31.0",
        "aiohttp>=3.8.0",
        "beautifulsoup4>=4.12.0",
        "lxml>=4.9.0",
        "selenium>=4.15.0",
        "webdriver-manager>=4.0.0",
        "celery>=5.3.0",
        "redis>=5.0.0",
        "loguru>=0.7.0",
        "jinja2>=3.1.0",
        "plotly>=5.15.0",
        "scikit-learn>=1.3.0",
    ]
    
    minimal_file = Path(__file__).parent / "requirements_minimal.txt"
    with open(minimal_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(minimal_deps))
    
    print("✅ Minimal requirements file created: requirements_minimal.txt")

def main():
    """Main setup function"""
    print("🚀 Pricing App Setup Starting...")
    print("="*60)
    
    # Check environment
    bench_dir = check_frappe_bench()
    print(f"✅ Frappe bench detected at: {bench_dir}")
    
    # Change to bench directory for commands
    os.chdir(bench_dir)
    
    try:
        # Step 1: Install system dependencies
        install_system_dependencies()
        
        # Step 2: Install Python dependencies
        install_python_dependencies()
        
        # Step 3: Setup Celery
        setup_celery()
        
        # Step 4: Create helper scripts
        create_install_script()
        create_requirements_minimal()
        
        print("\n" + "="*60)
        print("🎉 SETUP COMPLETED SUCCESSFULLY!")
        print("="*60)
        print()
        print("📋 Next steps:")
        print("   1. Run: bench --site [your-site] install-app pricing")
        print("   2. Run: bench --site [your-site] migrate")
        print("   3. Run: bench build")
        print("   4. Run: bench restart")
        print()
        print("🔧 Or simply run the install script:")
        print("   ./install.sh")
        print()
        print("⚠️  If you encounter any issues, try installing minimal dependencies:")
        print("   pip install -r requirements_minimal.txt")
        
    except KeyboardInterrupt:
        print("\n❌ Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
