import cv2
import numpy as np
from PIL import Image

input_path = "C:/Users/jian/.gemini/antigravity/brain/ac854e77-539b-485b-b716-56bbcc076b05/uploaded_image_1765940719599.png"
output_path = "C:/Users/jian/.gemini/antigravity/brain/ac854e77-539b-485b-b716-56bbcc076b05/uploaded_image_1765940719599_transparent.png"
output_icon_path = "C:/Users/jian/.gemini/antigravity/brain/ac854e77-539b-485b-b716-56bbcc076b05/icon_ocr.ico"

print(f"Processing (White BG Removal): {input_path}")

try:
    # 1. Load image
    img = cv2.imread(input_path)
    if img is None:
        raise Exception("Could not load image")
    
    # Convert manually to BGRA to handle transparency later
    b, g, r = cv2.split(img)
    
    # 2. Create Mask for Flood Fill
    # Mask size needs to be 2 pixels larger than image for cv2.floodFill
    h, w = img.shape[:2]
    mask = np.zeros((h+2, w+2), np.uint8)
    
    # 3. Flood Fill from 4 corners
    # We want to find the connected white background components
    # loDiff and upDiff set the tolerance. White is (255,255,255). 
    # Even simple white might have slight JPEG artifacts if converted from jpg, but png should be clean.
    # We'll set a small tolerance just in case (e.g., 5).
    flood_flags = 4 | cv2.FLOODFILL_MASK_ONLY | (255 << 8) # Fill value 255 for the mask
    
    seed_points = [(0, 0), (0, h-1), (w-1, 0), (w-1, h-1)]
    
    points_flooded = 0
    for seed in seed_points:
        # Check if seed is actually whitish (r,g,b > 240)
        pixel = img[seed[1], seed[0]]
        if np.mean(pixel) > 200: # It's light color
            num, _, _, _ = cv2.floodFill(img, mask, seed, (0,0,0), (10,10,10), (10,10,10), flood_flags)
            points_flooded += num
            
    print(f"Flooded {points_flooded} pixels as background.")

    # 4. Extract simple mask
    # The mask contains 255 for background, 0 for foreground.
    # Note: mask is (h+2, w+2), we discard the border.
    mask_simple = mask[1:-1, 1:-1]
    
    # 5. Create Alpha Channel
    # Background (255 in mask) -> Alpha 0
    # Foreground (0 in mask) -> Alpha 255
    alpha = np.where(mask_simple == 255, 0, 255).astype(np.uint8)
    
    # 6. Merge and Save
    rgba = cv2.merge([b, g, r, alpha])
    cv2.imwrite(output_path, rgba)
    print(f"Success! Saved to: {output_path}")

    # 7. Also save as ICO for the project
    img_pil = Image.open(output_path)
    img_pil.save(output_icon_path, format='ICO', sizes=[(256, 256)])
    print(f"Saved icon to: {output_icon_path}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
