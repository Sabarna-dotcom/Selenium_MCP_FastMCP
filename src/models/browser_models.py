"""
Pydantic models for all browser tool inputs.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class StartBrowserInput(BaseModel):
    browser_type: Literal["chrome", "firefox"] = Field(
        "chrome", description="Browser to launch: chrome or firefox"
    )
    headless: bool = Field(
        False, description="Run browser in headless mode (no visible window)"
    )


class NavigateInput(BaseModel):
    url: str = Field(..., description="Full URL to navigate to (include https://)")
    wait_until: Literal["load", "domcontentloaded", "none"] = Field(
        "load", description="Page load strategy: load (full), domcontentloaded (DOM only), none (no wait)"
    )


class SelectorInput(BaseModel):
    """Shared model for tools that locate a single element: browser_click, browser_hover."""
    selector: str = Field(..., description="Element selector value")
    by: Literal["css", "xpath", "id", "name", "text", "tag"] = Field(
        "css", description="Selector strategy: css, xpath, id, name, text (link text), tag"
    )
    timeout: int = Field(10, description="Max seconds to wait for element", ge=1, le=60)


class TypeInput(BaseModel):
    selector: str = Field(..., description="Element selector value")
    text: str = Field(..., description="Text to type into the element")
    by: Literal["css", "xpath", "id", "name"] = Field("css", description="Selector strategy")
    clear_first: bool = Field(True, description="Clear existing text before typing")
    timeout: int = Field(10, description="Max seconds to wait for element", ge=1, le=60)


class SelectInput(BaseModel):
    selector: str = Field(..., description="CSS selector for the <select> element")
    value: str = Field(..., description="Visible text of the option to select")
    by: Literal["css", "xpath", "id"] = Field("css", description="Selector strategy")
    timeout: int = Field(10, description="Max seconds to wait for element", ge=1, le=60)


class ScreenshotInput(BaseModel):
    filename: Optional[str] = Field(
        None, description="Optional filename to save screenshot (e.g. login_page.png). Saved in screenshots/ folder."
    )


class WaitForInput(BaseModel):
    selector: str = Field(..., description="Element selector to wait for")
    by: Literal["css", "xpath", "id"] = Field("css", description="Selector strategy")
    timeout: int = Field(10, description="Max seconds to wait", ge=1, le=60)
    condition: Literal["present", "visible", "clickable"] = Field(
        "visible", description="Wait condition: present (in DOM), visible (displayed), clickable (enabled)"
    )


class ScrollInput(BaseModel):
    direction: Literal["up", "down", "top", "bottom"] = Field(
        "down", description="Scroll direction: up, down, top (page top), bottom (page bottom)"
    )
    pixels: int = Field(300, description="Pixels to scroll (used for up/down only)", ge=0)


class ExecuteScriptInput(BaseModel):
    script: str = Field(..., description="JavaScript code to execute in browser context")


# ── Smart Browser Models ──────────────────────────────────────────────────

class SmartClickInput(BaseModel):
    description: str = Field(
        ..., description="Natural language description of the element to click (e.g. 'Sign In button', 'username input', 'close modal link')"
    )


class SmartTypeInput(BaseModel):
    field_description: str = Field(
        ..., description="Natural language description of the input field (e.g. 'username field', 'password input', 'search box')"
    )
    text: str = Field(..., description="Text to type into the field")
    clear_first: bool = Field(True, description="Clear existing text before typing")


class SmartVerifyInput(BaseModel):
    description: str = Field(
        ..., description="Natural language description of what to verify (e.g. 'error message is visible', 'iphone X product is present', 'user is logged in')"
    )


class SmartWaitInput(BaseModel):
    description: str = Field(
        ..., description="Natural language description of what to wait for (e.g. 'loading spinner disappears', 'submit button is clickable')"
    )
    timeout: int = Field(10, description="Max seconds to wait", ge=1, le=60)
