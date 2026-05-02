from PIL import Image, ImageDraw


def draw_boxes(image: Image.Image, blocks: list) -> Image.Image:
    result = image.copy()
    draw = ImageDraw.Draw(result)
    w_max, h_max = image.size
    for block in blocks:
        x0 = max(0, block['x'] - 5)
        y0 = max(0, block['y'] - 5)
        x1 = min(w_max, block['x'] + block['w'] + 5)
        y1 = min(h_max, block['y'] + block['h'] + 5)
        draw.rectangle([x0, y0, x1, y1], outline=(255, 0, 0), width=3)
    return result


def mask_text(image: Image.Image, blocks: list) -> Image.Image:
    result = image.copy()
    draw = ImageDraw.Draw(result)
    w_max, h_max = image.size
    for block in blocks:
        x0 = max(0, block['x'] - 5)
        y0 = max(0, block['y'] - 5)
        x1 = min(w_max, block['x'] + block['w'] + 5)
        y1 = min(h_max, block['y'] + block['h'] + 5)
        draw.rectangle([x0, y0, x1, y1], fill=(255, 255, 255))
    return result
