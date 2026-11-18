from PIL import Image, ImageDraw
import os

assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
os.makedirs(assets_dir, exist_ok=True)

# Create a 256x256 image
img = Image.new('RGBA', (256, 256), (31, 106, 165, 255)) # Blue background
draw = ImageDraw.Draw(img)

# Draw a checkmark
points = [(50, 130), (100, 180), (200, 80)]
draw.line(points, fill="white", width=40, joint="curve")

icon_path = os.path.join(assets_dir, "icon.png")
img.save(icon_path)
print(f"Icon saved to {icon_path}")
