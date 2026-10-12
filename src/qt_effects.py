"""
Qt-based Particle Effects Engine
Renders particles on a transparent background layer using QPainter
Full feature parity: confetti burst, mouse interaction, connection lines
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer, QPointF, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPolygonF
import random
import math


class ShockwaveRing:
    """Expanding neon ring effect triggered on task completion"""

    def __init__(self, x, y, color=None):
        self.x = x
        self.y = y
        self.radius = 14.0
        self.max_radius = 135.0
        self.life = 26
        self.max_life = 26
        self.dead = False
        self.color = QColor(color) if color else QColor(52, 211, 153)

    def update(self):
        progress = 1.0 - (self.life / self.max_life)
        # Ease-out expansion
        step = (self.max_radius - self.radius) * 0.16 + 1.5
        self.radius += step
        self.life -= 1
        if self.life <= 0:
            self.dead = True

    def get_alpha(self):
        ratio = max(0.0, self.life / self.max_life)
        return int(190 * (ratio * ratio))


class Particle:
    """Single particle with position, velocity, and visual properties"""
    
    def __init__(self, x, y, vx=0, vy=0, color=None, size=3, life=None, gravity=0, shape="circle"):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.shape = shape
        
        base_color = color or QColor(56, 189, 248)
        alpha = random.randint(75, 215) if life is None else 245
        self.color = QColor(base_color)
        self.color.setAlpha(alpha)
        self.base_alpha = alpha
        
        self.size = size
        self.life = life  # None = infinite
        self.max_life = life
        self.dead = False
        self.gravity = gravity
        self.phase = random.uniform(0, 2 * math.pi)
        self.phase_speed = random.uniform(0.04, 0.09)
        self.rotation = random.uniform(0, 360)
        self.spin = random.uniform(-9.0, 9.0) if life is not None else 0.0
        
    def update(self, width, height):
        self.x += self.vx
        self.y += self.vy
        self.vy += self.gravity  # Apply gravity
        self.phase += self.phase_speed
        
        if self.life is not None:
            # Air resistance for confetti/sparkles
            self.vx *= 0.965
            self.rotation = (self.rotation + self.spin) % 360
        
        # Wrap around edges (for ambient particles)
        if self.gravity == 0:
            if self.x < 0: self.x = width
            if self.x > width: self.x = 0
            if self.y < 0: self.y = height
            if self.y > height: self.y = 0
        
        # Life decay
        if self.life is not None:
            self.life -= 1
            if self.life <= 0:
                self.dead = True
                
    def get_alpha(self):
        """Get alpha based on remaining life or ambient twinkle"""
        if self.life is None or self.max_life is None:
            twinkle = 0.72 + 0.28 * math.sin(self.phase)
            return max(25, min(235, int(self.base_alpha * twinkle)))
        ratio = max(0.0, self.life / self.max_life)
        return int(self.color.alpha() * (ratio ** 0.85))


class ParticleBackground(QWidget):
    """
    Transparent widget that renders animated particles.
    Should be placed as the bottom-most layer in the window.
    """
    
    # Calculated: 1 particle per ~42000 pixels
    DENSITY_FACTOR = 1 / 42000.0
    
    # Default ambient palette (Midnight Sapphire)
    COLORS = [
        QColor(56, 189, 248, 190),    # Neon Sky Cyan (#38BDF8)
        QColor(129, 140, 248, 185),   # Electric Indigo (#818CF8)
        QColor(52, 211, 153, 180),    # Neon Emerald (#34D399)
        QColor(192, 132, 252, 175),   # Soft Violet (#C084FC)
        QColor(14, 165, 233, 185),    # Deep Azure (#0EA5E9)
        QColor(251, 191, 36, 160),    # Warm Starlight Gold (#FBBF24)
    ]

    # High-Contrast Light Mode ambient palette (rich jewel tones visible against daylight canvas)
    LIGHT_COLORS = [
        QColor(2, 132, 199, 230),     # Deep Sapphire Cyan (#0284C7)
        QColor(79, 70, 229, 225),     # Electric Indigo (#4F46E5)
        QColor(5, 150, 105, 225),     # Rich Emerald (#059669)
        QColor(124, 58, 237, 220),    # Royal Violet (#7C3AED)
        QColor(13, 148, 136, 225),    # Deep Teal (#0D9488)
        QColor(225, 29, 72, 210),     # Crimson Rose (#E11D48)
    ]

    THEME_PALETTES = {
        'dark': [
            QColor(33, 150, 243, 175),    # Classic Blue (#2196F3)
            QColor(144, 202, 249, 165),   # Soft Sky (#90CAF9)
            QColor(176, 190, 197, 160),   # Cool Silver (#B0BEC5)
            QColor(76, 175, 80, 165),     # Classic Green (#4CAF50)
            QColor(126, 87, 194, 165),    # Soft Purple (#7E57C2)
            QColor(255, 202, 40, 155),    # Warm Amber (#FFCA28)
        ],
        'midnight': COLORS,
        'obsidian': [
            QColor(226, 232, 240, 185),   # Platinum Silver (#E2E8F0)
            QColor(129, 140, 248, 185),   # Electric Indigo (#818CF8)
            QColor(148, 163, 184, 170),   # Slate Silver (#94A3B8)
            QColor(192, 132, 252, 175),   # Soft Violet (#C084FC)
            QColor(56, 189, 248, 175),    # Ice Cyan (#38BDF8)
            QColor(248, 250, 252, 190),   # Pure Starlight (#F8FAFC)
        ],
        'light': LIGHT_COLORS,
        'nebula': [
            QColor(232, 121, 249, 190),   # Neon Fuchsia (#E879F9)
            QColor(192, 132, 252, 185),   # Amethyst Violet (#C084FC)
            QColor(244, 114, 182, 185),   # Cosmic Rose (#F472B6)
            QColor(129, 140, 248, 180),   # Starlight Indigo (#818CF8)
            QColor(56, 189, 248, 175),    # Astral Cyan (#38BDF8)
            QColor(251, 191, 36, 165),    # Supernova Gold (#FBBF24)
        ],
        'emerald': [
            QColor(16, 185, 129, 190),    # Matrix Emerald (#10B981)
            QColor(52, 211, 153, 185),    # Neon Mint (#34D399)
            QColor(45, 212, 191, 185),    # Cyber Teal (#2DD4BF)
            QColor(110, 231, 183, 175),   # Soft Jade (#6EE7B7)
            QColor(163, 230, 53, 170),    # Bio Lime (#A3E635)
            QColor(56, 189, 248, 165),    # Aqua Glow (#38BDF8)
        ],
        'crimson': [
            QColor(244, 63, 94, 190),     # Crimson Ruby (#F43F5E)
            QColor(251, 113, 133, 185),   # Ember Rose (#FB7185)
            QColor(249, 115, 22, 185),    # Molten Orange (#F97316)
            QColor(251, 191, 36, 180),    # Solar Gold (#FBBF24)
            QColor(239, 68, 68, 185),     # Scarlet Flame (#EF4444)
            QColor(232, 121, 249, 165),   # Violet Spark (#E879F9)
        ],
        'nord': [
            QColor(136, 192, 208, 190),   # Nord Frost Cyan (#88C0D0)
            QColor(129, 161, 193, 185),   # Nord Glacier Blue (#81A1C1)
            QColor(143, 188, 187, 185),   # Nord Polar Teal (#8FBCBB)
            QColor(94, 129, 172, 185),    # Nord Fjord Blue (#5E81AC)
            QColor(163, 190, 140, 175),   # Nord Aurora Green (#A3BE8C)
            QColor(180, 142, 173, 175),   # Nord Aurora Purple (#B48EAD)
        ],
        'cyberpunk': [
            QColor(255, 42, 133, 195),    # Cyber Hot Pink (#FF2A85)
            QColor(0, 240, 255, 195),     # Electric Cyan (#00F0FF)
            QColor(252, 238, 9, 185),     # Synth Yellow (#FCEE09)
            QColor(184, 41, 255, 190),    # Neon Purple (#B829FF)
            QColor(56, 189, 248, 185),    # Laser Blue (#38BDF8)
            QColor(52, 211, 153, 180),    # Cyber Mint (#34D399)
        ],
        'sunset_light': [
            QColor(234, 88, 12, 230),     # Sunset Orange (#EA580C)
            QColor(225, 29, 72, 225),     # Crimson Rose (#E11D48)
            QColor(217, 119, 6, 225),     # Golden Amber (#D97706)
            QColor(147, 51, 234, 220),    # Dusk Purple (#9333EA)
            QColor(2, 132, 199, 215),     # Horizon Blue (#0284C7)
            QColor(5, 150, 105, 215),     # Oasis Emerald (#059669)
        ],
    }

    THEME_LINE_COLORS = {
        'dark': (144, 202, 249, 40),
        'midnight': (56, 189, 248, 48),
        'obsidian': (148, 163, 184, 42),
        'light': (2, 132, 199, 75),
        'nebula': (232, 121, 249, 52),
        'emerald': (16, 185, 129, 50),
        'crimson': (244, 63, 94, 50),
        'nord': (136, 192, 208, 48),
        'cyberpunk': (0, 240, 255, 58),
        'sunset_light': (234, 88, 12, 72),
    }
    
    # Confetti / Sparkle burst palette
    CONFETTI_COLORS = [
        QColor(52, 211, 153, 255),    # Emerald
        QColor(56, 189, 248, 255),    # Neon Cyan
        QColor(129, 140, 248, 255),   # Indigo
        QColor(251, 191, 36, 255),    # Amber Gold
        QColor(244, 114, 182, 255),   # Neon Rose
        QColor(167, 139, 250, 255),   # Violet
        QColor(45, 212, 191, 255),    # Teal
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Make widget transparent
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)  # Pass clicks through
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)  # Hint for faster compositing
        
        self.particles = []
        self.shockwaves = []
        self.mouse_x = -1
        self.mouse_y = -1
        self.simple_mode = False
        self.theme = 'dark'
        self._spawned = False
        self._prev_w = 0
        self._prev_h = 0

        # Continuous 60 FPS while window is visible; 0% CPU when hidden/minimized/simple_mode
        self._frame_count = 0
        self._mouse_idle_frames = 0
        self._MOUSE_REPEL_ACTIVE_FRAMES = 90  # ~1.5s active cursor repulsion after mouse stops moving
        self._running_fps = 60

        # Animation timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)

    def set_theme(self, theme):
        """Set active theme key for appropriate particle palette and contrast."""
        self.theme = theme
        self.update()
        
    def spawn_ambient(self, count=None, rect=None):
        """Spawn ambient background particles. Optional rect (x,y,w,h) to constrain spawning."""
        w = max(100, self.width())
        h = max(100, self.height())
        
        # Coordinate constraints
        rx, ry, rw, rh = 0, 0, w, h
        if rect:
            rx, ry, rw, rh = rect
        
        # Calculate optimal count if not provided
        if count is None:
            area = rw * rh
            count = int(area * self.DENSITY_FACTOR)
            if rect:
                count = max(1, count)
            else:
                count = max(24, min(count, 42))
            
        needed = count
        current_ambient = len([p for p in self.particles if p.life is None])
        
        if not rect:
            if current_ambient >= count:
                return
            needed = count - current_ambient
        else:
            max_allowed = max(24, min(int(w * h * self.DENSITY_FACTOR * 1.5), 42))
            if current_ambient + needed > max_allowed:
                needed = max(0, max_allowed - current_ambient)
        
        for _ in range(needed):
            x = rx + random.random() * rw
            y = ry + random.random() * rh
            vx = (random.random() - 0.5) * 0.25
            vy = (random.random() - 0.5) * 0.25
            c_idx = random.randrange(len(self.COLORS))
            color = self.COLORS[c_idx]
            size = random.uniform(2.2, 4.4)
            
            p = Particle(x, y, vx, vy, color, size)
            p.color_idx = c_idx
            self.particles.append(p)
        self._spawned = True
    
    def resizeEvent(self, event):
        """Dynamic scaling: wrap existing ambient particles into new bounds and top up count"""
        super().resizeEvent(event)
        
        w = max(1, self.width())
        h = max(1, self.height())
        
        if self._prev_w == 0:
            self._prev_w = w
            self._prev_h = h
            if w > 100 and not self.simple_mode:
                self.spawn_ambient(42)
            return
            
        for p in self.particles:
            if p.life is None:
                p.x = p.x % w
                p.y = p.y % h
                
        if not self.simple_mode and w > 100 and h > 100:
            self.spawn_ambient(42)
            
        self._prev_w = w
        self._prev_h = h
                
    def start(self, fps=60):
        """Start the 60 FPS animation loop while visible"""
        if self.simple_mode and not self.shockwaves and not any(p.life is not None for p in self.particles):
            return
        self._mouse_idle_frames = 0
        self._running_fps = fps
        if not self.timer.isActive():
            self.timer.start(max(16, 1000 // fps))
        
    def stop(self):
        """Stop the animation loop"""
        self.timer.stop()
        self._running_fps = 0
        
    def set_simple_mode(self, enabled):
        """Toggle simple mode (fewer particles, no connections)"""
        self.simple_mode = enabled
        if enabled:
            self.particles.clear()
            self.shockwaves.clear()
            self.stop()
            self.update()
        else:
            self.spawn_ambient()
            if self.isVisible():
                self.start(fps=60)
            self.update()
        
    def on_mouse_move(self, x, y):
        """Update mouse position for interactive effects and ensure 60 FPS loop is active"""
        if x == self.mouse_x and y == self.mouse_y:
            return
        self.mouse_x = x
        self.mouse_y = y
        self._mouse_idle_frames = 0
        if not self.simple_mode and not self.timer.isActive() and self.isVisible():
            self._running_fps = 60
            self.timer.start(16)
        
    def burst_confetti(self, x=None, y=None, count=28):
        """Spawn neon shockwave ring and multi-shape sparkle confetti burst at position"""
        if self.simple_mode:
            return
            
        if x is None:
            x = self.width() / 2
        if y is None:
            y = self.height() / 2
            
        is_light = self.theme in ('light', 'sunset_light')
        # Add dual neon shockwave rings (emerald + cyan)
        self.shockwaves.append(ShockwaveRing(x, y, QColor(16, 185, 129) if is_light else QColor(52, 211, 153)))
        ring_inner = ShockwaveRing(x, y, QColor(2, 132, 199) if is_light else QColor(56, 189, 248))
        ring_inner.radius = 6.0
        ring_inner.max_radius = 95.0
        self.shockwaves.append(ring_inner)

        shapes = ("diamond", "circle", "ribbon")
        for _ in range(max(12, min(count, 28))):
            angle = random.random() * 2 * math.pi
            speed = random.uniform(3.2, 8.8)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed - 2.6  # Upward celebration arc
            
            color = random.choice(self.CONFETTI_COLORS)
            size = random.uniform(3.0, 6.2)
            life = random.randint(36, 68)
            shape = random.choice(shapes)
            
            particle = Particle(x, y, vx, vy, color, size, life, gravity=0.16, shape=shape)
            self.particles.append(particle)

        # Wake 60 FPS loop immediately for smooth confetti playback
        self._mouse_idle_frames = 0
        if not self.timer.isActive() and self.isVisible():
            self._running_fps = 60
            self.timer.start(16)
        elif self.timer.isActive() and self._running_fps < 60:
            self._running_fps = 60
            self.timer.setInterval(16)

    def animate(self):
        """Update all particles at 60 FPS while window is visible; suspend to 0% CPU when hidden or minimized"""
        parent = self.parentWidget()
        win = self.window()
        if (
            not self.isVisible()
            or (parent is not None and not parent.isVisible())
            or (win is not None and win.isMinimized())
        ):
            self.stop()
            return

        self._frame_count += 1

        if self.simple_mode:
            if len([p for p in self.particles if p.life is None]) > 10:
                self.particles = [p for p in self.particles if p.life is not None]

        w = self.width()
        h = self.height()

        for sw in self.shockwaves:
            sw.update()
        self.shockwaves = [sw for sw in self.shockwaves if not sw.dead]

        has_transients = bool(self.shockwaves) or any(p.life is not None for p in self.particles)

        if self.simple_mode and not has_transients:
            self.stop()
            return

        self._mouse_idle_frames += 1

        # ── Update particles ──────────────────────────────────────────────────
        mx, my = self.mouse_x, self.mouse_y
        has_mouse = (mx >= 0 and my >= 0 and self._mouse_idle_frames < self._MOUSE_REPEL_ACTIVE_FRAMES)
        full_dirty = False

        for p in self.particles:
            p.update(w, h)

            if p.life is not None:
                if p.x < 260 or p.y < 44:
                    full_dirty = True
            else:
                if has_mouse:
                    dx = p.x - mx
                    dy = p.y - my
                    dist_sq = dx * dx + dy * dy

                    if 0 < dist_sq < 12100:  # 110px radius
                        dist = math.sqrt(dist_sq)
                        force = (110 - dist) / 110 * 0.024
                        p.vx += dx / dist * force
                        p.vy += dy / dist * force

                speed_sq = p.vx * p.vx + p.vy * p.vy
                if speed_sq > 0.2025:  # 0.45²
                    p.vx *= 0.95
                    p.vy *= 0.95
                if speed_sq > 12.25:   # 3.5²
                    speed = math.sqrt(speed_sq)
                    p.vx = (p.vx / speed) * 3.5
                    p.vy = (p.vy / speed) * 3.5

        for sw in self.shockwaves:
            if sw.x - sw.radius < 260 or sw.y - sw.radius < 44:
                full_dirty = True

        # Remove dead particles
        self.particles = [p for p in self.particles if not p.dead]

        # Dirty-region repaint: avoid invalidating the 250px Sidebar and 32px TitleBar
        # unless a shockwave/confetti particle actually overlaps them.
        if full_dirty or w <= 260 or h <= 40:
            self.update()
        else:
            self.update(250, 32, w - 250, h - 32)
        
    def paintEvent(self, event):
        """Draw shockwave rings, constellation lines, and glowing particles (culled to event.rect())"""
        ev_rect = event.rect()
        el, et, er, eb = ev_rect.left(), ev_rect.top(), ev_rect.right(), ev_rect.bottom()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        is_light = self.theme in ('light', 'sunset_light')
        palette = self.THEME_PALETTES.get(self.theme, self.THEME_PALETTES['dark'])
        lr, lg, lb, la = self.THEME_LINE_COLORS.get(self.theme, (144, 202, 249, 40))
        
        # 1. Draw expanding shockwave rings
        for sw in self.shockwaves:
            r = sw.radius + 4.0
            if sw.x + r < el or sw.x - r > er or sw.y + r < et or sw.y - r > eb:
                continue
            ring_color = QColor(sw.color)
            ring_color.setAlpha(sw.get_alpha())
            pen = QPen(ring_color, 2.4)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(sw.x, sw.y), sw.radius, sw.radius)

        # 2. Draw subtle constellation connection lines using 1D sweep-and-prune (culled to dirty rect)
        if not self.simple_mode:
            line_l, line_t, line_r, line_b = el - 148.0, et - 148.0, er + 148.0, eb + 148.0
            ambient = [
                p for p in self.particles
                if p.life is None and line_l <= p.x <= line_r and line_t <= p.y <= line_b
            ]
            ambient.sort(key=lambda p: p.x)
            max_dist_sq = 145.0 * 145.0
            n_amb = len(ambient)
            for i in range(n_amb):
                p1 = ambient[i]
                p1x, p1y = p1.x, p1.y
                p1_in = (el <= p1x <= er and et <= p1y <= eb)
                for j in range(i + 1, n_amb):
                    p2 = ambient[j]
                    dx = p2.x - p1x
                    if dx > 145.0:
                        break  # Sorted by x: no subsequent particle can be within 145px
                    dy = p2.y - p1y
                    if dy > 145.0 or dy < -145.0:
                        continue
                    if not p1_in and not (el <= p2.x <= er and et <= p2.y <= eb):
                        if (p1y < et and p2.y < et) or (p1y > eb and p2.y > eb):
                            continue
                    d_sq = dx * dx + dy * dy
                    if d_sq < max_dist_sq:
                        ratio = 1.0 - math.sqrt(d_sq) / 145.0
                        line_col = QColor(lr, lg, lb, int(la * ratio))
                        painter.setPen(QPen(line_col, 1.1))
                        painter.drawLine(QPointF(p1x, p1y), QPointF(p2.x, p2.y))
        
        painter.setPen(Qt.NoPen)
        
        # 3. Draw ambient starlight and burst confetti particles (culled to dirty rect)
        pl, pt, pr, pb = el - 16.0, et - 16.0, er + 16.0, eb + 16.0
        for p in self.particles:
            if p.x < pl or p.x > pr or p.y < pt or p.y > pb:
                continue
            alpha = p.get_alpha()
            if alpha <= 2:
                continue
            if p.life is None:
                c_idx = getattr(p, 'color_idx', 0) % len(palette)
                color = QColor(palette[c_idx])
            else:
                color = QColor(p.color)
            
            if p.shape == "circle":
                if is_light and p.life is None:
                    halo_color = QColor(color)
                    halo_color.setAlpha(max(18, min(95, int(alpha * 0.36))))
                    painter.setBrush(QBrush(halo_color))
                    painter.drawEllipse(QPointF(p.x, p.y), p.size * 2.4, p.size * 2.4)

                    core_alpha = max(110, min(245, int(alpha * 1.25)))
                    color.setAlpha(core_alpha)
                    painter.setBrush(QBrush(color))
                    painter.drawEllipse(QPointF(p.x, p.y), p.size * 1.3, p.size * 1.3)
                else:
                    halo_color = QColor(color)
                    halo_color.setAlpha(max(8, int(alpha * 0.22)))
                    painter.setBrush(QBrush(halo_color))
                    halo_r = p.size * 2.15
                    painter.drawEllipse(QPointF(p.x, p.y), halo_r, halo_r)
                    
                    color.setAlpha(alpha)
                    painter.setBrush(QBrush(color))
                    painter.drawEllipse(QPointF(p.x, p.y), p.size, p.size)
            elif p.shape == "diamond":
                color.setAlpha(alpha)
                painter.setBrush(QBrush(color))
                s = p.size * 1.35
                poly = QPolygonF([
                    QPointF(p.x, p.y - s),
                    QPointF(p.x + s * 0.75, p.y),
                    QPointF(p.x, p.y + s),
                    QPointF(p.x - s * 0.75, p.y),
                ])
                painter.drawPolygon(poly)
            else:
                # Tumbling confetti ribbon
                color.setAlpha(alpha)
                painter.save()
                painter.translate(QPointF(p.x, p.y))
                painter.rotate(p.rotation)
                painter.setBrush(QBrush(color))
                painter.drawRoundedRect(QRectF(-p.size * 1.1, -p.size * 0.45, p.size * 2.2, p.size * 0.9), 1.5, 1.5)
                painter.restore()
            
        painter.end()

