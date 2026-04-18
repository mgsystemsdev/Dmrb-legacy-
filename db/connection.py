from __future__ import annotations

import contextlib
import logging
import threading
import time

import psycopg2
import psycopg2.pool

from config.settings import get_setting

logger = logging.getLogger(__name__)

_pool: psycopg2.pool.ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()
_local = threading.local()


def _get_database_url() -> str:
    database_url = get_setting("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured.")
    return database_url


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                # connect_timeout caps TCP connect at 5s so an unreachable DB
                # (e.g. IPv6-only DSN hit from an IPv4-only network) fails fast
                # instead of hanging the FastAPI startup hook for ~2 minutes and
                # breaking Railway's 30s healthcheck window.
                try:
                    _pool = psycopg2.pool.ThreadedConnectionPool(
                        minconn=2,
                        maxconn=10,
                        dsn=_get_database_url(),
                        connect_timeout=5,
                        prepare_threshold=None,
                    )
                except TypeError:
                    _pool = psycopg2.pool.ThreadedConnectionPool(
                        minconn=2,
                        maxconn=10,
                        dsn=_get_database_url(),
                        connect_timeout=5,
                    )
    return _pool


def get_pool_stats() -> dict:
    pool = _get_pool()
    # psycopg2 pool doesn't have a lot of public stats, but we can return min/max
    # and maybe check internal state if we really want to, but min/max is a start.
    # Actually, AbstractConnectionPool has _used and _pool lists.
    return {
        "minconn": pool.minconn,
        "maxconn": pool.maxconn,
        "used": len(pool._used) if hasattr(pool, "_used") else -1,
        "rused": len(pool._rused) if hasattr(pool, "_rused") else -1,
    }


@contextlib.contextmanager
def get_connection():
    """Acquire a connection from the pool.

    Inside a transaction() block, reuses the same connection so all
    repository calls participate in the same atomic write.
    """
    if getattr(_local, "txn_conn", None) is not None:
        yield _local.txn_conn
        return

    pool = _get_pool()
    t0 = time.monotonic()
    conn = pool.getconn()
    elapsed = time.monotonic() - t0
    if elapsed > 0.1:
        logger.warning("DB pool acquisition took %.0fms", elapsed * 1000)
    conn.autocommit = True
    try:
        yield conn
    finally:
        pool.putconn(conn)


@contextlib.contextmanager
def transaction():
    """Wrap a block of DB writes in a single all-or-nothing transaction.

    Commits on clean exit; rolls back on any exception. Repository calls
    made inside this block reuse the same connection via thread-local state.
    """
    pool = _get_pool()
    conn = pool.getconn()
    _local.txn_conn = conn
    conn.autocommit = False
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.autocommit = True
        _local.txn_conn = None
        pool.putconn(conn)
