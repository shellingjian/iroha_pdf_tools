from rembg import remove, new_session
from PIL import Image
import os

input_path = "C:/Users/jian/.gemini/antigravity/brain/ac854e77-539b-485b-b716-56bbcc076b05/uploaded_image_1765939619265.jpg"
output_path = "C:/Users/jian/.gemini/antigravity/brain/ac854e77-539b-485b-b716-56bbcc076b05/uploaded_image_1765939619265_transparent_v2.png"

print(f"Processing with 'isnet-anime' model: {input_path}")

try:
    # Use isnet-anime model which is better for 2D graphics/illustrations
    session = new_session("isnet-anime")
    
    inp = Image.open(input_path)
    output = remove(inp, session=session)
    output.save(output_path)
    print(f"Success! Saved to: {output_path}")
except Exception as e:
    print(f"Error: {e}")
