"""
Selenium MCP Server — Entry Point

Phase 1: Browser + Smart Browser + GitHub Reader + Local Writer
Phase 2 (future): Azure DevOps
Phase 3 (future): GitHub Actions CI/CD
"""

import sys
import os

# ── Add src/ to Python path so all imports work ──────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from mcp.server.fastmcp import FastMCP

# ── Browser Tools ─────────────────────────────────────────────────────────
from tools.browser import (
    browser_start, browser_navigate, browser_click, browser_type,
    browser_hover, browser_select_option, browser_screenshot,
    browser_snapshot, browser_wait_for, browser_scroll,
    browser_back, browser_forward, browser_refresh,
    browser_get_url, browser_execute_script,
    browser_close, browser_status
)

# ── Smart Browser Tools ───────────────────────────────────────────────────
from tools.smart_browser import (
    smart_snapshot, smart_click, smart_type,
    smart_verify, smart_wait
)

# ── GitHub Reader Tools ───────────────────────────────────────────────────
from tools.github_reader import (
    explore_repo, read_codebase, search_files,
    get_folder_files, get_file, search_code,
    switch_repo, get_current_repo
)

# ── Local Writer Tools ────────────────────────────────────────────────────
from tools.local_writer import (
    write_file, write_to_active_file,
    get_active_file, set_project_root
)

# ── Create MCP Server ─────────────────────────────────────────────────────

mcp = FastMCP(
    name="selenium-mcp",
    instructions="""
    You are a QA automation assistant connected to browser, GitHub, and local filesystem.

    TOOLS AVAILABLE:

    ── BROWSER (Standard) ────────────────────────────────────────────────
    Use when you know exact CSS/XPath selectors.
    browser_navigate, browser_click, browser_type, browser_hover,
    browser_screenshot, browser_snapshot, browser_scroll, browser_status etc.

    ── BROWSER (Smart) ───────────────────────────────────────────────────
    Use for natural language interaction — no selectors needed.
    smart_snapshot()           → Clean accessibility tree (USE THIS instead of browser_snapshot)
    smart_click("description") → Click by plain English e.g. "Sign In button"
    smart_type("field", "text")→ Type by plain English e.g. "username field"
    smart_verify("condition")  → Verify something is present e.g. "error message visible"
    smart_wait("condition")    → Wait for something e.g. "page navigates to dashboard"

    ── GITHUB READER ─────────────────────────────────────────────────────
    explore_repo()         → Full recursive repo structure (ALWAYS call first)
    read_codebase()        → Read files (mode: read_all or read_relevant with query)
    get_file()             → Read one specific file
    search_files()         → Find files by name keyword
    search_code()          → Find files containing a keyword in their content
    get_folder_files()     → Read all files from a specific folder
    switch_repo()          → Switch to different GitHub repo at runtime
    get_current_repo()     → Show active repo

    ── LOCAL WRITER ──────────────────────────────────────────────────────
    write_file()           → Write any file anywhere (auto-detects path from context)
    write_to_active_file() → Overwrite the currently open IDE file
    get_active_file()      → Check what file is currently open in IDE
    set_project_root()     → Change local project root at runtime

    RECOMMENDED WORKFLOW:
    1. explore_repo(mode='structure_only') → understand project structure
    2. read_codebase(mode='read_relevant', query='...') → learn relevant patterns
    3. smart_snapshot() → understand live page UI
    4. smart_click/smart_type → interact with page naturally
    5. write_file() → write generated code to correct location
    """
)

# ── Register Browser Tools ────────────────────────────────────────────────
mcp.tool()(browser_start)
mcp.tool()(browser_navigate)
mcp.tool()(browser_click)
mcp.tool()(browser_type)
mcp.tool()(browser_hover)
mcp.tool()(browser_select_option)
mcp.tool()(browser_screenshot)
mcp.tool()(browser_snapshot)
mcp.tool()(browser_wait_for)
mcp.tool()(browser_scroll)
mcp.tool()(browser_back)
mcp.tool()(browser_forward)
mcp.tool()(browser_refresh)
mcp.tool()(browser_get_url)
mcp.tool()(browser_execute_script)
mcp.tool()(browser_close)
mcp.tool()(browser_status)

# ── Register Smart Browser Tools ─────────────────────────────────────────
mcp.tool()(smart_snapshot)
mcp.tool()(smart_click)
mcp.tool()(smart_type)
mcp.tool()(smart_verify)
mcp.tool()(smart_wait)

# ── Register GitHub Reader Tools ──────────────────────────────────────────
mcp.tool()(explore_repo)
mcp.tool()(read_codebase)
mcp.tool()(search_files)
mcp.tool()(get_folder_files)
mcp.tool()(get_file)
mcp.tool()(search_code)
mcp.tool()(switch_repo)
mcp.tool()(get_current_repo)

# ── Register Local Writer Tools ───────────────────────────────────────────
mcp.tool()(write_file)
mcp.tool()(write_to_active_file)
mcp.tool()(get_active_file)
mcp.tool()(set_project_root)

if __name__ == "__main__":
    mcp.run()
