import array
import collections
import ctypes
import os
import random
import threading
import time
import wave
import winsound


class _WAVEFORMATEX(ctypes.Structure):
    _fields_ = [
        ("wFormatTag", ctypes.c_ushort),
        ("nChannels", ctypes.c_ushort),
        ("nSamplesPerSec", ctypes.c_uint),
        ("nAvgBytesPerSec", ctypes.c_uint),
        ("nBlockAlign", ctypes.c_ushort),
        ("wBitsPerSample", ctypes.c_ushort),
        ("cbSize", ctypes.c_ushort),
    ]


class _WAVEHDR(ctypes.Structure):
    _fields_ = [
        ("lpData", ctypes.c_char_p),
        ("dwBufferLength", ctypes.c_uint),
        ("dwBytesRecorded", ctypes.c_uint),
        ("dwUser", ctypes.c_size_t),
        ("dwFlags", ctypes.c_uint),
        ("dwLoops", ctypes.c_uint),
        ("lpNext", ctypes.c_void_p),
        ("reserved", ctypes.c_size_t),
    ]


_WHDR_DONE = 0x00000001
_WHDR_PREPARED = 0x00000002
_WAVE_MAPPER = 0xFFFFFFFF


class SoundManager:
    """
    Low-latency, non-blocking audio engine for Daily Tasks.
    - Pre-loads and caches all WAV PCM buffers in memory on a background thread.
    - Uses a polyphonic 8-channel WinMM waveOut pool for micro-interactions
      (hover, click, typing, undo) so rapid inputs never block the UI thread,
      never queue up lag, and never cut off task completion/alert chimes.
    - Supports independent UI SFX mute and 0-100% volume scaling.
    """

    HOVER_COOLDOWN_SEC = 0.045
    CLICK_COOLDOWN_SEC = 0.025
    TYPE_COOLDOWN_SEC = 0.018
    POOL_CHANNELS = 8

    UI_SOUNDS = (
        "hover.wav",
        "click.wav",
        "undo.wav",
        "type_1.wav",
        "type_2.wav",
        "type_3.wav",
        "type_space.wav",
    )
    ALERT_SOUNDS = (
        "start.wav",
        "done.wav",
        "fail.wav",
        "urgent.wav",
        "reminder.wav",
    )

    def __init__(self, base_path):
        self.sounds_dir = os.path.join(base_path, "assets", "sounds")
        self.dnd_enabled = False
        self.ui_sounds_enabled = True
        self.ui_volume = 0.80  # 0.0 to 1.0 (default 80%)
        self._headless_mute = (
            os.environ.get("QT_QPA_PLATFORM", "").lower() == "offscreen"
            or os.environ.get("DAILYTASKS_MUTE_AUDIO", "") == "1"
        )

        # Debounce / state tracking (accessed on UI thread in <2us)
        self._last_hover_time = 0.0
        self._last_hover_id = None
        self._last_click_time = 0.0
        self._last_type_time = 0.0
        self._last_type_idx = 0

        # In-memory caches
        self._raw_pcm = {}       # filename -> array('h') of 16-bit PCM samples
        self._scaled_pcm = {}    # filename -> ctypes string buffer scaled by ui_volume
        self._cache_ready = False
        self._volume_dirty = False

        # Bounded non-blocking dispatch queue for UI SFX and alerts
        self._queue = collections.deque(maxlen=12)
        self._wake_event = threading.Event()
        self._closed = False
        self._reset_requested = False

        # Start dedicated daemon worker to preload buffers & drive WinMM pool
        self._worker = threading.Thread(target=self._audio_worker_loop, daemon=True)
        self._worker.start()

    def reset_audio_devices(self):
        """Request the worker thread to close and re-open WinMM waveOut handles (e.g. after sleep/wake or device swap)."""
        if not self._closed:
            self._reset_requested = True
            self._wake_event.set()

    def close(self):
        """Cleanly shut down the audio worker and release all WinMM waveOut handles."""
        if not self._closed:
            self._closed = True
            self._wake_event.set()
            try:
                if self._worker.is_alive():
                    self._worker.join(timeout=0.5)
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────
    # Settings & Volume Controls
    # ─────────────────────────────────────────────────────────
    def set_dnd(self, enabled: bool):
        self.dnd_enabled = bool(enabled)

    def set_ui_sounds_enabled(self, enabled: bool):
        self.ui_sounds_enabled = bool(enabled)

    def set_ui_volume(self, volume: float):
        """Set UI SFX volume in range [0.0, 1.0] (or [0, 100] percentage)."""
        if volume > 1.0:
            volume = volume / 100.0
        clamped = max(0.0, min(1.0, float(volume)))
        if abs(clamped - self.ui_volume) > 0.005:
            self.ui_volume = clamped
            self._volume_dirty = True
            self._wake_event.set()

    # ─────────────────────────────────────────────────────────
    # Core Task Alert Chimes (Unaffected by UI SFX Mute/Volume)
    # ─────────────────────────────────────────────────────────
    def _play_alert(self, filename: str):
        if self.dnd_enabled or self._closed:
            return
        self._queue.append(("alert", filename))
        self._wake_event.set()

    def play_start(self):
        self._play_alert("start.wav")

    def play_done(self):
        self._play_alert("done.wav")

    def play_fail(self):
        self._play_alert("fail.wav")

    def play_urgent(self):
        self._play_alert("urgent.wav")

    def play_reminder(self):
        self._play_alert("reminder.wav")

    # ─────────────────────────────────────────────────────────
    # Interactive UI Micro-SFX (Hover, Click, Typing, Undo)
    # ─────────────────────────────────────────────────────────
    def _can_play_ui_sfx(self) -> bool:
        return (
            not self._closed
            and not self.dnd_enabled
            and self.ui_sounds_enabled
            and self.ui_volume > 0.005
        )

    def play_hover(self, widget_id=None):
        """Play subtle hover brush with anti-fatigue cooldown and widget deduplication."""
        if not self._can_play_ui_sfx():
            return
        now = time.perf_counter()
        if widget_id is not None and widget_id == self._last_hover_id and (now - self._last_hover_time) < 0.22:
            return
        if (now - self._last_hover_time) < self.HOVER_COOLDOWN_SEC:
            return
        # Avoid playing hover on the exact same millisecond as a click
        if (now - self._last_click_time) < 0.040:
            return
        self._last_hover_time = now
        self._last_hover_id = widget_id
        self._queue.append(("ui", "hover.wav"))
        self._wake_event.set()

    def play_click(self):
        """Play crisp tactile click sound."""
        if not self._can_play_ui_sfx():
            return
        now = time.perf_counter()
        if (now - self._last_click_time) < self.CLICK_COOLDOWN_SEC:
            return
        self._last_click_time = now
        self._queue.append(("ui", "click.wav"))
        self._wake_event.set()

    def play_undo(self):
        """Play soft descending wooden/glass undo tap."""
        if not self._can_play_ui_sfx():
            return
        self._queue.append(("ui", "undo.wav"))
        self._wake_event.set()

    def play_type(self, key=None):
        """Play organic mechanical/soft keystroke sound with pitch variation."""
        if not self._can_play_ui_sfx():
            return
        now = time.perf_counter()
        if (now - self._last_type_time) < self.TYPE_COOLDOWN_SEC:
            return
        self._last_type_time = now

        # Deeper tactile thock for Space (0x20), Backspace (0x01000003), Return/Enter (0x01000004/5)
        if key in (0x20, 0x01000003, 0x01000004, 0x01000005):
            filename = "type_space.wav"
        else:
            # Cycle across 3 keycap variations without immediate repeat
            step = 1 if random.random() < 0.5 else 2
            self._last_type_idx = (self._last_type_idx + step) % 3
            filename = f"type_{self._last_type_idx + 1}.wav"

        self._queue.append(("ui", filename))
        self._wake_event.set()

    # ─────────────────────────────────────────────────────────
    # Background Pre-Loader & Polyphonic WinMM Worker
    # ─────────────────────────────────────────────────────────
    def _preload_buffers(self):
        """Load UI WAV PCM frames into memory and pre-scale for current volume."""
        for fname in self.UI_SOUNDS:
            path = os.path.join(self.sounds_dir, fname)
            if not os.path.exists(path):
                continue
            try:
                with wave.open(path, "rb") as wf:
                    raw_bytes = wf.readframes(wf.getnframes())
                    samples = array.array("h")
                    samples.frombytes(raw_bytes)
                    self._raw_pcm[fname] = samples
            except Exception:
                pass
        self._rebuild_scaled_buffers()
        self._cache_ready = True

    def _rebuild_scaled_buffers(self):
        """Rebuild volume-scaled in-memory PCM buffers using C-speed array ops."""
        vol = self.ui_volume
        for fname, samples in self._raw_pcm.items():
            if abs(vol - 1.0) < 0.01:
                raw = samples.tobytes()
            else:
                scaled = array.array("h", (int(s * vol) for s in samples))
                raw = scaled.tobytes()
            self._scaled_pcm[fname] = ctypes.create_string_buffer(raw, len(raw))
        self._volume_dirty = False

    def _open_waveout_pool(self, winmm_dll):
        """Open fixed pool of 8 polyphonic waveOut channels (44.1kHz, 16-bit, stereo)."""
        pool = []
        if winmm_dll is None or self._headless_mute:
            return pool
        try:
            wfx = _WAVEFORMATEX(1, 2, 44100, 44100 * 4, 4, 16, 0)
            for _ in range(self.POOL_CHANNELS):
                hwo = ctypes.c_void_p()
                res = winmm_dll.waveOutOpen(
                    ctypes.byref(hwo),
                    ctypes.c_uint(_WAVE_MAPPER),
                    ctypes.byref(wfx),
                    0,
                    0,
                    0,
                )
                if res == 0 and hwo.value:
                    hdr = _WAVEHDR()
                    pool.append((hwo, hdr, None))
        except Exception:
            pass
        return pool

    def _close_waveout_pool(self, winmm_dll, pool):
        """Reset, unprepare, and close all waveOut handles in the pool."""
        if winmm_dll is None or not pool:
            return
        for hwo, hdr, _ in pool:
            try:
                if hwo and hwo.value:
                    winmm_dll.waveOutReset(hwo)
                    if hdr.dwFlags & _WHDR_PREPARED:
                        winmm_dll.waveOutUnprepareHeader(hwo, ctypes.byref(hdr), ctypes.sizeof(hdr))
                    winmm_dll.waveOutClose(hwo)
            except Exception:
                pass
        pool.clear()

    def _audio_worker_loop(self):
        """Dedicated background thread managing the 8-channel WinMM pool."""
        self._preload_buffers()

        winmm = getattr(ctypes, "windll", None)
        winmm_dll = getattr(winmm, "winmm", None) if winmm else None

        channels = self._open_waveout_pool(winmm_dll)
        next_ch = 0

        try:
            while not self._closed:
                self._wake_event.wait()
                self._wake_event.clear()

                if self._closed:
                    break

                if self._reset_requested:
                    self._reset_requested = False
                    self._close_waveout_pool(winmm_dll, channels)
                    channels = self._open_waveout_pool(winmm_dll)
                    next_ch = 0

                if self._volume_dirty:
                    self._rebuild_scaled_buffers()

                while self._queue and not self._closed:
                    kind, filename = self._queue.popleft()
                    if self._headless_mute:
                        continue
                    if kind == "alert":
                        if self.dnd_enabled:
                            continue
                        path = os.path.join(self.sounds_dir, filename)
                        if os.path.exists(path):
                            try:
                                winsound.PlaySound(
                                    path,
                                    winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
                                )
                            except Exception:
                                pass
                    elif kind == "ui":
                        if not self._can_play_ui_sfx():
                            continue
                        buf = self._scaled_pcm.get(filename)
                        if buf is not None and winmm_dll is not None:
                            if not channels:
                                channels = self._open_waveout_pool(winmm_dll)
                                next_ch = 0

                        played_via_pool = False
                        if buf is not None and channels and winmm_dll is not None:
                            try:
                                # Find a free channel first, or reuse oldest channel
                                chosen_idx = None
                                for offset in range(len(channels)):
                                    idx = (next_ch + offset) % len(channels)
                                    hwo, hdr, _ = channels[idx]
                                    if not (hdr.dwFlags & _WHDR_PREPARED) or (hdr.dwFlags & _WHDR_DONE):
                                        chosen_idx = idx
                                        break
                                if chosen_idx is None:
                                    chosen_idx = next_ch
                                    hwo, hdr, _ = channels[chosen_idx]
                                    winmm_dll.waveOutReset(hwo)

                                next_ch = (chosen_idx + 1) % len(channels)
                                hwo, hdr, _ = channels[chosen_idx]

                                if hdr.dwFlags & _WHDR_PREPARED:
                                    winmm_dll.waveOutUnprepareHeader(hwo, ctypes.byref(hdr), ctypes.sizeof(hdr))

                                hdr.lpData = ctypes.cast(buf, ctypes.c_char_p)
                                hdr.dwBufferLength = len(buf)
                                hdr.dwBytesRecorded = 0
                                hdr.dwUser = 0
                                hdr.dwFlags = 0
                                hdr.dwLoops = 0
                                hdr.lpNext = None
                                hdr.reserved = 0

                                # Keep reference to buf in channel tuple so GC never collects during playback
                                channels[chosen_idx] = (hwo, hdr, buf)
                                prep_res = winmm_dll.waveOutPrepareHeader(hwo, ctypes.byref(hdr), ctypes.sizeof(hdr))
                                write_res = winmm_dll.waveOutWrite(hwo, ctypes.byref(hdr), ctypes.sizeof(hdr)) if prep_res == 0 else prep_res
                                if write_res == 0:
                                    played_via_pool = True
                                else:
                                    # Audio device handle invalidated (e.g. device unplugged or sleep/wake)
                                    self._close_waveout_pool(winmm_dll, channels)
                                    channels = self._open_waveout_pool(winmm_dll)
                                    next_ch = 0
                            except Exception:
                                pass

                        if not played_via_pool:
                            # Fallback if waveOut unavailable or recovering
                            path = os.path.join(self.sounds_dir, filename)
                            if os.path.exists(path):
                                try:
                                    winsound.PlaySound(
                                        path,
                                        winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
                                    )
                                except Exception:
                                    pass
        finally:
            self._close_waveout_pool(winmm_dll, channels)

