import errno
import io
import json
import shutil
import subprocess
import time
import random
import tempfile
import threading
import queue
import zipfile

from logging import getLogger
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil
import requests

from PIL import Image
from pydantic import BaseModel, field_validator
from pydantic.alias_generators import to_camel
from webview import Window

from installer import USER_DATA_PATH, USER_AGENT, BASE_PATH
from installer.downloader import DownloadClient
from installer.trainz import Kuid, TrainzConfig, TrainzError, TrainzUtil, close_trainz_database, patcher
from installer.utils import fullname, format_speed
from installer.winforms import TaskbarProgressState, set_taskbar_progress

# API endpoint for assets
ASSETS_URL = "https://dl.u7-trainz.de/api/assets.json"

# Kuid stub for scripts
SCRIPTS_KUID = Kuid("kuid:1041339:100113")

# Get logger
logger = getLogger(__name__)


class Asset(BaseModel):
    username: str
    kuid: Kuid
    sha1: str
    file_id: str
    revision: int

    class Config:
        arbitrary_types_allowed = True
        alias_generator = to_camel

    @field_validator("kuid", mode="before")
    def validate_kuid(cls, value: str) -> Kuid:
        if isinstance(value, str):
            return Kuid(value)

        if isinstance(value, Kuid):
            return value

        raise TypeError("Kuid must be a string or Kuid object")

    def get_url(self, download_version: str) -> str:
        return f"https://dl.u7-trainz.de/assets/{download_version}/{self.file_id}.zip?r={self.revision}"


class AssetsResponse(BaseModel):
    assets: List[Asset]
    last_revision: int

    class Config:
        alias_generator = to_camel


class AssetInstaller:
    def __init__(self, window: Window, install_path: Path, download_version: str, max_downloads: int = 0, downscale_textures: bool = False):
        self.window = window
        self.install_path = install_path
        self.download_version = download_version
        self.max_downloads = max_downloads
        self.downscale_textures = downscale_textures
        self.download_client = None
        self.trainz_util = TrainzUtil(install_path, timeout=10*60)
        self.assets = []
        self.failed_assets = []
        self.installed_count = 0
        self.cancelled = False

        # Create the installer and queue threads
        self.installer_thread = None
        self.queue_thread = threading.Thread(target=self._run_queue)
        self.queue = queue.Queue(maxsize=max_downloads)

    def _run_queue(self):
        while True:
            file_path = self.queue.get()

            # Check if the asset is None (end of queue)
            if file_path is None or self.cancelled:
                break

            try:
                self.install_from_path(file_path)
            except Exception as e:
                self._handle_error(e)
                return

            self.queue.task_done()

    def _run_installer(self, from_revision: int = 0, additional_options: Dict[str, Any] = None):
        set_taskbar_progress(TaskbarProgressState.INDETERMINATE)
        time.sleep(random.randint(2, 5))

        try:
            assets_json = self.get_assets()
        except requests.RequestException as e:
            self.show_error("nointernet", "Keine Internetverbindung", f"Bitte überprüfe deine Internetverbindung und versuche es erneut.")
            return

        # Filter assets by revision
        self.assets = [asset for asset in assets_json.assets if asset.revision > from_revision]

        # Check if there are any assets to install
        if not self.assets:
            self.show_error("error", "Keine Assets gefunden", "Es wurden keine neuen Assets gefunden die installiert werden können.")
            return

        # Get scripts asset from the list and remove it
        scripts_asset = next((asset for asset in self.assets if asset.kuid == SCRIPTS_KUID), None)

        # Install scripts asset if found
        if scripts_asset is not None:
            try:
                self.install_scripts(scripts_asset)
            except Exception as e:
                self._handle_error(e)
                return

            self.assets.remove(scripts_asset)

        try:
            if not self.trainz_util.echo("Hello World", timeout=5*60):
                raise TrainzError("Trainz database not started")
        except (subprocess.SubprocessError, TrainzError):
            self.show_error("error", "Fehler beim Starten von Trainz", "Die Trainz-Datenbank konnte nicht geöffnet werden. Bitte überprüfe deine Installation auf Fehler und versuche es erneut.")
            return

        self.update_progress("Warte auf die Installation von Assets...")

        def completion_callback(url: str, file_path: Path):
            # Add the file path to the queue
            self.queue.put(file_path)

            # Start the queue thread if not running
            if not self.queue_thread.is_alive():
                self.queue_thread.start()

        def error_callback(url: str, exc: Exception):
            # Pass the exception to the error handler
            self._handle_error(exc)

        urls = [asset.get_url(self.download_version) for asset in self.assets]

        # Create the download client and start the download
        self.download_client = DownloadClient(urls, USER_DATA_PATH / "Temp", completion_callback, error_callback)
        self.download_client.start()

        # Wait for the download to finish
        while self.download_client.is_running():
            self._update_download_progress()
            time.sleep(0.5)

        # Remove download speed from progress
        downloaded_count = self.download_client.downloaded_count
        total_count = self.download_client.total_count
        self.update_extra_progress(f"Assets werden heruntergeladen... ({downloaded_count}/{total_count})", 100, "100%")

        # Wait for the queue to finish
        self.queue.put(None)
        self.queue_thread.join()

        # Don't continue if the installation was cancelled
        if self.cancelled:
            return

        # Post-installation tasks and cleanup
        set_taskbar_progress(TaskbarProgressState.NORMAL, self.installed_count, len(self.assets))
        self.update_progress("Fertigstellung der Installation...", 100, "")
        self.update_extra_progress(None)

        try:
            self._run_post_install(additional_options)
        except Exception as e:
            self._handle_error(e)
            return

        # Save current assets.json file
        with open(USER_DATA_PATH / "assets.json", "w", encoding="utf-8") as f:
            try:
                json.dump(assets_json.model_dump(mode="json", by_alias=True), f, ensure_ascii=False)
            except Exception as e:
                self._handle_error(e)
                return

        # Show completion message
        if not self.failed_assets:
            self.show_error("success", "Installation abgeschlossen", "Die Installation von U-Bahn Sim Berlin ist erfolgreich abgeschlossen.")
        else:
            self.show_error("warning", "Installation abgeschlossen", "Einige Assets konnten während der Installation nicht eingebunden werden. Bitte überprüfe im Content Manager bevor du das Spiel startest.")

    def _run_post_install(self, additional_options: Dict[str, Any]):
        time.sleep(random.randint(5, 10))

        # Try to commit failed assets
        for kuid in self.failed_assets.copy():
            try:
                self.trainz_util.commit_asset(kuid)
                self.failed_assets.remove(kuid)
            except TrainzError:
                pass

        # Enable additional options if provided
        if additional_options:
            trainzoptions_file = self.install_path / "trainzoptions.txt"
            trainz_options = []

            # Read current trainzoptions.txt file
            with open(trainzoptions_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("-"):
                        trainz_options.append(line.strip())

            # Enable free interior camera
            if additional_options.get("enableFreeintcam", False) and "-freeintcam" not in trainz_options:
                trainz_options.append("-freeintcam")

            # Patch built-in sounds
            if additional_options.get("patchBuiltinSounds", False):
                try:
                    patcher.patch_sounds(self.install_path / "bin" / "trainz.exe")
                except Exception as e:
                    raise e

                if "-disablerailjointsound" not in trainz_options:
                    trainz_options.append("-disablerailjointsound")

            # Write modified trainzoptions.txt file
            with open(trainzoptions_file, "w", encoding="utf-8") as f:
                for option in trainz_options:
                    f.write(f"{option}\n")

        # Copy modified keyboard.txt to settings folder
        keyboard_file = BASE_PATH / "static" / "keyboard_de.txt"  # TODO: Add support for QWERTY
        shutil.copy(keyboard_file, self.install_path / "UserData" / "settings" / "keyboard.txt")

    def _update_download_progress(self):
        total_count = self.download_client.total_count
        downloaded_count = self.download_client.downloaded_count

        # Calculate the progress and speed
        progress = (downloaded_count / total_count) * 100
        current_speed = format_speed(self.download_client.current_speed)
        self.update_extra_progress(
            text=f"Assets werden heruntergeladen ({downloaded_count}/{total_count})",
            progress=progress,
            label=f"{int(progress)}% ({current_speed})"
        )

    def _handle_error(self, exc: Exception):
        logger.error("Error during installation", exc_info=exc)

        # Show an error message based on the exception
        if isinstance(exc, requests.RequestException):
            self.show_error("nointernet", "Keine Internetverbindung", f"Bitte überprüfe deine Internetverbindung und versuche es erneut.\nFehlercode: {fullname(exc)}")
        elif isinstance(exc, PermissionError):
            self.show_error("error", "Zugriffsfehler bei der Installation", "Der Installer hat keinen Schreibzugriff auf das Verzeichnis. Bitte führe die Installation als Administator erneut durch.")
        elif isinstance(exc, FileNotFoundError):
            self.show_error("error", "Datei nicht gefunden", f"Die folgende Datei konnte bei der Installation nicht gefunden werden:\n{exc.filename}")
        elif isinstance(exc, OSError) and exc.errno == errno.ENOSPC:
            self.show_error("error", "Nicht genügend Speicherplatz", "Bitte überprüfe den freien Speicherplatz auf deinem Systemlaufwerk oder begrenze die Anzahl der Downloads und versuche es erneut.")
        else:
            self.show_error("error", "Fehler während der Installation", f"Ein unbekannter Fehler ist während der Installation aufgetreten.\nFehlercode: {fullname(exc)}")

        # Stop the installer
        self.stop()

    def install_from_path(self, file_path: Path):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)

            # Extract the asset to the temporary directory
            with zipfile.ZipFile(file_path, "r") as zf:
                zf.extractall(temp_dir)

            # Load the asset config file
            config_file = TrainzConfig(temp_dir / "config.txt", encoding="auto")

            # Update the progress
            progress = (self.installed_count / len(self.assets)) * 100
            set_taskbar_progress(TaskbarProgressState.NORMAL, self.installed_count, len(self.assets))
            self.update_progress(f"Installiere Asset \"{config_file.username}\" <{config_file.kuid}>...", progress, f"{int(progress)}%")

            # Downscale textures if enabled
            if self.downscale_textures:
                for image_file in temp_dir.glob("**/*"):
                    # Skip directories
                    if not image_file.is_file():
                        continue

                    # Skip non-image files
                    if image_file.suffix.lower() not in [".bmp", ".jpg", ".jpeg", ".tga"]:
                        continue

                    with open(image_file, "rb") as f:
                        image = Image.open(io.BytesIO(f.read()))

                        # Don't downscale images smaller than 512x512
                        if image.width <= 512 or image.height <= 512:
                            continue

                    new_image = image.resize((image.width // 2, image.height // 2), Image.Resampling.BICUBIC)
                    new_image.save(image_file)

            # Install the asset
            self.trainz_util.delete_asset(config_file.kuid)
            self.trainz_util.install_from_path(temp_dir)

            try:
                self.trainz_util.commit_asset(config_file.kuid)
            except TrainzError:
                self.failed_assets.append(config_file.kuid)

            self.installed_count += 1

        # Delete the downloaded file
        file_path.unlink(missing_ok=True)

    def install_scripts(self, asset: Asset):
        self.update_progress("Installiere Skripte, dies kann eine Weile dauern...")

        # Define the local and temporary filenames
        local_filename = USER_DATA_PATH / "Temp" / f"{asset.file_id}.zip"
        temp_filename = local_filename.with_suffix(local_filename.suffix + ".part")

        if not local_filename.parent.exists():
            local_filename.parent.mkdir(parents=True)

        # Download the scripts asset
        with requests.get(asset.get_url(self.download_version), headers={"User-Agent": USER_AGENT}, stream=True) as r:
            r.raise_for_status()

            with temp_filename.open("wb") as f:
                for chunk in r.iter_content(chunk_size=4096):
                    f.write(chunk)

            temp_filename.replace(local_filename)

        # Check and close TADDaemon if still running
        for process in psutil.process_iter():
            if process.name().lower() == "taddaemon.exe":
                close_trainz_database()
                break

        # Extract the scripts asset to the install path
        with zipfile.ZipFile(local_filename, "r") as zf:
            zf.extractall(self.install_path / "scripts")

        # Delete the downloaded file
        local_filename.unlink(missing_ok=True)

    def update_progress(self, text: Optional[str] = None, progress: Optional[float] = None, label: Optional[str] = None, intermediate: Optional[bool] = None, color: Optional[str] = None):
        text = json.dumps(text, ensure_ascii=False)
        progress = f"{progress:.2f}" if progress is not None else "null"
        label = json.dumps(label, ensure_ascii=False)
        self.window.evaluate_js(f'updateProgress({text}, {progress}, {label}, {json.dumps(intermediate)}, {json.dumps(color)})')

    def update_extra_progress(self, text: Optional[str] = None, progress: Optional[float] = None, label: Optional[str] = None):
        text = json.dumps(text, ensure_ascii=False)
        progress = f"{progress:.2f}" if progress is not None else "null"
        label = json.dumps(label, ensure_ascii=False)
        self.window.evaluate_js(f'updateExtraProgress({text}, {progress}, {label})')

    def show_error(self, type: str, title: str, message: str):
        set_taskbar_progress(TaskbarProgressState.NO_PROGRESS)
        title = json.dumps(title, ensure_ascii=False)
        message = json.dumps(message, ensure_ascii=False)
        self.window.evaluate_js(f'showError("{type}", {title}, {message})')

    def start(self, from_revision: int = 0, additional_options: Dict[str, Any] = None):
        self.installer_thread = threading.Thread(target=self._run_installer, args=(from_revision, additional_options))
        self.installer_thread.start()

    def stop(self):
        self.cancelled = True
        self.queue.put(None)
        self.queue.join()
        self.installer_thread.join()
        self.download_client.stop()

    @staticmethod
    def get_assets(from_revision: int = 0) -> AssetsResponse:
        # Build the request URL
        if from_revision > 0:
            request_url = f"{ASSETS_URL}?revision={from_revision}"
        else:
            request_url = ASSETS_URL

        r = requests.get(request_url, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()

        # Parse the JSON response
        return AssetsResponse.model_validate(r.json())

    @staticmethod
    def load_assets(file_path: Path) -> AssetsResponse:
        # Load the assets from the file
        with open(file_path, "r", encoding="utf-8") as f:
            return AssetsResponse.model_validate(json.load(f))
