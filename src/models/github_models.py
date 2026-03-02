"""
Pydantic models for GitHub reader tool inputs.
Repo-agnostic — works with any language or folder structure.
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field
from config.settings import settings


class ExploreRepoInput(BaseModel):
    branch: str = Field(
        default_factory=lambda: settings.gh_default_branch,
        description="Branch to explore (e.g. main, develop, feature/login)"
    )
    mode: Literal["structure_only", "with_content"] = Field(
        "structure_only",
        description=(
            "structure_only → full recursive tree of all folders and files (fast, for orientation). "
            "with_content → full tree PLUS the content of every file (slow, for full understanding)."
        )
    )
    extension_filter: Optional[str] = Field(
        None,
        description="Only include files with this extension when mode=with_content (e.g. .py, .java). Leave empty for all files."
    )


class ReadCodebaseInput(BaseModel):
    branch: str = Field(
        default_factory=lambda: settings.gh_default_branch,
        description="Branch to read from"
    )
    mode: Literal["read_all", "read_relevant"] = Field(
        "read_relevant",
        description=(
            "read_all → read every file in the repo (comprehensive but slow for large repos). "
            "read_relevant → provide a query and Claude finds the most relevant files to read."
        )
    )
    query: Optional[str] = Field(
        None,
        description="Required when mode=read_relevant. Describe what you want to understand (e.g. 'login flow', 'how tests are structured', 'base test class setup')."
    )
    extension_filter: Optional[str] = Field(
        None,
        description="Only read files with this extension (e.g. .py, .java). Leave empty for all."
    )
    folder_filter: Optional[str] = Field(
        None,
        description="Limit reading to a specific folder (e.g. 'tests/', 'src/test/java'). Leave empty for entire repo."
    )


class SearchFilesInput(BaseModel):
    keyword: str = Field(
        ..., description="Keyword to search for in file names (e.g. 'login', 'cart', 'base', 'conftest')"
    )
    branch: str = Field(
        default_factory=lambda: settings.gh_default_branch,
        description="Branch to search in"
    )
    extension: Optional[str] = Field(
        None, description="Filter by file extension e.g. .py, .java, .js. Leave empty for all files."
    )


class GetFolderFilesInput(BaseModel):
    folder_path: str = Field(
        ..., description="Folder path in the repo (e.g. tests/, src/test/java/tests)"
    )
    branch: str = Field(
        default_factory=lambda: settings.gh_default_branch,
        description="Branch to read from"
    )
    extension: Optional[str] = Field(
        None, description="Filter by extension e.g. .py, .java. Leave empty for all files."
    )


class GetFileInput(BaseModel):
    file_path: str = Field(
        ..., description="Full path to file in repo (e.g. tests/login/test_login.py)"
    )
    branch: str = Field(
        default_factory=lambda: settings.gh_default_branch,
        description="Branch to read from"
    )


class SearchCodeInput(BaseModel):
    keyword: str = Field(
        ..., description="Keyword to search for inside file contents (e.g. 'def test_login', '@BeforeMethod', 'BasePage')"
    )
    branch: str = Field(
        default_factory=lambda: settings.gh_default_branch,
        description="Branch to search in"
    )
    folder_path: str = Field(
        "", description="Limit search to a specific folder. Empty means entire repo."
    )
    extension: Optional[str] = Field(
        None, description="Filter by file extension e.g. .py, .java"
    )


class SwitchRepoInput(BaseModel):
    owner: str = Field(..., description="GitHub username or org (e.g. Sabarna-dotcom)")
    repo: str = Field(..., description="Repository name (e.g. Python_Selenium_Web_Automation_PyTest)")
    branch: str = Field("main", description="Default branch to use after switching")
