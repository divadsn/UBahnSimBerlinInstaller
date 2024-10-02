import os
import psutil
import subprocess
import time
import winreg

from typing import Optional

from .trainzutil import TrainzError, TrainzUtil
from .trainzconfig import Kuid, TrainzConfig

__all__ = ["Kuid", "TrainzConfig", "TrainzError", "TrainzUtil", "close_trainz_database", "find_trainz_install_path"]


def find_trainz_install_path(check_64bit: bool = False, check_user: bool = False) -> Optional[str]:
    hkey = winreg.HKEY_LOCAL_MACHINE

    # Determine the registry path based on the system architecture
    if check_64bit:
        registry_path = "Software\\WOW6432Node\\Auran\\Products\\TrainzSimulator"
    else:
        registry_path = "Software\\Auran\\Products\\TrainzSimulator"

    # Add the virtual store path if the user install path should be checked
    if check_user:
        hkey = winreg.HKEY_CURRENT_USER
        registry_path = "Software\\Classes\\VirtualStore\\Machine\\" + registry_path

    try:
        with (winreg.OpenKey(hkey, registry_path) as registry_key):
            for i in range(winreg.QueryInfoKey(registry_key)[0]):
                subkey_name = winreg.EnumKey(registry_key, i)

                with winreg.OpenKey(registry_key, subkey_name) as subkey:
                    product_build = winreg.QueryValueEx(subkey, "ProductBuild")[0]

                    # Check if the product build is a number
                    if not product_build.isdigit():
                        continue

                    build_number = int(product_build)

                    # Check if the product build is within the range of supported builds
                    if 37625 <= build_number <= 49933:
                        product_install_path = winreg.QueryValueEx(subkey, "ProductInstallPath")[0]

                        # Check if the product install path exists
                        if not os.path.exists(product_install_path):
                            continue

                        # Check if the product install path contains the required files
                        if not os.path.exists(os.path.join(product_install_path, "bin", "Trainz.exe")):
                            continue

                        return product_install_path
    except FileNotFoundError:
        pass

    # Retry if no installation path was found in the system registry
    if not check_user:
        return find_trainz_install_path(check_64bit=check_64bit, check_user=True)

    # Retry if no 32-bit installation path was found
    if not check_64bit:
        return find_trainz_install_path(check_64bit=True)

    return None


def close_trainz_database() -> bool:
    process = subprocess.run(["taskkill", "/IM", "TADDaemon.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # If process failed to close, return False
    if process.returncode != 0:
        return False

    # Wait for process to close
    while True:
        for process in psutil.process_iter():
            if process.name().lower() == "taddaemon.exe":
                break
        else:
            break

        time.sleep(1)

    return True
