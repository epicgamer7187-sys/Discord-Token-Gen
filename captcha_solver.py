"""
captcha_solver.py - hCaptcha solving over plain HTTP. No extension, no pyautogui.

Env:
    SOLVERS         comma list, tried in order
                    (default: nopecha,capmonster,capsolver,2captcha,nonecap)
    NOPECHA_KEY / CAPMONSTER_KEY / CAPSOLVER_KEY / TWOCAPTCHA_KEY / NONECAP_KEY
    SOLVER_TIMEOUT  seconds per solve (default 180)
    SOLVER_POLL     poll interval seconds (default 3)
    SOLVER_ENTERPRISE  1 / 0 to force enterprise mode, else auto-detected

Every provider hands back a real hCaptcha response token (P1_... / E0_... style
string) - the value that belongs in the h-captcha-response field.

Enterprise note: Discord's register page uses an enterprise sitekey. Tokens
minted without the challenge's rqdata are rejected server-side, so rqdata is
passed through when the caller has it.

NOTE (Oct 2026): NopeCHA retired its hCaptcha endpoint on 2026-10-02 and now
answers HTTP 410 code 19.
"""
import os
import time
from urllib.parse import urlsplit

import requests

DISCORD_SITEKEY = "f5561ba9-8f1e-40ca-9e68-6b8aa015b4b8"

TIMEOUT = int(os.environ.get("SOLVER_TIMEOUT", "180"))
POLL = float(os.environ.get("SOLVER_POLL", "3"))
DEFAULT_ORDER = "nopecha,capmonster,capsolver,2captcha,nonecap"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


class SolverError(Exception):
    pass


class Discontinued(SolverError):
    pass


def _proxies(proxy):
    return {"http": proxy, "https": proxy} if proxy else None


def _split_proxy(proxy):
    u = urlsplit(proxy if "://" in proxy else "http://" + proxy)
    d = {"scheme": u.scheme or "http", "host": u.hostname, "port": u.port or 80}
    if u.username:
        d["username"] = u.username
    if u.password:
        d["password"] = u.password
    return d


class _Provider:
    name = "base"
    key_env = ""

    def __init__(self, key):
        self.key = key

    def solve(self, sitekey, url, proxy=None, rqdata=None, enterprise=False):
        raise NotImplementedError


class NopeCHA(_Provider):
    name = "nopecha"
    key_env = "NOPECHA_KEY"
    API = "https://api.nopecha.com/token"

    def solve(self, sitekey, url, proxy=None, rqdata=None, enterprise=False):
        body = {"key": self.key, "type": "hcaptcha", "sitekey": sitekey, "url": url}
        if enterprise:
            body["enterprise"] = True
            if rqdata:
                body["data"] = {"rqdata": rqdata}
        if proxy:
            body["proxy"] = _split_proxy(proxy)
        r = requests.post(self.API, json=body, timeout=30, proxies=_proxies(proxy))
        if r.status_code == 410:
            raise Discontinued("nopecha: hCaptcha endpoint discontinued (410)")
        if r.status_code == 401:
            raise SolverError("nopecha: invalid key")
        if r.status_code == 403:
            raise SolverError(f"nopecha: {r.json().get('message', 'forbidden')} (403)")
        data = r.json() if r.content else {}
        job = data.get("data")
        if not job:
            raise SolverError(f"nopecha: submit rejected {data}")

        deadline = time.time() + TIMEOUT
        while time.time() < deadline:
            time.sleep(POLL)
            g = requests.get(self.API, params={"key": self.key, "id": job},
                             timeout=30, proxies=_proxies(proxy))
            if g.status_code == 409:
                continue
            if g.status_code == 410:
                raise Discontinued("nopecha: hCaptcha endpoint discontinued (410)")
            if g.status_code >= 400:
                raise SolverError(f"nopecha: poll {g.status_code} {g.text[:120]}")
            tok = (g.json() or {}).get("data")
            if isinstance(tok, str) and len(tok) > 20:
                return tok
        raise SolverError("nopecha: solve timeout")


class _TaskPoll(_Provider):
    """Shared createTask/getTaskResult flow (CapMonster, CapSolver)."""
    create_url = ""
    result_url = ""
    task_proxied = ""
    task_proxyless = ""

    def _task(self, sitekey, url, proxy, rqdata, enterprise):
        base = {"websiteURL": url, "websiteKey": sitekey}
        if enterprise:
            base["isEnterprise"] = True
            if rqdata:
                base["enterprisePayload"] = {"rqdata": rqdata}
        if not proxy:
            return {**base, "type": self.task_proxyless}
        p = _split_proxy(proxy)
        task = {
            **base,
            "type": self.task_proxied,
            "proxyType": "http" if p["scheme"] in ("http", "https") else "socks5",
            "proxyAddress": p["host"],
            "proxyPort": p["port"],
        }
        if "username" in p:
            task["proxyLogin"] = p["username"]
            task["proxyPassword"] = p.get("password", "")
        return task

    def solve(self, sitekey, url, proxy=None, rqdata=None, enterprise=False):
        r = requests.post(self.create_url, timeout=30, proxies=_proxies(proxy),
                          json={"clientKey": self.key,
                                "task": self._task(sitekey, url, proxy, rqdata, enterprise)})
        data = r.json() if r.content else {}
        if data.get("errorId"):
            raise SolverError(f"{self.name}: {data.get('errorCode')} {data.get('errorDescription', '')}")
        task_id = data.get("taskId")
        if not task_id:
            raise SolverError(f"{self.name}: no taskId")

        deadline = time.time() + TIMEOUT
        while time.time() < deadline:
            time.sleep(POLL)
            g = requests.post(self.result_url, timeout=30, proxies=_proxies(proxy),
                              json={"clientKey": self.key, "taskId": task_id})
            d = g.json() if g.content else {}
            if d.get("errorId"):
                raise SolverError(f"{self.name}: {d.get('errorCode')}")
            if d.get("status") == "ready":
                sol = d.get("solution") or {}
                tok = sol.get("gRecaptchaResponse") or sol.get("token")
                if tok:
                    return tok
        raise SolverError(f"{self.name}: solve timeout")


class CapMonster(_TaskPoll):
    name = "capmonster"
    key_env = "CAPMONSTER_KEY"
    create_url = "https://api.capmonster.cloud/createTask"
    result_url = "https://api.capmonster.cloud/getTaskResult"
    task_proxied = "HCaptchaTask"
    task_proxyless = "HCaptchaTaskProxyless"


class CapSolver(_TaskPoll):
    name = "capsolver"
    key_env = "CAPSOLVER_KEY"
    create_url = "https://api.capsolver.com/createTask"
    result_url = "https://api.capsolver.com/getTaskResult"
    task_proxied = "HCaptchaTask"
    task_proxyless = "HCaptchaTaskProxyLess"


class TwoCaptcha(_Provider):
    name = "2captcha"
    key_env = "TWOCAPTCHA_KEY"

    def solve(self, sitekey, url, proxy=None, rqdata=None, enterprise=False):
        body = {"key": self.key, "method": "hcaptcha", "sitekey": sitekey,
                "pageurl": url, "json": 1, "userAgent": UA}
        if enterprise:
            body["enterprise"] = 1
            if rqdata:
                body["data"] = rqdata
        if proxy:
            p = _split_proxy(proxy)
            body["proxy"] = f"{p['host']}:{p['port']}"
            if "username" in p:
                body["proxy_user"] = p["username"]
                body["proxy_password"] = p.get("password", "")
        r = requests.post("https://2captcha.com/in.php", data=body, timeout=30,
                          proxies=_proxies(proxy))
        data = r.json()
        if data.get("status") != 1:
            raise SolverError(f"2captcha: {data.get('request')}")
        job = data["request"]

        deadline = time.time() + TIMEOUT
        while time.time() < deadline:
            time.sleep(5)
            g = requests.get("https://2captcha.com/res.php", timeout=30, proxies=_proxies(proxy),
                             params={"key": self.key, "action": "get", "id": job, "json": 1})
            d = g.json()
            if d.get("status") == 1:
                return d["request"]
            if d.get("request") not in ("CAPCHA_NOT_READY", "CAPTCHA_NOT_READY"):
                raise SolverError(f"2captcha: {d.get('request')}")
        raise SolverError("2captcha: solve timeout")


class NoneCap(_Provider):
    name = "nonecap"
    key_env = "NONECAP_KEY"

    def solve(self, sitekey, url, proxy=None, rqdata=None, enterprise=False):
        body = {"type": "hcaptcha_enterprise" if enterprise else "hcaptcha",
                "sitekey": sitekey, "url": url}
        if enterprise and rqdata:
            body["rqdata"] = rqdata
        r = requests.post(
            "https://api.nonecap.com/v1/solves",
            params={"wait": 90},
            timeout=TIMEOUT + 30,
            proxies=_proxies(proxy),
            headers={"Authorization": f"Bearer {self.key}"},
            json=body,
        )
        if r.status_code == 401:
            raise SolverError("nonecap: invalid key")
        data = r.json() if r.content else {}
        if data.get("status") == "solved" and data.get("token"):
            return data["token"]
        job = data.get("id")
        if not job:
            raise SolverError(f"nonecap: {data}")
        deadline = time.time() + TIMEOUT
        while time.time() < deadline:
            time.sleep(POLL)
            g = requests.get(f"https://api.nonecap.com/v1/solves/{job}", timeout=30,
                             proxies=_proxies(proxy),
                             headers={"Authorization": f"Bearer {self.key}"})
            d = g.json() if g.content else {}
            if d.get("status") == "solved" and d.get("token"):
                return d["token"]
            if d.get("status") in ("failed", "error"):
                raise SolverError(f"nonecap: {d.get('status')}")
        raise SolverError("nonecap: solve timeout")


REGISTRY = {c.name: c for c in (NopeCHA, CapMonster, CapSolver, TwoCaptcha, NoneCap)}


def configured(log=print):
    order = [s.strip().lower() for s in os.environ.get("SOLVERS", DEFAULT_ORDER).split(",") if s.strip()]
    out = []
    for name in order:
        cls = REGISTRY.get(name)
        if not cls:
            log(f"[solver] unknown provider '{name}' - skipped")
            continue
        key = os.environ.get(cls.key_env, "").strip()
        if not key:
            continue
        out.append(cls(key))
    return out


def solve_hcaptcha(sitekey, url, proxy=None, rqdata=None, enterprise=False, log=print):
    """Try every configured provider in order. Returns a token or raises SolverError."""
    providers = configured(log)
    if not providers:
        raise SolverError("no solver configured - set NOPECHA_KEY or another *_KEY")
    last = None
    for p in providers:
        started = time.time()
        kind = "hcaptcha_enterprise" if enterprise else "hcaptcha"
        log(f"{p.name}: submitting {kind} job (rqdata={'yes' if rqdata else 'no'})...")
        try:
            tok = p.solve(sitekey, url, proxy, rqdata, enterprise)
            log(f"{p.name}: token received in {time.time() - started:.1f}s")
            return tok
        except Discontinued as e:
            log(f"{p.name}: {e}")
            last = e
        except Exception as e:
            log(f"{p.name}: failed - {e}")
            last = e
    raise SolverError(f"every solver failed (last: {last})")
