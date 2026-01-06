from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def mock_sleep():
    """Skip sleep calls to speed up tests."""
    with patch("time.sleep"):
        yield
