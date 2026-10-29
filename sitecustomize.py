"""
Auto-imported by CPython at startup (PYTHONPATH=/app). Injects the Chromium
flags a root container needs and guarantees DISPLAY exists.
"""
import os

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
    "--disable-blink-features=AutomationControlled",
    "--password-store=basic",
    "--use-mock-keychain",
]

if os.environ.get("CHROME_HEADLESS", "0") == "1":
    CHROME_FLAGS.append("--headless=new")

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
