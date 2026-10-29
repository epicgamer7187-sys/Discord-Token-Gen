# ============================================================
#  Discord Token Gen - Railway container
#  Headed Chromium on a virtual display, captcha solved over HTTP API
# ============================================================
FROM python:3.12

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:99 \
    CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_BIN=/usr/bin/chromedriver \
    KEEP_ALIVE=1 \
    TZ=UTC

RUN apt-get update && apt-get install -y --no-install-recommends \
        xvfb \
        xauth \
        x11-utils \
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
 && pip install --no-cache-dir -r requirements.txt

COPY . .

COPY sitecustomize.py /app/sitecustomize.py

RUN chmod +x /app/start.sh && mkdir -p /tmp/run

CMD ["/app/start.sh"]
