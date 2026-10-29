import os
import re
import sys
import json
import time
import random
import string
import shutil
import tempfile
import subprocess
import traceback
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit

import requests
import tls_client
import undetected_chromedriver as uc
from colorama import Fore, Style, init
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait, Select as SeleniumSelect
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

from captcha_solver import solve_hcaptcha, configured as configured_solvers, DISCORD_SITEKEY, SolverError

init(autoreset=True)

REGISTER_MODE = os.environ.get("REGISTER_MODE", "browser").strip().lower()
GLOBAL_NAME = os.environ.get("GLOBAL_NAME", "Lunarxterm")
FIXED_PASSWORD = os.environ.get("ACCOUNT_PASSWORD", "").strip()
DOB = os.environ.get("DATE_OF_BIRTH", "2000-09-20").strip()
TOKENS_FILE = os.environ.get("TOKENS_FILE", "tokens.txt")
EVS_FILE = os.environ.get("EVS_FILE", "evs.txt")
PROXY_FILE = os.environ.get("PROXY_FILE", "proxies.txt")
SOLVE_ATTEMPTS = int(os.environ.get("SOLVE_ATTEMPTS", "3"))
LOGIN_WAIT = int(os.environ.get("LOGIN_WAIT", "90"))

banner = f'''
██████╗ ██╗██╗   ██╗███████╗██████╗ 
██╔══██╗██║██║   ██║██╔════╝██╔══██╗
██████╔╝██║██║   ██║█████╗  ██████╔╝
██╔══██╗██║╚██╗ ██╔╝██╔══╝  ██╔══██╗
██║  ██║██║ ╚████╔╝ ███████╗██║  ██║
╚═╝  ╚═╝╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝
🚀 Ultimate EVS Tool 🚀
[+] Programmed By Anomus.LY
[+] Modified By Uzif
[+] https://haxs.dev/
[+] captcha: API mode (no extension)
'''

API_HEADERS = {
    "accept": "*/*",
    "content-type": "application/json",
    "origin": "https://discord.com",
    "referer": "https://discord.com/register",
    "user-agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
    "x-discord-locale": "en-US",
}


# ------------------------------------------------------------------ helpers

def timestamp():
    return f"{Fore.LIGHTBLACK_EX}[{datetime.now().strftime('%H:%M:%S %d-%m-%Y')}]"


def log(msg, color=Fore.BLUE):
    print(f"{timestamp()} {color}{msg}{Style.RESET_ALL}", flush=True)


def random_sleep(base=2, variation=3):
    time.sleep(base + random.uniform(0, variation))


def generate_email():
    user = "".join(random.choices(string.ascii_lowercase, k=11))
    return f"{user}{''.join(random.choices(string.digits, k=6))}@gmail.com"


def generate_random_string(length=12):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def normalize_proxy(line):
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if "://" in line:
        return line
    parts = line.split(":")
    if len(parts) == 2:
        return f"http://{parts[0]}:{parts[1]}"
    if len(parts) == 4:
        return f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
    return None


def load_proxies():
    if not os.path.isfile(PROXY_FILE):
        return []
    out = []
    with open(PROXY_FILE, encoding="utf-8") as f:
        for line in f:
            p = normalize_proxy(line)
            if p:
                out.append(p)
    return out


PROXIES = load_proxies()


def pick_proxy():
    return random.choice(PROXIES) if PROXIES else None


def chrome_proxy_flag(proxy):
    """Chrome cannot take credentials in --proxy-server."""
    if not proxy:
        return None
    u = urlsplit(proxy)
    host = u.hostname or ""
    port = f":{u.port}" if u.port else ""
    return f"http://{host}{port}"


def save_credentials(email, password, token):
    with open(TOKENS_FILE, "a", encoding="utf-8") as f:
        f.write(token + "\n")
    with open(EVS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{email}:{password}:{token}\n")
    log("token saved to tokens.txt and evs.txt", Fore.GREEN)


# -------------------------------------------------------------- rate limits

def account_ratelimit():
    """Ask Discord how long registration is blocked, using a throwaway identity."""
    try:
        mail = f"{generate_email()}"
        client = tls_client.Session(client_identifier="chrome_110")
        client.headers = {
            "Accept": "*/*",
            "Content-Type": "application/json",
            "Origin": "https://discord.com",
            "Referer": "https://discord.com/register",
            "User-Agent": API_HEADERS["user-agent"],
            "X-Discord-Locale": "en-US",
        }
        payload = {
            "email": mail,
            "password": "ultimate12$$",
            "date_of_birth": DOB,
            "username": mail,
            "consent": True,
            "captcha_service": "hcaptcha",
            "global_name": GLOBAL_NAME,
            "captcha_key": None,
            "invite": None,
            "promotional_email_opt_in": False,
            "gift_code_sku_id": None,
        }
        req = client.post("https://discord.com/api/v9/auth/register", json=payload)
        if "The resource is being rate limited" in req.text:
            return req.json().get("retry_after", 1)
        return 1
    except Exception as e:
        log(f"rate limit probe failed: {e}", Fore.YELLOW)
        return 1


# ------------------------------------------------------------------ browser

def get_chrome_major_version():
    binary = os.environ.get("CHROME_BIN", "/usr/bin/chromium")
    try:
        out = subprocess.check_output([binary, "--version"], stderr=subprocess.STDOUT).decode()
        m = re.search(r"(\d+)\.", out)
        return int(m.group(1)) if m else None
    except Exception as e:
        log(f"could not detect chrome version: {e}", Fore.YELLOW)
        return None


def build_driver(proxy):
    profile = tempfile.mkdtemp(prefix="chr-")
    options = uc.ChromeOptions()
    options.binary_location = os.environ.get("CHROME_BIN", "/usr/bin/chromium")
    options.add_argument(f"--user-data-dir={profile}")
    options.add_argument("--lang=en-US")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("prefs", {"intl.accept_languages": "en-US,en"})
    flag = chrome_proxy_flag(proxy)
    if flag:
        options.add_argument(f"--proxy-server={flag}")
        log(f"browser proxy: {flag}", Fore.MAGENTA)

    driver = uc.Chrome(
        options=options,
        driver_executable_path=os.environ.get("CHROMEDRIVER_BIN", "/usr/bin/chromedriver"),
        version_main=get_chrome_major_version(),
    )
    driver.set_window_size(1920, 1080)
    driver._profile_dir = profile
    return driver


def close_driver(driver):
    if not driver:
        return
    profile = getattr(driver, "_profile_dir", None)
    try:
        driver.quit()
        log("driver closed", Fore.GREEN)
    except Exception:
        pass
    if profile:
        shutil.rmtree(profile, ignore_errors=True)


def fill_date_of_birth(driver, month, day, year):
    month_names = ["January", "February", "March", "April", "May", "June", "July",
                   "August", "September", "October", "November", "December"]

    try:
        selects = WebDriverWait(driver, 5).until(
            EC.presence_of_all_elements_located((By.TAG_NAME, "select")))
        if len(selects) >= 3:
            SeleniumSelect(selects[0]).select_by_visible_text(month_names[month - 1])
            time.sleep(0.3)
            SeleniumSelect(selects[1]).select_by_visible_text(str(day))
            time.sleep(0.3)
            SeleniumSelect(selects[2]).select_by_visible_text(str(year))
            time.sleep(0.3)
            log("date set", Fore.GREEN)
            return True
    except Exception:
        pass

    def click_and_pick(index, value):
        boxes = driver.find_elements(By.XPATH, '//*[@role="combobox"]')
        ActionChains(driver).move_to_element(boxes[index]).click().perform()
        time.sleep(0.4)
        ActionChains(driver).send_keys(value).perform()
        time.sleep(0.4)
        opt = WebDriverWait(driver, 5).until(EC.element_to_be_clickable(
            (By.XPATH, f'//*[@role="option"][normalize-space(.)="{value}"]')))
        driver.execute_script("arguments[0].scrollIntoView(true);", opt)
        driver.execute_script("arguments[0].click();", opt)
        time.sleep(0.3)

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, '//*[@role="combobox"]')))
        click_and_pick(0, month_names[month - 1])
        click_and_pick(1, str(day))
        click_and_pick(2, str(year))
        log("date set", Fore.GREEN)
        return True
    except Exception as e:
        log(f"date fill failed: {e}", Fore.RED)
        return False


def accept_terms(driver):
    try:
        boxes = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, "//input[@type='checkbox']")))
        clicked = 0
        for box in boxes:
            if not box.is_selected():
                driver.execute_script("arguments[0].scrollIntoView(true);", box)
                time.sleep(0.3)
                driver.execute_script("arguments[0].click();", box)
                clicked += 1
        log(f"{clicked} checkbox(es) ticked", Fore.BLUE)
    except Exception as e:
        log(f"terms click failed: {e}", Fore.YELLOW)


def submit_button(driver):
    return WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.XPATH, '//button[@type="submit"]')))


def read_sitekey(driver):
    """Pull the live hCaptcha sitekey out of the page; fall back to Discord's."""
    for _ in range(24):
        for el in driver.find_elements(By.CSS_SELECTOR, "[data-sitekey]"):
            value = el.get_attribute("data-sitekey")
            if value:
                return value
        for frame in driver.find_elements(By.CSS_SELECTOR, 'iframe[src*="hcaptcha"]'):
            m = re.search(r"sitekey=([0-9a-fA-F-]{36})", frame.get_attribute("src") or "")
            if m:
                return m.group(1)
        time.sleep(0.5)
    log("sitekey not found in DOM, using built-in", Fore.YELLOW)
    return DISCORD_SITEKEY


INJECT_JS = r"""
const token = arguments[0];
const hits = [];
const fire = (el, type) => el.dispatchEvent(new Event(type, {bubbles: true}));

for (const sel of ['textarea[name="h-captcha-response"]', 'textarea#h-captcha-response',
                   'textarea[name="g-recaptcha-response"]', 'textarea#g-recaptcha-response']) {
  for (const ta of document.querySelectorAll(sel)) {
    ta.value = token; fire(ta, 'input'); fire(ta, 'change'); hits.push('field:' + sel);
  }
}

for (const node of document.querySelectorAll('[data-callback], .h-captcha, iframe[src*="hcaptcha"]')) {
  const cb = node.getAttribute && node.getAttribute('data-callback');
  if (cb && typeof window[cb] === 'function') {
    try { window[cb](token); hits.push('callback:' + cb); } catch (e) {}
  }
}

for (const el of document.querySelectorAll('form, div, section')) {
  const key = Object.keys(el).find(k => k.startsWith('__reactProps$'));
  if (!key) continue;
  const props = el[key] || {};
  for (const name of ['onCaptchaVerify', 'onCaptchaSuccess', 'onVerify',
                      'onCaptchaSolved', 'handleCaptchaSuccess', 'onHCaptchaSuccess']) {
    if (typeof props[name] === 'function') {
      try { props[name](token); hits.push('react:' + name); } catch (e) {}
    }
  }
}

try { if (window.hcaptcha && window.hcaptcha.execute) hits.push('widget-live'); } catch (e) {}
return hits;
"""


def inject_token(driver, token):
    try:
        hits = driver.execute_script(INJECT_JS, token) or []
        log(f"token injected ({len(hits)} hook(s): {', '.join(hits[:3]) or 'none'})", Fore.BLUE)
        return bool(hits)
    except WebDriverException as e:
        log(f"injection error: {e}", Fore.RED)
        return False


def page_error(driver):
    try:
        text = driver.find_element(By.TAG_NAME, "body").text.lower()
    except Exception:
        return ""
    for needle in ("captcha", "rate limit", "something went wrong", "already registered"):
        if needle in text:
            return needle
    return ""


def register_in_browser(email):
    password = FIXED_PASSWORD or email
    proxy = pick_proxy()
    driver = build_driver(proxy)
    try:
        driver.get("https://discord.com/register")
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.NAME, "email")))
        driver.find_element(By.NAME, "email").send_keys(email)
        driver.find_element(By.NAME, "global_name").send_keys(GLOBAL_NAME)
        driver.find_element(By.NAME, "username").send_keys(generate_random_string())
        driver.find_element(By.NAME, "password").send_keys(password)

        month, day, year = (int(x) for x in DOB.split("-")[1:3][::-1]) if False else (None, None, None)
        parts = DOB.split("-")
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])

        log("setting date of birth...", Fore.YELLOW)
        fill_date_of_birth(driver, month, day, year)
        accept_terms(driver)

        limit = account_ratelimit()
        if limit and limit > 1:
            log(f"rate limited for {limit}s, waiting", Fore.RED)
            time.sleep(limit)

        submit_button(driver).click()
        log("form submitted, waiting for captcha widget...", Fore.YELLOW)

        token = None
        for attempt in range(1, SOLVE_ATTEMPTS + 1):
            sitekey = read_sitekey(driver)
            log(f"attempt {attempt}/{SOLVE_ATTEMPTS} - solving {sitekey[:8]}...", Fore.YELLOW)
            try:
                token = solve_hcaptcha(sitekey, "https://discord.com/register", proxy, log=log)
            except SolverError as e:
                log(f"solve failed: {e}", Fore.RED)
                random_sleep(3, 4)
                continue

            inject_token(driver, token)
            time.sleep(1)
            try:
                submit_button(driver).click()
            except Exception:
                driver.execute_script("document.querySelector('button[type=submit]')?.click()")

            try:
                WebDriverWait(driver, 45).until(EC.url_contains("discord.com/channels/@me"))
                log("redirected into the app", Fore.GREEN)
                break
            except TimeoutException:
                err = page_error(driver)
                log(f"still on the form (hint: {err or 'none'})", Fore.YELLOW)
                token = None

        if token is None:
            log("registration did not complete", Fore.RED)
            return None

        time.sleep(3)
        local = driver.execute_script("return window.localStorage.getItem('token')")
        local = (local or "").strip('"')
        if local:
            return email, password, local

        log("localStorage empty, trying API login", Fore.YELLOW)
        return email, password, None
    finally:
        close_driver(driver)


# ---------------------------------------------------------------- api mode

def register_via_api(email):
    password = FIXED_PASSWORD or email
    proxy = pick_proxy()
    proxies = {"http": proxy, "https": proxy} if proxy else None

    for attempt in range(1, SOLVE_ATTEMPTS + 1):
        log(f"api attempt {attempt}/{SOLVE_ATTEMPTS} - solving captcha...", Fore.YELLOW)
        try:
            captcha = solve_hcaptcha(DISCORD_SITEKEY, "https://discord.com/register", proxy, log=log)
        except SolverError as e:
            log(f"solve failed: {e}", Fore.RED)
            continue

        payload = {
            "email": email,
            "password": password,
            "date_of_birth": DOB,
            "username": generate_random_string(),
            "consent": True,
            "captcha_service": "hcaptcha",
            "global_name": GLOBAL_NAME,
            "captcha_key": captcha,
            "invite": None,
            "promotional_email_opt_in": False,
            "gift_code_sku_id": None,
        }
        try:
            r = requests.post("https://discord.com/api/v9/auth/register", json=payload,
                              headers=API_HEADERS, timeout=40, proxies=proxies)
        except requests.RequestException as e:
            log(f"register request failed: {e}", Fore.RED)
            continue

        if r.status_code == 200:
            token = (r.json() or {}).get("token")
            if token:
                return email, password, token
            log("200 without a token", Fore.RED)
            continue

        log(f"register rejected {r.status_code}: {r.text[:180]}", Fore.RED)
        if r.status_code == 429:
            try:
                time.sleep(float(r.json().get("retry_after", 5)) + 1)
            except Exception:
                time.sleep(5)
    return None


# --------------------------------------------------------------------- main

def main():
    log(f"mode={REGISTER_MODE} solvers={[p.name for p in configured_solvers(log)]}", Fore.MAGENTA)
    if PROXIES:
        log(f"{len(PROXIES)} proxies loaded", Fore.MAGENTA)
    else:
        log("no proxies loaded - datacenter IP, expect more captchas", Fore.YELLOW)

    while True:
        email = generate_email()
        log(f"using email {email}", Fore.BLUE)
        try:
            if REGISTER_MODE == "api":
                result = register_via_api(email)
            else:
                result = register_in_browser(email)
                if result and not result[2]:
                    result = (result[0], result[1], None)
        except KeyboardInterrupt:
            raise
        except Exception:
            log("iteration crashed:", Fore.RED)
            traceback.print_exc()
            result = None

        if result:
            email, password, token = result
            if not token:
                log("no token in the browser session, falling back to login", Fore.YELLOW)
                token = login_and_fetch_token(email, password)
            if token:
                save_credentials(email, password, token)
                log("account done, restarting loop", Fore.GREEN)
            else:
                log(f"no token for {email}", Fore.RED)
        else:
            log("iteration failed, retrying", Fore.RED)

        random_sleep(4, 5)


def login_and_fetch_token(email, password):
    data = {"login": email, "password": password, "undelete": "false"}
    try:
        r = requests.post("https://discord.com/api/v9/auth/login", json=data,
                          headers=API_HEADERS, timeout=30)
        if r.status_code == 200:
            token = (r.json() or {}).get("token")
            if token:
                return token
            log("login ok but no token field", Fore.RED)
        elif "captcha-required" in r.text:
            log("login wants its own captcha - account still created", Fore.YELLOW)
        else:
            log(f"login failed {r.status_code}: {r.text[:150]}", Fore.RED)
    except requests.RequestException as e:
        log(f"login error: {e}", Fore.RED)
    return None


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("stopped by user", Fore.YELLOW)
