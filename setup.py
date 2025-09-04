#!/usr/bin/env python3
"""Setup script for FITS Cataloger."""

import os
import subprocess
import sys
from pathlib import Path


def check_python_version():
    """Check if Python version is compatible."""
    if sys.version_info < (3, 11):
        print("❌ Python 3.11 or higher is required")
        print(f"   Current version: {sys.version}")
        return False
    
    print(f"✅ Python version OK: {sys.version_info.major}.{sys.version_info.minor}")
    return True


def create_virtual_environment():
    """Create virtual environment if it doesn't exist."""
    venv_path = Path("venv")
    
    if venv_path.exists():
        print("✅ Virtual environment already exists")
        return True
    
    print("📦 Creating virtual environment...")
    try:
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
        print("✅ Virtual environment created")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create virtual environment: {e}")
        return False


def get_pip_command():
    """Get the appropriate pip command for the platform."""
    if os.name == 'nt':  # Windows
        return ["venv\\Scripts\\pip"]
    else:  # Unix-like
        return ["venv/bin/pip"]


def install_dependencies():
    """Install Python dependencies."""
    print("📦 Installing dependencies...")
    
    pip_cmd = get_pip_command()
    
    try:
        # Upgrade pip first
        subprocess.run(pip_cmd + ["install", "--upgrade", "pip"], check=True)
        
        # Install requirements
        subprocess.run(pip_cmd + ["install", "-r", "requirements.txt"], check=True)
        
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False


def setup_configuration():
    """Set up initial configuration."""
    config_path = Path("config.json")
    
    if config_path.exists():
        print("✅ Configuration file already exists")
        return True
    
    print("⚙️  Creating default configuration...")
    
    try:
        # Import within function to avoid import errors if deps not installed
        from config import create_default_config
        
        create_default_config("config.json")
        print("✅ Default configuration created")
        print("📝 Please edit config.json with your specific paths and equipment")
        return True
        
    except ImportError as e:
        print(f"❌ Cannot create config (dependencies not installed?): {e}")
        return False
    except Exception as e:
        print(f"❌ Failed to create configuration: {e}")
        return False


def test_installation():
    """Test the installation."""
    print("🧪 Testing installation...")
    
    try:
        # Try importing main modules
        import main
        import config
        import models
        import fits_processor
        import file_monitor
        
        print("✅ All modules import successfully")
        
        # Try running basic test
        result = subprocess.run([
            sys.executable, "test_basic.py"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Basic tests passed")
            return True
        else:
            print("❌ Basic tests failed:")
            print(result.stdout)
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Installation test failed: {e}")
        return False


def print_next_steps():
    """Print next steps for the user."""
    print("\n" + "=" * 50)
    print("🎉 FITS Cataloger Setup Complete!")
    print("=" * 50)
    
    print("\n📋 Next Steps:")
    print("1. Edit config.json with your paths and equipment:")
    print("   - Set quarantine_dir to your incoming files folder")
    print("   - Set image_dir to your organized files folder") 
    print("   - Add your cameras and telescopes")
    
    print("\n2. Test database connection:")
    if os.name == 'nt':
        print("   venv\\Scripts\\python main.py test-db")
    else:
        print("   venv/bin/python main.py test-db")
    
    print("\n3. Perform initial scan:")
    if os.name == 'nt':
        print("   venv\\Scripts\\python main.py scan")
    else:
        print("   venv/bin/python main.py scan")
    
    print("\n4. Start monitoring:")
    if os.name == 'nt':
        print("   venv\\Scripts\\python main.py monitor")
    else:
        print("   venv/bin/python main.py monitor")
    
    print("\n📖 See README.md for detailed usage instructions")


def main():
    """Main setup function."""
    print("FITS Cataloger Setup")
    print("=" * 30)
    
    # Check prerequisites
    if not check_python_version():
        sys.exit(1)
    
    # Setup steps
    steps = [
        ("Creating virtual environment", create_virtual_environment),
        ("Installing dependencies", install_dependencies),
        ("Setting up configuration", setup_configuration),
        ("Testing installation", test_installation),
    ]
    
    for step_name, step_func in steps:
        print(f"\n🔄 {step_name}...")
        if not step_func():
            print(f"❌ Setup failed at: {step_name}")
            sys.exit(1)
    
    print_next_steps()


if __name__ == "__main__":
    main()
