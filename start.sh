#!/usr/bin/env bash
# Entrypoint: virtual display -> sanity checks -> main.py -> persist output
set -uo pipefail

export DISPLAY="${DISPLAY:-:99}"

echo "==> boot: pwd=$(pwd) display=$DISPLAY python=$(command -v python)"

# ---- persist generated files on the Railway volume (mounted at /data) ----
if [ -d /data ]; then
  for f in tokens.txt evs.txt; do
    touch "/data/$f"
    rm -f "/app/$f"
    ln -sf "/data/$f" "/app/$f"
  done
  if [ -s /data/proxies.txt ]; then
    rm -f /app/proxies.txt
    ln -sf /data/proxies.txt /app/proxies.txt
  fi
  echo "==> /data volume detected - tokens/evs persisted there"
else
  echo "!! no /data volume - output will be lost on redeploy"
fi

# ---- virtual X display (pyautogui cannot even import without DISPLAY) ----
Xvfb "$DISPLAY" -screen 0 1920x1080x24 -nolisten tcp &
XVFB_PID=$!
for _ in $(seq 1 100); do
  xdpyinfo -display "$DISPLAY" >/dev/null 2>&1 && break
  sleep 0.1
done
xdpyinfo -display "$DISPLAY" >/dev/null 2>&1 \
  && echo "==> display $DISPLAY is up (pid $XVFB_PID)" \
  || echo "!! display $DISPLAY never came up"

# ---- loud sanity checks instead of silent death ----
command -v chromium     >/dev/null || echo "!! chromium missing"
command -v chromedriver >/dev/null || echo "!! chromedriver missing"
command -v scrot        >/dev/null || echo "!! scrot missing"
[ -s proxies.txt ] || echo "!! proxies.txt is EMPTY - generator will very likely fail"

echo "==> launching main.py"
python -u main.py 2>&1 | tee /tmp/run/run.log
CODE="${PIPESTATUS[0]}"

echo "=================================================="
echo "==> main.py exited with code $CODE"
echo "=================================================="
tail -n 60 /tmp/run/run.log

kill "$XVFB_PID" 2>/dev/null || true

if [ "${KEEP_ALIVE:-1}" = "1" ]; then
  echo "==> holding container open (KEEP_ALIVE=1). Set KEEP_ALIVE=0 for a restart loop."
  sleep infinity
fi

exit "$CODE"
