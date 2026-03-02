from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # ── GitHub ──────────────────────────────────
    gh_token: str = Field(..., description="GitHub Personal Access Token")
    gh_owner: str = Field(..., description="GitHub org or username")
    gh_repo: str = Field(..., description="GitHub repository name")
    gh_default_branch: str = Field("main", description="Default branch to read from")

    # ── Local Project ────────────────────────────
    project_root: str = Field(".", description="Absolute path to your local project root")

    # ── Selenium ─────────────────────────────────
    default_browser: str = Field("chrome", description="chrome or firefox")
    default_headless: bool = Field(False, description="Run browser headless by default")
    default_timeout: int = Field(30, description="Default WebDriverWait timeout in seconds")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Allow runtime mutation (needed for switch_repo)
        frozen = False


# Single shared instance used across all tools
settings = Settings()
