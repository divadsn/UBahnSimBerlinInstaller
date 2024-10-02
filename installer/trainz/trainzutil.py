import subprocess

from dataclasses import dataclass

from pathlib import Path
from typing import List, Optional, Union

__all__ = ["AssetStatus", "TrainzError", "TrainzUtil"]


@dataclass
class AssetStatus:
    open_for_edit: bool
    installed: bool
    archived: bool
    download_station: bool
    modified: bool
    missing_dependencies: bool
    faulty: bool


class TrainzError(Exception):
    pass


class TrainzUtil:
    def __init__(self, trainz_path: Union[Path, str], timeout: Optional[float] = None):
        trainzutil_path = Path(trainz_path) / "bin" / "TrainzUtil.exe"

        if not trainzutil_path.exists():
            raise FileNotFoundError(f"TrainzUtil.exe not found at: {trainz_path}")

        self.trainzutil_path = trainzutil_path
        self.timeout = timeout

    def run_command(self, command: str, *args, timeout: Optional[float] = None) -> List[str]:
        process = subprocess.run([self.trainzutil_path, command, *args], capture_output=True, encoding="utf-8", text=True, timeout=timeout if timeout else self.timeout, creationflags=subprocess.CREATE_NO_WINDOW)
        output = process.stdout.splitlines()

        for line in output:
            if line.startswith("-"):
                raise TrainzError(line.split(" : ", maxsplit=1)[1].strip())
        else:
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, process.args, process.stdout, process.stderr)

        return output

    def build_version(self, timeout: Optional[float] = None) -> int:
        output = self.run_command("version", timeout=timeout)
        return int(output[0].split()[1])

    def echo(self, message: str, timeout: Optional[float] = None) -> bool:
        output = self.run_command("echo", message, timeout=timeout)
        return output[0].strip() == message

    def install_cdp(self, file_path: Union[Path, str]) -> str:
        output = self.run_command("installCDP", str(file_path))
        return output[0].split("<")[1].split(">")[0]

    def install_from_path(self, asset_path: Union[Path, str]) -> str:
        output = self.run_command("installfrompath", str(asset_path))
        return output[0].split("<")[1].split(">")[0]

    def open_for_edit(self, kuid: str) -> Path:
        output = self.run_command("edit", kuid)
        return Path(output[0].split(" : ", maxsplit=1)[1].strip())

    def commit_asset(self, kuid: str) -> bool:
        try:
            self.run_command("commit", kuid)
        except subprocess.CalledProcessError:
            return False

        return True

    def revert_asset(self, kuid: str) -> bool:
        try:
            self.run_command("revert", kuid)
        except subprocess.CalledProcessError:
            return False

        return True

    def delete_asset(self, kuid: str) -> bool:
        try:
            self.run_command("delete", kuid)
        except subprocess.CalledProcessError:
            return False

        return True

    def status_asset(self, kuid: str) -> AssetStatus:
        output = self.run_command("status", kuid)
        status = output[0].split(" : ", maxsplit=1)[1].split(" : ", maxsplit=1)[0]

        if len(status) < 7:
            raise TrainzError(f"Invalid status: {status}")

        return AssetStatus(status[0] == "E", status[1] == "I", status[2] == "A", status[3] == "D", status[4] == "L", status[5] == "M", status[6] == "F")
