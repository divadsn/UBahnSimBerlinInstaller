import subprocess

from pathlib import Path
from typing import List, Optional, Union

__all__ = ["TrainzError", "TrainzUtil"]


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

        if process.returncode != 0:
            for line in output:
                if line.startswith("-"):
                    raise TrainzError(line.split(" : ", maxsplit=1)[1].strip())
            else:
                raise subprocess.CalledProcessError(process.returncode, process.args, process.stdout, process.stderr)

        return output

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
