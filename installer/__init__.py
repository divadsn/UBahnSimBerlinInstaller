import sys
import requests

from pathlib import Path
from platform import python_version
from appdirs import user_data_dir

if getattr(sys, 'frozen', False):
    BASE_PATH = Path(sys._MEIPASS) / "installer"
else:
    BASE_PATH = Path(__file__).parent

# Determine the path to the DLL files
DLL_PATH = BASE_PATH / "dlls"

# Determine the path of the local app data folder
USER_DATA_PATH = Path(user_data_dir("Installer", "U-Bahn Sim Berlin"))

# Create user-agent string
USER_AGENT = f"USBInstaller/1.1 (+https://dl.u7-trainz.de) Python/{python_version()} requests/{requests.__version__}"
