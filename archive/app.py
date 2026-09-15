import customtkinter as ctk
import tkinter as tk
import json
import threading
import time
import os
import ctypes
import sys
from datetime import datetime, timedelta
from PIL import Image, ImageTk, ImageDraw, ImageFont
from plyer import notification

from .task_manager import TaskManager
from .ui_components import TaskCard
from .sound_manager import SoundManager
from .effects import EffectsEngine



ICON_CATEGORIES = {
    "Essentials 🏠": ["📝", "💻", "💼", "📚", "📅", "🏠", "🛒", "🧹", "🔧", "📞", "💳", "🗑️", "📦", "🛋️", "🛁", "🔑", "🔒", "🚪"],
    "Health & Self 🧘": ["🏋️", "🧘", "💤", "💊", "🚿", "🦷", "💇", "💅", "🧖", "🚽", "🧴", "🤲", "🕌", "🛐", "🧠", "🫀", "👓"],
    "Food & Drink 🍔": ["☕", "🍵", "🥤", "🍼", "🍺", "🥂", "🍽️", "🍳", "🥣", "🥗", "🥪", "🌮", "🍔", "🍕", "🍟", "🍦", "🍩", "🍫", "🥦", "🍎", "🍇", "🍉", "🎂", "🍿"],
    "Sports & Fun ⚽": ["🎮", "🎨", "🎵", "🎬", "⚽", "🏀", "🏈", "🎾", "🏐", "🏉", "🎱", "🏓", "🏸", "🥊", "🥋", "🥅", "🏹", "🎣", "🏊", "🚴", "🏇", "🧩", "🎲", "🎯", "🎳"],
    "Travel & Places ✈️": ["🚗", "🚌", "🚂", "✈️", "🚀", "🚲", "🛵", "🛑", "🚧", "⛽", "🏕️", "🏖️", "🏞️", "🏥", "🏦", "🏫", "🏭", "🏰", "🕌", "⛩️", "🗿", "🗺️"],
    "Nature & Animals 🐾": ["☀️", "🌙", "⭐", "☁️", "⛈️", "❄️", "🔥", "💧", "🐶", "🐱", "🐭", "🐹", "🐰", "🦊", "🐻", "🐼", "🦁", "🐯", "💐", "🌹", "🌵", "🌴", "🌲", "🍀"],
    "Objects 🎒": ["📱", "💻", "⌚", "📷", "🔋", "💡", "🔦", "🕯️", "📚", "✏️", "🖌️", "✂️", "🎁", "🎈", "🎉", "🕶️", "☂️", "💍", "👑", "🎒", "👠", "👕"]
}


class DailyTasksApp(ctk.CTk):
    def __init__(self):
        # Win32: Set App User Model ID to fix taskbar icon
        # Must be done before window creation for best effect
        try:
            myappid = 'dailytasks.app.v1.0'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

        super().__init__()
        
        # Window Setup
        self.title("Daily Tasks")
        self.geometry("1000x600")
        
        # Path Helper
        if hasattr(sys, '_MEIPASS'):
            self.base_path = sys._MEIPASS
        else:
            self.base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # App Icon and Badge Setup
        self.icon_path = os.path.join(self.base_path, "assets", "icon.png")
        self.last_badge_count = -1

        # Theme
        ctk.set_appearance_mode("Dark")
        
        # Data Manager
        self.task_manager = TaskManager()
        self.sound_manager = SoundManager(self.base_path)
        
        # Data Manager
        self.task_manager = TaskManager()
        self.sound_manager = SoundManager(self.base_path)
        
        # Initial Icon Update
        self.update_app_icon()
        
        # State
        self.dnd_enabled = False
        self.current_date_str = datetime.now().strftime("%Y-%m-%d")
        
        # UI Layout
        self._setup_ui()
        
        # Effects Engine - uses scroll_frame's internal canvas
        target_canvas = getattr(self.scroll_frame, "_parent_canvas", None) or getattr(self.scroll_frame, "_canvas", None)
        self.effects = EffectsEngine(self, target_canvas=target_canvas)
        self.effects.spawn_ambient(100)
        self.effects.start()
        
        # Load Tasks
        self.refresh_tasks(animate=True)
        
        # Start Timer Loop
        # Start Timer Loop
        self.after(1000, self.update_loop)

        # Responsive Grid
        self.cols = 4
        self.bind("<Configure>", self.on_resize)

    def _setup_ui(self):
        # --- UI LAYOUT ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # 1. Sidebar
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)
        
        logo_label = ctk.CTkLabel(self.sidebar_frame, text="Daily Tasks", font=("Roboto", 20, "bold"))
        logo_label.pack(padx=20, pady=(20, 10))
        
        add_btn = ctk.CTkButton(
            self.sidebar_frame, 
            text="+ Add Task",
            command=self.open_add_task_dialog
        )
        add_btn.pack(padx=20, pady=10)
        
        # Switches
        self.dnd_switch = ctk.CTkSwitch(self.sidebar_frame, text="Do Not Disturb", command=self.toggle_dnd)
        self.dnd_switch.pack(pady=10, padx=20, anchor="w")
        
        self.prayer_mode_switch = ctk.CTkSwitch(
             self.sidebar_frame, 
             text="Prayer Times",
             command=self.toggle_prayer_mode
        )
        self.prayer_mode_switch.pack(pady=10, padx=20, anchor="w")

        self.simple_mode_switch = ctk.CTkSwitch(
             self.sidebar_frame, 
             text="Simple Mode",
             command=self.toggle_simple_mode
        )
        self.simple_mode_switch.pack(pady=10, padx=20, anchor="w")
        
        # 2. Main Content
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent", bg_color="transparent")
        self.scroll_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        
        # Make internal canvas match app background
        try:
            internal_canvas = getattr(self.scroll_frame, "_parent_canvas", None) or getattr(self.scroll_frame, "_canvas", None)
            if internal_canvas:
                internal_canvas.configure(bg="#2B2B2B")
        except: pass

    def refresh_tasks(self, animate=False):
        tasks = self.task_manager.get_tasks()
        tasks.sort(key=lambda x: x['start_time'])
        
        # Determine Grid Layout
        if not hasattr(self, 'cols'): self.cols = 4
        for i in range(self.cols):
            self.scroll_frame.grid_columnconfigure(i, weight=1)

        # Handle Empty State
        if not tasks:
            for widget in self.scroll_frame.winfo_children():
                widget.destroy()
            
            empty = ctk.CTkLabel(
                self.scroll_frame,
                text="No tasks for today.\nClick '+' to add one.",
                text_color="gray"
            )
            empty.grid(row=0, column=0, columnspan=self.cols, pady=50)
            self.update_app_icon()
            return

        # Smart Diff: Update Existing, Create New, Delete Old
        current_map = {}
        # Clear "Empty" label if exists and map current cards
        for widget in self.scroll_frame.winfo_children():
            if isinstance(widget, TaskCard):
                current_map[widget.id] = widget
            else:
                widget.destroy()

        processed_ids = set()
        
        for i, job in enumerate(tasks):
            t_id = job['id']
            processed_ids.add(t_id)
            
            # Grid Position
            row = i // self.cols
            col = i % self.cols
            
            if t_id in current_map:
                # Update Existing
                card = current_map[t_id]
                card.update_content(job)
                
                # Ensure Grid position (Only if changed to prevent jitter)
                try:
                    info = card.grid_info()
                    curr_r = int(info.get('row', -1))
                    curr_c = int(info.get('column', -1))
                    if curr_r != row or curr_c != col:
                        card.grid(row=row, column=col, sticky="", padx=5, pady=5)
                except:
                     card.grid(row=row, column=col, sticky="", padx=5, pady=5)
            else:
                # Create New
                card = TaskCard(
                    self.scroll_frame,
                    task_data=job,
                    on_complete=self.on_task_complete,
                    on_delete=self.on_task_delete,
                    on_edit=self.open_edit_task_dialog
                )
                
                if animate and not getattr(self, 'simple_mode_enabled', False):
                    # Staggered Entrance
                    delay = i * 150 # 150ms delay
                    def show_card(c=card, r=row, cl=col):
                        c.grid(row=r, column=cl, sticky="", padx=5, pady=5)
                    self.after(delay, show_card)
                else:
                    card.grid(row=row, column=col, sticky="", padx=5, pady=5)

                # Init Visuals
                card.set_animations_enabled(not getattr(self, 'simple_mode_enabled', False))
                if job['status'] == 'active': card.set_active()
                elif job['status'] == 'failed': card.set_failed()
                elif job['status'] == 'done': card.update_state_visuals()

        # Delete Old (Not in new list)
        for t_id, widget in current_map.items():
            if t_id not in processed_ids:
                widget.destroy()
        
        self.update_app_icon()

    def regrid_tasks(self):
        # Re-calculate layout without destroying widgets
        widgets = self.scroll_frame.winfo_children()
        if not widgets: return
        
        # Skip if purely empty label (hacky check)
        if len(widgets) == 1 and isinstance(widgets[0], ctk.CTkLabel):
             widgets[0].grid(columnspan=self.cols)
             return

        for i in range(self.cols):
            self.scroll_frame.grid_columnconfigure(i, weight=1)
            
        for i, card in enumerate(widgets):
            row = i // self.cols
            col = i % self.cols
            card.grid(row=row, column=col, sticky="", padx=5, pady=5)

    def on_resize(self, event):
        if event.widget == self:
            # Width available for cards
            # 240 card + 10 padding = 250.
            # Let's say 260 to be safe.
            new_cols = max(1, event.width // 260)
            
            if new_cols != self.cols:
                self.cols = new_cols
                self.regrid_tasks()

    def open_edit_task_dialog(self, task_id):
        # Find task
        tasks = self.task_manager.get_tasks()
        task = next((t for t in tasks if t['id'] == task_id), None)
        if not task: return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Edit Task")
        dialog.geometry("400x550")
        dialog.attributes("-topmost", True)
        
        container = ctk.CTkFrame(dialog, fg_color="transparent")
        container.pack(fill="both", expand=True)
        
        # Shared State
        current_icon = task.get('image_path')
        if not current_icon:
            name_lower = task['name'].lower()
            if "fajr" in name_lower: current_icon = "🌅"
            elif "dhuhr" in name_lower: current_icon = "☀️"
            elif "asr" in name_lower: current_icon = "🌤️"
            elif "maghrib" in name_lower: current_icon = "🌇"
            elif "isha" in name_lower: current_icon = "🌙"
            else: current_icon = "📝"
            
        selected_icon = ctk.StringVar(value=current_icon)
        
        # --- FRAMES ---
        form_frame = ctk.CTkFrame(container, fg_color="transparent")
        icons_frame = ctk.CTkFrame(container, fg_color="transparent")
        
        def show_form():
            icons_frame.pack_forget()
            form_frame.pack(fill="both", expand=True, padx=20, pady=20)
            
        def show_icons():
            form_frame.pack_forget()
            icons_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # --- 1. FORM VIEW ---
        # Name
        ctk.CTkLabel(form_frame, text="Task Name").pack(pady=(0,5))
        name_entry = ctk.CTkEntry(form_frame)
        name_entry.insert(0, task['name'])
        name_entry.pack(fill="x", pady=5)
        
        # Icon Section
        ctk.CTkLabel(form_frame, text="Icon").pack(pady=(10,5))
        icon_row = ctk.CTkFrame(form_frame, fg_color="transparent")
        icon_row.pack(pady=5)
        
        icon_preview = ctk.CTkLabel(icon_row, textvariable=selected_icon, font=("Segoe UI Emoji", 32))
        icon_preview.pack(side="left", padx=10)
        
        ctk.CTkButton(icon_row, text="Change Icon", width=100, command=show_icons).pack(side="left", padx=10)
        
        # Time Inputs Helper
        def create_time_input(parent, label_text, default_hour="00", default_min="00", default_ampm="AM"):
            frame = ctk.CTkFrame(parent, fg_color="transparent")
            frame.pack(pady=5)
            ctk.CTkLabel(frame, text=label_text, width=70, anchor="w").pack(side="left")
            h = ctk.CTkEntry(frame, width=40, placeholder_text="HH"); h.pack(side="left", padx=2)
            h.insert(0, default_hour)
            ctk.CTkLabel(frame, text=":").pack(side="left")
            m = ctk.CTkEntry(frame, width=40, placeholder_text="MM"); m.pack(side="left", padx=2)
            m.insert(0, default_min)
            ap = ctk.CTkOptionMenu(frame, values=["AM", "PM"], width=60); ap.pack(side="left", padx=5)
            ap.set(default_ampm)
            return h, m, ap

        def parse_24h(t_str):
            try:
                dt = datetime.strptime(t_str, "%H:%M")
                return dt.strftime("%I"), dt.strftime("%M"), dt.strftime("%p")
            except: return "12", "00", "AM"

        sh, sm, sp = parse_24h(task['start_time'])
        eh, em, ep = parse_24h(task['end_time'])
        
        s_h, s_m, s_p = create_time_input(form_frame, "Start", sh, sm, sp)
        e_h, e_m, e_p = create_time_input(form_frame, "End", eh, em, ep)

        def save():
            name = name_entry.get()
            def to_24h(h, m, p):
                try: return datetime.strptime(f"{h}:{m} {p}", "%I:%M %p").strftime("%H:%M")
                except: return None
            
            start = to_24h(s_h.get(), s_m.get(), s_p.get())
            end = to_24h(e_h.get(), e_m.get(), e_p.get())
            
            if name and start and end:
                self.task_manager.update_task_details(task_id, name, start, end, image_path=selected_icon.get())
                self.refresh_tasks()
                dialog.destroy()

        def delete():
            self.task_manager.delete_task(task_id)
            self.refresh_tasks()
            dialog.destroy()
        
        # Actions
        btn_frame = ctk.CTkFrame(form_frame, fg_color="transparent")
        btn_frame.pack(pady=20, side="bottom")
        ctk.CTkButton(btn_frame, text="Delete", fg_color="#D32F2F", command=delete, width=80).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Cancel", fg_color="gray", command=dialog.destroy, width=80).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Save", command=save, width=80).pack(side="left", padx=5)
        
        # --- 2. ICONS VIEW ---
        # Same as Add Dialog... could refactor, but copy-paste is safer/faster for now
        header_row = ctk.CTkFrame(icons_frame, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, 10))
        ctk.CTkButton(header_row, text="← Back", width=60, fg_color="transparent", border_width=1, command=show_form).pack(side="left")
        ctk.CTkLabel(header_row, text="Select Icon", font=("Roboto", 16, "bold")).pack(side="left", padx=20)
        
        scroll = ctk.CTkScrollableFrame(icons_frame)
        scroll.pack(fill="both", expand=True)
        
        cols = 6
        for category, icons in ICON_CATEGORIES.items():
            ctk.CTkLabel(scroll, text=category, font=("Roboto", 12, "bold"), anchor="w").pack(fill="x", pady=(10, 5))
            cat_frame = ctk.CTkFrame(scroll, fg_color="transparent")
            cat_frame.pack(fill="x")
            
            for i, icon in enumerate(icons):
                btn = ctk.CTkButton(
                    cat_frame, text=icon, width=40, height=40, font=("Segoe UI Emoji", 20),
                    fg_color="transparent", hover_color=("gray85", "gray25"),
                    command=lambda c=icon: [selected_icon.set(c), show_form()]
                )
                btn.grid(row=i//cols, column=i%cols, padx=2, pady=2)
                
        # Initialize
        show_form()

    def open_icon_picker(self, parent, on_select):
        picker = ctk.CTkToplevel(parent)
        picker.title("Select Icon")
        picker.geometry("500x600")
        picker.attributes("-topmost", True)
        
        # Header
        ctk.CTkLabel(picker, text="Choose an Icon", font=("Roboto", 18, "bold")).pack(pady=10)
        
        # Scrollable Content
        scroll = ctk.CTkScrollableFrame(picker)
        scroll.pack(fill="both", expand=True, padx=10, pady=10)
        
        cols = 8 # Wider grid since we have specific sections
        
        for category, icons in ICON_CATEGORIES.items():
            # Category Header
            ctk.CTkLabel(
                scroll, 
                text=category, 
                font=("Roboto", 14, "bold"), 
                anchor="w",
                text_color=("gray20", "gray80")
            ).pack(fill="x", pady=(15, 5), padx=5)
            
            # Category Grid Frame
            cat_frame = ctk.CTkFrame(scroll, fg_color="transparent")
            cat_frame.pack(fill="x", padx=5)
            
            for i, icon in enumerate(icons):
                btn = ctk.CTkButton(
                    cat_frame,
                    text=icon,
                    width=40,
                    height=40,
                    font=("Segoe UI Emoji", 24),
                    fg_color="transparent",
                    hover_color=("gray85", "gray25"),
                    command=lambda c=icon: [on_select(c), picker.destroy()]
                )
                btn.grid(row=i//cols, column=i%cols, padx=2, pady=2)


    def open_add_task_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Add New Task")
        dialog.geometry("400x550")
        dialog.attributes("-topmost", True)
        
        container = ctk.CTkFrame(dialog, fg_color="transparent")
        container.pack(fill="both", expand=True)

        # Shared State
        selected_icon = ctk.StringVar(value="📝")
        
        # --- FRAMES ---
        form_frame = ctk.CTkFrame(container, fg_color="transparent")
        icons_frame = ctk.CTkFrame(container, fg_color="transparent")
        
        def show_form():
            icons_frame.pack_forget()
            form_frame.pack(fill="both", expand=True, padx=20, pady=20)
            
        def show_icons():
            form_frame.pack_forget()
            icons_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # --- 1. FORM VIEW ---
        # Task Name
        ctk.CTkLabel(form_frame, text="Task Name").pack(pady=(0, 5))
        name_entry = ctk.CTkEntry(form_frame)
        name_entry.pack(fill="x", pady=5)
        
        # Icon Section
        ctk.CTkLabel(form_frame, text="Icon").pack(pady=(10, 5))
        icon_row = ctk.CTkFrame(form_frame, fg_color="transparent")
        icon_row.pack(pady=5)
        
        icon_preview = ctk.CTkLabel(
            icon_row,
            textvariable=selected_icon,
            font=("Segoe UI Emoji", 32)
        )
        icon_preview.pack(side="left", padx=10)
        
        ctk.CTkButton(
            icon_row,
            text="Change Icon",
            width=100,
            command=show_icons
        ).pack(side="left", padx=10)

        # Time Inputs Helper
        def create_time_input(parent, label_text, default_hour=None, default_min="00", default_ampm="AM"):
            frame = ctk.CTkFrame(parent, fg_color="transparent")
            frame.pack(pady=5)
            ctk.CTkLabel(frame, text=label_text, width=70, anchor="w").pack(side="left")
            h = ctk.CTkEntry(frame, width=40, placeholder_text="HH"); h.pack(side="left", padx=2)
            if default_hour: h.insert(0, default_hour)
            ctk.CTkLabel(frame, text=":").pack(side="left")
            m = ctk.CTkEntry(frame, width=40, placeholder_text="MM"); m.pack(side="left", padx=2)
            m.insert(0, default_min)
            ap = ctk.CTkOptionMenu(frame, values=["AM", "PM"], width=60); ap.pack(side="left", padx=5)
            ap.set(default_ampm)
            return h, m, ap

        now = datetime.now()
        s_h, s_m, s_p = create_time_input(form_frame, "Start", now.strftime("%I"), now.strftime("%M"), now.strftime("%p"))
        e_h, e_m, e_p = create_time_input(form_frame, "End", now.strftime("%I"), now.strftime("%M"), now.strftime("%p"))

        def save():
            name = name_entry.get()
            def to_24h(h, m, p):
                try:
                    return datetime.strptime(f"{h}:{m} {p}", "%I:%M %p").strftime("%H:%M")
                except: return None
            
            start = to_24h(s_h.get(), s_m.get(), s_p.get())
            end = to_24h(e_h.get(), e_m.get(), e_p.get())
            
            if name and start and end:
                self.task_manager.add_task(name, start, end, image_path=selected_icon.get())
                self.refresh_tasks()
                dialog.destroy()

        # Action Buttons
        btn_row = ctk.CTkFrame(form_frame, fg_color="transparent")
        btn_row.pack(pady=20, side="bottom")
        ctk.CTkButton(btn_row, text="Cancel", fg_color="gray", command=dialog.destroy, width=80).pack(side="left", padx=5)
        ctk.CTkButton(btn_row, text="Save", command=save, width=80).pack(side="left", padx=5)

        # --- 2. ICONS VIEW ---
        # Header + Back
        header_row = ctk.CTkFrame(icons_frame, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, 10))
        ctk.CTkButton(header_row, text="← Back", width=60, fg_color="transparent", border_width=1, command=show_form).pack(side="left")
        ctk.CTkLabel(header_row, text="Select Icon", font=("Roboto", 16, "bold")).pack(side="left", padx=20)
        
        # Scrollable Grid
        scroll = ctk.CTkScrollableFrame(icons_frame)
        scroll.pack(fill="both", expand=True)
        
        cols = 6
        for category, icons in ICON_CATEGORIES.items():
            ctk.CTkLabel(scroll, text=category, font=("Roboto", 12, "bold"), anchor="w").pack(fill="x", pady=(10, 5))
            cat_frame = ctk.CTkFrame(scroll, fg_color="transparent")
            cat_frame.pack(fill="x")
            
            for i, icon in enumerate(icons):
                btn = ctk.CTkButton(
                    cat_frame, text=icon, width=40, height=40, font=("Segoe UI Emoji", 20),
                    fg_color="transparent", hover_color=("gray85", "gray25"),
                    command=lambda c=icon: [selected_icon.set(c), show_form()]
                )
                btn.grid(row=i//cols, column=i%cols, padx=2, pady=2)

        # Initialize
        show_form()

    def toggle_prayer_mode(self):
        is_on = bool(self.prayer_mode_switch.get())
        
        if is_on:
            # Add (Sync)
            self.prayer_mode_switch.configure(state="disabled", text="Loading...")
            
            def _sync():
                try:
                    success = self.task_manager.sync_prayer_times()
                    self.after(0, lambda: self._post_sync(success))
                except Exception as e:
                    print(f"Sync thread failed: {e}")
                    self.after(0, lambda: self._post_sync(False))
                
            threading.Thread(target=_sync, daemon=True).start()
        else:
            # Remove
            self.task_manager.remove_synced_tasks()
            self.refresh_tasks()

    def _post_sync(self, success):
        self.prayer_mode_switch.configure(state="normal", text="Prayer Mode")
        if success:
            self.refresh_tasks()
        else:
            # If failed, turn switch back off (visual feedback)
            self.prayer_mode_switch.deselect()

    def toggle_dnd(self):
        self.dnd_enabled = bool(self.dnd_switch.get())
        self.update_app_icon()
        self.sound_manager.set_dnd(self.dnd_enabled)

    def toggle_simple_mode(self):
        enabled = bool(self.simple_mode_switch.get())
        self.simple_mode_enabled = enabled
        self.effects.set_simple_mode(enabled)
        
        # Propagate to all TaskCards
        for widget in self.scroll_frame.winfo_children():
            if isinstance(widget, TaskCard):
                widget.set_animations_enabled(not enabled)
            
    def on_task_complete(self, task_id, status='done', pos=None):
        self.task_manager.update_task_status(task_id, status)
        self.update_app_icon()
        if status == 'done':
            self.sound_manager.play_done()
            
            # Trigger Confetti (if enabled)
            if not getattr(self, 'simple_mode_enabled', False):
                if pos:
                    try:
                        c = self.effects.canvas
                        rel_x = pos[0] - c.winfo_rootx()
                        rel_y = pos[1] - c.winfo_rooty()
                        self.effects.burst_confetti(rel_x, rel_y)
                    except:
                        self.effects.burst_confetti()
                else:
                     self.effects.burst_confetti()
        
    def on_task_delete(self, task_id):
        self.task_manager.delete_task(task_id)
        self.refresh_tasks()

    def get_occlusion_rects(self):
        rects = []
        try:
            target_canvas = getattr(self.scroll_frame, "_parent_canvas", None) or getattr(self.scroll_frame, "_canvas", None)
            if not target_canvas: return []
            
            # Canvas Screen Pos
            cx = target_canvas.winfo_rootx()
            cy = target_canvas.winfo_rooty()
            
            # Check all task cards
            for widget in self.scroll_frame.winfo_children():
                if isinstance(widget, TaskCard):
                    if not widget.winfo_viewable(): continue
                    
                    dx = widget.winfo_rootx() - cx
                    dy = widget.winfo_rooty() - cy
                    
                    c_x = target_canvas.canvasx(dx)
                    c_y = target_canvas.canvasy(dy)
                    
                    w = widget.winfo_width()
                    h = widget.winfo_height()
                    
                    rects.append((c_x, c_y, c_x+w, c_y+h))
        except: pass
        return rects

    def update_loop(self):
        now = datetime.now()
        current_time_str = now.strftime("%H:%M")
        today_str = now.strftime("%Y-%m-%d")

        # 1. Daily Reset Check
        if today_str != self.current_date_str:
            self.current_date_str = today_str
            self.task_manager.reset_daily_tasks()
            self.refresh_tasks() # Refresh UI

        # 2. Check Task Times
        tasks = self.task_manager.get_tasks()
        needs_refresh = False
        
        for task in tasks:
            # Skip if done or failed
            if task['status'] in ['done', 'failed']:
                continue
                
            start = task['start_time']
            end = task['end_time']
            
            try:
                # We assume tasks are for "today"
                start_dt = datetime.strptime(f"{today_str} {start}", "%Y-%m-%d %H:%M")
                end_dt = datetime.strptime(f"{today_str} {end}", "%Y-%m-%d %H:%M")
                
                # Check for Active
                if start_dt <= now <= end_dt:
                    if task['status'] != 'active':
                        task['status'] = 'active'
                        self.task_manager.update_task_status(task['id'], 'active')
                        self.send_notification(f"Task Started: {task['name']}", "It's time!")
                        self.sound_manager.play_start()
                        needs_refresh = True
                
                # Check for Failure (Missed deadline)
                elif now > end_dt:
                    if task['status'] != 'failed':
                        task['status'] = 'failed'
                        self.task_manager.update_task_status(task['id'], 'failed')
                        self.sound_manager.play_fail()
                        needs_refresh = True
            
            except ValueError:
                pass # Time format error

        if needs_refresh:
            self.refresh_tasks()
            
        # 3. Urgency Visuals & Sounds
        has_urgent = False
        has_active = False
        
        try:
            for widget in self.scroll_frame.winfo_children():
                if isinstance(widget, TaskCard) and widget.status == 'active':
                    has_active = True
                    end_str = widget.task_data['end_time']
                    end_dt = datetime.strptime(f"{today_str} {end_str}", "%Y-%m-%d %H:%M")
                    remaining = end_dt - now
                    # Less than 30 mins and not expired
                    if timedelta(seconds=0) < remaining < timedelta(minutes=30):
                         widget.start_urgent_flashing()
                         has_urgent = True
                    else:
                         widget.stop_flashing()
                         widget.set_active_visuals() # Ensure yellow
        except Exception: 
            pass
            
        # Periodic Sounds
        if now.second == 0:
            if has_urgent:
                # Urgent Alarm (Every minute)
                self.sound_manager.play_urgent()
            elif has_active and now.minute % 5 == 0:
                # Gentle Reminder (Every 5 minutes)
                self.sound_manager.play_reminder()
            
        self.after(1000, self.update_loop) # Check every second

    def update_app_icon(self):
        # Debounce: Schedule update to prevent lag from spamming
        if getattr(self, '_icon_update_scheduled', False):
            return 
        
        self._icon_update_scheduled = True
        self.after(200, self._perform_icon_update)

    def _perform_icon_update(self):
        self._icon_update_scheduled = False
        try:
            if not hasattr(self, 'icon_path') or not os.path.exists(self.icon_path):
                return
            
            # Cache Base Image (RAM)
            if not getattr(self, '_cached_base_icon', None):
                self._cached_base_icon = Image.open(self.icon_path).convert("RGBA")
            
            # Count active
            active_count = 0
            # If DND is On, suppress badge
            if not getattr(self, 'dnd_enabled', False):
                for t in self.task_manager.get_tasks():
                    if t.get('status') == 'active': active_count += 1
            
            # Check if visual update is needed
            if hasattr(self, 'last_badge_count') and self.last_badge_count == active_count:
                return
            self.last_badge_count = active_count
            
            # Draw on COPY of cached image
            img = self._cached_base_icon.copy()
            
            if active_count > 0:
                draw = ImageDraw.Draw(img)
                w, h = img.size
                badge_size = int(w * 0.45) 
                x0, y0 = w - badge_size, h - badge_size
                
                # Draw Circle (Red with White border)
                draw.ellipse([x0, y0, w-1, h-1], fill="#D32F2F", outline="white", width=int(w*0.02))
                
                # Draw Text
                text = str(active_count)
                fs = int(badge_size * 0.65)
                try: font = ImageFont.truetype("arialbd.ttf", fs)
                except: 
                    try: font = ImageFont.truetype("arial.ttf", fs)
                    except: font = ImageFont.load_default()
                
                try:
                    left, top, right, bottom = draw.textbbox((0,0), text, font=font)
                    tw, th = right - left, bottom - top
                except:
                    tw, th = draw.textsize(text, font=font)
                    
                draw.text((x0 + (badge_size-tw)/2, y0 + (badge_size-th)/2 - th*0.1), text, fill="white", font=font)
                
            # 1. Update Taskbar (ICO)
            try:
                ico_path = os.path.join(os.path.dirname(self.icon_path), "badge.ico")
                img.save(ico_path, format='ICO', sizes=[(256, 256)])
                self.wm_iconbitmap(ico_path)
            except Exception as e_ico:
                print(f"ICO update failed: {e_ico}")
                
            # 2. Update Window (PNG)
            self.iconphoto(False, ImageTk.PhotoImage(img))
            
        except Exception as e:
            print(f"Badge update failed: {e}")

    def flash_window(self):
        try:
            import ctypes
            # Flash the window in taskbar
            # internal winfo_id works for getting HWND on Windows usually
            hwnd = self.winfo_id()
            # FlashWindow(HWND, bInvert)
            ctypes.windll.user32.FlashWindow(hwnd, True)
        except Exception as e:
            print(f"Taskbar flash failed: {e}")

    def send_notification(self, title, message):
        if self.dnd_enabled:
            return

        # Flash taskbar always (visual cue) -> Now controlled by DND too
        self.flash_window()
            
        try:
            notification.notify(
                title=title,
                message=message,
                app_name="Daily Tasks",
                # app_icon=None, # Add icon path if available
                timeout=10
            )
        except Exception as e:
            print(f"Notification failed: {e}")

if __name__ == "__main__":
    app = DailyTasksApp()
    app.mainloop()
