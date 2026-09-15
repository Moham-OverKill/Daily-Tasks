import customtkinter as ctk
from datetime import datetime

class TaskCard(ctk.CTkFrame):
    def __init__(self, master, task_data, on_complete, on_delete, on_edit, **kwargs):
        super().__init__(master, width=240, height=250, **kwargs)
        self.grid_propagate(False) # Enforce size
        
        self.task_data = task_data
        self.on_complete = on_complete
        self.on_delete = on_delete
        self.on_edit = on_edit
        
        self.id = task_data['id']
        self.status = task_data.get('status', 'pending')
        
        # Grid Configuration
        self.grid_columnconfigure(0, weight=1) # Center content
        self.grid_columnconfigure(1, weight=0) # Menu corner
        self.grid_rowconfigure(1, weight=1) # Icon spacer
        
        # 0. Status Label (Top Left)
        self.status_label = ctk.CTkLabel(
            self,
            text="",
            font=("Roboto", 12, "bold"),
            text_color="gray"
        )
        self.status_label.grid(row=0, column=0, sticky="nw", padx=10, pady=5)

        # 1. Menu Button (Top Right)
        if not task_data.get('is_synced'):
            self.menu_btn = ctk.CTkButton(
                self,
                text="⋮",
                width=30,
                fg_color="transparent",
                text_color="gray",
                font=("Arial", 16),
                hover_color=("gray85", "gray25"),
                command=lambda: self.on_edit(self.id)
            )
            self.menu_btn.grid(row=0, column=1, sticky="ne", padx=5, pady=5)

        # 2. Icon (Center Top)
        icon_text = task_data.get('image_path')
        if not icon_text:
            icon_text = "📝"
            name_lower = task_data['name'].lower()
            if "fajr" in name_lower: icon_text = "🌅"
            elif "dhuhr" in name_lower: icon_text = "☀️"
            elif "asr" in name_lower: icon_text = "🌤️"
            elif "maghrib" in name_lower: icon_text = "🌇"
            elif "isha" in name_lower: icon_text = "🌙"
        
        self.icon_label = ctk.CTkLabel(
            self,
            text=icon_text,
            font=("Segoe UI Emoji", 48)
        )
        self.icon_label.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(0, 0), padx=5)

        # 3. Task Name
        self.name_label = ctk.CTkLabel(
            self, 
            text=task_data['name'], 
            font=("Roboto", 16, "bold"),
            wraplength=200
        )
        self.name_label.grid(row=2, column=0, columnspan=2, padx=10, pady=(2, 0))
        
        # Helper to format time to 12h
        def fmt_12h(t_str):
            try:
                dt = datetime.strptime(t_str, "%H:%M")
                return dt.strftime("%I:%M %p").lstrip("0")
            except:
                return t_str

        # 4. Time Range
        self.time_label = ctk.CTkLabel(
            self,
            text=f"{fmt_12h(task_data['start_time'])} — {fmt_12h(task_data['end_time'])}",
            font=("Roboto", 12),
            text_color="gray"
        )
        self.time_label.grid(row=3, column=0, columnspan=2, padx=10, pady=(2, 5))

        # 5. Action Button Removed - Interaction is now full card click
        # (Button code removed)
        
        # Click Interaction
        self.bind("<Button-1>", self._handle_done_event)

        # Flashing State Variables
        self.is_flashing = False # Urgent
        self.flash_state = False 
        self.flash_job = None
        
        self.is_pulsing = False # Active
        self.pulse_step = 0
        self.pulse_job = None
        
        # Initial Render
        self.update_state_visuals()
        
        # Hover Effects
        self.bind("<Enter>", self.on_hover)
        self.bind("<Leave>", self.on_unhover)
        # Recursive bind for children so they don't break the hover or click
        for child in self.winfo_children():
            child.bind("<Enter>", self.on_hover)
            child.bind("<Leave>", self.on_unhover)
            child.bind("<Button-1>", self._handle_done_event)
            
    def _handle_done_event(self, event=None):
        self._handle_done()

    def on_hover(self, event):
        if not getattr(self, 'animations_enabled', True): return
        
        # Cancel any pending unhover
        if hasattr(self, '_hover_job') and self._hover_job:
            self.after_cancel(self._hover_job)
            self._hover_job = None
            
        # Glow Effect (Border Highlight) - No Size Change!
        if self.status != 'active' and not self.is_flashing:
            self.configure(border_width=2, border_color="#00E5FF")

    def on_unhover(self, event):
        # Schedule unhover check to prevent flicker when moving to children
        if hasattr(self, '_hover_job') and self._hover_job:
             self.after_cancel(self._hover_job)
        
        self._hover_job = self.after(50, self._check_hover_exit)
        
    def _check_hover_exit(self):
        try:
            x, y = self.winfo_pointerxy()
            widget_x = self.winfo_rootx()
            widget_y = self.winfo_rooty()
            w = self.winfo_width()
            h = self.winfo_height()
            
            # If mouse is outside box, Reset Glow
            if not (widget_x <= x <= widget_x + w and widget_y <= y <= widget_y + h):
                if self.status != 'active' and not self.is_flashing:
                    self.configure(border_width=0)
        except:
            # Safe reset
            if self.status != 'active' and not self.is_flashing:
                self.configure(border_width=0)

    def _handle_done(self):
        if getattr(self, '_cooldown_active', False): return

        # Interactive Feedback (Squish/Flash)
        self.animate_press()

        # Calc Pos for Confetti (Center of Card)
        try:
            cx = self.winfo_rootx() + self.winfo_width()/2
            cy = self.winfo_rooty() + self.winfo_height()/2
            pos = (cx, cy)
        except: pos = None

        # Toggle Logic
        old_status = self.status
        if self.status == 'done':
            # Undo
            self.stop_flashing() # Stops urgent
            self.stop_pulse()
            self.task_data['status'] = 'pending'
            self.status = 'pending'
            self.on_complete(self.id, 'pending', pos=pos)
        else:
            # Mark Done
            self.stop_flashing()
            self.stop_pulse()
            self.task_data['status'] = 'done'
            self.status = 'done'
            self.on_complete(self.id, 'done', pos=pos)
            
        self.update_state_visuals()
        
        # Apply Cooldown (1000ms)
        self._cooldown_active = True
        # self.action_btn.configure(state="disabled") # Removed
        self.after(1000, self._reset_cooldown)

    def _reset_cooldown(self):
        self._cooldown_active = False
        # Button state logic removed
        try:
            if self.status == 'done':
                pass # self.action_btn.configure(state="normal", text="Undo")
            elif self.status == 'failed':
                 pass # self.action_btn.configure(state="normal", text="Mark Done")
            else:
                 pass # self.action_btn.configure(state="normal", text="Done")
        except: pass

    def set_animations_enabled(self, enabled):
        self.animations_enabled = enabled
        if not enabled:
            self.stop_pulse()
            self.stop_flashing()
            self.update_state_visuals()
            # Reset Size
            try:
                self.configure(width=240, height=250)
                self.grid_configure(padx=5, pady=5)
            except: pass
        else:
            if self.status == 'active':
                self.start_active_pulse()

    def animate_press(self):
        if not getattr(self, 'animations_enabled', True): return
        # Quick Flash Effect
        try:
            self.configure(border_width=3, border_color="#FFFFFF")
            self.after(100, lambda: self.configure(border_width=0) if self.status != 'active' else None)
        except: pass

    def set_failed(self):
        self.stop_flashing()
        self.stop_pulse()
        self.task_data['status'] = 'failed'
        self.status = 'failed'
        self.update_state_visuals()
        
    def set_active(self):
        if self.status != 'done' and self.status != 'failed':
            self.task_data['status'] = 'active'
            self.status = 'active'
            self.update_state_visuals()

    def stop_flashing(self):
        if self.flash_job:
            self.after_cancel(self.flash_job)
            self.flash_job = None
        self.is_flashing = False

    def stop_pulse(self):
        if self.pulse_job:
            self.after_cancel(self.pulse_job)
            self.pulse_job = None
        self.is_pulsing = False
        
    def start_urgent_flashing(self):
        self.stop_pulse() # Urgent overrides pulse
        if not self.is_flashing:
            self.is_flashing = True
            self.flash_loop()
    
    def flash_loop(self):
        if not self.is_flashing: return
        self.flash_state = not self.flash_state
        color = "#FF0000" if self.flash_state else "#FFD700"
        self.configure(border_width=3, border_color=color)
        self.flash_job = self.after(500, self.flash_loop)

    def start_active_pulse(self):
        if not getattr(self, 'animations_enabled', True): return
        if self.is_flashing: return
        if self.status != 'active': return
        self.is_pulsing = True
        self.pulse_loop()
        
    def pulse_loop(self):
        if not self.is_pulsing: return
        if self.is_flashing: return 
        
        # Breathing: Cyan -> Blue -> Cyan
        colors = ["#00E5FF", "#00B8D4", "#0091EA", "#00B8D4", "#00E5FF", "#84FFFF"]
        
        self.pulse_step = (self.pulse_step + 1) % len(colors)
        color = colors[self.pulse_step]
        
        self.configure(border_width=2, border_color=color)
        self.pulse_job = self.after(150, self.pulse_loop)

    def update_state_visuals(self):
        # Base visuals based on status
        if self.status == 'done':
            self.configure(fg_color="#2E7D32", border_width=0) 
            self.status_label.configure(text="DONE", text_color="#A5D6A7")
            # self.action_btn.configure(text="Undo", state="normal", fg_color="gray", hover_color="gray25")
            self.time_label.configure(text_color="white")
            self.icon_label.configure(text_color="white")
            self.name_label.configure(text_color="white")
            
        elif self.status == 'failed':
            self.configure(fg_color="#C62828", border_width=0) 
            self.status_label.configure(text="FAILED", text_color="#EF9A9A")
            # self.action_btn.configure(text="Mark Done", state="normal", fg_color="#B71C1C", hover_color="#D32F2F")
            self.time_label.configure(text_color="white")
            self.icon_label.configure(text_color="white")
            self.name_label.configure(text_color="white")
            
        else: # Pending / Active
            self.configure(fg_color=["#2B2B2B", "#2B2B2B"])
            
            if self.status == 'active':
                self.status_label.configure(text="ACTIVE", text_color="#00E5FF")
                # self.action_btn.configure(text="Done", state="normal", fg_color=["#3B8ED0", "#1F6AA5"], hover_color=["#36719F", "#144870"])
                
                # Start Pulse if not urgent
                if not self.is_flashing:
                    self.start_active_pulse()
            else:
                self.configure(border_width=0)
                self.status_label.configure(text="PENDING", text_color="gray")
                # self.action_btn.configure(text="Done", state="normal", fg_color=["#3B8ED0", "#1F6AA5"], hover_color=["#36719F", "#144870"])
            
            self.time_label.configure(text_color="gray")
            self.icon_label.configure(text_color="white")
            self.name_label.configure(text_color=["gray10", "#DCE4EE"])

    def update_content(self, task_data):
        self.task_data = task_data
        self.id = task_data['id']
        self.status = task_data.get('status', 'pending')
        
        self.name_label.configure(text=task_data['name'])
        
        icon_text = task_data.get('image_path')
        if not icon_text:
             icon_text = "📝"
             name_lower = task_data['name'].lower()
             if "fajr" in name_lower: icon_text = "🌅"
             elif "dhuhr" in name_lower: icon_text = "☀️"
             elif "asr" in name_lower: icon_text = "🌤️"
             elif "maghrib" in name_lower: icon_text = "🌇"
             elif "isha" in name_lower: icon_text = "🌙"
        self.icon_label.configure(text=icon_text)

        def fmt_12h(t_str):
            try:
                dt = datetime.strptime(t_str, "%H:%M")
                return dt.strftime("%I:%M %p").lstrip("0")
            except:
                return t_str
        self.time_label.configure(text=f"{fmt_12h(task_data['start_time'])} — {fmt_12h(task_data['end_time'])}")
        
        self.update_state_visuals()
