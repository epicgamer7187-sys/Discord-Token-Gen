# ============================================================
#  Discord Token Gen - Railway container
#  Headed Chromium on a virtual display (pyautogui needs a real X display)
# ============================================================
FROM python:3.12

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:99 \
    CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver \
    SE_OFFLINE=true \
    KEEP_ALIVE=1 \
    TZ=UTC

# --- system packages -------------------------------------------------
# xvfb/xauth/x11-utils : virtual display that pyautogui imports against
# scrot                : pyautogui screenshot backend on Linux
# chromium + driver    : matched pair, avoids version drift
# fonts                : stops blank/tofu rendering breaking element matching
RUN apt-get update && apt-get install -y --no-install-recommends \
        xvfb \
        xauth \
        x11-utils \
        scrot \
        python3-tk \
        chromium \
        chromium-driver \
        fonts-liberation \
        fonts-dejavu-core \
        ca-certificates \
        libgbm1 \
        libasound2 \
        libnss3 \
        libxss1 \
        libgtk-3-0 \
        libx11-xcb1 \
        libxcb-dri3-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir \
        python-xlib pygetwindow pymsgbox pytweening pyscreeze mouseinfo

COPY . .

# Auto-loaded at interpreter start (PYTHONPATH=/app) - injects the Chrome
# flags a root container needs, without you editing main.py.
COPY sitecustomize.py /app/sitecustomize.py

RUN chmod +x /app/start.sh && mkdir -p /tmp/run

CMD ["/app/start.sh"]
