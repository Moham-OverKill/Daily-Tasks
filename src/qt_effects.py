"""
Qt-based Particle Effects Engine
Renders particles on a transparent background layer using QPainter
Full feature parity: confetti burst, mouse interaction, connection lines
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush
import random
import math


class Particle:
    """Single particle with position, velocity, and visual properties"""
    
    def __init__(self, x, y, vx=0, vy=0, color=None, size=3, life=None, gravity=0):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        
        # Random opacity for depth (50-220)
        base_color = color or QColor(0, 229, 255) # Cyan default
        alpha = random.randint(50, 220)
        self.color = QColor(base_color)
        self.color.setAlpha(alpha)
        
        self.size = size
        self.life = life  # None = infinite
        self.max_life = life
        self.dead = False
        self.gravity = gravity
        
    def update(self, width, height):
        self.x += self.vx
        self.y += self.vy
        self.vy += self.gravity  # Apply gravity
        
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
        """Get alpha based on remaining life"""
        if self.life is None or self.max_life is None:
            return self.color.alpha()
        return int(self.color.alpha() * (self.life / self.max_life))


class ParticleBackground(QWidget):
    """
    Transparent widget that renders animated particles.
    Should be placed as the bottom-most layer in the window.
    """
    
    # Calculated: 1 particle per ~60000 pixels (was 40000)
    DENSITY_FACTOR = 1 / 60000.0
    
    # Particle color palette (matching original design)
    COLORS = [
        QColor(0, 229, 255, 180),    # Cyan
        QColor(76, 175, 80, 180),    # Green
        QColor(255, 193, 7, 180),    # Yellow/Gold
        QColor(156, 39, 176, 180),   # Purple
        QColor(33, 150, 243, 180),   # Blue
    ]
    
    # Confetti colors (more vibrant)
    CONFETTI_COLORS = [
        QColor(255, 82, 82, 255),    # Red
        QColor(255, 193, 7, 255),    # Yellow
        QColor(76, 175, 80, 255),    # Green
        QColor(33, 150, 243, 255),   # Blue
        QColor(156, 39, 176, 255),   # Purple
        QColor(255, 152, 0, 255),    # Orange
        QColor(0, 229, 255, 255),    # Cyan
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Make widget transparent
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)  # Pass clicks through
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)  # Hint for faster compositing
        
        self.particles = []
        self.mouse_x = -1
        self.mouse_y = -1
        self.simple_mode = False
        self._spawned = False
        self._prev_w = 0
        self._prev_h = 0
        
        # Animation timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        
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
            # Use the area of the RECT, not full window, if provided
            area = rw * rh
            count = int(area * self.DENSITY_FACTOR)
            # Clamping is tricky for small rects (strips), so we set a minimum density
            if rect:
                # Ensure at least some particles in strips
                count = max(1, count)
            else:
                count = max(10, min(count, 30)) # Hard cap at 30 particles for extreme optimization
            
        # If adding to existing (and no rect constraint), only spawn difference
        # But if rect is provided, we force spawn count in that rect
        needed = count
        current_ambient = len([p for p in self.particles if p.life is None])
        
        if not rect:
            if current_ambient >= count:
                return
            needed = count - current_ambient
        else:
            # HARD CAP: Prevent snowball memory leak from continuous small resize events
            max_allowed = max(10, min(int(w * h * self.DENSITY_FACTOR * 1.5), 30))
            if current_ambient + needed > max_allowed:
                needed = max(0, max_allowed - current_ambient)
        
        for _ in range(needed):
            x = rx + random.random() * rw
            y = ry + random.random() * rh
            vx = (random.random() - 0.5) * 0.2  # Slower for better performance
            vy = (random.random() - 0.5) * 0.2
            color = random.choice(self.COLORS)
            size = random.randint(2, 5)
            
            self.particles.append(Particle(x, y, vx, vy, color, size))
        self._spawned = True
    
    def resizeEvent(self, event):
        """Dynamic scaling: Cull off-screen, spawn specifically in new gaps"""
        super().resizeEvent(event)
        
        w = self.width()
        h = self.height()
        
        # Store initial size on first run
        if self._prev_w == 0:
            self._prev_w = w
            self._prev_h = h
            if w > 100: self.spawn_ambient()
            return
            
        # 1. Strict Culling (Shrinking)
        # Remove particles strictly outside new bounds
        self.particles = [p for p in self.particles if p.x <= w and p.y <= h]
        
        # 2. Coordinate-Aware Spawning (Expanding)
        # Identify new areas
        
        # Right Strip (Full height of NEW area, width is delta)
        if w > self._prev_w:
            delta_w = w - self._prev_w
            # Rect: (old_w, 0, delta_w, h)
            self.spawn_ambient(rect=(self._prev_w, 0, delta_w, h))
            
        # Bottom Strip (Full width of OLD area, height is delta)
        # Note: We use old width to avoid overlapping with the Right Strip corner if both expanded
        # Actually simplest is: Right Strip (full height), Bottom Strip (remaining width)
        if h > self._prev_h:
            delta_h = h - self._prev_h
            # Rect: (0, old_h, old_w, delta_h) -> If we used 'w' here we'd double spawn corner
            # So we spawn bottom strip only up to old width
            # But wait, if we only expanded height, w == prev_w, so it works.
            # If we expanded BOTH, Right Strip covers (old_w -> w, 0 -> h).
            # So Bottom Strip should cover (0 -> old_w, old_h -> h).
            self.spawn_ambient(rect=(0, self._prev_h, self._prev_w, delta_h))
            
        # Update trackers
        self._prev_w = w
        self._prev_h = h
                
    def start(self, fps=30):
        """Start the animation loop (30 FPS for smooth visual quality with minimal CPU usage)"""
        self.timer.start(1000 // fps)
        
    def stop(self):
        """Stop the animation loop"""
        self.timer.stop()
        
    def set_simple_mode(self, enabled):
        """Toggle simple mode (fewer particles, no connections)"""
        self.simple_mode = enabled
        if enabled:
            # Clear ALL particles in simple mode
            self.particles.clear()
        else:
            # Respawn ambient particles
            self.spawn_ambient()
        
    def on_mouse_move(self, x, y):
        """Update mouse position for interactive effects"""
        self.mouse_x = x
        self.mouse_y = y
        
    def burst_confetti(self, x=None, y=None, count=50):
        """Spawn confetti burst at position (for task completion)"""
        if self.simple_mode:
            return
            
        if x is None:
            x = self.width() / 2
        if y is None:
            y = self.height() / 2
            
        # REDUCED: 25 particles (was 50) to prevent UI stutter on task completion
        for _ in range(max(10, min(count, 25))):
            angle = random.random() * 2 * math.pi
            speed = random.uniform(3, 8)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed - 3  # Upward bias
            
            color = random.choice(self.CONFETTI_COLORS)
            size = random.randint(3, 7)
            life = random.randint(40, 80)
            
            particle = Particle(x, y, vx, vy, color, size, life, gravity=0.15)
            self.particles.append(particle)
        
    def animate(self):
        """Update all particles and trigger repaint"""
        if not self.isVisible() or not self.parentWidget().isVisible():
            return

        if self.simple_mode and len([p for p in self.particles if p.life is None]) > 10:
            # Only update confetti in simple mode
            self.particles = [p for p in self.particles if p.life is not None]
            
        w = self.width()
        h = self.height()
        
        # Update particles
        for p in self.particles:
            p.update(w, h)
            
            # Mouse interaction (only for ambient particles)
            if p.life is None and self.mouse_x >= 0 and self.mouse_y >= 0:
                dx = p.x - self.mouse_x
                dy = p.y - self.mouse_y
                dist = math.sqrt(dx*dx + dy*dy)
                
                if dist < 100 and dist > 0:
                    force = (100 - dist) / 100 * 0.02
                    p.vx += dx / dist * force
                    p.vy += dy / dist * force
                    
            # Damping is CRITICAL to prevent infinite speed increase from mouse interaction
            if p.life is None:
                speed = math.sqrt(p.vx*p.vx + p.vy*p.vy)
                # Only apply drag if they are moving faster than natural wandering speed
                if speed > 0.5:
                    p.vx *= 0.95
                    p.vy *= 0.95
                
                # Hard clamp maximum velocity to prevent zipping and crashing
                if speed > 4.0:
                    p.vx = (p.vx / speed) * 4.0
                    p.vy = (p.vy / speed) * 4.0
        
        # Remove dead particles
        self.particles = [p for p in self.particles if not p.dead]
        
        # Request repaint
        self.update()
        
    def paintEvent(self, event):
        """Draw all particles and connections"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        if not self.simple_mode:
            # OPTIMIZATION: Connection lines disabled to save CPU (User reported high usage)
            # This O(N^2) loop was the main bottleneck. 
            # To re-enable, we would need a spatial partition system (Quadtree) which is overkill here.
            pass
            
            # ambient_particles = [p for p in self.particles if p.life is None]
            # pen = QPen()
            # pen.setWidth(1)
            # 
            # for i, p1 in enumerate(ambient_particles):
            #     for p2 in ambient_particles[i+1:]:
            #         dx = p1.x - p2.x
            #         dy = p1.y - p2.y
            #         dist_sq = dx*dx + dy*dy
            #         
            #         # Optimization: Squared check avoids sqrt for far particles
            #         if dist_sq < 14400: # 120^2
            #             dist = math.sqrt(dist_sq)
            #             # Fade based on distance
            #             alpha = int(80 * (1 - dist/120))
            #             pen.setColor(QColor(100, 100, 100, alpha))
            #             painter.setPen(pen)
            #             painter.drawLine(QPointF(p1.x, p1.y), QPointF(p2.x, p2.y))
        
        # OPTIMIZATION: Move pen setting out of loop
        painter.setPen(Qt.NoPen)
        
        for p in self.particles:
            color = QColor(p.color)
            color.setAlpha(p.get_alpha())
            painter.setBrush(QBrush(color))
            painter.drawEllipse(QPointF(p.x, p.y), p.size, p.size)
            
        painter.end()
