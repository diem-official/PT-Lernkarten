from PIL import Image, ImageDraw

try:
    from simple_lama_inpainting import SimpleLama
except ImportError:
    SimpleLama = None  # pragma: no cover

_lama = None


def _get_lama():
    global _lama
    if _lama is None:
        if SimpleLama is None:
            raise RuntimeError("simple-lama-inpainting is not installed")
        _lama = SimpleLama()
    return _lama


def create_mask(image_size: tuple, labels: list, padding: int = 5) -> Image.Image:
    """Binary RGB mask: white = region to inpaint."""
    mask = Image.new('RGB', image_size, 0)
    draw = ImageDraw.Draw(mask)
    w_max, h_max = image_size
    for label in labels:
        x0 = max(0, label['x'] - padding)
        y0 = max(0, label['y'] - padding)
        x1 = min(w_max, label['x'] + label['w'] + padding)
        y1 = min(h_max, label['y'] + label['h'] + padding)
        draw.rectangle([x0, y0, x1, y1], fill=(255, 255, 255))
    return mask


def remove_text(image: Image.Image, labels: list) -> Image.Image:
    """Remove text regions from image using LaMa inpainting."""
    mask = create_mask(image.size, labels)
    return _get_lama()(image, mask)
