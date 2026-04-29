import pytest
import ocr


@pytest.fixture(autouse=True)
def reset_ocr_engine():
    """Reset the OCR engine singleton between tests so each test gets a fresh mock."""
    ocr._ocr_engine = None
    yield
    ocr._ocr_engine = None
