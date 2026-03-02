"""
Smart browser tools using accessibility tree + natural language.
Claude can describe elements in plain English — no CSS/XPath needed.
These tools mirror how Playwright MCP works, implemented via JS injection in Selenium.
"""

import json
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from src.core.browser_session import get_driver, is_driver_alive
from src.core.logger import get_logger
from src.core.exceptions import handle_exceptions, ElementNotFoundException, BrowserActionException
from src.models.browser_models import (
    SmartClickInput, SmartTypeInput, SmartVerifyInput, SmartWaitInput
)

log = get_logger("tools.smart_browser")

# ── JS: Extract Accessibility Tree from the page ──────────────────────────

_ACCESSIBILITY_TREE_JS = """
(function() {
    var index = 0;
    var elements = [];

    function getRole(el) {
        var tag = el.tagName.toLowerCase();
        var type = (el.getAttribute('type') || '').toLowerCase();
        var role = el.getAttribute('role') || '';

        if (role) return role;
        if (tag === 'button') return 'button';
        if (tag === 'a') return 'link';
        if (tag === 'input') {
            if (type === 'checkbox') return 'checkbox';
            if (type === 'radio') return 'radio';
            if (type === 'submit' || type === 'button') return 'button';
            return 'input';
        }
        if (tag === 'select') return 'select';
        if (tag === 'textarea') return 'textarea';
        if (tag === 'img') return 'image';
        if (tag === 'h1' || tag === 'h2' || tag === 'h3') return 'heading';
        if (tag === 'li') return 'listitem';
        if (tag === 'table') return 'table';
        return tag;
    }

    function getName(el) {
        return (
            el.getAttribute('aria-label') ||
            el.getAttribute('placeholder') ||
            el.getAttribute('title') ||
            el.getAttribute('name') ||
            el.getAttribute('alt') ||
            (el.innerText || '').trim().substring(0, 80) ||
            el.getAttribute('value') ||
            el.getAttribute('id') ||
            ''
        );
    }

    function getState(el) {
        var states = [];
        if (el.disabled) states.push('disabled');
        if (el.checked) states.push('checked');
        if (el.getAttribute('aria-checked') === 'true') states.push('checked');
        if (el.getAttribute('aria-expanded') === 'true') states.push('expanded');
        if (el.getAttribute('aria-selected') === 'true') states.push('selected');
        if (el.getAttribute('aria-hidden') === 'true') states.push('hidden');

        var rect = el.getBoundingClientRect();
        var visible = rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).visibility !== 'hidden';
        if (!visible) states.push('hidden');
        else states.push('visible');

        return states.join(',');
    }

    function isInteractive(el) {
        var tag = el.tagName.toLowerCase();
        var role = (el.getAttribute('role') || '').toLowerCase();
        var interactiveTags = ['a', 'button', 'input', 'select', 'textarea', 'option'];
        var interactiveRoles = ['button', 'link', 'checkbox', 'radio', 'menuitem', 'tab', 'option', 'combobox', 'textbox'];
        var hasClick = el.onclick !== null || el.getAttribute('onclick') !== null;
        return interactiveTags.includes(tag) || interactiveRoles.includes(role) || hasClick;
    }

    function walk(el, depth) {
        if (!el || el.nodeType !== 1) return;
        if (['script', 'style', 'noscript', 'meta', 'head'].includes(el.tagName.toLowerCase())) return;

        var role = getRole(el);
        var name = getName(el);
        var state = getState(el);
        var interactive = isInteractive(el);

        if (interactive && name && !state.includes('hidden')) {
            index++;
            var indent = '  '.repeat(depth);
            var stateStr = state ? ' [' + state + ']' : '';
            elements.push('[' + index + '] ' + indent + role.padEnd(12) + ' "' + name + '"' + stateStr);

            // Store mapping for finding elements later
            el.setAttribute('data-mcp-index', index);
        }

        for (var i = 0; i < el.children.length; i++) {
            walk(el.children[i], depth + (interactive ? 1 : 0));
        }
    }

    walk(document.body, 0);
    return elements.join('\\n');
})();
"""

# ── JS: Find element by MCP index ─────────────────────────────────────────

_FIND_BY_INDEX_JS = """
(function(idx) {
    var el = document.querySelector('[data-mcp-index="' + idx + '"]');
    return el ? true : false;
})(arguments[0]);
"""

_CLICK_BY_INDEX_JS = """
(function(idx) {
    var el = document.querySelector('[data-mcp-index="' + idx + '"]');
    if (el) { el.click(); return true; }
    return false;
})(arguments[0]);
"""

_TYPE_BY_INDEX_JS = """
(function(idx, text, clearFirst) {
    var el = document.querySelector('[data-mcp-index="' + idx + '"]');
    if (el) {
        el.focus();
        if (clearFirst) { el.value = ''; }
        el.value = text;
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        return true;
    }
    return false;
})(arguments[0], arguments[1], arguments[2]);
"""


# ── Internal helpers ──────────────────────────────────────────────────────

def _get_driver_or_fail():
    if not is_driver_alive():
        log.info("No active browser session — auto-starting with defaults")
    return get_driver()   # get_driver already imported at top of file

def _build_accessibility_tree(driver) -> str:
    """Run JS on the page and return the accessibility tree string."""
    log.debug("Building accessibility tree via JS injection")
    tree = driver.execute_script(_ACCESSIBILITY_TREE_JS)
    log.debug(f"Accessibility tree has {len(tree.splitlines())} interactive elements")
    return tree


def _find_best_match_index(tree: str, description: str) -> int:
    """
    Find the best matching element index from the accessibility tree
    based on a natural language description.
    Returns the element index number, or -1 if not found.
    """
    description_lower = description.lower()
    lines = tree.strip().splitlines()

    # Score each line
    best_score = 0
    best_index = -1

    for line in lines:
        if not line.strip():
            continue

        # Extract index from [N]
        try:
            idx = int(line.split(']')[0].replace('[', '').strip())
        except (ValueError, IndexError):
            continue

        line_lower = line.lower()
        score = 0

        # Exact description words match
        for word in description_lower.split():
            if word in line_lower:
                score += 2

        # Role match bonus
        role_keywords = {
            'button': ['button', 'submit', 'click', 'press', 'sign', 'login', 'logout'],
            'input': ['input', 'field', 'enter', 'type', 'fill'],
            'link': ['link', 'navigate', 'go to', 'href'],
            'checkbox': ['checkbox', 'check', 'tick', 'select'],
            'select': ['dropdown', 'select', 'choose', 'option'],
        }
        for role, keywords in role_keywords.items():
            if role in line_lower:
                for kw in keywords:
                    if kw in description_lower:
                        score += 3

        if score > best_score:
            best_score = score
            best_index = idx

    return best_index if best_score > 0 else -1


# ── Tools ─────────────────────────────────────────────────────────────────

@handle_exceptions
def smart_snapshot() -> str:
    """
    Get a clean accessibility tree of the current page.
    Use this INSTEAD of browser_snapshot() — it returns structured,
    readable element info instead of raw HTML.

    Returns numbered interactive elements Claude can reference:
    [1] button    "Sign In"           [visible]
    [2] input     "Username"          [visible]
    [3] checkbox  "Remember me"       [visible,unchecked]

    Claude can then use smart_click("Sign In button") or
    smart_type("username field", "myuser") referencing these elements.
    """
    driver = _get_driver_or_fail()
    log.info(f"Building smart accessibility snapshot of: {driver.current_url}")
    tree = _build_accessibility_tree(driver)
    element_count = len([l for l in tree.splitlines() if l.strip()])

    return (
        f"✅ Accessibility Tree | URL: {driver.current_url} | Title: {driver.title}\n"
        f"   {element_count} interactive elements found\n\n"
        f"{'='*60}\n"
        f"{tree}\n"
        f"{'='*60}\n\n"
        f"💡 Use smart_click('description'), smart_type('field', 'text'), smart_verify('description') to interact."
    )


@handle_exceptions
def smart_click(input: SmartClickInput) -> str:
    """
    Click an element described in plain English.
    No CSS/XPath needed — just describe what you want to click.
    Examples:
      smart_click("Sign In button")
      smart_click("close modal")
      smart_click("add to cart")
      smart_click("Accept cookies")
    Automatically takes a snapshot first to find the right element.
    """
    driver = _get_driver_or_fail()
    log.info(f"Smart click: '{input.description}'")

    # Build accessibility tree
    tree = _build_accessibility_tree(driver)
    idx = _find_best_match_index(tree, input.description)

    if idx == -1:
        # Fallback: try XPath text search
        log.info(f"No match in tree, trying XPath text fallback for: '{input.description}'")
        try:
            words = input.description.lower().split()
            for word in words:
                if len(word) > 3:
                    elements = driver.find_elements(
                        By.XPATH,
                        f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{word}') and not(self::script) and not(self::style)]"
                    )
                    clickable = [e for e in elements if e.is_displayed() and e.is_enabled()]
                    if clickable:
                        clickable[0].click()
                        return f"✅ Smart clicked (text match): '{input.description}' via word '{word}'"
        except Exception as e:
            log.warning(f"XPath fallback failed: {e}")

        return (
            f"❌ Could not find element matching: '{input.description}'\n"
            f"   Try calling smart_snapshot() first to see available elements.\n"
            f"   Or use browser_click() with an explicit selector."
        )

    # Click by MCP index
    result = driver.execute_script(_CLICK_BY_INDEX_JS, idx)
    if result:
        log.info(f"Smart clicked element [{idx}] matching '{input.description}'")
        return f"✅ Smart clicked: '{input.description}' → element [{idx}]"

    return f"❌ Found element [{idx}] but click failed. Try browser_click() with explicit selector."


@handle_exceptions
def smart_type(input: SmartTypeInput) -> str:
    """
    Type text into a field described in plain English.
    No CSS/XPath needed — just describe the field.
    Examples:
      smart_type("username field", "myuser@email.com")
      smart_type("password input", "mypassword")
      smart_type("search box", "iphone")
      smart_type("first name", "John")
    Automatically takes a snapshot first to find the right field.
    """
    driver = _get_driver_or_fail()
    log.info(f"Smart type: '{input.field_description}' = '{input.text}'")

    tree = _build_accessibility_tree(driver)
    idx = _find_best_match_index(tree, input.field_description)

    if idx == -1:
        # Fallback: try finding by placeholder or label
        log.info(f"No match in tree, trying attribute fallback for: '{input.field_description}'")
        try:
            words = input.field_description.lower().split()
            for word in words:
                if len(word) > 2:
                    for attr in ['placeholder', 'name', 'id', 'aria-label']:
                        elements = driver.find_elements(
                            By.XPATH,
                            f"//input[contains(translate(@{attr}, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{word}')]"
                        )
                        visible = [e for e in elements if e.is_displayed()]
                        if visible:
                            if input.clear_first:
                                visible[0].clear()
                            visible[0].send_keys(input.text)
                            return f"✅ Smart typed in '{input.field_description}' via {attr}='{word}': '{input.text}'"
        except Exception as e:
            log.warning(f"Attribute fallback failed: {e}")

        return (
            f"❌ Could not find field matching: '{input.field_description}'\n"
            f"   Try calling smart_snapshot() to see available input fields.\n"
            f"   Or use browser_type() with an explicit selector."
        )

    result = driver.execute_script(_TYPE_BY_INDEX_JS, idx, input.text, input.clear_first)
    if result:
        log.info(f"Smart typed in element [{idx}] matching '{input.field_description}'")
        return f"✅ Smart typed in '{input.field_description}' → element [{idx}]: '{input.text}'"

    return f"❌ Found field [{idx}] but type failed. Try browser_type() with explicit selector."


@handle_exceptions
def smart_verify(input: SmartVerifyInput) -> str:
    """
    Verify something is present or visible on the page using plain English.
    Examples:
      smart_verify("error message is visible")
      smart_verify("iphone X product is present on the page")
      smart_verify("user is logged in")
      smart_verify("success notification appears")
    Returns PASS or FAIL with explanation.
    """
    driver = _get_driver_or_fail()
    log.info(f"Smart verify: '{input.description}'")

    page_text = driver.execute_script("return document.body.innerText;").lower()
    page_source = driver.page_source.lower()
    description_lower = input.description.lower()

    # Extract meaningful keywords (ignore common words)
    stop_words = {'is', 'are', 'the', 'a', 'an', 'on', 'in', 'at', 'to', 'of', 'and', 'or', 'that', 'this', 'page', 'present', 'visible', 'shown', 'displayed'}
    keywords = [w for w in description_lower.split() if w not in stop_words and len(w) > 2]

    matches = [kw for kw in keywords if kw in page_text or kw in page_source]
    score = len(matches) / len(keywords) if keywords else 0

    tree = _build_accessibility_tree(driver)

    if score >= 0.6:
        matched_str = ', '.join(f'"{m}"' for m in matches)
        log.info(f"Smart verify PASS: '{input.description}' — matched {matched_str}")
        return (
            f"✅ VERIFIED: '{input.description}'\n"
            f"   Matched keywords: {matched_str}\n"
            f"   URL: {driver.current_url}"
        )
    else:
        missing = [kw for kw in keywords if kw not in matches]
        missing_str = ', '.join(f'"{m}"' for m in missing)
        log.warning(f"Smart verify FAIL: '{input.description}' — missing {missing_str}")
        return (
            f"❌ NOT VERIFIED: '{input.description}'\n"
            f"   Missing keywords: {missing_str}\n"
            f"   URL: {driver.current_url}\n"
            f"   Tip: Call smart_snapshot() to see what's currently on the page."
        )


@handle_exceptions
def smart_wait(input: SmartWaitInput) -> str:
    """
    Wait for something described in plain English.
    Examples:
      smart_wait("loading spinner disappears", timeout=10)
      smart_wait("submit button is clickable", timeout=5)
      smart_wait("error message appears", timeout=8)
      smart_wait("page navigates to dashboard", timeout=15)
    """
    driver = _get_driver_or_fail()
    log.info(f"Smart wait: '{input.description}' (timeout={input.timeout}s)")

    description_lower = input.description.lower()

    # Detect wait type from description
    is_disappear = any(w in description_lower for w in ['disappear', 'gone', 'hidden', 'removed', 'closes', 'vanish'])
    is_navigate = any(w in description_lower for w in ['navigate', 'redirect', 'page', 'url', 'goes to'])
    is_clickable = any(w in description_lower for w in ['clickable', 'enabled', 'active'])

    try:
        if is_navigate:
            # Wait for URL change or page title change
            initial_url = driver.current_url
            WebDriverWait(driver, input.timeout).until(
                lambda d: d.current_url != initial_url or d.execute_script("return document.readyState") == "complete"
            )
            return f"✅ Smart wait complete: '{input.description}' | New URL: {driver.current_url}"

        # For other waits, rebuild snapshot after timeout
        import time
        time.sleep(min(2, input.timeout))  # small initial wait

        tree = _build_accessibility_tree(driver)
        idx = _find_best_match_index(tree, input.description)

        if idx != -1 and not is_disappear:
            return f"✅ Smart wait complete: element matching '{input.description}' is present → [{idx}]"
        elif is_disappear:
            # Check the element is no longer in tree
            if idx == -1:
                return f"✅ Smart wait complete: '{input.description}' — element no longer visible"
            return f"⚠️ Element still present after wait. Try increasing timeout."

        return (
            f"⚠️ Smart wait: condition may not be fully met for '{input.description}'\n"
            f"   Call smart_snapshot() to check current page state."
        )

    except Exception as e:
        return (
            f"⏱️ Smart wait timeout after {input.timeout}s: '{input.description}'\n"
            f"   Detail: {str(e)}\n"
            f"   Call smart_snapshot() to check current page state."
        )
