import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from PIL import Image
from inpaint import create_mask


def test_mask_covers_label_center():
    labels = [{"x": 10, "y": 20, "w": 100, "h": 30}]
    mask = create_mask((400, 300), labels)
    assert mask.size == (400, 300)
    assert mask.getpixel((60, 35)) == (255, 255, 255)   # center of label


def test_mask_outside_label_is_black():
    labels = [{"x": 10, "y": 20, "w": 100, "h": 30}]
    mask = create_mask((400, 300), labels)
    assert mask.getpixel((300, 250)) == (0, 0, 0)


def test_mask_padding_clamps_to_image_bounds():
    labels = [{"x": 0, "y": 0, "w": 10, "h": 10}]
    mask = create_mask((50, 50), labels, padding=20)   # would go negative
    assert mask.size == (50, 50)                        # must not raise


def test_mask_multiple_labels():
    labels = [
        {"x": 10, "y": 10, "w": 50, "h": 20},
        {"x": 200, "y": 100, "w": 80, "h": 30},
    ]
    mask = create_mask((400, 300), labels)
    assert mask.getpixel((35, 20)) == (255, 255, 255)
    assert mask.getpixel((240, 115)) == (255, 255, 255)
    assert mask.getpixel((120, 60)) == (0, 0, 0)        # between the two
