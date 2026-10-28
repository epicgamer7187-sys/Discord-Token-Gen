"""
Auto-imported by CPython at startup (PYTHONPATH=/app makes /app importable
during site initialisation). Injects everything Chromium needs to run as root
inside a container, and guarantees DISPLAY exists before pyautogui/mouseinfo
try to read it.
"""
import os

# pyautogui -> mouseinfo does os.environ['DISPLAY'] at import time.
os.environ.setdefault("DISPLAY", ":99")

CHROME_FLAGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-software-rasterizer",
    "--window-size=1920,1080",
    "--window-position=0,0",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-features=Translate,BackForwardCache,MediaRouter,OptimizationHints",
    "--password-store=basic",
    "--use-mock-keychain",
]

# Set CHROME_HEADLESS=1 if main.py drives Chrome via pyautogui anyway.
# WARNING: with --headless=new there is no X window, so pyautogui clicks/keys
# land on the root window and do nothing. Default is headed.
if os.environ.get("CHROME_HEADLESS", "0") == "1":
    CHROME_FLAGS.append("--headless=new")

# CHROME_EXTRA_FLAGS="--foo,--bar" for one-off additions
for _extra in os.environ.get("CHROME_EXTRA_FLAGS", "").split(","):
    _extra = _extra.strip()
    if _extra:
        CHROME_FLAGS.append(_extra)


def _apply(options):
    try:
        existing = set(options.arguments)
        for flag in CHROME_FLAGS:
            if flag not in existing:
                options.arguments.append(flag)
    except Exception as exc:
        print(f"[sitecustomize] could not apply flags: {exc}")


# ---- 1. every ChromeOptions instance gets the flags ---------------------
try:
    from selenium.webdriver.chrome.options import Options as _ChromeOptions

    _orig_options_init = _ChromeOptions.__init__

    def _patched_options_init(self, *args, **kwargs):
        _orig_options_init(self, *args, **kwargs)
        _apply(self)

    _ChromeOptions.__init__ = _patched_options_init
    print("[sitecustomize] ChromeOptions patched")
except Exception as exc:
    print(f"[sitecustomize] ChromeOptions patch skipped: {exc}")


# ---- 2. webdriver.Chrome() called with no options at all ----------------
try:
    from selenium import webdriver as _wd

    _orig_chrome_init = _wd.Chrome.__init__

    def _patched_chrome_init(self, *args, **kwargs):
        if kwargs.get("options") is None and kwargs.get("chrome_options") is None and len(args) < 1:
            opts = _wd.ChromeOptions()
            _apply(opts)
            kwargs["options"] = opts
        return _orig_chrome_init(self, *args, **kwargs)

    _wd.Chrome.__init__ = _patched_chrome_init
    print("[sitecustomize] webdriver.Chrome patched")
except Exception as exc:
    print(f"[sitecustomize] webdriver.Chrome patch skipped: {exc}")


# ---- 3. seleniumwire, if the repo uses it -------------------------------
try:
    from seleniumwire import webdriver as _swd

    _orig_sw_init = _swd.Chrome.__init__

    def _patched_sw_init(self, *args, **kwargs):
        if kwargs.get("options") is None and kwargs.get("chrome_options") is None and len(args) < 1:
            opts = _swd.ChromeOptions()
            _apply(opts)
            kwargs["options"] = opts
        return _orig_sw_init(self, *args, **kwargs)

    _swd.Chrome.__init__ = _patched_sw_init
    print("[sitecustomize] seleniumwire.Chrome patched")
except Exception:
    pass


# ---- 4. undetected-chromedriver, if the repo uses it --------------------
try:
    import undetected_chromedriver as _uc

    _orig_uc_init = _uc.Chrome.__init__

    def _patched_uc_init(self, *args, **kwargs):
        if kwargs.get("options") is None and len(args) < 1:
            opts = _uc.ChromeOptions()
            _apply(opts)
            kwargs["options"] = opts
        kwargs.setdefault("use_subprocess", True)
        return _orig_uc_init(self, *args, **kwargs)

    _uc.Chrome.__init__ = _patched_uc_init
    print("[sitecustomize] undetected_chromedriver patched")
except Exception:
    pass


print("[sitecustomize] container patches applied")
