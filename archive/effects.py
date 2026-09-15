import tkinter as tk
import random
import math

class Particle:
    def __init__(self, p_type="ambient", rel_x=None, rel_y=None):
        self.type = p_type
        self.dead = False
        
        # Position is now RELATIVE (0.0 to 1.0)
        if rel_x is not None: self.rel_x = rel_x
        else: self.rel_x = random.random()
            
        if rel_y is not None: self.rel_y = rel_y
        else: self.rel_y = random.random()

        if self.type == "ambient":
            # Velocity is still absolute pixels/frame approx (scaled by logic later)
            # Reduced significantly for "Zen" feel
            self.vx = random.uniform(-0.0003, 0.0003) 
            self.vy = random.uniform(-0.0003, 0.0003)
            self.size = random.randint(4, 9) # Increased size
            # Expanded Palette: Blue, Cyan, Purple, Gold, Teal
            self.color_list = ["#3B8ED0", "#1F6AA5", "#607D8B", "#455A64", "#00BCD4", "#7C4DFF", "#FFD700", "#009688"]
            self.color = random.choice(self.color_list)
            
        elif self.type == "confetti":
            self.rel_x = rel_x if rel_x else 0.5
            self.rel_y = rel_y if rel_y else 0.5
            # Confetti physics needs to be somewhat absolute to feel "heavy"
            # We will handle confetti update differently or convert back and forth
            # Let's keep confetti absolute positions in pixels for physics accuracy
            # but usually we map rel->screen.
            # Hybrid approach: Particle stores rel_x, rel_y.
            # For confetti, we interpret these changes rapidly.
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(0.002, 0.010) # Relative speed
            self.vx = math.cos(angle) * speed
            self.vy = math.sin(angle) * speed
            self.size = random.randint(4, 9)
            self.color = random.choice(["#FFD700", "#FF5252", "#69F0AE", "#448AFF", "#E040FB"])
            self.gravity = 0.0005
            self.drag = 0.95
            
        elif self.type == "trail":
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(0.0005, 0.0015)
            self.vx = math.cos(angle) * speed
            self.vy = math.sin(angle) * speed
            self.size = random.randint(2, 4)
            self.color = random.choice(["#FFD700", "#3B8ED0", "#FF5252"])
            self.life = 1.0
            self.decay = 0.08

    def update(self, aspect_ratio=1.0):
        # aspect_ratio used to normalize speed if needed
        self.rel_x += self.vx
        self.rel_y += self.vy
        
        if self.type == "ambient":
            # Damping: Only slow down if moving faster than calm drift speed
            # This allows Repulsion bursts to fade out.
            calm_speed = 0.0004
            curr_sq = self.vx*self.vx + self.vy*self.vy
            
            if curr_sq > calm_speed*calm_speed:
                self.vx *= 0.95
                self.vy *= 0.95
            
            # Bounce/Wrap
            if self.rel_x < 0: self.rel_x = 1.0
            if self.rel_x > 1: self.rel_x = 0.0
            if self.rel_y < 0: self.rel_y = 1.0
            if self.rel_y > 1: self.rel_y = 0.0
            
        elif self.type == "confetti":
            self.vy += self.gravity
            self.vx *= self.drag
            self.vy *= self.drag
            if self.rel_y > 1.2 or self.rel_x < -0.2 or self.rel_x > 1.2: self.dead = True
            if abs(self.vx) < 0.0001 and abs(self.vy) < 0.0001: self.dead = True
            
        elif self.type == "trail":
            self.life -= self.decay
            if self.life <= 0: self.dead = True

class EffectsEngine:
    def __init__(self, master_widget, target_canvas=None, occlusion_check=None):
        self.master = master_widget
        self.running = False
        self.simple_mode = False
        self.external_canvas = target_canvas is not None
        self.occlusion_check = occlusion_check
        self.mx = -1
        self.my = -1
        
        if self.external_canvas:
            self.canvas = target_canvas
            self.canvas.bind("<Configure>", self.on_resize, add="+")
            self.width = max(1, self.canvas.winfo_width())
            self.height = max(1, self.canvas.winfo_height())
        else:
            # Background Canvas - under everything
            self.canvas = tk.Canvas(self.master, highlightthickness=0, bg="#2B2B2B")
            self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
            # Lower it below all widgets
            self.canvas.lower()
            self.width = 1000
            self.height = 600
            self.canvas.bind("<Configure>", self.on_resize)
            
        self.particles = []
        self.master.bind_all("<Motion>", self.on_mouse_move, add="+")
        
    def on_resize(self, event):
        self.width = max(1, event.width)
        self.height = max(1, event.height)
        
    def on_mouse_move(self, event):
        try:
            cx = self.canvas.winfo_rootx()
            cy = self.canvas.winfo_rooty()
            self.mx = event.x_root - cx
            self.my = event.y_root - cy
        except:
            self.mx = -1
            self.my = -1
        
    def start(self):
        if self.running: return
        self.running = True
        self.animate()
        
    def stop(self):
        self.running = False
        self.canvas.delete("particle")
        self.particles = []
        
    def set_simple_mode(self, enabled):
        self.simple_mode = enabled
        if enabled:
            self.stop()
            if not self.external_canvas:
                 self.canvas.place_forget()
        else:
            if not self.external_canvas:
                self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
                tk.Misc.lower(self.canvas)
            self.spawn_ambient(100) # Re-seed
            self.start()

    def get_viewport_pos(self, rel_x, rel_y):
        # Convert relative to absolute pixel coords
        # Add canvas scrolling offset
        bx = rel_x * self.width
        by = rel_y * self.height
        
        if self.external_canvas:
            return self.canvas.canvasx(bx), self.canvas.canvasy(by)
        return bx, by
        
    def spawn_ambient(self, count=100):
        if self.simple_mode: return
        
        self.particles = [p for p in self.particles if p.type != "ambient"]
        
        for _ in range(count):
            # Try to find a spot not too close to others
            best_x, best_y = random.random(), random.random()
            
            # Simple retry heuristic
            for _ in range(10):
                cx, cy = random.random(), random.random()
                too_close = False
                for p in self.particles:
                    if p.type == "ambient":
                        dx = p.rel_x - cx
                        dy = p.rel_y - cy
                        if dx*dx + dy*dy < 0.005: 
                            too_close = True
                            break
                if not too_close:
                    best_x, best_y = cx, cy
                    break
            
            self.particles.append(Particle("ambient", best_x, best_y))

    def burst_confetti(self, x_px=None, y_px=None):
        if self.simple_mode: return
        
        # Convert pixel to relative
        rel_x = 0.5
        rel_y = 0.5
        if x_px is not None and self.width > 0: rel_x = x_px / self.width
        if y_px is not None and self.height > 0: rel_y = y_px / self.height
        
        for _ in range(50):
            self.particles.append(Particle("confetti", rel_x, rel_y))

    def animate(self):
        if not self.running: return
        
        self.canvas.delete("particle")
        
        rel_mx = self.mx / self.width if self.width > 0 else -1
        rel_my = self.my / self.height if self.height > 0 else -1
        
        if not self.simple_mode and self.mx > -50:
             self.particles.append(Particle("trail", rel_mx, rel_my))

        ambient_particles = [p for p in self.particles if p.type == "ambient"]
        if not self.simple_mode and self.width > 0:
             max_dist_px = 200
             
             connections = {p: 0 for p in ambient_particles}
             
             # Get Occluders
             occluders = []
             if self.occlusion_check:
                  try: occluders = self.occlusion_check()
                  except: pass
             
             for i, p1 in enumerate(ambient_particles):
                 # Get P1 Vis
                 vx1, vy1 = self.get_viewport_pos(p1.rel_x, p1.rel_y)
                 p1_visible = True
                 for r in occluders:
                     if r[0] <= vx1 <= r[2] and r[1] <= vy1 <= r[3]:
                         p1_visible = False
                         break
                 
                 closest_p = None
                 
                 for p2 in ambient_particles[i+1:]:
                     dx = p1.rel_x - p2.rel_x
                     dy = p1.rel_y - p2.rel_y
                     dist_sq = dx*dx + dy*dy
                     
                     # 1. Separation (Anti-Clumping)
                     if dist_sq < 0.003 and dist_sq > 0:
                         dist = math.sqrt(dist_sq)
                         force = (0.003 - dist_sq) * 0.1
                         nx = dx / dist
                         ny = dy / dist
                         push = force * 0.0002
                         p1.vx += nx * push
                         p1.vy += ny * push
                         p2.vx -= nx * push
                         p2.vy -= ny * push

                     # 2. Connections
                     if connections[p1] >= 3 or connections[p2] >= 3: continue

                     if dist_sq < 0.05: 
                         vx2, vy2 = self.get_viewport_pos(p2.rel_x, p2.rel_y)
                         
                         # Check P2 Vis for line
                         p2_visible = True
                         for r in occluders:
                             if r[0] <= vx2 <= r[2] and r[1] <= vy2 <= r[3]:
                                 p2_visible = False
                                 break
                                 
                         # Only draw connection if at least one end is visible
                         if not (p1_visible or p2_visible): continue

                         px_dist = math.hypot(vx1-vx2, vy1-vy2)
                         
                         if px_dist < max_dist_px:
                             alpha = int((1 - px_dist/max_dist_px) * 100)
                             if alpha > 10:
                                 gray_val = int(43 + (1 - px_dist/max_dist_px) * 50)
                                 color = f"#{gray_val:02x}{gray_val:02x}{gray_val:02x}"
                                 self.canvas.create_line(vx1, vy1, vx2, vy2, fill=color, width=1, tags="particle")
                                 connections[p1] += 1
                                 connections[p2] += 1

    
        # Update Loop & Draw Points
        occluders = []
        if self.occlusion_check:
            try: occluders = self.occlusion_check()
            except: pass

        to_remove = []
        for p in self.particles:
            # Repulsion (Logic omitted for brevity, keeping existing)
            # Just focus on drawing
            if p.type == "ambient" and rel_mx > 0:
                # ... existing repulsion ...
                dx = p.rel_x - rel_mx
                dy = p.rel_y - rel_my
                dist = math.hypot(dx, dy)
                if dist < 0.15 and dist > 0:
                    force = (0.15 - dist) / 0.15
                    angle = math.atan2(dy, dx)
                    p.vx += math.cos(angle) * force * 0.0003
                    p.vy += math.sin(angle) * force * 0.0003
            
            p.update()
            if p.dead:
                to_remove.append(p)
                continue
                
            # DRAW POINT
            vx, vy = self.get_viewport_pos(p.rel_x, p.rel_y)
            
            # Visibility Check
            visible = True
            for r in occluders:
                if r[0] <= vx <= r[2] and r[1] <= vy <= r[3]:
                     visible = False
                     break
            if not visible: continue

            r = p.size
            if p.type == "trail": r = r * p.life
            
            self.canvas.create_oval(
                vx, vy, vx+r, vy+r, 
                fill=p.color, outline="",
                tags="particle"
            )
            
        for p in to_remove:
            self.particles.remove(p)
            
        ambient_count = len(ambient_particles)
        if ambient_count < 100 and not self.simple_mode: 
            self.spawn_ambient(1) # Spawn 1 at a time to maintain
            
        # Ensure particles are ON TOP (but masked)
        if self.external_canvas:
            self.canvas.tag_raise("particle")

        self.master.after(20, self.animate)
