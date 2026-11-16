# Application version & GitHub Release endpoints
APP_VERSION = "1.5.0"
GITHUB_REPO = "Moham-OverKill/Daily-Tasks"
GITHUB_RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES_PAGE_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"
INSTALLER_ASSET_NAME = "DailyTasksSetup.exe"

# Expanded icon categories & smart search engine
from .emoji_data import EMOJI_CATEGORIES, EMOJI_DATA, GLOBAL_EMOJI_ENGINE

# Icon categories for task & note selection
ICON_CATEGORIES = EMOJI_CATEGORIES

# Flattened list for indexing (deterministic order is crucial for routine sharing)
# The original release icons are strictly preserved at indices 0..159 to guarantee share code backward compatibility
_ORIGINAL_CATEGORIES = {
    "Essentials 🏠": ["📝", "💻", "💼", "📅", "🏠", "🛒", "🧹", "🔧", "📞", "💳", "🗑️", "📦", "🛋️", "🛁", "🔑", "🔒", "🚪"],
    "Health & Self 🧘": ["🏋️", "🧘", "💤", "💊", "🚿", "🦷", "💇", "💅", "🧖", "🚽", "🧴", "🧠", "🫀"],
    "Faith & Spirit 🤲": ["📖", "📿", "🤲", "🕌", "🛐", "🌙", "🕯️", "⛪", "🛕", "🕍"],
    "Education 🎓": ["📚", "🎓", "✏️", "🎒", "📒", "🏫", "🔬", "🔭", "🖌️", "✂️", "📏", "📎"],
    "Food & Drink 🍔": ["☕", "🍵", "🥤", "🍼", "🍺", "🥂", "🍽️", "🍳", "🥣", "🥗", "🥪", "🌮", "🍔", "🍕", "🍟", "🍦", "🍩", "🍫", "🥦", "🍎", "🍇", "🍉", "🎂", "🍿"],
    "Sports & Fun ⚽": ["🎮", "🎨", "🎵", "🎬", "⚽", "🏀", "🏈", "🎾", "🏐", "🏐", "🎱", "🏓", "🏸", "🥊", "🥋", "🥅", "🏹", "🎣", "🏊", "🚴", "🏇", "🧩", "🎲", "🎯", "🎳"],
    "Travel & Places ✈️": ["🚗", "🚌", "🚂", "✈️", "🚀", "🚲", "🛵", "🛑", "🚧", "⛽", "🏕️", "🏖️", "🏞️", "🏥", "🏦", "🏭", "🏰", "⛩️", "🗿", "🗺️"],
    "Nature & Animals 🐾": ["☀️", "⭐", "☁️", "⛈️", "❄️", "🔥", "💧", "🐶", "🐱", "🐭", "🐹", "🐰", "🦊", "🐻", "🐼", "🦁", "🦁", "🐯", "💐", "🌹", "🌵", "🌴", "🌲", "🍀"],
    "Objects 🎒": ["📱", "⌚", "📷", "🔋", "💡", "🔦", "🎁", "🎈", "🎉", "🕶️", "👓", "☂️", "💍", "👑", "👠", "👕"]
}

ALL_ICONS = ["❓"] # Essential Fallback at index 0
for cat in sorted(_ORIGINAL_CATEGORIES.keys()): 
    for icon in _ORIGINAL_CATEGORIES[cat]:
        if icon not in ALL_ICONS:
            ALL_ICONS.append(icon)

# Deterministically append all expanded emojis
for item in EMOJI_DATA:
    ch = item[0]
    if ch not in ALL_ICONS:
        ALL_ICONS.append(ch)
