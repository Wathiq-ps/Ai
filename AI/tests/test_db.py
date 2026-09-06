import asyncio

import pytest

from app.config import settings
from app.db import get_pool


def test_get_pool_raises_without_database_url():
    original = settings.database_url
    settings.database_url = ""
    try:
        with pytest.raises(RuntimeError, match="DATABASE_URL"):
            asyncio.run(get_pool())
    finally:
        settings.database_url = original
