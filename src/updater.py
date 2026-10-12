"""
In-App Update Checker & Seamless Installer Engine for Daily Tasks.
Zero-dependency implementation using Win32 WinINet (with stdlib fallback)
to check GitHub Releases and stream-download DailyTasksSetup.exe.
"""

import os
import re
import sys
import tempfile
import threading
import subprocess
from PySide6.QtCore import QObject, Signal

from .api_handler import _http_get_json
from .constants import (
    APP_VERSION,
    GITHUB_RELEASES_API_URL,
    GITHUB_RELEASES_PAGE_URL,
    INSTALLER_ASSET_NAME,
)


def parse_version(version_str: str) -> tuple:
    """
    Normalize a version string (e.g. 'v1.3.0', 'V1.2', '1.2.5-beta1')
    into a tuple of integers (e.g. (1, 3, 0)).
    """
    if not version_str:
        return (0, 0, 0)
    cleaned = str(version_str).strip().lstrip("vV").strip()
    # Strip pre-release or build metadata suffix (-alpha, +build, etc.)
    cleaned = re.split(r"[-+\s]", cleaned, maxsplit=1)[0]
    parts = []
    for token in cleaned.split("."):
        m = re.match(r"^(\d+)", token.strip())
        if m:
            parts.append(int(m.group(1)))
        else:
            break
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def is_newer_version(latest: str, current: str = APP_VERSION) -> bool:
    """Return True if `latest` represents a strictly newer version than `current`."""
    v_lat = parse_version(latest)
    v_cur = parse_version(current)
    max_len = max(len(v_lat), len(v_cur))
    v_lat = v_lat + (0,) * (max_len - len(v_lat))
    v_cur = v_cur + (0,) * (max_len - len(v_cur))
    return v_lat > v_cur


def _download_file_stream(url: str, dest_path: str, progress_cb=None, timeout: int = 30) -> bool:
    """
    Stream a binary file from `url` to `dest_path` in 64 KB chunks.
    Uses Win32 WinINet on Windows (zero OpenSSL/requests dependency),
    falling back to stdlib urllib.request when needed.
    """
    part_path = dest_path + ".part"
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    if sys.platform == "win32":
        try:
            import ctypes
            wininet = ctypes.windll.wininet
            wininet.InternetOpenW.restype = ctypes.c_void_p
            wininet.InternetOpenUrlW.restype = ctypes.c_void_p

            h_inet = wininet.InternetOpenW(f"DailyTasks/{APP_VERSION}", 0, None, None, 0)
            if h_inet:
                try:
                    INTERNET_FLAG_RELOAD = 0x80000000
                    INTERNET_FLAG_NO_CACHE_WRITE = 0x04000000
                    hdrs = f"User-Agent: DailyTasks/{APP_VERSION}\r\nAccept: application/octet-stream\r\n"
                    h_url = wininet.InternetOpenUrlW(
                        ctypes.c_void_p(h_inet),
                        url,
                        hdrs,
                        len(hdrs),
                        INTERNET_FLAG_RELOAD | INTERNET_FLAG_NO_CACHE_WRITE,
                        0,
                    )
                    if h_url:
                        try:
                            # Query HTTP status code (HTTP_QUERY_STATUS_CODE = 19)
                            status_buf = ctypes.create_unicode_buffer(32)
                            status_len = ctypes.c_ulong(ctypes.sizeof(status_buf))
                            if wininet.HttpQueryInfoW(
                                ctypes.c_void_p(h_url), 19, status_buf, ctypes.byref(status_len), None
                            ):
                                try:
                                    status_code = int(status_buf.value.strip())
                                    if status_code >= 400:
                                        return False
                                except ValueError:
                                    pass

                            # Query Content-Length (HTTP_QUERY_CONTENT_LENGTH = 5)
                            total_bytes = 0
                            len_buf = ctypes.create_unicode_buffer(64)
                            len_size = ctypes.c_ulong(ctypes.sizeof(len_buf))
                            if wininet.HttpQueryInfoW(
                                ctypes.c_void_p(h_url), 5, len_buf, ctypes.byref(len_size), None
                            ):
                                try:
                                    total_bytes = int(len_buf.value.strip())
                                except ValueError:
                                    total_bytes = 0

                            chunk_size = 65536
                            buf = ctypes.create_string_buffer(chunk_size)
                            bytes_read = ctypes.c_ulong(0)
                            downloaded = 0
                            last_pct = -1

                            with open(part_path, "wb") as f:
                                while (
                                    wininet.InternetReadFile(
                                        ctypes.c_void_p(h_url), buf, chunk_size, ctypes.byref(bytes_read)
                                    )
                                    and bytes_read.value > 0
                                ):
                                    f.write(buf.raw[: bytes_read.value])
                                    downloaded += bytes_read.value
                                    if progress_cb and total_bytes > 0:
                                        pct = max(0, min(100, int((downloaded * 100) // total_bytes)))
                                        if pct != last_pct:
                                            last_pct = pct
                                            progress_cb(pct)

                            if downloaded > 0:
                                if progress_cb and last_pct < 100:
                                    progress_cb(100)
                                os.replace(part_path, dest_path)
                                return True
                        finally:
                            wininet.InternetCloseHandle(ctypes.c_void_p(h_url))
                finally:
                    wininet.InternetCloseHandle(ctypes.c_void_p(h_inet))
        except Exception:
            pass

    # Fallback: stdlib urllib.request
    try:
        import urllib.request

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": f"DailyTasks/{APP_VERSION}",
                "Accept": "application/octet-stream",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if getattr(resp, "status", 200) >= 400:
                return False
            total_bytes = int(resp.headers.get("Content-Length", 0) or 0)
            downloaded = 0
            last_pct = -1
            with open(part_path, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb and total_bytes > 0:
                        pct = max(0, min(100, int((downloaded * 100) // total_bytes)))
                        if pct != last_pct:
                            last_pct = pct
                            progress_cb(pct)
            if downloaded > 0:
                if progress_cb and last_pct < 100:
                    progress_cb(100)
                os.replace(part_path, dest_path)
                return True
    except Exception:
        pass

    try:
        if os.path.exists(part_path):
            os.remove(part_path)
    except OSError:
        pass
    return False


class UpdateManager(QObject):
    """
    Asynchronous update checker and silent installer coordinator.
    Emits Qt signals so all UI updates occur safely on the main thread.
    """

    check_started = Signal()
    up_to_date = Signal(str)                     # current_version
    update_available = Signal(str, str, str)     # latest_version, asset_download_url, release_html_url
    check_failed = Signal(str)                   # error_message
    download_started = Signal(str)               # version being downloaded
    download_progress = Signal(int)              # 0..100
    download_finished = Signal(str)              # local_installer_path
    download_failed = Signal(str)                # error_message

    def __init__(self, parent=None, on_quit_callback=None):
        super().__init__(parent)
        self._checking = False
        self._downloading = False
        self._on_quit_callback = on_quit_callback
        self.latest_version = ""
        self.download_url = ""
        self.release_html_url = GITHUB_RELEASES_PAGE_URL

    @property
    def is_busy(self) -> bool:
        return self._checking or self._downloading

    def check_for_updates(self, silent: bool = False):
        """Check GitHub Releases API on a background daemon thread."""
        if self._checking or self._downloading:
            return
        self._checking = True
        self.check_started.emit()

        def _worker():
            try:
                data = _http_get_json(
                    GITHUB_RELEASES_API_URL,
                    headers={"Accept": "application/vnd.github+json"},
                    timeout=8,
                )
                if not isinstance(data, dict) or "tag_name" not in data:
                    if not silent:
                        self.check_failed.emit("Could not reach GitHub Releases.")
                    return

                tag_name = str(data.get("tag_name") or "").strip()
                clean_ver = tag_name.lstrip("vV").strip() or APP_VERSION
                html_url = str(data.get("html_url") or GITHUB_RELEASES_PAGE_URL)

                # Locate DailyTasksSetup.exe asset URL
                asset_url = ""
                assets = data.get("assets") or []
                if isinstance(assets, list):
                    for asset in assets:
                        if not isinstance(asset, dict):
                            continue
                        name = str(asset.get("name") or "")
                        dl_url = str(asset.get("browser_download_url") or "")
                        if name.lower() == INSTALLER_ASSET_NAME.lower() and dl_url:
                            asset_url = dl_url
                            break
                    if not asset_url:
                        for asset in assets:
                            if not isinstance(asset, dict):
                                continue
                            name = str(asset.get("name") or "")
                            dl_url = str(asset.get("browser_download_url") or "")
                            if name.lower().endswith(".exe") and dl_url:
                                asset_url = dl_url
                                break

                if is_newer_version(clean_ver, APP_VERSION):
                    self.latest_version = clean_ver
                    self.download_url = asset_url
                    self.release_html_url = html_url
                    self.update_available.emit(clean_ver, asset_url, html_url)
                else:
                    self.up_to_date.emit(APP_VERSION)
            except Exception as e:
                if not silent:
                    self.check_failed.emit(str(e))
            finally:
                self._checking = False

        threading.Thread(target=_worker, daemon=True).start()

    def download_and_install(self, download_url: str = "", version: str = "", expected_version: str = ""):
        """
        Stream DailyTasksSetup.exe to %TEMP%\\DailyTasksUpdate\\DailyTasksSetup.exe,
        verify PE header ('MZ'), and launch the silent upgrade.
        """
        if self._downloading:
            return

        target_url = download_url or self.download_url
        target_ver = version or expected_version or self.latest_version or APP_VERSION
        if not target_url:
            # If the release has no .exe attached, open the release page in browser
            try:
                import webbrowser
                webbrowser.open(self.release_html_url or GITHUB_RELEASES_PAGE_URL)
            except Exception:
                pass
            return

        self._downloading = True
        self.download_started.emit(target_ver)
        self.download_progress.emit(0)

        def _dl_worker():
            try:
                update_dir = os.path.join(tempfile.gettempdir(), "DailyTasksUpdate")
                os.makedirs(update_dir, exist_ok=True)
                dest_path = os.path.join(update_dir, INSTALLER_ASSET_NAME)

                ok = _download_file_stream(
                    target_url,
                    dest_path,
                    progress_cb=lambda pct: self.download_progress.emit(pct),
                    timeout=60,
                )
                if not ok or not os.path.exists(dest_path) or os.path.getsize(dest_path) < 4096:
                    self.download_failed.emit("Download failed or incomplete.")
                    return

                # Verify valid Windows PE header ('MZ')
                with open(dest_path, "rb") as f:
                    magic = f.read(2)
                if magic != b"MZ":
                    try:
                        os.remove(dest_path)
                    except OSError:
                        pass
                    self.download_failed.emit("Downloaded file is not a valid installer.")
                    return

                self.download_finished.emit(dest_path)
            except Exception as e:
                self.download_failed.emit(str(e))
            finally:
                self._downloading = False

        threading.Thread(target=_dl_worker, daemon=True).start()

    def launch_silent_installer(self, installer_path: str):
        """
        Spawn Inno Setup installer detached in silent mode and cleanly exit
        the current process so the installer can overwrite and relaunch.
        """
        if not installer_path or not os.path.exists(installer_path):
            self.download_failed.emit("Installer file not found.")
            return

        try:
            creationflags = 0
            if sys.platform == "win32":
                creationflags = (
                    getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
                    | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
                )
            subprocess.Popen(
                [
                    installer_path,
                    "/VERYSILENT",
                    "/SUPPRESSMSGBOXES",
                    "/NORESTART",
                ],
                creationflags=creationflags,
                close_fds=True,
            )
        except Exception as e:
            self.download_failed.emit(f"Failed to launch installer: {e}")
            return

        if callable(self._on_quit_callback):
            self._on_quit_callback()
        else:
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app is not None:
                app.quit()
