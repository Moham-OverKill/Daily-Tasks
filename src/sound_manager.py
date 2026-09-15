import winsound
import os

class SoundManager:
    def __init__(self, base_path):
        self.sounds_dir = os.path.join(base_path, "assets", "sounds")
        self.dnd_enabled = False
        
    def set_dnd(self, enabled):
        self.dnd_enabled = enabled
        
    def _play(self, filename):
        if self.dnd_enabled: return
        
        path = os.path.join(self.sounds_dir, filename)
        if os.path.exists(path):
            try:
                # Play async so it doesn't block UI
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            except: pass

    def play_start(self): self._play("start.wav")
    def play_done(self): self._play("done.wav")
    def play_fail(self): self._play("fail.wav")
    def play_urgent(self): self._play("urgent.wav")
    def play_reminder(self): self._play("reminder.wav")
