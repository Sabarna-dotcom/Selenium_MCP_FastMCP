"""
GitHub reader tools — repo-agnostic, works with any language/framework.
Supports full recursive exploration, read_all/read_relevant codebase reading,
and runtime repo switching.
"""

import base64
from typing import Optional

from src.core.http_client import get_github_client, build_github_url
from src.core.logger import get_logger
from src.core.exceptions import (
    handle_exceptions,
    GitHubAPIException,
    GitHubFileNotFoundException,
)
from src.models.github_models import (
    ExploreRepoInput,
    ReadCodebaseInput,
    SearchFilesInput,
    GetFolderFilesInput,
    GetFileInput,
    SearchCodeInput,
    SwitchRepoInput,
)
from src.config.settings import settings

log = get_logger("tools.github_reader")


# ── Internal helpers ──────────────────────────────────────────────────────

def _decode_content(encoded: str) -> str:
    """Decode base64 file content returned by GitHub API."""
    return base64.b64decode(encoded).decode("utf-8")


def _get_tree(branch: str) -> list[dict]:
    """
    Fetch the FULL recursive file tree of the repo on a given branch.
    Returns flat list of every file and folder with their paths.
    """
    client = get_github_client()
    url = build_github_url(f"git/trees/{branch}?recursive=1")
    log.debug(f"Fetching full recursive tree: {url}")
    response = client.get(url)

    if response.status_code == 404:
        raise GitHubFileNotFoundException(f"Branch '{branch}' not found in repo")
    if response.status_code != 200:
        raise GitHubAPIException(f"GitHub API error {response.status_code}: {response.text[:300]}")

    data = response.json()
    if data.get("truncated"):
        log.warning("Repo tree is truncated — repo may be very large")

    return data.get("tree", [])


def _fetch_file_content(file_path: str, branch: str) -> str:
    """Fetch content of a single file from GitHub."""
    client = get_github_client()
    url = build_github_url(f"contents/{file_path}?ref={branch}")
    response = client.get(url)

    if response.status_code == 404:
        raise GitHubFileNotFoundException(f"File '{file_path}' not found on branch '{branch}'")
    if response.status_code != 200:
        raise GitHubAPIException(f"GitHub API error {response.status_code}: {response.text[:300]}")

    data = response.json()
    if isinstance(data, list):
        raise GitHubFileNotFoundException(f"'{file_path}' is a directory, not a file")

    return _decode_content(data["content"])


def _format_files(files: list[dict]) -> str:
    """Format list of files into readable string for Claude."""
    if not files:
        return "No files found."
    result = []
    for f in files:
        result.append(f"{'='*60}\n📄 {f['name']}  ({f['path']})\n{'='*60}\n{f['content']}")
    return "\n\n".join(result)


def _detect_project_type(tree_paths: list[str]) -> str:
    """Detect project language/framework from file tree."""
    files = [p.lower() for p in tree_paths]
    if any("pom.xml" in f for f in files):
        return "Java / Maven (TestNG/JUnit)"
    if any("build.gradle" in f for f in files):
        return "Java / Gradle"
    if any("conftest.py" in f for f in files) or any("pytest.ini" in f for f in files):
        return "Python / Pytest"
    if any(f.endswith(".py") for f in files):
        return "Python"
    if any("package.json" in f for f in files):
        if any("playwright" in f for f in files):
            return "JavaScript / Playwright"
        if any("cypress" in f for f in files):
            return "JavaScript / Cypress"
        return "JavaScript / Node"
    if any(f.endswith(".cs") for f in files):
        return "C# / .NET"
    if any(f.endswith(".rb") for f in files):
        return "Ruby"
    return "Unknown"


def _build_tree_display(tree: list[dict], extension_filter: Optional[str] = None) -> tuple[str, int, int]:
    """
    Build a full recursive tree display string from flat tree list.
    Returns (display_string, folder_count, file_count).
    """
    # Collect all unique folder paths
    folders = set()
    files = []

    for item in tree:
        if item["type"] == "tree":
            folders.add(item["path"])
        elif item["type"] == "blob":
            if extension_filter is None or item["path"].endswith(extension_filter):
                files.append(item["path"])

    # Build indented tree display
    lines = []
    all_paths = sorted(list(folders) + files)

    # Group by depth for display
    processed = set()

    def add_folder_contents(prefix: str, depth: int):
        indent = "  " * depth
        # Files directly in this folder
        for f in sorted(files):
            parent = "/".join(f.split("/")[:-1])
            if parent == prefix and f not in processed:
                lines.append(f"{indent}  📄 {f.split('/')[-1]}")
                processed.add(f)
        # Subfolders directly in this folder
        for folder in sorted(folders):
            folder_parent = "/".join(folder.split("/")[:-1])
            if folder_parent == prefix and folder not in processed:
                lines.append(f"{indent}  📂 {folder.split('/')[-1]}/")
                processed.add(folder)
                add_folder_contents(folder, depth + 1)

    # Root level items
    for f in sorted(files):
        if "/" not in f and f not in processed:
            lines.append(f"  📄 {f}")
            processed.add(f)

    for folder in sorted(folders):
        if "/" not in folder and folder not in processed:
            lines.append(f"  📂 {folder}/")
            processed.add(folder)
            add_folder_contents(folder, 1)

    return "\n".join(lines), len(folders), len(files)


def _require_repo_config(branch: str = None) -> str | None:
    missing = []
    if not settings.gh_owner: missing.append("owner")
    if not settings.gh_repo:  missing.append("repo")
    if branch is not None and not branch: missing.append("branch")

    if not missing:
        return None

    lines = [f"⚠️ Missing: {', '.join(missing)}. Please provide:"]
    if "owner" in missing:
        lines.append("   • owner: GitHub username or org (e.g. Sabarna-dotcom)")
    if "repo" in missing:
        lines.append("   • repo: repository name (e.g. Python_Selenium_Web_Automation_PyTest)")
    if "branch" in missing:
        lines.append("   • branch: branch name (e.g. main, develop)")
    lines.append("\n💡 Call switch_repo(owner='...', repo='...', branch='...') to set these.")
    return "\n".join(lines)


# ── Tools ─────────────────────────────────────────────────────────────────

@handle_exceptions
def explore_repo(input: ExploreRepoInput) -> str:
    """
    Explore the FULL recursive structure of the GitHub repo in one call.
    Always call this first to understand the project before reading files.
    Works for any language: Java, Python, JS, C# etc.

    mode=structure_only → complete tree of ALL folders and files (fast).
    mode=with_content   → complete tree PLUS content of every file (slow).

    branch: branch to explore
    mode: structure_only | with_content
    extension_filter: only show/read files with this extension (e.g. .py, .java)
    """
    msg = _require_repo_config(input.branch)
    if msg: return msg

    log.info(f"Exploring repo | branch={input.branch} | mode={input.mode} | filter={input.extension_filter}")

    tree = _get_tree(input.branch)
    all_paths = [item["path"] for item in tree if item["type"] == "blob"]
    project_type = _detect_project_type(all_paths)

    tree_display, folder_count, file_count = _build_tree_display(tree, input.extension_filter)

    header = [
        f"📦 {settings.gh_owner}/{settings.gh_repo} | branch: {input.branch}",
        f"🔍 Project type: {project_type}",
        f"📊 {folder_count} folders | {file_count} files" + (f" (filtered: {input.extension_filter})" if input.extension_filter else ""),
        f"",
        f"📁 Full Repository Structure:",
        tree_display,
    ]

    if input.mode == "structure_only":
        header.append(f"\n💡 Call explore_repo(mode='with_content') to read all file contents.")
        header.append(f"   Call get_file(file_path=...) to read a specific file.")
        header.append(f"   Call read_codebase() to read files intelligently.")
        log.info(f"Structure explored: {folder_count} folders, {file_count} files")
        return "\n".join(header)

    # with_content mode — read every file
    file_items = [item for item in tree if item["type"] == "blob"]
    if input.extension_filter:
        file_items = [f for f in file_items if f["path"].endswith(input.extension_filter)]

    header.append(f"\n{'='*60}")
    header.append(f"📖 File Contents ({len(file_items)} files):")
    header.append(f"{'='*60}")

    files_content = []
    for item in file_items:
        try:
            content = _fetch_file_content(item["path"], input.branch)
            filename = item["path"].split("/")[-1]
            files_content.append(f"\n📄 {filename}  ({item['path']})\n{'-'*60}\n{content}")
            log.debug(f"Read: {item['path']}")
        except Exception as e:
            files_content.append(f"\n⚠️ Could not read {item['path']}: {str(e)}")

    log.info(f"Full explore with content: {len(file_items)} files read")
    return "\n".join(header) + "\n".join(files_content)


@handle_exceptions
def read_codebase(input: ReadCodebaseInput) -> str:
    """
    Read and understand the codebase from GitHub.

    mode=read_all      → reads every file in the repo (or filtered by extension/folder).
                         Best for small/medium repos when you need full context.

    mode=read_relevant → provide a query describing what you want to understand,
                         Claude finds and reads the most relevant files.
                         Best for large repos when you need targeted context.

    branch: branch to read
    mode: read_all | read_relevant
    query: describe what to understand (required for read_relevant)
    extension_filter: only read files with this extension (.py, .java, .ts etc.)
    folder_filter: only read files inside this folder
    """
    msg = _require_repo_config(input.branch)
    if msg: return msg

    log.info(f"Reading codebase | branch={input.branch} | mode={input.mode} | query='{input.query}'")

    tree = _get_tree(input.branch)
    all_paths = [item["path"] for item in tree if item["type"] == "blob"]
    project_type = _detect_project_type(all_paths)

    # Filter candidates
    candidates = [item for item in tree if item["type"] == "blob"]
    if input.extension_filter:
        candidates = [f for f in candidates if f["path"].endswith(input.extension_filter)]
    if input.folder_filter:
        candidates = [f for f in candidates if f["path"].startswith(input.folder_filter)]

    if input.mode == "read_all":
        log.info(f"Reading all {len(candidates)} files")
        files_read = []
        for item in candidates:
            try:
                content = _fetch_file_content(item["path"], input.branch)
                filename = item["path"].split("/")[-1]
                files_read.append({"name": filename, "path": item["path"], "content": content})
            except Exception as e:
                log.warning(f"Skipping {item['path']}: {e}")

        header = (
            f"📚 Codebase Read (read_all) | {settings.gh_owner}/{settings.gh_repo} | branch: {input.branch}\n"
            f"🔍 Project type: {project_type}\n"
            f"📊 {len(files_read)} files read\n"
            f"{'='*60}\n"
        )
        log.info(f"read_all complete: {len(files_read)} files")
        return header + _format_files(files_read)

    else:  # read_relevant
        if not input.query:
            return (
                "❌ query is required when mode=read_relevant.\n"
                "   Provide a description like: 'login flow', 'how tests are structured', 'base class setup'"
            )

        query_lower = input.query.lower()
        query_words = [w for w in query_lower.split() if len(w) > 2]

        # Score each file by relevance to query
        scored = []
        for item in candidates:
            path_lower = item["path"].lower()
            score = sum(2 for word in query_words if word in path_lower)
            if score > 0:
                scored.append((score, item))

        # Sort by score, take top 15
        scored.sort(key=lambda x: x[0], reverse=True)
        top_files = [item for _, item in scored[:15]]

        # If very few results, also grab common important files
        important_patterns = ['conftest', 'base', 'setup', 'config', 'fixture', '__init__', 'requirements', 'pom']
        for item in candidates:
            name_lower = item["path"].split("/")[-1].lower()
            if any(p in name_lower for p in important_patterns) and item not in top_files:
                top_files.append(item)
                if len(top_files) >= 20:
                    break

        log.info(f"read_relevant: found {len(top_files)} relevant files for query '{input.query}'")

        files_read = []
        for item in top_files:
            try:
                content = _fetch_file_content(item["path"], input.branch)
                filename = item["path"].split("/")[-1]
                files_read.append({"name": filename, "path": item["path"], "content": content})
            except Exception as e:
                log.warning(f"Skipping {item['path']}: {e}")

        header = (
            f"📚 Codebase Read (read_relevant) | {settings.gh_owner}/{settings.gh_repo} | branch: {input.branch}\n"
            f"🔍 Project type: {project_type}\n"
            f"🎯 Query: '{input.query}'\n"
            f"📊 {len(files_read)} relevant files found and read\n"
            f"{'='*60}\n"
        )
        return header + _format_files(files_read)


@handle_exceptions
def search_files(input: SearchFilesInput) -> str:
    """
    Search for files by name keyword across the entire repo tree.
    keyword: e.g. 'login', 'cart', 'base', 'conftest'
    extension: optional filter e.g. '.py', '.java'
    branch: branch to search in
    """
    msg = _require_repo_config(input.branch)
    if msg: return msg

    log.info(f"Searching files | keyword='{input.keyword}' | branch={input.branch} | ext={input.extension}")
    tree = _get_tree(input.branch)

    matches = []
    for item in tree:
        if item["type"] != "blob":
            continue
        name = item["path"].split("/")[-1].lower()
        if input.keyword.lower() in name:
            if input.extension is None or item["path"].endswith(input.extension):
                matches.append(item["path"])

    if not matches:
        return (
            f"No files found matching '{input.keyword}'"
            + (f" with extension '{input.extension}'" if input.extension else "")
            + f" on branch '{input.branch}'"
        )

    lines = [f"🔍 Search '{input.keyword}' on branch '{input.branch}' — {len(matches)} found:"]
    for path in sorted(matches):
        lines.append(f"   📄 {path}")
    lines.append(f"\n💡 Use get_file(file_path=...) to read any of these files.")

    log.info(f"Found {len(matches)} files matching '{input.keyword}'")
    return "\n".join(lines)


@handle_exceptions
def get_folder_files(input: GetFolderFilesInput) -> str:
    """
    Read all files from a specific folder in the repo.
    folder_path: exact folder path in repo
    branch: branch to read from
    extension: optional file extension filter (.py, .java etc.)
    """
    log.info(f"Reading folder | folder={input.folder_path} | branch={input.branch} | ext={input.extension}")
    client = get_github_client()
    url = build_github_url(f"contents/{input.folder_path}?ref={input.branch}")
    response = client.get(url)

    if response.status_code == 404:
        raise GitHubFileNotFoundException(f"Folder '{input.folder_path}' not found on branch '{input.branch}'")
    if response.status_code != 200:
        raise GitHubAPIException(f"GitHub API error {response.status_code}: {response.text[:300]}")

    items = response.json()
    if not isinstance(items, list):
        raise GitHubFileNotFoundException(f"'{input.folder_path}' is not a folder")

    file_items = [
        i for i in items
        if i["type"] == "file" and (input.extension is None or i["name"].endswith(input.extension))
    ]

    if not file_items:
        return (
            f"No files found in '{input.folder_path}' on branch '{input.branch}'"
            + (f" with extension '{input.extension}'" if input.extension else "")
        )

    files = []
    for item in file_items:
        try:
            content = _decode_content(client.get(item["url"]).json()["content"])
            files.append({"name": item["name"], "content": content, "path": item["path"]})
        except Exception as e:
            log.warning(f"Skipping {item['name']}: {e}")

    log.info(f"Read {len(files)} files from '{input.folder_path}'")
    return f"📂 {input.folder_path}  (branch: {input.branch})\n" + _format_files(files)


@handle_exceptions
def get_file(input: GetFileInput) -> str:
    """
    Read any specific file from the repo by its full path.
    file_path: full path e.g. tests/login/test_login.py
    branch: branch to read from
    """
    log.info(f"Reading file: {input.file_path} | branch={input.branch}")
    content = _fetch_file_content(input.file_path, input.branch)
    filename = input.file_path.split("/")[-1]
    log.info(f"Read: {filename} ({len(content)} chars)")
    return f"📄 {filename}  (branch: {input.branch})\nPath: {input.file_path}\n{'='*60}\n{content}"


@handle_exceptions
def search_code(input: SearchCodeInput) -> str:
    """
    Search for a keyword inside file contents across the repo.
    keyword: e.g. 'def test_login', '@BeforeMethod', 'BasePage'
    branch: branch to search in
    folder_path: limit to subfolder or empty for entire repo
    extension: optional file extension filter
    """
    log.info(f"Code search | keyword='{input.keyword}' | branch={input.branch}")
    tree = _get_tree(input.branch)

    candidates = [
        item["path"] for item in tree
        if item["type"] == "blob"
        and (not input.folder_path or item["path"].startswith(input.folder_path))
        and (not input.extension or item["path"].endswith(input.extension))
    ]

    log.info(f"Scanning {len(candidates)} files")
    matches = []

    for file_path in candidates:
        try:
            content = _fetch_file_content(file_path, input.branch)
            if input.keyword.lower() in content.lower():
                lines = content.splitlines()
                matching_lines = [
                    f"   Line {i+1}: {line.strip()}"
                    for i, line in enumerate(lines)
                    if input.keyword.lower() in line.lower()
                ][:3]
                matches.append({"path": file_path, "lines": matching_lines})
        except Exception as e:
            log.debug(f"Skipping {file_path}: {e}")

    if not matches:
        return f"No files found containing '{input.keyword}' on branch '{input.branch}'"

    lines = [f"🔍 Code search: '{input.keyword}' — found in {len(matches)} files:"]
    for match in matches:
        lines.append(f"\n   📄 {match['path']}")
        for line in match["lines"]:
            lines.append(line)

    log.info(f"Found '{input.keyword}' in {len(matches)} files")
    return "\n".join(lines)


@handle_exceptions
def switch_repo(input: SwitchRepoInput) -> str:
    """
    Switch to a different GitHub repo at runtime — no restart needed.
    All subsequent GitHub tools will use this new repo.
    owner: GitHub username or org (e.g. Sabarna-dotcom)
    repo: repository name (e.g. Python_Selenium_Web_Automation_PyTest)
    branch: default branch to use after switching (default: main)
    """
    old = f"{settings.gh_owner}/{settings.gh_repo}"
    settings.gh_owner = input.owner
    settings.gh_repo = input.repo
    settings.gh_default_branch = input.branch
    log.info(f"Switched repo: {old} → {input.owner}/{input.repo} | branch={input.branch}")
    return (
        f"✅ Switched repo: {old} → {input.owner}/{input.repo}\n"
        f"   Default branch: {input.branch}\n"
        f"   Call explore_repo() to explore the new repo."
    )


@handle_exceptions
def get_current_repo() -> str:
    """Show which GitHub repo and branch is currently active."""
    return (
        f"📦 Active repo: {settings.gh_owner}/{settings.gh_repo}\n"
        f"🌿 Default branch: {settings.gh_default_branch}"
    )
