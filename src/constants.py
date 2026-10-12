# Application version & GitHub Release endpoints
APP_VERSION = "1.4.1"
GITHUB_REPO = "Moham-OverKill/Daily-Tasks"
GITHUB_RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES_PAGE_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"
INSTALLER_ASSET_NAME = "DailyTasksSetup.exe"

# Icon categories for task selection
ICON_CATEGORIES = {
    "Essentials 🏠": ["📝", "💻", "💼", "📅", "🏠", "🛒", "🧹", "🔧", "📞", "💳", "🗑️", "📦", "🛋️", "🛁", "🔑", "🔒", "🚪"],
    "Health & Self 🧘": ["🏋️", "🧘", "💤", "💊", "🚿", "🦷", "💇", "💅", "🧖", "🚽", "🧴", "🧠", "🫀"],
    "Faith & Spirit 🤲": ["📖", "📿", "🤲", "🕌", "🛐", "🌙", "🕯️", "⛪", "🛕", "🕍"],
    "Education 🎓": ["📚", "🎓", "✏️", "🎒", "📒", "🏫", "🔬", "🔭", "🖌️", "✂️", "📏", "📎"],
    "Food & Drink 🍔": ["☕", "🍵", "🥤", "🍼", "🍺", "🥂", "🍽️", "🍳", "🥣", "🥗", "🥪", "🌮", "🍔", "🍕", "🍟", "🍦", "🍩", "🍫", "🥦", "🍎", "🍇", "🍉", "🎂", "🍿"],
    "Sports & Fun ⚽": ["🎮", "🎨", "🎵", "🎬", "⚽", "🏀", "🏈", "🎾", "🏐", "🏉", "🎱", "🏓", "🏸", "🥊", "🥋", "🥅", "🏹", "🎣", "🏊", "🚴", "🏇", "🧩", "🎲", "🎯", "🎳"],
    "Travel & Places ✈️": ["🚗", "🚌", "🚂", "✈️", "🚀", "🚲", "🛵", "🛑", "🚧", "⛽", "🏕️", "🏖️", "🏞️", "🏥", "🏦", "🏭", "🏰", "⛩️", "🗿", "🗺️"],
    "Nature & Animals 🐾": ["☀️", "⭐", "☁️", "⛈️", "❄️", "🔥", "💧", "🐶", "🐱", "🐭", "🐹", "🐰", "🦊", "🐻", "🐼", "🦁", "🦁", "🐯", "💐", "🌹", "🌵", "🌴", "🌲", "🍀"],
    "Objects 🎒": ["📱", "⌚", "📷", "🔋", "💡", "🔦", "🎁", "🎈", "🎉", "🕶️", "👓", "☂️", "💍", "👑", "👠", "👕"]
}

# Flattened list for indexing (deterministic order is crucial for sharing)
ALL_ICONS = ["❓"] # Essential Fallback at index 0
for cat in sorted(ICON_CATEGORIES.keys()): 
    for icon in ICON_CATEGORIES[cat]:
        if icon not in ALL_ICONS:
            ALL_ICONS.append(icon)
