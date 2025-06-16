import sys

from pathlib import Path
from logging import getLogger

import httpx

from appdirs import user_data_dir

__version__ = "1.5"
__version_info__ = tuple(map(int, __version__.split(".")))

VERSION_CODE = 9

if getattr(sys, 'frozen', False):
    BASE_PATH = Path(sys._MEIPASS) / __name__
else:
    BASE_PATH = Path(__file__).parent

# Determine the path to the DLL files
DLL_PATH = BASE_PATH / "dlls"

# Determine the path to the templates folder
TEMPLATES_PATH = BASE_PATH / "templates"

# Determine the path of the local app data folder
USER_DATA_PATH = Path(user_data_dir("Installer", "U-Bahn Sim Berlin"))

# Create user-agent string
USER_AGENT = f"USBInstaller/{__version__} (+https://dl.u7-trainz.de) {httpx._client.USER_AGENT}"

# Set database URL based on the user data path
DATABASE_URL = f"sqlite:///{USER_DATA_PATH / 'database.db'}"

logger = getLogger(__name__)
