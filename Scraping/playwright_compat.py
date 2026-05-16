"""Small browser compatibility layer backed by Playwright.

This module keeps the scraper's existing synchronous control flow while running
all browser automation through Playwright.
"""

import time
import uuid

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


class TimeoutException(Exception):
    """Raised when a browser wait exceeds its timeout."""


class NoSuchElementException(Exception):
    """Raised when a requested element cannot be found."""


class NoAlertPresentException(Exception):
    """Raised when code asks for an alert but no dialog was captured."""


class By:
    ID = "id"
    XPATH = "xpath"
    CSS_SELECTOR = "css selector"


class _ExpectedConditions:
    @staticmethod
    def presence_of_element_located(locator):
        def _predicate(driver):
            return driver.find_element(*locator)

        return _predicate

    @staticmethod
    def element_to_be_clickable(locator):
        def _predicate(driver):
            element = driver.find_element(*locator)
            if element.is_enabled() and element.is_visible():
                return element
            return False

        return _predicate


EC = _ExpectedConditions()


class WebDriverWait:
    def __init__(self, driver, timeout, poll_frequency=0.25):
        self.driver = driver
        self.timeout = timeout
        self.poll_frequency = poll_frequency

    def until(self, method):
        deadline = time.monotonic() + self.timeout
        last_error = None
        while time.monotonic() <= deadline:
            try:
                value = method(self.driver)
                if value:
                    return value
            except Exception as exc:
                last_error = exc
            time.sleep(self.poll_frequency)

        if last_error:
            raise TimeoutException(str(last_error))
        raise TimeoutException(f"Timed out after {self.timeout} seconds")


class Alert:
    def __init__(self, driver):
        self.driver = driver
        self.text = driver.consume_alert_text(peek=True)
        if self.text is None:
            raise NoAlertPresentException("No alert present")

    def accept(self):
        self.driver.consume_alert_text(peek=False)


class Select:
    def __init__(self, element):
        self.element = element

    @property
    def options(self):
        return self.element.find_elements("css selector", "option")

    def select_by_value(self, value):
        self.element.select_option(str(value))


class PlaywrightElement:
    def __init__(self, locator):
        self.locator = locator.first

    def click(self, force=False):
        self.locator.click(timeout=20_000, force=force)

    def get_attribute(self, name):
        if name == "innerText":
            return self.locator.inner_text(timeout=20_000)
        return self.locator.get_attribute(name, timeout=20_000)

    def is_enabled(self):
        return self.locator.is_enabled(timeout=20_000)

    def is_visible(self):
        return self.locator.is_visible(timeout=20_000)

    def select_option(self, value):
        self.locator.select_option(value=value, timeout=20_000)

    def find_elements(self, by, value):
        locator = self.locator.locator(_selector(by, value))
        return [PlaywrightElement(locator.nth(index)) for index in range(locator.count())]


class _SwitchTo:
    def __init__(self, driver):
        self.driver = driver

    @property
    def alert(self):
        return Alert(self.driver)

    def window(self, handle):
        self.driver.switch_to_window(handle)


class PlaywrightDriver:
    def __init__(self, headless=True, browser_args=None):
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=headless,
            args=browser_args or [],
        )
        self._context = self._browser.new_context(ignore_https_errors=True)
        self._context.set_default_timeout(20_000)
        self._context.set_default_navigation_timeout(60_000)
        self._page_handles = {}
        self._page = self._context.new_page()
        self._handle_for_page(self._page)
        self._alert_texts = []
        self._page_load_timeout = 60_000
        self.switch_to = _SwitchTo(self)
        self._register_dialog_handler(self._page)
        self._context.on("page", self._register_dialog_handler)

    def _handle_for_page(self, page):
        if page not in self._page_handles:
            self._page_handles[page] = uuid.uuid4().hex
        return self._page_handles[page]

    def _register_dialog_handler(self, page):
        self._handle_for_page(page)
        page.on("dialog", self._handle_dialog)

    def _handle_dialog(self, dialog):
        self._alert_texts.append(dialog.message)
        dialog.accept()

    def consume_alert_text(self, peek=False):
        if not self._alert_texts:
            return None
        if peek:
            return self._alert_texts[0]
        return self._alert_texts.pop(0)

    def set_page_load_timeout(self, seconds):
        self._page_load_timeout = int(seconds * 1000)
        self._context.set_default_navigation_timeout(self._page_load_timeout)

    def implicitly_wait(self, seconds):
        self._context.set_default_timeout(int(seconds * 1000))

    def get(self, url):
        self._page.goto(url, wait_until="domcontentloaded", timeout=self._page_load_timeout)

    def refresh(self):
        self._page.reload(wait_until="domcontentloaded", timeout=self._page_load_timeout)

    @property
    def page_source(self):
        return self._page.content()

    @property
    def current_url(self):
        return self._page.url

    @property
    def current_window_handle(self):
        return self._handle_for_page(self._page)

    @property
    def window_handles(self):
        return [self._handle_for_page(page) for page in self._context.pages if not page.is_closed()]

    def switch_to_window(self, handle):
        for page in self._context.pages:
            if not page.is_closed() and self._handle_for_page(page) == handle:
                self._page = page
                self._page.bring_to_front()
                self._wait_for_page_url(page)
                return
        raise NoSuchElementException(f"Browser page handle not found: {handle}")

    def _wait_for_page_url(self, page, timeout_ms=10_000):
        try:
            page.wait_for_function("location.href !== 'about:blank'", timeout=timeout_ms)
        except PlaywrightTimeoutError:
            pass

    def close(self):
        page = self._page
        page.close()
        remaining_pages = [open_page for open_page in self._context.pages if not open_page.is_closed()]
        self._page_handles.pop(page, None)
        if remaining_pages:
            self._page = remaining_pages[0]

    def quit(self):
        self._context.close()
        self._browser.close()
        self._playwright.stop()

    def execute_script(self, script):
        return self._page.evaluate(script)

    def find_element(self, by, value=None):
        locator = self._page.locator(_selector(by, value))
        try:
            locator.first.wait_for(state="attached", timeout=20_000)
        except PlaywrightTimeoutError as exc:
            raise NoSuchElementException(str(exc)) from exc
        return PlaywrightElement(locator)

    def find_elements(self, by, value=None):
        locator = self._page.locator(_selector(by, value))
        return [PlaywrightElement(locator.nth(index)) for index in range(locator.count())]


def _selector(by, value=None):
    if value is None:
        value = by
        by = By.CSS_SELECTOR

    if by == By.ID:
        return f"#{value}"
    if by == By.XPATH or by == "xpath":
        return f"xpath={value}"
    if by == By.CSS_SELECTOR:
        return value
    return value
