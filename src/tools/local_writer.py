"""
Local file writer tools.
Generic — can write any file type to any path.
Supports: absolute path, relative path from project root, or active IDE file.
"""

import os
from src.config.settings import settings
from src.core.logger import get_logger
from src.core.exceptions import handle_exceptions, LocalWriteException
from src.models.writer_models import WriteFileInput, WriteFileToActiveInput

log = get_logger("tools.local_writer")


# ── Internal helper ───────────────────────────────────────────────────────

def _write_to_path(full_path: str, content: str) -> str:
    """Write content to an absolute path. Creates directories if needed."""
    directory = os.path.dirname(full_path)

    if directory:
        try:
            os.makedirs(directory, exist_ok=True)
            log.debug(f"Directory ensured: {directory}")
        except OSError as e:
            raise LocalWriteException(f"Cannot create directory '{directory}': {e}")

    try:
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        log.info(f"File written: {full_path} ({len(content)} chars)")
    except OSError as e:
        raise LocalWriteException(f"Cannot write file '{full_path}': {e}")

    return full_path


def _resolve_path(input: WriteFileInput) -> tuple[str, str]:
    """
    Resolve the final write path based on provided inputs.
    Returns (full_path, resolution_method).

    Priority:
    1. absolute_path (explicit full path)
    2. active_file_path directory (write to IDE's open file directory)
    3. folder_path + PROJECT_ROOT (relative path)
    4. None → return guidance message
    """

    # Priority 1: Explicit absolute path
    if input.absolute_path:
        # If absolute_path already includes the filename, use as-is
        if input.absolute_path.endswith(input.filename):
            return input.absolute_path, "absolute_path"
        # Otherwise treat as directory
        return os.path.join(input.absolute_path, input.filename), "absolute_path"

    # Priority 2: Active file path from IDE (Copilot/VS Code)
    if input.active_file_path:
        directory = os.path.dirname(input.active_file_path)
        return os.path.join(directory, input.filename), "active_file_directory"

    # Priority 3: folder_path relative to PROJECT_ROOT
    if input.folder_path:
        full_dir = os.path.join(settings.project_root, input.folder_path)
        return os.path.join(full_dir, input.filename), "project_root+folder_path"

    # Priority 4: No path given
    return None, "no_path"


# ── Tools ─────────────────────────────────────────────────────────────────

@handle_exceptions
def write_file(input: WriteFileInput) -> str:
    """
    Write any file to the local filesystem.
    Works for any language and file type: .java, .py, .js, .ts, .xml, .json, .yaml etc.

    Path resolution priority:
    1. absolute_path  → write directly to that full path
    2. active_file_path → write to same folder as the open IDE file (Copilot/VS Code)
    3. folder_path    → write to PROJECT_ROOT/folder_path/filename
    4. nothing given  → returns a message asking where to write

    Examples:
      write_file(filename="LoginTest.java", content="...", absolute_path="C:/projects/myapp/tests/LoginTest.java")
      write_file(filename="test_login.py", content="...", folder_path="tests/login")
      write_file(filename="conftest.py", content="...", folder_path="tests")
    """
    log.info(f"write_file called: {input.filename}")

    full_path, method = _resolve_path(input)

    if full_path is None:
        log.warning("write_file called with no path information")
        return (
            f"⚠️ No path provided for '{input.filename}'.\n\n"
            f"Please specify one of:\n"
            f"  • absolute_path: full path e.g. 'C:/projects/myapp/tests/login/{input.filename}'\n"
            f"  • folder_path: relative path inside project root e.g. 'tests/login'\n"
            f"  • active_file_path: path of the currently open file in your IDE (auto-provided by Copilot)\n\n"
            f"  Current project root: {settings.project_root}"
        )

    written_path = _write_to_path(full_path, input.content)
    log.info(f"Written via [{method}]: {written_path}")

    return (
        f"✅ File written successfully:\n"
        f"   📄 {written_path}\n"
        f"   Method: {method}\n\n"
        f"👉 Review the file in your IDE before committing."
    )


@handle_exceptions
def write_to_active_file(input: WriteFileToActiveInput) -> str:
    """
    Overwrite the currently active/open file in the IDE with new content.
    Used by Copilot/VS Code when a file is open — writes directly to that file.
    active_file_path: provided automatically by the IDE context.
    content: new full content to write.
    """
    log.info(f"Writing to active file: {input.active_file_path}")

    if not os.path.exists(os.path.dirname(input.active_file_path) or "."):
        raise LocalWriteException(f"Directory does not exist: {os.path.dirname(input.active_file_path)}")

    written_path = _write_to_path(input.active_file_path, input.content)
    filename = os.path.basename(written_path)

    return (
        f"✅ Active file updated:\n"
        f"   📄 {written_path}\n\n"
        f"👉 Changes are live in your IDE. Review before committing."
    )


@handle_exceptions
def get_active_file(active_file_path: str = "") -> str:
    """
    Get information about the currently active file in the IDE.
    When used from VS Code/Copilot: the IDE passes the open file path automatically.
    When used from Claude Desktop: returns guidance on how to specify paths.
    active_file_path: passed by VS Code/Copilot context (empty when using Claude Desktop)
    """
    if active_file_path:
        log.info(f"Active file: {active_file_path}")
        exists = os.path.exists(active_file_path)
        size = os.path.getsize(active_file_path) if exists else 0
        return (
            f"✅ Active file detected:\n"
            f"   📄 {active_file_path}\n"
            f"   Exists: {exists}\n"
            f"   Size: {size} bytes\n\n"
            f"💡 write_file() will write to this file's directory automatically."
        )
    else:
        return (
            f"ℹ️ No active file detected.\n\n"
            f"If using VS Code + Copilot: the active file path is passed automatically.\n"
            f"If using Claude Desktop: specify the path manually in write_file():\n"
            f"  • absolute_path: 'C:/projects/myapp/tests/LoginTest.java'\n"
            f"  • folder_path: 'tests/login' (relative to PROJECT_ROOT={settings.project_root})"
        )


@handle_exceptions
def set_project_root(path: str) -> str:
    """
    Change the project root directory at runtime.
    Useful when switching between different local projects without editing .env.
    path: absolute path to your project root (e.g. C:/projects/my-other-project)
    """
    old = settings.project_root
    settings.project_root = path
    log.info(f"Project root changed: {old} → {path}")
    return (
        f"✅ Project root updated:\n"
        f"   Old: {old}\n"
        f"   New: {path}\n\n"
        f"All write_file() calls using folder_path will now write to this root."
    )
