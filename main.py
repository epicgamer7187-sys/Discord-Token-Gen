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
from urllib.parse import urlsplit, unquote

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

REGISTER_MODE = os.environ.get("REGISTER_MODE", "api").strip().lower()
GLOBAL_NAME = os.environ.get("GLOBAL_NAME", "Lunarxterm")
FIXED_PASSWORD = os.environ.get("ACCOUNT_PASSWORD", "").strip()
DOB = os.environ.get("DATE_OF_BIRTH", "2000-09-20").strip()
TOKENS_FILE = os.environ.get("TOKENS_FILE", "tokens.txt")
EVS_FILE = os.environ.get("EVS_FILE", "evs.txt")
PROXY_FILE = os.environ.get("PROXY_FILE", "proxies.txt")
SOLVE_ATTEMPTS = int(os.environ.get("SOLVE_ATTEMPTS", "3"))
SUBMIT_WAIT = int(os.environ.get("SUBMIT_WAIT", "12"))
SHOT_DIR = os.environ.get("SHOT_DIR", "/data/shots" if os.path.isdir("/data") else "/tmp/shots")
SITEKEY_CACHE = os.environ.get(
    "SITEKEY_CACHE", "/data/sitekey.txt" if os.path.isdir("/data") else "/tmp/sitekey.txt")

REGISTER_URL = "https://discord.com/api/v9/auth/register"
PAGE_URL = "https://discord.com/register"

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
    "referer": PAGE_URL,
    "user-agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
    "x-discord-locale": "en-US",
}

SUPER_PROPS = ("eyJvcyI6IldpbmRvd3MiLCJicm93c2VyIjoiQ2hyb21lIiwiZGV2aWNlIjoiIiwic3lzdGVtX2xvY2Fs"
               "ZSI6ImVuLVVTIiwiYnJvd3Nlcl91c2VyX2FnZW50IjoiTW96aWxsYS81LjAgKFdpbmRvd3MgTlQgMTAu"
               "MDsgV2luNjQ7IHg2NCkgQXBwbGVXZWJLaXQvNTM3LjM2IChLSFRNTCwgbGlrZSBHZWNrbykgQ2hyb21l"
               "LzEzMS4wLjAuMCBTYWZhcmkvNTM3LjM2IiwiYnJvd3Nlcl92ZXJzaW9uIjoiMTMxLjAuMC4wIiwib3Nf"
               "dmVyc2lvbiI6IjEwIiwicmVmZXJyZXIiOiIiLCJyZWZlcnJpbmdfZG9tYWluIjoiIiwicmVmZXJyZXJf"
               "Y3VycmVudCI6IiIsInJlZmVycmFsX2N1cnJlbnQiOiIiLCJyZWxlYXNlX2NoYW5uZWwiOiJzdGFibGUi"
               "LCJjbGllbnRfYnVpbGRfbnVtYmVyIjo0MDAwMDAsImNsaWVudF9ldmVudF9zb3VyY2UiOm51bGx9")


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
    if not proxy:
        return None
    u = urlsplit(proxy)
    return f"http://{u.hostname}{':' + str(u.port) if u.port else ''}"


def save_credentials(email, password, token):
    with open(TOKENS_FILE, "a", encoding="utf-8") as f:
        f.write(token + "\n")
    with open(EVS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{email}:{password}:{token}\n")
    log("token saved to tokens.txt and evs.txt", Fore.GREEN)


def sitekey_candidates():
    out = []
    env = os.environ.get("DISCORD_SITEKEY", "").strip()
    if env:
        out.append(env)
    try:
        if os.path.isfile(SITEKEY_CACHE):
            cached = open(SITEKEY_CACHE, encoding="utf-8").read().strip()
            if cached and cached not in out:
                out.append(cached)
    except Exception:
        pass
    if DISCORD_SITEKEY not in out:
        out.append(DISCORD_SITEKEY)
    return out


def cache_sitekey(key):
    try:
        with open(SITEKEY_CACHE, "w", encoding="utf-8") as f:
            f.write(key)
    except Exception:
        pass


def save_shot(driver, tag):
    try:
        os.makedirs(SHOT_DIR, exist_ok=True)
        path = os.path.join(SHOT_DIR, f"{datetime.now().strftime('%H%M%S')}-{tag}.png")
        driver.save_screenshot(path)
        log(f"screenshot: {path}", Fore.MAGENTA)
    except Exception:
        pass


# -------------------------------------------------------------- rate limits

def account_ratelimit():
    try:
        mail = generate_email()
        client = make_client(pick_proxy())
        req = client.post(REGISTER_URL, json=build_payload(mail, "ultimate12$$"))
        if "The resource is being rate limited" in req.text:
            return req.json().get("retry_after", 1)
        return 1
    except Exception as e:
        log(f"rate limit probe failed: {e}", Fore.YELLOW)
        return 1


# --------------------------------------------------------------------- api

def make_client(proxy=None):
    client = tls_client.Session(client_identifier="chrome_120")
    client.headers = {**API_HEADERS, "x-super-properties": SUPER_PROPS}
    if proxy:
        client.proxies = {"http": proxy, "https": proxy}
    return client


def build_payload(email, password, captcha=None, rqdata=None, session_id=None):
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
    if rqdata:
        payload["captcha_rqdata"] = rqdata
    if session_id:
        payload["captcha_session_id"] = session_id
    return payload


def fetch_challenge(client, email, password):
    """Discord answers a tokenless register with the challenge descriptor."""
    r = client.post(REGISTER_URL, json=build_payload(email, password))
    if r.status_code == 400 and "captcha-required" in r.text:
        try:
            return r.json()
        except Exception:
            return {}
    if r.status_code == 429:
        try:
            time.sleep(float(r.json().get("retry_after", 5)) + 1)
        except Exception:
            time.sleep(5)
    log(f"challenge fetch -> {r.status_code} {r.text[:200]}", Fore.YELLOW)
    return None


def api_register(email, password, captcha=None, rqdata=None, session_id=None):
    proxy = pick_proxy()
    client = make_client(proxy)
    if proxy:
        log(f"api proxy: {proxy}", Fore.MAGENTA)

    for attempt in range(1, SOLVE_ATTEMPTS + 1):
        if captcha is None:
            challenge = fetch_challenge(client, email, password)
            if challenge is None:
                continue

            sitekey = challenge.get("captcha_sitekey") or sitekey_candidates()[0]
            service = (challenge.get("captcha_service") or "hcaptcha").lower()
            enterprise = service.endswith("enterprise")
            invisible = bool(challenge.get("should_serve_invisible_captcha"))
            rqdata = challenge.get("captcha_rqdata") or rqdata
            session_id = challenge.get("captcha_session_id") or session_id
            if sitekey:
                cache_sitekey(sitekey)

            log(f"attempt {attempt}/{SOLVE_ATTEMPTS} challenge: sitekey={sitekey[:8]}... "
                f"service={service} invisible={invisible} "
                f"session={'yes' if session_id else 'no'} rqdata={'yes' if rqdata else 'no'}",
                Fore.MAGENTA)

            try:
                captcha = solve_hcaptcha(sitekey, PAGE_URL, proxy, rqdata=rqdata,
                                         enterprise=enterprise, invisible=invisible, log=log)
            except SolverError as e:
                log(f"solve failed: {e}", Fore.RED)
                captcha = None
                continue

        try:
            r = client.post(REGISTER_URL,
                            json=build_payload(email, password, captcha, rqdata, session_id))
        except Exception as e:
            log(f"register request failed: {e}", Fore.RED)
            captcha = None
            continue

        if r.status_code == 200:
            token = (r.json() or {}).get("token")
            if token:
                return email, password, token
            log("200 without a token", Fore.RED)
            return None

        log(f"register rejected {r.status_code}: {r.text[:400]}", Fore.RED)

        if r.status_code == 400 and "captcha-required" in r.text:
            captcha = None
            continue
        if r.status_code == 429:
            try:
                time.sleep(float(r.json().get("retry_after", 5)) + 1)
            except Exception:
                time.sleep(5)
            captcha = None
            continue
        return None
    return None


def register_via_api(email):
    return api_register(email, FIXED_PASSWORD or email)


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


def _is_checked(el):
    try:
        if el.is_selected():
            return True
    except Exception:
        pass
    return (el.get_attribute("aria-checked") or "").lower() == "true"


def _click_js(driver, el):
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    time.sleep(0.2)
    try:
        driver.execute_script("arguments[0].click();", el)
    except WebDriverException:
        ActionChains(driver).move_to_element(el).click().perform()


def accept_terms(driver):
    ticked = 0
    for selector in ("input[type='checkbox']", "[role='checkbox']"):
        for el in driver.find_elements(By.CSS_SELECTOR, selector):
            try:
                if _is_checked(el):
                    continue
                _click_js(driver, el)
                ticked += 1
            except Exception:
                pass
    if ticked == 0:
        for el in driver.find_elements(
                By.XPATH, "//label[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'terms')]"):
            try:
                _click_js(driver, el)
                ticked += 1
            except Exception:
                pass
    if ticked == 0:
        log("no consent control found", Fore.RED)
        return False
    log(f"{ticked} consent control(s) clicked", Fore.BLUE)
    time.sleep(0.5)
    return True


def find_submit(driver):
    for xpath in ('//button[@type="submit"]',
                  '//button[contains(., "Continue")]',
                  '//button[contains(., "Register")]'):
        for el in driver.find_elements(By.XPATH, xpath):
            if el.is_displayed():
                return el
    return None


def click_submit(driver):
    btn = find_submit(driver)
    if btn is None:
        log("submit button not found", Fore.RED)
        return False
    _click_js(driver, btn)
    return True


def read_widget(driver):
    sitekey = rqdata = None
    for _ in range(24):
        for el in driver.find_elements(By.CSS_SELECTOR, "[data-sitekey]"):
            sitekey = sitekey or el.get_attribute("data-sitekey")
            rqdata = rqdata or el.get_attribute("data-rqdata")
        for frame in driver.find_elements(By.CSS_SELECTOR, 'iframe[src*="hcaptcha"]'):
            src = frame.get_attribute("src") or ""
            m = re.search(r"[?&]sitekey=([0-9a-fA-F-]{36})", src)
            if m:
                sitekey = sitekey or m.group(1)
            m = re.search(r"[?&]rqdata=([^&]+)", src)
            if m:
                rqdata = rqdata or unquote(m.group(1))
        if sitekey and rqdata:
            break
        if not rqdata:
            try:
                m = re.search(r'"rqdata"\s*:\s*"([^"]{20,})"', driver.page_source)
                if m:
                    rqdata = m.group(1)
            except Exception:
                pass
        if sitekey and rqdata:
            break
        time.sleep(0.5)
    if sitekey:
        cache_sitekey(sitekey)
        log(f"widget: sitekey={sitekey[:8]}... rqdata={'yes' if rqdata else 'no'}", Fore.MAGENTA)
    return sitekey, rqdata


def open_register_page(driver, email, password):
    driver.get(PAGE_URL)
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.NAME, "email")))
    driver.find_element(By.NAME, "email").send_keys(email)
    driver.find_element(By.NAME, "global_name").send_keys(GLOBAL_NAME)
    driver.find_element(By.NAME, "username").send_keys(generate_random_string())
    driver.find_element(By.NAME, "password").send_keys(password)
    parts = DOB.split("-")
    log("setting date of birth...", Fore.YELLOW)
    fill_date_of_birth(driver, int(parts[1]), int(parts[2]), int(parts[0]))
    accept_terms(driver)
    click_submit(driver)
    log("form submitted, waiting for the captcha widget...", Fore.YELLOW)
    time.sleep(2)


def register_hybrid(email):
    password = FIXED_PASSWORD or email
    proxy = pick_proxy()
    driver = build_driver(proxy)
    try:
        open_register_page(driver, email, password)
        sitekey, rqdata = read_widget(driver)
        sitekey = sitekey or sitekey_candidates()[0]
        log("hybrid: browser renders the challenge, API submits", Fore.MAGENTA)
        return api_register(email, password)
    finally:
        close_driver(driver)


def register_in_browser(email):
    password = FIXED_PASSWORD or email
    proxy = pick_proxy()
    driver = build_driver(proxy)
    try:
        open_register_page(driver, email, password)
        sitekey, rqdata = read_widget(driver)
        for attempt in range(1, SOLVE_ATTEMPTS + 1):
            log(f"browser attempt {attempt}/{SOLVE_ATTEMPTS}", Fore.YELLOW)
            try:
                token = solve_hcaptcha(sitekey or sitekey_candidates()[0], PAGE_URL, proxy,
                                       rqdata=rqdata, invisible=True, log=log)
            except SolverError as e:
                log(f"solve failed: {e}", Fore.RED)
                random_sleep(2, 3)
                continue
            try:
                driver.execute_script(
                    "for (const ta of document.querySelectorAll('textarea[name=\"h-captcha-response\"]'))"
                    " { ta.value = arguments[0]; ta.dispatchEvent(new Event('input',{bubbles:true})); }",
                    token)
            except Exception:
                pass
            click_submit(driver)
            try:
                WebDriverWait(driver, SUBMIT_WAIT).until(EC.url_contains("discord.com/channels/@me"))
                time.sleep(3)
                local = (driver.execute_script("return window.localStorage.getItem('token')") or "").strip('"')
                return email, password, local or None
            except TimeoutException:
                save_shot(driver, f"attempt{attempt}")
                log("still on the form", Fore.YELLOW)
        return api_register(email, password)
    finally:
        close_driver(driver)


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
            if REGISTER_MODE == "browser":
                result = register_in_browser(email)
            elif REGISTER_MODE == "hybrid":
                result = register_hybrid(email)
            else:
                result = register_via_api(email)
        except KeyboardInterrupt:
            raise
        except Exception:
            log("iteration crashed:", Fore.RED)
            traceback.print_exc()
            result = None

        if result:
            email, password, token = result
            if not token:
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
