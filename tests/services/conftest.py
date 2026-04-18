"""Fixtures for service tests."""
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def allow_writes():
    """Bypass the Streamlit write guard so service writes work in tests."""
    with patch("services.turnover_service.check_writes_enabled"), \
         patch("services.task_service.check_writes_enabled"):
        yield
