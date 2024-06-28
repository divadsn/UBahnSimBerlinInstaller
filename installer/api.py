import os
import json

from pathlib import Path
from typing import Any, Optional, Dict

import psutil
import requests
import wmi

from webview import Window
from webview.platforms.winforms import BrowserView

from installer import USER_DATA_PATH
from installer.config import get_config
from installer.installer import AssetInstaller
from installer.trainz import find_trainz_install_path
from installer.winforms import show_message_box, show_folder_picker_dialog, MessageBoxButtons, MessageBoxIcon

config_path = USER_DATA_PATH / "config.json"


class InstallerAPI:
    def __init__(self):
        self._window: Optional[Window] = None

        if not USER_DATA_PATH.exists():
            USER_DATA_PATH.mkdir(parents=True)

        if os.path.exists(USER_DATA_PATH / "assets.json"):
            self._installed_assets = AssetInstaller.load_assets(USER_DATA_PATH / "assets.json")
        else:
            self._installed_assets = None

        self._config = get_config(config_path)

    def getConfig(self) -> Dict[str, Any]:
        return self._config.model_dump(mode="json", by_alias=True)

    def saveConfig(self):
        # Save the config to the file
        with open(config_path, "w", encoding="utf-8") as file:
            json.dump(self.getConfig(), file, indent=4, ensure_ascii=False)

    def isInstalled(self) -> bool:
        # It is not installed if the config file doesn't exist
        if not config_path.exists():
            return False

        # Check if the user has already installed
        return self._installed_assets is not None

    def isInstallationAborted(self) -> bool:
        # Check if the user has aborted the installation before (lock file exists)
        return Path(USER_DATA_PATH / "assets.json.lock").exists()

    def isNvidiaGPU(self) -> bool:
        # Create a WMI object
        wmi_obj = wmi.WMI()

        # Query WMI for GPU information
        gpu_info = wmi_obj.Win32_VideoController()

        # Check if user has an NVIDIA GPU
        for gpu in gpu_info:
            if "nvidia" in gpu.Description.lower():
                return True

        return False

    def findInstallPath(self) -> Optional[str]:
        return find_trainz_install_path(check_user=False)

    def selectInstallPath(self, current_path) -> Optional[str]:
        i = BrowserView.instances.get(self._window.uid)
        selected_path = show_folder_picker_dialog(initial_directory=current_path, window=i)

        # Do nothing if the user cancels the dialog
        if not selected_path:
            return None

        # Validate the selected path
        if not self.validateInstallPath(selected_path):
            show_message_box("Der ausgewählte Pfad enthält keine Trainz-Installation.", "Fehler", MessageBoxButtons.OK, MessageBoxIcon.WARNING, window=i)
            return None

        return selected_path

    def validateInstallPath(self, path: str, save_config: bool = False) -> bool:
        # Check if selected path contains Trainz.exe, bin/Trainz.exe or bin/ContentManager.exe
        files_to_check = ["Trainz.exe", "bin/ContentManager.exe", "bin/Trainz.exe", "bin/TrainzUtil.exe"]

        for file in files_to_check:
            if not os.path.exists(os.path.join(path, file)):
                return False

        if save_config:
            self._config.install_path = path

        return True

    def isTrainzRunning(self) -> bool:
        process_names = ["trainz.exe", "contentmanager.exe", "launcher.exe"]

        # Check if Trainz.exe or ContentManager.exe is running
        for proc in psutil.process_iter():
            if proc.name().lower() in process_names:
                return True

        return False

    def checkForUpdates(self) -> Optional[int]:
        try:
            new_assets = AssetInstaller.get_assets(from_revision=self._installed_assets.last_revision)
        except requests.HTTPError as e:
            # Check if the server returned a 404 error
            if e.response.status_code == 404:
                return None
            else:
                raise e

        # Return new revision number
        return new_assets.last_revision

    def startInstall(self, install_path: str, download_version: str, additional_options: Dict[str, Any]):
        self._config.install_path = install_path
        self._config.download_version = download_version
        self._config.downscale_textures = additional_options.pop("downscaleTextures", False)
        self._config.max_downloads = additional_options.pop("maxDownloads", 0)

        try:
            self.saveConfig()
        except Exception as e:
            i = BrowserView.instances.get(self._window.uid)
            show_message_box(str(e), "Fehler", MessageBoxButtons.OK, MessageBoxIcon.ERROR, window=i)
            return

        installer = AssetInstaller(self._window, Path(install_path), download_version, self._config.max_downloads, self._config.downscale_textures)
        installer.start(additional_options.pop("fromRevision", 0), additional_options)

    def startUpdate(self):
        installer = AssetInstaller(self._window, self._config.install_path, self._config.download_version, self._config.max_downloads, self._config.downscale_textures)
        installer.start(from_revision=self._installed_assets.last_revision)

    def openContentManager(self):
        # Open ContentManager.exe
        os.startfile(os.path.join(self._config.install_path, "bin", "ContentManager.exe"))

    def openTrainz(self):
        # Open Trainz.exe
        os.startfile(os.path.join(self._config.install_path, "Trainz.exe"))

    def setConfirmClose(self, confirm_close: bool):
        self._window.confirm_close = confirm_close

    def setTitle(self, title: str):
        self._window.set_title(title)

    def close(self):
        self._window.destroy()
