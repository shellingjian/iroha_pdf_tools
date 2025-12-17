import cv2
import numpy as np
from PIL import Image

input_path = "C:/Users/jian/.gemini/antigravity/brain/ac854e77-539b-485b-b716-56bbcc076b05/uploaded_image_1765939619265.jpg"
output_path = "C:/Users/jian/.gemini/antigravity/brain/ac854e77-539b-485b-b716-56bbcc076b05/uploaded_image_1765939619265_manual_fix.png"

print(f"Processing (Smart Flood Fill): {input_path}")

try:
    # 1. Load image
    img = cv2.imread(input_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    # 2. Identify background colors from corners
    # We sample a few points from the top-left margin to find the checkerboard colors
    bg_colors = set()
    samples = []
    # Sample top-left 20x20 area
    patch = img[0:20, 0:20].reshape(-1, 3)
    
    # Simple quantization to handle JPEG noise
    for p in patch:
        samples.append(tuple(p))
    
    # Find dominant colors (likely 2 for checkerboard)
    from collections import Counter
    counts = Counter(samples)
    
    # Take top 2 most common colors as background candidates
    # (Assuming the corner IS background)
    most_common = counts.most_common(5)
    print("Dominant colors in corner:", most_common)
    
    bg_candidates = [c[0] for c in most_common if c[1] > 5] # Filter noise
    
    # 3. Create a mask via Flood Fill (BFS)
    h, w = img.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)
    
    # Tolerance for color matching (JPEG artifacts)
    TOLERANCE = 15
    
    def color_match(c1, c2):
        return np.mean(np.abs(np.array(c1) - np.array(c2))) < TOLERANCE

    # Queue for BFS: (x, y)
    queue = []
    
    # Start from borders
    # Top/Bottom
    for x in range(w):
        queue.append((x, 0))
        queue.append((x, h-1))
    # Left/Right
    for y in range(h):
        queue.append((0, y))
        queue.append((w-1, y))
        
    visited = np.zeros((h, w), dtype=bool)
    
    # Add initial valid border pixels to actual processing queue
    # Only start flooding if the border pixel itself matches the background palette
    proc_queue = []
    for x, y in queue:
        pixel = tuple(img[y, x])
        is_bg = False
        for bg_c in bg_candidates:
            if color_match(pixel, bg_c):
                is_bg = True
                break
        if is_bg:
            proc_queue.append((x, y))
            visited[y, x] = True
            mask[y, x] = 255 # 255 means Background (Transparent)

    # BFS
    idx = 0
    while idx < len(proc_queue):
        cx, cy = proc_queue[idx]
        idx += 1
        
        # Check 4 neighbors
        for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
            nx, ny = cx + dx, cy + dy
            
            if 0 <= nx < w and 0 <= ny < h and not visited[ny, nx]:
                pixel = tuple(img[ny, nx])
                is_bg = False
                for bg_c in bg_candidates:
                    if color_match(pixel, bg_c):
                        is_bg = True
                        break
                
                if is_bg:
                    visited[ny, nx] = True
                    mask[ny, nx] = 255
                    proc_queue.append((nx, ny))

    # 4. Create output RGBA image
    # Mask: 255 is BG, 0 is FG
    # We want Alpha: 0 for BG, 255 for FG
    alpha = 255 - mask
    
    r, g, b = cv2.split(img)
    rgba = cv2.merge([r, g, b, alpha])
    
    # Save
    output = Image.fromarray(rgba)
    output.save(output_path)
    print(f"Success! Saved to: {output_path}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
