import sys
import requests.utils

from pathlib import Path
from appdirs import user_data_dir

__version__ = "1.1"

if getattr(sys, 'frozen', False):
    BASE_PATH = Path(sys._MEIPASS) / "installer"
else:
    BASE_PATH = Path(__file__).parent

# Determine the path to the DLL files
DLL_PATH = BASE_PATH / "dlls"

# Determine the path of the local app data folder
USER_DATA_PATH = Path(user_data_dir("Installer", "U-Bahn Sim Berlin"))

# Create user-agent string
USER_AGENT = f"USBInstaller/{__version__} (+https://dl.u7-trainz.de) {requests.utils.default_user_agent()}"
