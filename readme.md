
# ⚡ DISCORD TOKEN GENERATOR v1.9

## 🚀 Setup
1. **Clone the repository:**
   ```bash
   git clone https://github.com/uziff/Discord-Token-Gen.git
   cd Discord-Token-Gen

2. **Install Requirements:**
   ```
   pip install -r requirements.txt
   ```


3. **Run the tool:**
   ```
   python main.py
   ```


## ⚙️ How It Works

**The tool will automatically**:

* Create Discord accounts using Selenium
* Handle and solve CAPTCHA prompts automatically
* Extract and save Discord tokens

**Check results in your output files**:

* `tokens.txt` - Generated Discord tokens
* `evs.txt` - Complete account data (`email:password:token`)

---

## 🌐 Proxies support

To add your own proxies, just follow the simple instructions in [proxy help.txt](https://github.com/uziff/Discord-Token-Gen/blob/main/proxy%20help.txt)

---

## 🎯 About

A **Selenium-based Discord Token Generator** that automates account creation using temporary emails and saves extracted tokens automatically. Simple, automated, and built for testing and learning.

### ✨ Automation Features

1. 🤖 **Automate Discord registration** with Selenium
2. 🧩 **Automatic CAPTCHA solving**
3. 🚦 **Rate limiting handled automatically** to prevent blocks
4. 🔑 **Token extraction** via Discord API login
5. 💾 **Save credentials** to organized output files

---

## 🛠️ Technical Details

| Component | Description | Purpose |
| --- | --- | --- |
| `Selenium WebDriver` | Browser automation | Account registration |
| `Undetected Chrome` | Stealth browser | Bypass detection |
| `TLS Client` | Rate limit detection | API monitoring |
| `Random Generation` | Fake user data | Realistic accounts |

---

## 📬 Contact & Custom Tools

Looking for something unique? DM us on Discord with your idea and budget!

* 💬 **Discord**: [`uzif`](https://dsc.gg/uzif)<br>
*If this tool saved you time or helped you out, enjoy! It's completely free. **As it should.***

---

## ⚖️ Disclaimer

> This tool is for **educational and testing purposes only**.
> The creator is **not responsible** for any misuse or violations of Discord’s Terms of Service. Please use responsibly.
> I've heard rumors that the original creator, HassanXTech, is a bit of a scammer. I did not check myself, so make sure to watch out for that.

```

## Solver configuration (env vars on Railway)

Captcha is solved over HTTP API - no Chrome extension is installed.

| Variable | Meaning |
| --- | --- |
| `NOPECHA_KEY` | NopeCHA key. hCaptcha endpoint is dead since 2026-10-02 (HTTP 410). |
| `CAPMONSTER_KEY` | CapMonster Cloud key (proxied + proxyless tasks supported) |
| `CAPSOLVER_KEY` | CapSolver key |
| `TWOCAPTCHA_KEY` | 2Captcha key |
| `NONECAP_KEY` | NoneCap key (hCaptcha only) |
| `SOLVERS` | override order, default `nopecha,capmonster,capsolver,2captcha,nonecap` |
| `SOLVER_TIMEOUT` | seconds per solve, default `180` |
| `REGISTER_MODE` | `browser` (default) or `api` (no Chromium at all) |
| `GLOBAL_NAME` / `ACCOUNT_PASSWORD` / `DATE_OF_BIRTH` | account identity, defaults `Lunarxterm` / =email / `2000-09-20` |
| `SOLVE_ATTEMPTS` | captcha/submit retries per account, default `3` |
| `CHROME_HEADLESS` | `1` to drop Xvfb rendering |

Set at least one key besides NopeCHA or nothing will solve.
Put proxies in `proxies.txt` (`host:port` or `host:port:user:pass`, one per line).
Proxy auth on the browser side needs IP whitelisting, Chrome cannot type credentials.
