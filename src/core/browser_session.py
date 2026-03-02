from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager

from src.config.settings import settings
from src.core.logger import get_logger

log = get_logger("core.browser_session")

_driver = None


def get_driver(browser_type: str = None, headless: bool = None) -> webdriver.Remote:
    """
    Returns the existing WebDriver session or creates a new one.
    Auto-starts with defaults from .env if no session exists.
    """
    global _driver

    if _driver is not None:
        try:
            _ = _driver.current_url
            log.debug("Reusing existing browser session")
            return _driver
        except Exception:
            log.warning("Existing browser session is dead — creating a new one")
            _driver = None

    browser = (browser_type or settings.default_browser).lower()
    use_headless = headless if headless is not None else settings.default_headless

    log.info(f"Creating new browser session: {browser} | headless={use_headless}")

    if browser == "chrome":
        options = webdriver.ChromeOptions()
        if use_headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        _driver = webdriver.Chrome(
            service=ChromeService(ChromeDriverManager().install()),
            options=options
        )

    elif browser == "firefox":
        options = webdriver.FirefoxOptions()
        if use_headless:
            options.add_argument("--headless")
        _driver = webdriver.Firefox(
            service=FirefoxService(GeckoDriverManager().install()),
            options=options
        )

    else:
        raise ValueError(f"Unsupported browser: '{browser}'. Use 'chrome' or 'firefox'.")

    _driver.implicitly_wait(settings.default_timeout)
    log.info(f"Browser session created successfully: {browser}")
    return _driver


def close_driver() -> None:
    """Quit the browser and reset the session."""
    global _driver
    if _driver is not None:
        log.info("Closing browser session")
        try:
            _driver.quit()
            log.info("Browser session closed")
        except Exception as e:
            log.warning(f"Error while closing browser: {e}")
        _driver = None
    else:
        log.debug("close_driver called but no active session")


def is_driver_alive() -> bool:
    """Check whether a browser session is currently active."""
    global _driver
    if _driver is None:
        return False
    try:
        _ = _driver.current_url
        return True
    except Exception:
        log.debug("Driver session found dead during health check")
        _driver = None
        return False
