import asyncpg
from pgvector.asyncpg import register_vector

from app.config import settings

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Lazy singleton connection pool. Connects to `wathiq_ai`'s restricted
    role — knowledge.* only, see 2026_08_04_990000_grant_wathiq_privileges.php.
    `register_vector` teaches asyncpg to send/receive `knowledge.chunks.embedding`
    as a plain list[float] instead of a raw pgvector wire string."""
    global _pool
    if _pool is None:
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL is not set")
        _pool = await asyncpg.create_pool(
            settings.database_url, min_size=1, max_size=10, init=register_vector
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
