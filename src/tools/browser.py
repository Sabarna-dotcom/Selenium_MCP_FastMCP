"""
Standard browser tools using explicit CSS/XPath selectors.
For natural language interaction, use smart_browser.py tools instead.
"""

import os
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

from src.core.browser_session import get_driver, close_driver, is_driver_alive
from src.core.logger import get_logger
from src.core.exceptions import (
    handle_exceptions,
    BrowserActionException,
    ElementNotFoundException,
)
from src.models.browser_models import (
    StartBrowserInput, NavigateInput, SelectorInput,
    TypeInput, SelectInput, ScreenshotInput,
    ScrollInput, WaitForInput, ExecuteScriptInput
)

from src.config.settings import settings

log = get_logger("tools.browser")

BY_MAP = {
    "css":   By.CSS_SELECTOR,
    "xpath": By.XPATH,
    "id":    By.ID,
    "name":  By.NAME,
    "tag":   By.TAG_NAME,
    "text":  By.LINK_TEXT
}


def _get_by(by: str) -> By:
    b = BY_MAP.get(by.lower())
    if not b:
        raise BrowserActionException(
            f"Unknown selector strategy: '{by}'. Use: {list(BY_MAP.keys())}"
        )
    return b


def _get_or_start_driver():
    """Auto-starts browser with defaults if no session is active."""
    if not is_driver_alive():
        log.info("No active browser session — auto-starting with defaults from .env")
    return get_driver()


def _wait_for_element(driver, selector: str, by: str, timeout: int, condition="clickable"):
    by_strategy = _get_by(by)
    wait = WebDriverWait(driver, timeout)
    try:
        if condition == "clickable":
            return wait.until(EC.element_to_be_clickable((by_strategy, selector)))
        elif condition == "visible":
            return wait.until(EC.visibility_of_element_located((by_strategy, selector)))
        return wait.until(EC.presence_of_element_located((by_strategy, selector)))
    except Exception:
        raise ElementNotFoundException(
            f"Element not found: [{by}] '{selector}' within {timeout}s"
        )

def _inject_auth_if_needed(url: str) -> str:
    """
    Detect environment from URL and inject basic auth credentials.
    Checks if 'qa', 'uat', or 'ppe' appears in the URL hostname.
    Returns URL unchanged if no match or credentials not configured.
    """
    from urllib.parse import urlparse, urlunparse

    parsed = urlparse(url)
    hostname = parsed.netloc.lower()

    # Detect env and get credentials
    if "qa" in hostname:
        user, pwd = settings.qa_user, settings.qa_pass
        env = "QA"
    elif "uat" in hostname:
        user, pwd = settings.uat_user, settings.uat_pass
        env = "UAT"
    elif "ppe" in hostname:
        user, pwd = settings.ppe_user, settings.ppe_pass
        env = "PPE"
    else:
        return url  # prod or unknown — no auth needed

    if not user or not pwd:
        log.warning(f"{env} detected in URL but credentials not set in .env")
        return url  # navigate without auth — let it fail naturally

    # Inject credentials into URL
    auth_netloc = f"{user}:{pwd}@{parsed.netloc}"
    auth_url = str(urlunparse(parsed._replace(netloc=auth_netloc)))
    log.info(f"{env} environment detected — auth injected")
    return auth_url

# ── Tools ─────────────────────────────────────────────────────────────────

@handle_exceptions
def browser_start(input: StartBrowserInput) -> str:
    """
    OPTIONAL — only call this when overriding defaults.
    Use when: browser_type != chrome, or headless=True needed.
    All other browser tools auto-start Chrome if no session exists.
    browser_type: chrome | firefox
    headless: run without visible UI
    """
    if is_driver_alive():
        driver = get_driver()
        return f"ℹ️ Browser already active: {driver.current_url}. Call browser_close() first to restart with new options."
    log.info(f"Starting browser: type={input.browser_type}, headless={input.headless}")
    get_driver(browser_type=input.browser_type, headless=input.headless)
    return f"✅ Browser started: {input.browser_type} | headless={input.headless}"


@handle_exceptions
def browser_navigate(input: NavigateInput) -> str:
    """
    Navigate to a URL. Auto-starts browser if not running.
    Always use full URL with https:// prefix.
    wait_until: load | domcontentloaded | none
    """
    driver = _get_or_start_driver()

    url = _inject_auth_if_needed(input.url)

    log.info(f"Navigating to: {input.url}")
    driver.get(url)
    log.info(f"Page loaded: {driver.title}")
    return f"✅ Navigated to: {input.url} | Title: {driver.title} | URL: {driver.current_url}"


@handle_exceptions
def browser_click(input: SelectorInput) -> str:
    """
    Click an element by selector. Auto-starts browser if not running.
    by: css | xpath | id | name | text | tag
    Tip: Use smart_click() if you don't know the exact selector.
    """
    driver = _get_or_start_driver()
    log.info(f"Clicking element: [{input.by}] {input.selector}")
    el = _wait_for_element(driver, input.selector, input.by, input.timeout, "clickable")
    el.click()
    return f"✅ Clicked: [{input.by}] {input.selector}"


@handle_exceptions
def browser_type(input: TypeInput) -> str:
    """
    Type text into an element. Auto-starts browser if not running.
    clear_first: clears existing text before typing.
    Tip: Use smart_type() if you don't know the exact selector.
    """
    driver = _get_or_start_driver()
    log.info(f"Typing into [{input.by}] {input.selector}: '{input.text}'")
    el = _wait_for_element(driver, input.selector, input.by, input.timeout, "present")
    if input.clear_first:
        el.clear()
    el.send_keys(input.text)
    return f"✅ Typed into [{input.by}] {input.selector}: '{input.text}'"


@handle_exceptions
def browser_hover(input: SelectorInput) -> str:
    """Hover over an element. Auto-starts browser if not running."""
    driver = _get_or_start_driver()
    log.info(f"Hovering over [{input.by}] {input.selector}")
    el = _wait_for_element(driver, input.selector, input.by, input.timeout, "present")
    ActionChains(driver).move_to_element(el).perform()
    return f"✅ Hovered: [{input.by}] {input.selector}"


@handle_exceptions
def browser_select_option(input: SelectInput) -> str:
    """Select a dropdown option by visible text. Auto-starts browser if not running."""
    driver = _get_or_start_driver()
    log.info(f"Selecting '{input.value}' from [{input.by}] {input.selector}")
    el = _wait_for_element(driver, input.selector, input.by, input.timeout, "present")
    Select(el).select_by_visible_text(input.value)
    return f"✅ Selected '{input.value}' from [{input.by}] {input.selector}"


@handle_exceptions
def browser_screenshot(input: ScreenshotInput) -> str:
    """
    Take a screenshot. Returns base64.
    Saves to screenshots/ folder if filename is provided.
    Auto-starts browser if not running.
    """
    driver = _get_or_start_driver()
    log.info(f"Taking screenshot | filename={input.filename}")
    screenshot_b64 = driver.get_screenshot_as_base64()
    if input.filename:
        os.makedirs("screenshots", exist_ok=True)
        path = os.path.join("screenshots", input.filename)
        driver.save_screenshot(path)
        log.info(f"Screenshot saved: {path}")
        return f"✅ Screenshot saved: {path}\nBase64: {screenshot_b64}"
    return f"✅ Screenshot taken\nBase64: {screenshot_b64}"


@handle_exceptions
def browser_snapshot() -> str:
    """
    Get raw HTML page source.
    Use smart_snapshot() instead for a clean accessibility tree Claude can read easily.
    Auto-starts browser if not running.
    """
    driver = _get_or_start_driver()
    log.info(f"Taking DOM snapshot of: {driver.current_url}")
    source = driver.page_source
    log.debug(f"Snapshot length: {len(source)} chars")
    return f"✅ Page snapshot\nURL: {driver.current_url}\nTitle: {driver.title}\n\n{source}"


@handle_exceptions
def browser_wait_for(input: WaitForInput) -> str:
    """
    Wait for an element using explicit selector.
    Use smart_wait() for natural language waiting.
    """
    driver = _get_or_start_driver()
    log.info(f"Waiting for [{input.by}] {input.selector} (timeout={input.timeout}s, condition={input.condition})")
    _wait_for_element(driver, input.selector, input.by, input.timeout, input.condition)
    return f"✅ Element found: [{input.by}] {input.selector}"


@handle_exceptions
def browser_scroll(input: ScrollInput) -> str:
    """Scroll the page. direction: up | down | top | bottom. Auto-starts browser if not running."""
    driver = _get_or_start_driver()
    log.info(f"Scrolling {input.direction} by {input.pixels}px")
    if input.direction == "top":
        driver.execute_script("window.scrollTo(0, 0);")
    elif input.direction == "bottom":
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    elif input.direction == "down":
        driver.execute_script(f"window.scrollBy(0, {input.pixels});")
    else:
        driver.execute_script(f"window.scrollBy(0, -{input.pixels});")
    return f"✅ Scrolled {input.direction}"


@handle_exceptions
def browser_back() -> str:
    """Navigate back in browser history."""
    driver = _get_or_start_driver()
    driver.back()
    return f"✅ Navigated back | Current URL: {driver.current_url}"


@handle_exceptions
def browser_forward() -> str:
    """Navigate forward in browser history."""
    driver = _get_or_start_driver()
    driver.forward()
    return f"✅ Navigated forward | Current URL: {driver.current_url}"


@handle_exceptions
def browser_refresh() -> str:
    """Refresh the current page."""
    driver = _get_or_start_driver()
    driver.refresh()
    return f"✅ Page refreshed | URL: {driver.current_url}"


@handle_exceptions
def browser_get_url() -> str:
    """Get the current page URL and title."""
    driver = _get_or_start_driver()
    return f"✅ URL: {driver.current_url} | Title: {driver.title}"


@handle_exceptions
def browser_execute_script(input: ExecuteScriptInput) -> str:
    """Execute JavaScript on the current page."""
    driver = _get_or_start_driver()
    log.info(f"Executing script: {input.script[:100]}")
    result = driver.execute_script(input.script)
    return f"✅ Script executed | Result: {result}"


@handle_exceptions
def browser_close() -> str:
    """Close the active browser session."""
    log.info("Closing browser session")
    close_driver()
    return "✅ Browser session closed"


@handle_exceptions
def browser_status() -> str:
    """Check if a browser session is currently active."""
    alive = is_driver_alive()
    if alive:
        driver = get_driver()
        return f"✅ Browser is active | URL: {driver.current_url}"
    return "ℹ️ No active browser session — will auto-start on next browser tool call."
