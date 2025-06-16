import os
import json

from logging import getLogger
from pathlib import Path
from typing import Any, Optional, Dict

import httpx
import psutil
import webview
import wmi

from webview import Window
from webview.platforms.winforms import BrowserView

from usb_installer import USER_DATA_PATH, database as db
from usb_installer.config import get_config
from usb_installer.database.models import Installation
from usb_installer.installer import AssetInstaller
from usb_installer.trainz import find_trainz_install_path
from usb_installer.winforms import show_message_box, show_folder_picker_dialog, MessageBoxButtons, MessageBoxIcon

logger = getLogger(__name__)


class InstallerAPI:
    def __init__(self):
        if os.path.exists(USER_DATA_PATH / "assets.json"):
            self._installed_assets = AssetInstaller.load_assets(USER_DATA_PATH / "assets.json")
        else:
            self._installed_assets = None

        self._config = get_config(USER_DATA_PATH / "config.json")

    def getConfig(self) -> Dict[str, Any]:
        return self._config.model_dump(mode="json", by_alias=True)

    def saveConfig(self):
        # Save the config to the file
        with open(USER_DATA_PATH / "config.json", "w", encoding="utf-8") as file:
            json.dump(self.getConfig(), file, indent=4, ensure_ascii=False)

    def isInstalled(self) -> bool:
        # Check if there is at least one completed installation in the database
        with db.SessionLocal() as session:
            installations = session.query(Installation).filter(Installation.finished_at.isnot(None)).count()
            return installations > 0

        return False

    def isInstallationAborted(self) -> bool:
        # Check if the last installation is not completed (finished_at is None) and not cancelled
        with db.SessionLocal() as session:
            last_installation = session.query(Installation).order_by(Installation.started_at.desc()).first()
            if last_installation and last_installation.finished_at is None and not last_installation.cancelled:
                logger.warning("Last installation was aborted or not completed")
                return True

        logger.info("No incomplete or aborted installation found")
        return False

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
        logger.info("Searching for Trainz installation path...")
        trainz_path = find_trainz_install_path(check_user=False)

        if not trainz_path:
            logger.warning("No Trainz installation found.")
            return None

        logger.info(f"Found Trainz installation at: {trainz_path}")
        return trainz_path

    def selectInstallPath(self, current_path) -> Optional[str]:
        logger.info("Opening folder picker dialog to select Trainz installation path...")
        i = BrowserView.instances.get(webview.windows[0].uid)
        selected_path = show_folder_picker_dialog(initial_directory=current_path, window=i)

        # Do nothing if the user cancels the dialog
        if not selected_path:
            logger.info("User cancelled the folder picker dialog.")
            return None

        # Validate the selected path
        if not self.validateInstallPath(selected_path):
            logger.warning("The selected path does not contain a valid Trainz installation: %s", selected_path)
            show_message_box("Der ausgewählte Pfad enthält keine Trainz-Installation.", "Fehler", MessageBoxButtons.OK, MessageBoxIcon.WARNING, window=i)
            return None

        logger.info("Selected Trainz installation path: %s", selected_path)
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
        logger.info("Checking if Trainz is currently running...")
        process_names = ["trainz.exe", "contentmanager.exe", "launcher.exe"]

        # Check if Trainz.exe or ContentManager.exe is running
        for proc in psutil.process_iter():
            try:
                if proc.name().lower() in process_names:
                    exe_dir = os.path.dirname(proc.exe())
                    if "trainz.exe" in [f.lower() for f in os.listdir(exe_dir)]:
                        logger.warning("Trainz is currently running (%s, PID: %s)", proc.name(), proc.pid)
                        return True
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                continue

        return False

    def checkForMigration(self) -> bool:
        # Check if the assets.json file exists
        if not os.path.exists(USER_DATA_PATH / "assets.json"):
            return False

        # Check if the database is already migrated
        with db.SessionLocal() as session:
            installation = session.query(Installation).order_by(Installation.started_at.desc()).first()
            if installation and installation.from_revision == 0:
                return False

        return True

    def checkForUpdates(self) -> Optional[int]:
        try:
            new_assets = AssetInstaller.get_assets(from_revision=self._installed_assets.last_revision)
        except httpx.HTTPStatusError as e:
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
            i = BrowserView.instances.get(webview.windows[0].uid)
            show_message_box(str(e), "Fehler", MessageBoxButtons.OK, MessageBoxIcon.ERROR, window=i)
            return

        installer = AssetInstaller(webview.windows[0], Path(install_path), download_version, self._config.max_downloads, self._config.downscale_textures)
        installer.start(additional_options.pop("fromRevision", 0), additional_options)

    def startUpdate(self):
        installer = AssetInstaller(webview.windows[0], self._config.install_path, self._config.download_version, self._config.max_downloads, self._config.downscale_textures)
        installer.start(from_revision=self._installed_assets.last_revision)

    def openContentManager(self):
        # Open ContentManager.exe
        os.startfile(os.path.join(self._config.install_path, "bin", "ContentManager.exe"))

    def openTrainz(self):
        # Open Trainz.exe
        os.startfile(os.path.join(self._config.install_path, "Trainz.exe"))

    def setConfirmClose(self, confirm_close: bool):
        webview.windows[0].confirm_close = confirm_close

    def setTitle(self, title: str):
        webview.windows[0].set_title(title)

    def close(self):
        webview.windows[0].destroy()
