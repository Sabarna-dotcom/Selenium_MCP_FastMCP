import functools
import traceback
from typing import Callable, Any

from src.core.logger import get_logger

log = get_logger("exceptions")


# ── Custom Exceptions ─────────────────────────────────────────────────────

class MCPBaseException(Exception):
    """Base class for all MCP custom exceptions."""
    pass


class BrowserNotStartedException(MCPBaseException):
    """Raised when a browser tool is called before browser_start."""
    pass


class BrowserActionException(MCPBaseException):
    """Raised when a Selenium browser action fails."""
    pass


class ElementNotFoundException(MCPBaseException):
    """Raised when an element cannot be found within the timeout."""
    pass


class GitHubAPIException(MCPBaseException):
    """Raised when a GitHub API call fails."""
    pass


class GitHubFileNotFoundException(MCPBaseException):
    """Raised when a file or folder is not found in the GitHub repo."""
    pass


class LocalWriteException(MCPBaseException):
    """Raised when writing a file to the local project fails."""
    pass


class ConfigurationException(MCPBaseException):
    """Raised when a required config value is missing or invalid."""
    pass


# ── Exception → User-friendly message map ────────────────────────────────

EXCEPTION_MESSAGES = {
    BrowserNotStartedException: "🚫 Browser is not started. Call browser_start() first.",
    ElementNotFoundException:   "🔍 Element not found within the timeout period.",
    BrowserActionException:     "⚠️ Browser action failed.",
    GitHubAPIException:         "🐙 GitHub API request failed.",
    GitHubFileNotFoundException:"📂 File or folder not found in the GitHub repo.",
    LocalWriteException:        "💾 Failed to write file to local project.",
    ConfigurationException:     "⚙️ Configuration error — check your .env file.",
}


# ── Decorator ─────────────────────────────────────────────────────────────

def handle_exceptions(func: Callable) -> Callable:
    """
    Decorator that wraps MCP tool functions with:
    - Structured logging (entry, exit, errors)
    - Friendly error messages returned to Claude
    - Full traceback logged to file (not shown to Claude)
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        tool_name = func.__name__
        log.info(f"▶ TOOL CALLED  : {tool_name} | args={_safe_repr(args)} kwargs={_safe_repr(kwargs)}")

        try:
            result = func(*args, **kwargs)
            log.info(f"✅ TOOL SUCCESS : {tool_name}")
            log.debug(f"   RESULT      : {str(result)[:300]}")
            return result

        except MCPBaseException as e:
            friendly = EXCEPTION_MESSAGES.get(type(e), str(e))
            log.error(f"❌ TOOL ERROR   : {tool_name} | {type(e).__name__}: {e}")
            return f"❌ {friendly}\n   Detail: {str(e)}"

        except Exception as e:
            log.error(
                f"💥 UNEXPECTED ERROR : {tool_name} | {type(e).__name__}: {e}\n"
                f"{traceback.format_exc()}"
            )
            return (
                f"💥 Unexpected error in '{tool_name}': {type(e).__name__}: {str(e)}\n"
                f"   Check logs for full traceback."
            )

    return wrapper


# ── Helper ────────────────────────────────────────────────────────────────

def _safe_repr(value: Any, max_len: int = 200) -> str:
    """Truncate long values in logs to avoid flooding."""
    try:
        r = repr(value)
        return r[:max_len] + "..." if len(r) > max_len else r
    except Exception:
        return "<unrepresentable>"
