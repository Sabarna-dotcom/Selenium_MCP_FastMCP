"""
Pydantic models for local file writer tool inputs.
Generic — can write any file type to any path.
"""

from typing import Optional
from pydantic import BaseModel, Field
from config.settings import settings


class WriteFileInput(BaseModel):
    filename: str = Field(
        ...,
        description="Filename including extension (e.g. LoginTest.java, test_login.py, conftest.py, utils.js)"
    )
    content: str = Field(
        ...,
        description="Full file content to write"
    )
    absolute_path: Optional[str] = Field(
        None,
        description=(
            "Full absolute path to write the file (e.g. C:/projects/myapp/tests/login/LoginTest.java). "
            "Use this when you know the exact target location. "
            "If provided, folder_path and project_root are ignored."
        )
    )
    folder_path: Optional[str] = Field(
        None,
        description=(
            "Relative folder path inside project_root (e.g. src/test/java/tests/login, tests/checkout). "
            "File will be written to PROJECT_ROOT/folder_path/filename. "
            "Ignored if absolute_path is provided."
        )
    )
    active_file_path: Optional[str] = Field(
        None,
        description=(
            "Path of the currently active/open file in the IDE (passed by Copilot/VS Code). "
            "If provided and no absolute_path or folder_path given, writes to this file's directory."
        )
    )


class WriteFileToActiveInput(BaseModel):
    content: str = Field(
        ...,
        description="Full file content to write to the currently active file"
    )
    active_file_path: str = Field(
        ...,
        description="Full path of the currently open file in the IDE (passed by VS Code/Copilot context)"
    )
