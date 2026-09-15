import winsound
import os
import time

try:
    base_dir = r"."
    path = os.path.join(base_dir, "assets", "sounds", "start.wav")
    
    print(f"Testing Disk Playback for {path}...")
    if os.path.exists(path):
        winsound.PlaySound(path, winsound.SND_FILENAME)
        print("Disk Playback API call complete.")
    else:
        print("File not found!")

    time.sleep(1)

    print("Testing RAM Playback...")
    if os.path.exists(path):
        with open(path, "rb") as f:
            data = f.read()
        print(f"Read {len(data)} bytes.")
        winsound.PlaySound(data, winsound.SND_MEMORY)
        print("RAM Playback API call complete.")

except Exception as e:
    print(f"Error: {e}")
