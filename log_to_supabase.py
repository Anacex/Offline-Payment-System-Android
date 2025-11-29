# log_to_supabase.py
import os
import json
import asyncio
import warnings
from typing import Any, Dict, Optional
import time
import asyncpg
from dotenv import load_dotenv

# Suppress "Future exception was never retrieved" warnings for logging tasks
# We handle exceptions in callbacks, but Python checks before callbacks run
warnings.filterwarnings("ignore", message=".*Future exception was never retrieved.*", category=RuntimeWarning)

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
# Track active logging tasks for graceful shutdown
_active_tasks: set = set()
_shutting_down: bool = False

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

async def _insert_log_async(level: str, message: str, meta: Dict[str, Any], raise_on_failure: bool = False) -> bool:
    """
    Insert log entry - handles connection errors gracefully.
    Returns True on success, False on failure (or raises exception if raise_on_failure=True).
    """
    global _shutting_down
    
    # Don't log if we're shutting down
    if _shutting_down:
        if raise_on_failure:
            raise RuntimeError("Logging is shutting down")
        return False
    
    max_retries = 2
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            # Check if shutting down before each retry
            if _shutting_down:
                if raise_on_failure:
                    raise RuntimeError("Logging is shutting down")
                return False
            
            pool = await _get_pool()
            try:
                async with pool.acquire() as conn:
                    # Execute the INSERT
                    result = await conn.execute(
                        f"""
                        INSERT INTO {LOG_TABLE} (level, message, meta)
                        VALUES ($1, $2, $3)
                        """,
                        level, message, json.dumps(meta or {})
                    )
                    # Verify the INSERT succeeded (result should be like "INSERT 0 1")
                    if result and "INSERT" in result:
                        return True  # Success - exit function
                    else:
                        # INSERT didn't return expected result
                        if raise_on_failure:
                            raise RuntimeError(f"INSERT returned unexpected result: {result}")
                        return False
            except (asyncpg.exceptions.ConnectionDoesNotExistError, 
                    asyncpg.exceptions.InterfaceError,
                    asyncpg.exceptions.PostgresConnectionError,
                    asyncpg.exceptions.PoolAcquireTimeoutError) as e:
                last_exception = e
                # Connection pool issue - reset pool and retry
                global _pool
                if _pool and attempt < max_retries - 1 and not _shutting_down:
                    try:
                        await _pool.close()
                    except:
                        pass
                    _pool = None
                    # Small delay before retry
                    await asyncio.sleep(0.1)
                    continue
                # If last attempt or shutting down
                if raise_on_failure:
                    raise e
                return False
            except asyncio.CancelledError:
                # Task was cancelled (e.g., during shutdown) - this is normal
                if raise_on_failure:
                    raise
                return False
            except Exception as e:
                last_exception = e
                if raise_on_failure:
                    raise
                return False
        except asyncio.CancelledError:
            # Task was cancelled - this is normal during shutdown
            if raise_on_failure:
                raise
            return False
        except Exception as e:
            last_exception = e
            # Pool creation or other error
            if attempt >= max_retries - 1 or _shutting_down:
                if raise_on_failure:
                    raise e
                return False
            await asyncio.sleep(0.1)
    
    # All retries failed
    if raise_on_failure and last_exception:
        raise last_exception
    return False

def _handle_log_task_exception(task: asyncio.Task) -> None:
    """Handle exceptions in background logging tasks to prevent 'Future exception was never retrieved' warnings"""
    global _active_tasks
    try:
        # Get the result - this will raise if task had an exception
        task.result()
    except (asyncio.CancelledError, 
            asyncpg.exceptions.ConnectionDoesNotExistError,
            asyncpg.exceptions.InterfaceError,
            asyncpg.exceptions.PostgresConnectionError,
            asyncpg.exceptions.PoolAcquireTimeoutError):
        # These are expected during shutdown or connection issues - ignore silently
        pass
    except Exception as e:
        # Any other error - silently ignore (logging failures shouldn't break the app)
        # Only log to console if it's not a connection-related error
        if not isinstance(e, (asyncpg.exceptions.ConnectionDoesNotExistError,
                             asyncpg.exceptions.InterfaceError,
                             asyncpg.exceptions.PostgresConnectionError)):
            # Suppress all errors - logging failures shouldn't break the app
            pass
    finally:
        # Always remove task from active set
        _active_tasks.discard(task)

def log_event(level: str, message: str, meta: Dict[str, Any] = None) -> None:
    """
    Non-blocking, fire-and-forget logging interface.
    Use this from sync or async code.
    """
    global _shutting_down, _active_tasks
    
    # Don't create new tasks if shutting down
    if _shutting_down:
        return
    
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    payload_meta = meta or {}

    if loop and loop.is_running():
        # Create task with comprehensive exception handling
        # Use a pattern that ensures exceptions are always retrieved
        async def _safe_insert_log():
            try:
                # Fire-and-forget mode: don't raise on failure
                await _insert_log_async(level, message, payload_meta, raise_on_failure=False)
            except (asyncio.CancelledError,
                    asyncpg.exceptions.ConnectionDoesNotExistError,
                    asyncpg.exceptions.InterfaceError,
                    asyncpg.exceptions.PostgresConnectionError,
                    asyncpg.exceptions.PoolAcquireTimeoutError):
                # Suppress connection errors - they're expected
                return
            except Exception:
                # Suppress all other errors - logging failures shouldn't break the app
                return
        
        # Create task and immediately schedule exception handler
        task = asyncio.create_task(_safe_insert_log())
        _active_tasks.add(task)
        
        # Create a background handler that waits for the task and retrieves exceptions
        async def _wait_and_handle_task():
            try:
                await task
            except Exception:
                # Exception retrieved - prevents "Future exception was never retrieved"
                pass
            finally:
                _active_tasks.discard(task)
        
        # Schedule the handler immediately
        asyncio.create_task(_wait_and_handle_task())
    else:
        try:
            asyncio.run(_insert_log_async(level, message, payload_meta, raise_on_failure=False))
        except Exception:
            pass

def log_event_blocking(level: str, message: str, meta: Dict[str, Any] = None, timeout: float = 2.0) -> bool:
    """
    Blocking/synchronous logging for critical events (like OTPs).
    Waits for the log to be written with a timeout.
    Returns True if successful, False otherwise.
    Can be called from synchronous code.
    """
    global _shutting_down
    
    if _shutting_down:
        return False
    
    payload_meta = meta or {}
    
    try:
        # Check if we're in an async context
        loop = asyncio.get_running_loop()
        # We're in an async context (FastAPI), but we're in a sync function
        # Use asyncio.run_coroutine_threadsafe to run in the existing event loop
        import concurrent.futures
        import threading
        
        # Create a future to track the result
        future = concurrent.futures.Future()
        
        def _set_result(result):
            if not future.done():
                future.set_result(result)
        
        def _set_exception(exc):
            if not future.done():
                future.set_exception(exc)
        
        # Schedule the coroutine in the existing event loop
        task = asyncio.run_coroutine_threadsafe(
            _insert_log_async(level, message, payload_meta, raise_on_failure=True),
            loop
        )
        
        # Wait for the result with timeout
        try:
            result = task.result(timeout=timeout)
            return result is True
        except concurrent.futures.TimeoutError:
            # Timeout occurred - cancel the task to avoid hanging
            task.cancel()
            try:
                task.result(timeout=0.1)  # Wait briefly for cancellation
            except:
                pass
            return False
        except Exception as e:
            # Exception occurred
            return False
    except RuntimeError:
        # No event loop running, create one
        try:
            asyncio.run(_insert_log_async(level, message, payload_meta))
            return True
        except Exception:
            return False

async def log_event_sync(level: str, message: str, meta: Dict[str, Any] = None, timeout: float = 5.0) -> bool:
    """
    Synchronous logging for critical events (like OTPs).
    Waits for the log to be written with a timeout.
    Returns True if successful, False otherwise.
    """
    global _shutting_down
    
    if _shutting_down:
        return False
    
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No event loop, create one
        try:
            asyncio.run(_insert_log_async(level, message, meta or {}))
            return True
        except Exception:
            return False
    
    payload_meta = meta or {}
    
    # Create a task and wait for it with timeout
    async def _safe_insert():
        try:
            await _insert_log_async(level, message, payload_meta)
            return True
        except Exception:
            return False
    
    try:
        task = asyncio.create_task(_safe_insert())
        # Wait for completion with timeout
        result = await asyncio.wait_for(task, timeout=timeout)
        return result
    except asyncio.TimeoutError:
        # Log timed out, but that's okay - at least we tried
        return False
    except Exception:
        return False

async def close_log_pool() -> None:
    """Close the connection pool and wait for pending logging tasks"""
    global _pool, _shutting_down, _active_tasks
    
    # Mark as shutting down to prevent new logging tasks
    _shutting_down = True
    
    # Wait a short time for active tasks to complete (with timeout)
    if _active_tasks:
        try:
            # Wait up to 2 seconds for tasks to complete
            await asyncio.wait_for(
                asyncio.gather(*_active_tasks, return_exceptions=True),
                timeout=2.0
            )
        except asyncio.TimeoutError:
            # Cancel remaining tasks if they take too long
            for task in _active_tasks:
                if not task.done():
                    task.cancel()
            # Wait a bit more for cancellation to complete
            await asyncio.gather(*_active_tasks, return_exceptions=True)
        except Exception:
            pass
    
    # Close the pool
    if _pool is not None:
        try:
            await _pool.close()
        except Exception:
            pass
        _pool = None
    
    _active_tasks.clear()

