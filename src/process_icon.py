import os
from PIL import Image
import io

def process_icon():
    # Input path (from user upload)
    input_path = r"C:/Users/jian/.gemini/antigravity/brain/9974a4ff-85bb-4521-8d0d-992666733f7c/uploaded_image_1765908434832.png"
    output_ico_path = r"src/assets/icon_main.ico"
    output_logo_path = r"src/assets/logo_sidebar.png"

    print(f"Processing image from: {input_path}")

    try:
        # Open original image directly
        image = Image.open(input_path)
        
        # 1. Save as PNG for Sidebar Logo (High Res)
        # Resize moderately to avoid huge files in UI
        logo_img = image.copy()
        logo_img.thumbnail((400, 400), Image.Resampling.LANCZOS) 
        logo_img.save(output_logo_path)
        print(f"Saved sidebar logo to {output_logo_path}")

        # 2. Save as ICO
        # ICO needs strictly defined sizes
        # We use high quality resampling to keep the pixel art looking okay-ish when downscaled,
        # or NEAREST if we wanted to enforce jagged edges (but LANCZOS is usually safer for general usage)
        img_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
        image.save(output_ico_path, format='ICO', sizes=img_sizes)
        print(f"Saved ICO to {output_ico_path}")

    except Exception as e:
        print(f"Error processing icon: {e}")

if __name__ == "__main__":
    process_icon()
