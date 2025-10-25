import os
import sys
import requests
import zipfile
import platform
import shutil

PLATFORM_TOOLS_URLS = {
    'darwin': 'https://dl.google.com/android/repository/platform-tools-latest-darwin.zip',
    'win32': 'https://dl.google.com/android/repository/platform-tools-latest-windows.zip',
    'linux': 'https://dl.google.com/android/repository/platform-tools-latest-linux.zip',
}

def download_and_unzip(url, dest_folder):
    """Downloads and unzips a file."""
    if not os.path.exists(dest_folder):
        os.makedirs(dest_folder)
    
    zip_path = os.path.join(dest_folder, 'platform-tools.zip')
    
    print(f"Downloading {url} to {zip_path}...")
    try:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(zip_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
    except Exception as e:
        print(f"Failed to download: {e}")
        return False

    print(f"Unzipping {zip_path}...")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(dest_folder)
    except Exception as e:
        print(f"Failed to unzip: {e}")
        return False
    finally:
        os.remove(zip_path)
        
    return True

def main():
    current_platform = sys.platform
    if current_platform not in PLATFORM_TOOLS_URLS:
        print(f"Unsupported platform: {current_platform}")
        return

    url = PLATFORM_TOOLS_URLS[current_platform]
    
    # Download and unzip to a temporary directory
    temp_dir = 'temp_platform_tools'
    if not download_and_unzip(url, temp_dir):
        return

    # Find adb and copy it to the resources folder
    platform_tools_dir = os.path.join(temp_dir, 'platform-tools')
    
    if sys.platform == 'darwin':
        platform_res_dir = 'src/adbfs'
        adb_exe = 'adb'
    elif sys.platform == 'win32':
        platform_res_dir = 'src/adbfs'
        adb_exe = 'adb.exe'
    elif sys.platform.startswith('linux'):
        platform_res_dir = 'src/adbfs'
        adb_exe = 'adb'
    
    if not os.path.exists(platform_res_dir):
        os.makedirs(platform_res_dir)
        
    src_adb_path = os.path.join(platform_tools_dir, adb_exe)
    dest_adb_path = os.path.join(platform_res_dir, adb_exe)
    
    if os.path.exists(src_adb_path):
        print(f"Copying {adb_exe} to {platform_res_dir}...")
        shutil.copy(src_adb_path, dest_adb_path)
        
        # On Windows, we also need AdbWinApi.dll and AdbWinUsbApi.dll
        if sys.platform == 'win32':
            for dll in ['AdbWinApi.dll', 'AdbWinUsbApi.dll']:
                src_dll_path = os.path.join(platform_tools_dir, dll)
                if os.path.exists(src_dll_path):
                    shutil.copy(src_dll_path, platform_res_dir)
    else:
        print(f"Error: {adb_exe} not found in {platform_tools_dir}")

    # Clean up
    print("Cleaning up temporary files...")
    shutil.rmtree(temp_dir)
    
    print("ADB setup complete.")

if __name__ == '__main__':
    main()
