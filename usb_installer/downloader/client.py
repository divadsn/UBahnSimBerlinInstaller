import logging
import time
import threading

from pathlib import Path
from typing import Callable, List, Tuple

import httpx

from usb_installer import USER_AGENT
from usb_installer.utils import readable_size

logger = logging.getLogger(__name__)


class DownloadClient:
    def __init__(
        self,
        urls: List[Tuple[str, str]],
        download_dir: Path,
        completion_callback: Callable[[str, Path], None],
        error_callback: Callable[[str, Exception], None],
        max_retries: int = 5,
    ):
        self.urls = urls
        self.download_dir = download_dir
        self.completion_callback = completion_callback
        self.error_callback = error_callback
        self.max_retries = max_retries

        self.download_thread = threading.Thread(target=self._download_urls)
        self.stop_download = False
        self.current_speed = 0.0
        self.progress = 0.0
        self.downloaded_count = 0

        if not download_dir.exists():
            download_dir.mkdir(parents=True)

    @property
    def total_count(self) -> int:
        return len(self.urls)

    def _download_url(self, url: str, filename: str, client: httpx.Client):
        local_filename = self.download_dir / filename
        temp_filename = local_filename.with_suffix(local_filename.suffix + ".part")
        logger.info(f"Downloading {url} to {local_filename}")

        retries = 0

        while retries < self.max_retries and not self.stop_download:
            self.progress = 0.0
            self.current_speed = 0.0

            try:
                with client.stream("GET", url, follow_redirects=True, timeout=60) as r:
                    r.raise_for_status()

                    total_size_in_bytes = int(r.headers.get("content-length", 0))
                    downloaded_size = 0
                    logger.info(f"Total size: {readable_size(total_size_in_bytes)}")

                    # Start time for calculating speed
                    start_time = time.time()

                    with open(temp_filename, 'wb') as f:
                        for data in r.iter_bytes(chunk_size=4096):
                            if self.stop_download:
                                logger.info("Download stopped by user")
                                return  # Stop the download

                            f.write(data)
                            downloaded_size += len(data)
                            self.progress = (downloaded_size / total_size_in_bytes) * 100

                            # Calculate elapsed time and speed
                            elapsed_time = time.time() - start_time
                            self.current_speed = downloaded_size / elapsed_time if elapsed_time > 0 else 0

                # Rename the file
                temp_filename.replace(local_filename)
                logger.info(f"Finished downloading {url} (took {elapsed_time:.2f} seconds, speed: {readable_size(self.current_speed)}/s)")

                self.downloaded_count += 1
                self.completion_callback(url, local_filename)
                break  # Break the loop if download is successful
            except httpx.RequestError as e:
                retries += 1
                logger.error(f"Error downloading {url}. Attempt {retries} of {self.max_retries}", exc_info=e)
                if retries >= self.max_retries:
                    self.error_callback(url, e)
            except Exception as e:
                logger.error(f"Error downloading {url}", exc_info=e)
                self.error_callback(url, e)
                break

    def _download_urls(self):
        logger.info(f"Starting download of {self.total_count} URLs")

        with httpx.Client(headers={"User-Agent": USER_AGENT}) as client:
            for url, filename in self.urls:
                if self.stop_download:
                    break

                self._download_url(url, filename, client)

        logger.info("Finished downloading URLs")

    def start(self, daemon=False):
        self.download_thread.start()

        if daemon:
            self.download_thread.join()

    def stop(self):
        self.stop_download = True
        self.download_thread.join()

    def is_running(self):
        return self.download_thread.is_alive()
