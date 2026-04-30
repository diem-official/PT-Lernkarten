from PIL import Image, ImageDraw


def remove_text(image: Image.Image, labels: list, padding: int = 5) -> Image.Image:
    """Paint white rectangles over text label regions."""
    result = image.copy()
    draw = ImageDraw.Draw(result)
    w_max, h_max = image.size
    for label in labels:
        x0 = max(0, label['x'] - padding)
        y0 = max(0, label['y'] - padding)
        x1 = min(w_max, label['x'] + label['w'] + padding)
        y1 = min(h_max, label['y'] + label['h'] + padding)
        draw.rectangle([x0, y0, x1, y1], fill=(255, 255, 255))
    return result
