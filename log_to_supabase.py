# log_to_supabase.py
import os
import json
import asyncio
from typing import Any, Dict, Optional
import time
import asyncpg
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
# log_to_supabase.py is in the project root, so .env should be in the same directory
from pathlib import Path
project_root = Path(__file__).resolve().parent
env_path = project_root / ".env"

if env_path.exists():
    load_dotenv(env_path)
else:
    # Fallback: try loading from current directory
    load_dotenv()

# Check for DATABASE_URL (preferred) or DB_URL (fallback)
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("DB_URL")
LOG_TABLE = os.getenv("SUPABASE_LOG_TABLE", "server_logs")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL or DB_URL must be set in the environment or .env file. "
        f"Current working directory: {os.getcwd()}, "
        f"Looking for .env at: {env_path}"
    )

# Connection pool (module-level)
_pool: Optional[asyncpg.pool.Pool] = None

async def _get_pool() -> asyncpg.pool.Pool:
    global _pool
    if _pool is None:
        # create a pool with small size suitable for lightweight logging
        # Set max_inactive_connection_lifetime to prevent stale connections
        _pool = await asyncpg.create_pool(
            DATABASE_URL, 
            min_size=1, 
            max_size=4, 
            command_timeout=10,
            max_inactive_connection_lifetime=300  # Close connections after 5 min of inactivity
        )
    return _pool

async def _insert_log_async(level: str, message: str, meta: Dict[str, Any]) -> None:
    """Insert log entry - handles connection errors gracefully"""
    max_retries = 2
    for attempt in range(max_retries):
        try:
            pool = await _get_pool()
            try:
                async with pool.acquire() as conn:
                    await conn.execute(
                        f"""
                        INSERT INTO {LOG_TABLE} (level, message, meta)
                        VALUES ($1, $2, $3)
                        """,
                        level, message, json.dumps(meta or {})
                    )
                return  # Success - exit function
            except (asyncpg.exceptions.ConnectionDoesNotExistError, 
                    asyncpg.exceptions.InterfaceError,
                    asyncpg.exceptions.PostgresConnectionError,
                    asyncpg.exceptions.PoolAcquireTimeoutError) as e:
                # Connection pool issue - reset pool and retry
                global _pool
                if _pool and attempt < max_retries - 1:
                    try:
                        await _pool.close()
                    except:
                        pass
                    _pool = None
                    # Small delay before retry
                    await asyncio.sleep(0.1)
                    continue
                # If last attempt, silently fail
                return
            except Exception:
                # Any other error - silently fail
                return
        except Exception:
            # Pool creation or other error - silently fail
            if attempt >= max_retries - 1:
                return
            await asyncio.sleep(0.1)

def _handle_log_task_exception(task: asyncio.Task) -> None:
    """Handle exceptions in background logging tasks to prevent 'Future exception was never retrieved' warnings"""
    try:
        task.result()  # This will raise if task had an exception
    except Exception:
        pass  # Silently ignore - logging failures shouldn't break the app

def log_event(level: str, message: str, meta: Dict[str, Any] = None) -> None:
    """
    Non-blocking, fire-and-forget logging interface.
    Use this from sync or async code.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    payload_meta = meta or {}

    if loop and loop.is_running():
        # Create task and add exception handler to prevent "Future exception was never retrieved"
        task = asyncio.create_task(_insert_log_async(level, message, payload_meta))
        task.add_done_callback(_handle_log_task_exception)
    else:
        try:
            asyncio.run(_insert_log_async(level, message, payload_meta))
        except Exception:
            pass

async def close_log_pool() -> None:
    global _pool
    if _pool is not None:
        try:
            await _pool.close()
        except Exception:
            pass
        _pool = None

