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
from PySide6.QtCore import QObject, Signal, QTimer

from .api_handler import _http_get_json
from .constants import (
    APP_VERSION,
    GITHUB_REPO,
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


def _check_github_latest_web(timeout: int = 8) -> dict:
    """
    Fallback checker immune to GitHub unauthenticated REST API rate limits (HTTP 403).
    Resolves the latest release tag by inspecting the HTTP redirect target of
    'https://github.com/{GITHUB_REPO}/releases/latest' -> '.../releases/tag/vX.Y.Z'.
    Returns a dict with 'tag_name', 'html_url', and 'asset_url', or None on failure.
    """
    web_url = GITHUB_RELEASES_PAGE_URL
    tag_name = ""

    # Strategy 1: WinINet on Windows (zero Python SSL/networking dependencies)
    if sys.platform == "win32":
        try:
            import ctypes
            wininet = ctypes.windll.wininet
            wininet.InternetOpenW.restype = ctypes.c_void_p
            wininet.InternetOpenUrlW.restype = ctypes.c_void_p

            h_inet = wininet.InternetOpenW(f"DailyTasks/{APP_VERSION}", 0, None, None, 0)
            if h_inet:
                try:
                    timeout_ms = ctypes.c_uint(max(1000, int(timeout * 1000)))
                    wininet.InternetSetOptionW(ctypes.c_void_p(h_inet), 2, ctypes.byref(timeout_ms), ctypes.sizeof(timeout_ms))
                    wininet.InternetSetOptionW(ctypes.c_void_p(h_inet), 5, ctypes.byref(timeout_ms), ctypes.sizeof(timeout_ms))
                    wininet.InternetSetOptionW(ctypes.c_void_p(h_inet), 6, ctypes.byref(timeout_ms), ctypes.sizeof(timeout_ms))

                    INTERNET_FLAG_RELOAD = 0x80000000
                    h_url = wininet.InternetOpenUrlW(
                        ctypes.c_void_p(h_inet),
                        web_url,
                        None,
                        0,
                        INTERNET_FLAG_RELOAD,
                        0,
                    )
                    if h_url:
                        try:
                            # INTERNET_OPTION_URL = 34 queries the effective/final URL after redirects
                            buf = ctypes.create_unicode_buffer(1024)
                            buflen = ctypes.c_ulong(ctypes.sizeof(buf))
                            if wininet.InternetQueryOptionW(ctypes.c_void_p(h_url), 34, buf, ctypes.byref(buflen)):
                                final_url = str(buf.value).strip()
                                m = re.search(r"/releases/tag/([^/?#]+)", final_url)
                                if m:
                                    tag_name = m.group(1).strip()
                        finally:
                            wininet.InternetCloseHandle(ctypes.c_void_p(h_url))
                finally:
                    wininet.InternetCloseHandle(ctypes.c_void_p(h_inet))
        except Exception:
            pass

    # Strategy 2: stdlib urllib.request fallback (inspects HTTP 302/301 Location header)
    if not tag_name:
        try:
            import urllib.request
            import urllib.error

            class _NoRedirect(urllib.request.HTTPRedirectHandler):
                def redirect_request(self, req, fp, code, msg, headers, newurl):
                    return None

            opener = urllib.request.build_opener(_NoRedirect)
            req = urllib.request.Request(
                web_url,
                headers={"User-Agent": f"DailyTasks/{APP_VERSION}"},
                method="HEAD",
            )
            try:
                resp = opener.open(req, timeout=timeout)
                final_url = resp.geturl() if hasattr(resp, "geturl") else ""
                m = re.search(r"/releases/tag/([^/?#]+)", final_url)
                if m:
                    tag_name = m.group(1).strip()
            except urllib.error.HTTPError as e:
                loc = e.headers.get("Location") or ""
                m = re.search(r"/releases/tag/([^/?#]+)", loc)
                if m:
                    tag_name = m.group(1).strip()
        except Exception:
            pass

    if tag_name:
        html_url = f"https://github.com/{GITHUB_REPO}/releases/tag/{tag_name}"
        asset_url = f"https://github.com/{GITHUB_REPO}/releases/download/{tag_name}/{INSTALLER_ASSET_NAME}"
        return {
            "tag_name": tag_name,
            "html_url": html_url,
            "asset_url": asset_url,
        }
    return None


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
                    # Enforce strict connect/send/receive timeouts in milliseconds
                    timeout_ms = ctypes.c_uint(max(1000, int(timeout * 1000)))
                    wininet.InternetSetOptionW(ctypes.c_void_p(h_inet), 2, ctypes.byref(timeout_ms), ctypes.sizeof(timeout_ms)) # INTERNET_OPTION_CONNECT_TIMEOUT
                    wininet.InternetSetOptionW(ctypes.c_void_p(h_inet), 5, ctypes.byref(timeout_ms), ctypes.sizeof(timeout_ms)) # INTERNET_OPTION_SEND_TIMEOUT
                    wininet.InternetSetOptionW(ctypes.c_void_p(h_inet), 6, ctypes.byref(timeout_ms), ctypes.sizeof(timeout_ms)) # INTERNET_OPTION_RECEIVE_TIMEOUT

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
                            status_ok = True
                            if wininet.HttpQueryInfoW(
                                ctypes.c_void_p(h_url), 19, status_buf, ctypes.byref(status_len), None
                            ):
                                try:
                                    status_code = int(status_buf.value.strip())
                                    if status_code >= 400:
                                        status_ok = False
                                except ValueError:
                                    pass

                            if status_ok:
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
        import ssl

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": f"DailyTasks/{APP_VERSION}",
                "Accept": "application/octet-stream",
            },
        )
        try:
            resp_cm = urllib.request.urlopen(req, timeout=timeout)
        except Exception as ssl_err:
            # If standard SSL verification fails (e.g. corporate proxy / antivirus TLS interception), retry with unverified context
            ctx = ssl._create_unverified_context()
            resp_cm = urllib.request.urlopen(req, timeout=timeout, context=ctx)

        with resp_cm as resp:
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
    _check_finished = Signal()                   # internal thread-safe signal to stop watchdog

    def __init__(self, parent=None, on_quit_callback=None):
        super().__init__(parent)
        self._checking = False
        self._downloading = False
        self.is_interactive_check = False
        self._on_quit_callback = on_quit_callback
        self.latest_version = ""
        self.download_url = ""
        self.release_html_url = GITHUB_RELEASES_PAGE_URL
        self._watchdog_timer = None
        self._check_finished.connect(self._stop_watchdog)

    def _stop_watchdog(self):
        if self._watchdog_timer is not None:
            self._watchdog_timer.stop()

    def _on_watchdog_timeout(self):
        if self._checking:
            self._checking = False
            if self.is_interactive_check:
                self.check_failed.emit("Connection timed out. Please check your internet connection.")
            else:
                self.up_to_date.emit(APP_VERSION)

    @property
    def is_busy(self) -> bool:
        return self._checking or self._downloading

    def check_for_updates(self, silent: bool = False):
        """Check GitHub Releases API with rate-limit resilient web redirect fallback."""
        if self._checking or self._downloading:
            return
        self._checking = True
        self.is_interactive_check = not silent

        if not silent:
            if self._watchdog_timer is None:
                self._watchdog_timer = QTimer(self)
                self._watchdog_timer.setSingleShot(True)
                self._watchdog_timer.timeout.connect(self._on_watchdog_timeout)
            self._watchdog_timer.stop()
            self._watchdog_timer.start(12000)
            self.check_started.emit()

        def _worker():
            try:
                tag_name = ""
                asset_url = ""
                html_url = GITHUB_RELEASES_PAGE_URL

                # 1. Primary: GitHub REST API
                try:
                    data = _http_get_json(
                        GITHUB_RELEASES_API_URL,
                        headers={"Accept": "application/vnd.github+json"},
                        timeout=8,
                    )
                    if isinstance(data, dict) and "tag_name" in data:
                        tag_name = str(data.get("tag_name") or "").strip()
                        html_url = str(data.get("html_url") or GITHUB_RELEASES_PAGE_URL)
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
                except Exception:
                    pass

                # 2. Resilient Fallback: Web redirect tracking (immune to REST API 60 req/hr rate limits)
                if not tag_name:
                    web_res = _check_github_latest_web(timeout=8)
                    if web_res:
                        tag_name = web_res.get("tag_name") or ""
                        html_url = web_res.get("html_url") or html_url
                        asset_url = web_res.get("asset_url") or asset_url

                self._check_finished.emit()

                if not tag_name:
                    if not silent:
                        self.check_failed.emit("Could not reach GitHub Releases. Please check your internet connection.")
                    else:
                        self.up_to_date.emit(APP_VERSION)
                    return

                clean_ver = tag_name.lstrip("vV").strip() or APP_VERSION
                if not asset_url:
                    asset_url = f"https://github.com/{GITHUB_REPO}/releases/download/{tag_name}/{INSTALLER_ASSET_NAME}"

                if is_newer_version(clean_ver, APP_VERSION):
                    self.latest_version = clean_ver
                    self.download_url = asset_url
                    self.release_html_url = html_url
                    self.update_available.emit(clean_ver, asset_url, html_url)
                else:
                    self.up_to_date.emit(APP_VERSION)
            except Exception as e:
                self._check_finished.emit()
                if not silent:
                    self.check_failed.emit(str(e))
                else:
                    self.up_to_date.emit(APP_VERSION)
            finally:
                self._checking = False

        threading.Thread(target=_worker, daemon=True).start()

    def download_and_install(self, *args, **kwargs):
        """
        Stream DailyTasksSetup.exe to %TEMP%\\DailyTasksUpdate\\DailyTasksSetup.exe,
        verify PE header ('MZ'), and launch the silent upgrade.
        Flexible argument parsing prevents TypeError across caller versions.
        """
        if self._downloading:
            return

        target_url = kwargs.get("download_url") or ""
        target_ver = kwargs.get("version") or kwargs.get("expected_version") or ""

        for arg in args:
            if isinstance(arg, str):
                if arg.startswith("http://") or arg.startswith("https://"):
                    if not target_url:
                        target_url = arg
                elif not target_ver:
                    target_ver = arg

        target_url = target_url or self.download_url
        target_ver = target_ver or self.latest_version or APP_VERSION

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
                    "/SP-",
                    "/VERYSILENT",
                    "/SUPPRESSMSGBOXES",
                    "/NORESTART",
                ],
                creationflags=creationflags,
                close_fds=True,
            )
        except Exception as e:
            # Fallback: attempt native OS startfile
            try:
                os.startfile(installer_path)
            except Exception as start_err:
                self.download_failed.emit(f"Failed to launch installer: {e} ({start_err})")
                return

        if callable(self._on_quit_callback):
            self._on_quit_callback()
        else:
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app is not None:
                app.quit()
