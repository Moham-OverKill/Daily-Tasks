"""
Centralized emoji and custom icon asset resolver.
Maps Unicode emoji glyphs to unclipped Microsoft Fluent 3D PNG assets.
"""
import os
import sys
import functools
from typing import Optional


def emoji_to_hex(ch: str) -> str:
    """
    Convert a Unicode emoji string into standard lowercase hex codepoints,
    stripping variation selectors (\\ufe0f, \\ufe0e) and whitespace.
    """
    if not ch or not isinstance(ch, str):
        return ""
    norm = ch.replace('\ufe0f', '').replace('\ufe0e', '').strip()
    if not norm:
        return ""
    return '-'.join(f'{ord(c):x}' for c in norm)


def get_bundled_emojis_dir() -> str:
    """Return the absolute path to the bundled assets/emojis directory."""
    if getattr(sys, 'frozen', False):
        base_dir = getattr(sys, '_MEIPASS', os.path.abspath('.'))
    else:
        # src/ -> project root
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, 'assets', 'emojis')


def get_cache_emojis_dir() -> str:
    """Return the absolute path to the user AppData emoji cache directory."""
    appdata = os.getenv('APPDATA', os.path.expanduser('~'))
    cache_dir = os.path.join(appdata, 'DailyTasks', 'cache', 'emojis')
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


@functools.lru_cache(maxsize=512)
def resolve_emoji_asset(icon_val: str) -> Optional[str]:
    """
    Resolve an icon string (Unicode emoji or custom image path) to an absolute image file path.
    Returns None if no image asset is available (caller should fall back to font glyph).
    """
    if not icon_val or not isinstance(icon_val, str):
        return None

    # 1. Custom image path check
    is_path = any(s in icon_val.lower() for s in ['\\', '/', '.png', '.jpg', '.jpeg', '.webp'])
    if is_path:
        resolved = icon_val
        if not os.path.isabs(resolved) and 'cache' in resolved:
            appdata = os.getenv('APPDATA', os.path.expanduser('~'))
            resolved = os.path.normpath(os.path.join(appdata, 'DailyTasks', resolved))
        if os.path.isfile(resolved):
            return resolved
        return None

    # 2. Check bundled 3D Fluent emoji assets
    hx = emoji_to_hex(icon_val)
    if not hx:
        return None

    bundled_dir = get_bundled_emojis_dir()
    bundled_file = os.path.join(bundled_dir, f"{hx}.png")
    if os.path.isfile(bundled_file):
        return bundled_file

    # 3. Check AppData cache
    cached_dir = get_cache_emojis_dir()
    cached_file = os.path.join(cached_dir, f"{hx}.png")
    if os.path.isfile(cached_file):
        return cached_file

    return None
