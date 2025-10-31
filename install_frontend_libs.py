#!/usr/bin/env python3
"""
FITS Cataloger - Frontend Library Installer
This script downloads and installs JavaScript and CSS libraries that aren't included in the repository.
"""

import os
import sys
import urllib.request
from pathlib import Path


# Library definitions with URLs and target paths
LIBRARIES = {
    "js": [
        {
            "name": "Vue.js 3",
            "url": "https://cdn.jsdelivr.net/npm/vue@3.4.21/dist/vue.global.prod.js",
            "filename": "vue.global.prod.js"
        },
        {
            "name": "Axios",
            "url": "https://cdn.jsdelivr.net/npm/axios@1.6.7/dist/axios.min.js",
            "filename": "axios.min.js"
        },
        {
            "name": "Toast UI Editor JS",
            "url": "https://uicdn.toast.com/editor/latest/toastui-editor-all.min.js",
            "filename": "toastui-editor-all.min.js"
        }
    ],
    "css": [
        {
            "name": "Tailwind CSS",
            "urls": [  # Multiple URLs to try in order
                "https://unpkg.com/tailwindcss@2.2.19/dist/tailwind.min.css",
                "https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css",
                "https://cdnjs.cloudflare.com/ajax/libs/tailwindcss/2.2.19/tailwind.min.css"
            ],
            "filename": "tailwind.min.css",
            "note": "Using Tailwind CSS v2.2.19 (last version with pre-built CSS)"
        },
        {
            "name": "Toast UI Editor CSS",
            "url": "https://uicdn.toast.com/editor/latest/toastui-editor.min.css",
            "filename": "toastui-editor.min.css"
        }
    ]
}


def download_file(url: str, output_path: Path) -> bool:
    """Download a file from a URL to the specified path."""
    try:
        print(f"  Downloading from {url}...")
        with urllib.request.urlopen(url, timeout=30) as response:
            content = response.read()
        
        with open(output_path, 'wb') as f:
            f.write(content)
        
        return True
    except Exception as e:
        print(f"  ✗ Error downloading: {e}")
        return False


def download_with_fallbacks(lib: dict, output_path: Path) -> bool:
    """Download a file, trying multiple URLs if provided."""
    urls = lib.get("urls", [lib.get("url")])  # Support both 'url' and 'urls'
    
    if isinstance(urls, str):
        urls = [urls]
    
    for i, url in enumerate(urls):
        if i > 0:
            print(f"  Trying fallback URL {i}...")
        
        if download_file(url, output_path):
            return True
    
    return False


def install_libraries():
    """Install all frontend libraries."""
    # Get script directory and static directory
    script_dir = Path(__file__).parent.resolve()
    static_dir = script_dir / "static"
    
    print("=" * 50)
    print("FITS Cataloger - Frontend Library Installer")
    print("=" * 50)
    print()
    
    # Create directories
    js_lib_dir = static_dir / "js" / "lib"
    css_lib_dir = static_dir / "css" / "lib"
    
    print("Creating library directories...")
    js_lib_dir.mkdir(parents=True, exist_ok=True)
    css_lib_dir.mkdir(parents=True, exist_ok=True)
    print("✓ Directories created")
    print()
    
    # Track results
    total_files = sum(len(libs) for libs in LIBRARIES.values())
    downloaded = 0
    skipped = 0
    failed = 0
    
    # Install JavaScript libraries
    print("Installing JavaScript libraries...")
    print("-" * 50)
    for lib in LIBRARIES["js"]:
        output_path = js_lib_dir / lib["filename"]
        
        if output_path.exists():
            print(f"⊙ {lib['name']} already exists, skipping")
            skipped += 1
        else:
            print(f"→ {lib['name']}")
            if download_with_fallbacks(lib, output_path):
                print(f"✓ {lib['name']} downloaded successfully")
                downloaded += 1
            else:
                print(f"✗ Failed to download {lib['name']}")
                failed += 1
        print()
    
    # Install CSS libraries
    print("Installing CSS libraries...")
    print("-" * 50)
    for lib in LIBRARIES["css"]:
        output_path = css_lib_dir / lib["filename"]
        
        if output_path.exists():
            print(f"⊙ {lib['name']} already exists, skipping")
            skipped += 1
        else:
            print(f"→ {lib['name']}")
            if lib.get("note"):
                print(f"  Note: {lib['note']}")
            if download_with_fallbacks(lib, output_path):
                print(f"✓ {lib['name']} downloaded successfully")
                downloaded += 1
            else:
                print(f"✗ Failed to download {lib['name']}")
                failed += 1
        print()
    
    # Print summary
    print("=" * 50)
    if failed == 0:
        print("✓ Frontend library installation complete!")
    else:
        print(f"⚠ Installation completed with {failed} error(s)")
    print("=" * 50)
    print()
    print("Summary:")
    print(f"  Total files:     {total_files}")
    print(f"  Downloaded:      {downloaded}")
    print(f"  Skipped:         {skipped}")
    print(f"  Failed:          {failed}")
    print()
    
    if downloaded > 0 or skipped > 0:
        print("Installed libraries:")
        print("  JavaScript:")
        print("    - Vue.js 3.4.21")
        print("    - Axios 1.6.7")
        print("    - Toast UI Editor (latest)")
        print("  CSS:")
        print("    - Tailwind CSS 2.2.19")
        print("    - Toast UI Editor (latest)")
        print()
    
    if failed == 0:
        print("You can now run the web interface with: python run_web.py")
        return 0
    else:
        print("Please check your internet connection and try again.")
        return 1


def main():
    """Main entry point."""
    try:
        sys.exit(install_libraries())
    except KeyboardInterrupt:
        print("\n\nInstallation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()