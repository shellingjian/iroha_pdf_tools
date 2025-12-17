
import fitz
from PIL import Image

def save_pdf_optimized(doc, path):
    """
    Save PDF with optimization (garbage collection and deflation).
    """
    try:
        doc.save(path, garbage=4, deflate=True)
        return True
    except Exception as e:
        print(f"Error saving PDF: {e}")
        return False

def render_page_to_image(page, max_size):
    """
    Render a PyMuPDF page to a PIL Image, constrained by max_size (longest side).
    """
    try:
        rect = page.rect
        zoom = max_size / max(rect.height, rect.width)
        zoom = min(zoom, 2.0) # Limit max zoom to avoid excessive memory on small pages
        
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        return img
    except Exception as e:
        print(f"Error rendering page: {e}")
        return None
