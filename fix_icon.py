from PIL import Image, ImageDraw, ImageOps
import os

try:
    assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    icon_path = os.path.join(assets_dir, "icon.png")
    
    if not os.path.exists(icon_path):
        print("Icon not found!")
        exit(1)

    img = Image.open(icon_path).convert("RGBA")
    
    # Create mask
    size = img.size
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    
    # Draw rounded rectangle on mask (white = opaque, black = transparent)
    # Radius ~ 20% of width
    radius = int(size[0] * 0.2)
    draw.rounded_rectangle([(0, 0), size], radius, fill=255)
    
    # Apply mask
    img.putalpha(mask)
    
    # Verify by checking a corner pixel (optional, but good for debug)
    # Save back
    img.save(icon_path, "PNG")
    print(f"Fixed transparency for {icon_path}")

except Exception as e:
    print(f"Error: {e}")
