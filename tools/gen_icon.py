from PIL import Image
import os

input_path = "C:/Users/jian/.gemini/antigravity/brain/ac854e77-539b-485b-b716-56bbcc076b05/uploaded_image_1765941714285.png"
output_path = "d:/ai/project/iroha_pdf_tools/src/assets/icons/icon_ocr.ico"

try:
    img = Image.open(input_path)
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    img.save(output_path, format='ICO', sizes=[(256, 256)])
    print(f"Success! Saved icon to: {output_path}")
except Exception as e:
    print(f"Error: {e}")
