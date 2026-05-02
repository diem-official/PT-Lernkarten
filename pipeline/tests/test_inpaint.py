import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from PIL import Image
from inpaint import draw_boxes, mask_text


def _block(x, y, w, h):
    return {"id": 0, "x": x, "y": y, "w": w, "h": h, "text": "T"}


def test_draw_boxes_returns_copy():
    img = Image.new("RGB", (100, 100), (200, 200, 200))
    assert draw_boxes(img, [_block(10, 10, 20, 20)]) is not img


def test_draw_boxes_marks_border_pixel_red():
    # draw_boxes uses outline — sample border pixel at (5,5) after 5px padding on block at (10,10)
    img = Image.new("RGB", (100, 100), (200, 200, 200))
    result = draw_boxes(img, [_block(10, 10, 20, 20)])
    assert result.getpixel((5, 5))[0] > 200


def test_mask_text_returns_copy():
    img = Image.new("RGB", (100, 100), (200, 200, 200))
    assert mask_text(img, [_block(10, 10, 20, 20)]) is not img


def test_mask_text_whites_out_center():
    img = Image.new("RGB", (100, 100), (0, 0, 0))
    assert mask_text(img, [_block(10, 10, 20, 20)]).getpixel((20, 20)) == (255, 255, 255)
