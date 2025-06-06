import subprocess

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union

from usb_installer.trainz.trainzconfig import Kuid

__all__ = ["AssetStatus", "TrainzError", "TrainzUtil"]


@dataclass
class AssetStatus:
    """
    Data class to represent the status of an asset in Trainz.
    """

    open_for_edit: bool
    installed: bool
    archived: bool
    download_station: bool
    modified: bool
    missing_dependencies: bool
    faulty: bool


class TrainzError(Exception):
    """
    Custom exception for errors from TrainzUtil.
    """

    pass


class TrainzUtil:
    """
    Utility class for interacting with TrainzUtil.exe to manage Trainz assets.
    """

    def __init__(self, trainz_path: Union[Path, str], timeout: Optional[float] = None):
        """
        Initialize the TrainzUtil with the path to Trainz and an optional timeout.

        :param trainz_path: Path to the Trainz installation directory.
        :param timeout: Optional timeout for command execution in seconds.
        :raises FileNotFoundError: If TrainzUtil.exe is not found in the specified path.
        """
        trainzutil_path = Path(trainz_path) / "bin" / "TrainzUtil.exe"

        if not trainzutil_path.exists():
            raise FileNotFoundError(f"TrainzUtil.exe not found at {trainz_path}")

        self.trainzutil_path = trainzutil_path
        self.timeout = timeout

    def run_command(self, command: str, *args, timeout: Optional[float] = None) -> List[str]:
        """
        Run a command using TrainzUtil and return the output.

        :param command: The command to run (e.g., "version", "echo", "installCDP").
        :param args: Additional arguments for the command.
        :param timeout: Optional timeout for the command execution.
        :raises TrainzError: If the command returns an error.
        :return: List of output lines from the command.
        """
        process = subprocess.run(
            args=[self.trainzutil_path, command, *args],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            encoding="utf-8",
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout if timeout else self.timeout,
        )

        # Split the output into lines
        output = process.stdout.split("\n")

        for line in output:
            if line.startswith("-"):
                raise TrainzError(line.split(" : ", maxsplit=1)[1].strip())
        else:
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, process.args, process.stdout, process.stderr)

        return output

    def build_version(self, timeout: Optional[float] = None) -> int:
        """
        Get the build version of Trainz.

        :param timeout: Optional timeout for the command execution.
        :return: Build version as an integer.
        """
        output = self.run_command("version", timeout=timeout)
        return int(output[0].split()[1])

    def echo(self, message: str, timeout: Optional[float] = None) -> bool:
        """
        Echo a message to the TrainzUtil command line and check if it matches.

        :param message: The message to echo.
        :param timeout: Optional timeout for the command execution.
        :return: True if the echoed message matches, False otherwise.
        """
        output = self.run_command("echo", message, timeout=timeout)
        return output[0].strip() == message

    def install_cdp(self, file_path: Union[Path, str]) -> Kuid:
        """
        Install a CDP file using TrainzUtil.

        :param file_path: Path to the CDP file to install.
        :return: The kuid of the installed asset.
        """
        output = self.run_command("installCDP", str(file_path))
        return Kuid.from_string(output[0].split("<")[1].split(">")[0])

    def install_from_path(self, asset_path: Union[Path, str]) -> Kuid:
        """
        Install an asset from a given path using TrainzUtil.

        :param asset_path: Path to the asset to install.
        :return: The kuid of the installed asset.
        """
        output = self.run_command("installfrompath", str(asset_path))
        return Kuid.from_string(output[0].split("<")[1].split(">")[0])

    def open_for_edit(self, kuid: Union[Kuid, str]) -> Path:
        """
        Open an asset for editing using its kuid.

        :param kuid: The kuid of the asset to open for editing.
        :return: Path to the asset file opened for editing.
        """
        output = self.run_command("edit", str(kuid))
        return Path(output[0].split(" : ", maxsplit=1)[1].strip())

    def commit_asset(self, kuid: Union[Kuid, str]) -> bool:
        """
        Commit an asset that has been opened for editing.

        :param kuid: The kuid of the asset to commit.
        :return: True if the commit was successful, False otherwise.
        """
        try:
            self.run_command("commit", str(kuid))
        except subprocess.CalledProcessError:
            return False

        return True

    def revert_asset(self, kuid: Union[Kuid, str]) -> bool:
        """
        Revert an asset that has been opened for editing.

        :param kuid: The kuid of the asset to revert.
        :return: True if the revert was successful, False otherwise.
        """
        try:
            self.run_command("revert", str(kuid))
        except subprocess.CalledProcessError:
            return False

        return True

    def delete_asset(self, kuid: Union[Kuid, str]) -> bool:
        """
        Delete an asset using its kuid.

        :param kuid: The kuid of the asset to delete.
        :return: True if the deletion was successful, False otherwise.
        """
        try:
            self.run_command("delete", str(kuid))
        except subprocess.CalledProcessError:
            return False

        return True

    def status_asset(self, kuid: Union[Kuid, str]) -> AssetStatus:
        """
        Get the status of an asset using its kuid.

        :param kuid: The kuid of the asset to check the status of.
        :return: AssetStatus object representing the status of the asset.
        """
        output = self.run_command("status", str(kuid))
        status = output[0].split(" : ", maxsplit=1)[1].split(" : ", maxsplit=1)[0]

        # Check if the status string is valid
        if status.upper() != "EIADLMF":
            raise TrainzError(f"Invalid status: {status}")

        return AssetStatus(status[0] == "E", status[1] == "I", status[2] == "A", status[3] == "D", status[4] == "L", status[5] == "M", status[6] == "F")  # fmt: skip
