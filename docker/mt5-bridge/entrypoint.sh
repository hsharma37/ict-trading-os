#!/usr/bin/env bash
# First-run installer + process supervisor for the containerized MT5 bridge.
# Idempotent: everything lands in the persistent WINEPREFIX volume, so
# installs and the terminal login happen once and survive restarts.
set -euo pipefail

PY_VER="3.12.10"
PY_EXE="/root/installers/python-${PY_VER}-amd64.exe"
MT5_EXE="/root/installers/mt5setup.exe"
MT5_TERMINAL="${WINEPREFIX}/drive_c/Program Files/MetaTrader 5/terminal64.exe"
WINE_PY="${WINEPREFIX}/drive_c/Program Files/Python312/python.exe"
MT5_DOWNLOAD_URL="${MT5_DOWNLOAD_URL:-https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe}"

mkdir -p /root/installers

# Virtual display first — Wine installers need one even in silent mode.
Xvfb :99 -screen 0 1280x900x24 &
sleep 2

if [ ! -f "${MT5_TERMINAL}" ]; then
    echo "[setup] First run: installing MT5 terminal under Wine…"
    wineboot --init || true
    sleep 5
    [ -f "${MT5_EXE}" ] || wget -qO "${MT5_EXE}" "${MT5_DOWNLOAD_URL}"
    wine "${MT5_EXE}" /auto || true          # silent install; returns before finishing
    for i in $(seq 1 60); do
        [ -f "${MT5_TERMINAL}" ] && break
        sleep 5
    done
    [ -f "${MT5_TERMINAL}" ] || { echo "[setup] MT5 install FAILED — check /auto support for this build"; exit 1; }
    echo "[setup] MT5 terminal installed."
fi

if [ ! -f "${WINE_PY}" ]; then
    echo "[setup] Installing Windows Python ${PY_VER} under Wine…"
    [ -f "${PY_EXE}" ] || wget -qO "${PY_EXE}" \
        "https://www.python.org/ftp/python/${PY_VER}/python-${PY_VER}-amd64.exe"
    wine "${PY_EXE}" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    sleep 5
    [ -f "${WINE_PY}" ] || { echo "[setup] Python install FAILED"; exit 1; }
fi

# Bridge deps inside Wine Python (MetaTrader5 must live NEXT to the terminal).
if ! wine "${WINE_PY}" -c "import MetaTrader5, flask, requests, dotenv" 2>/dev/null; then
    echo "[setup] Installing bridge requirements into Wine Python…"
    wine "${WINE_PY}" -m pip install --no-warn-script-location \
        MetaTrader5 flask requests python-dotenv || \
    { echo "[setup] pip install FAILED"; exit 1; }
fi

echo "[setup] Ready. Terminal login: open noVNC (port 6080) the first time."
kill %1 2>/dev/null || true   # supervisord owns Xvfb from here

exec /usr/bin/supervisord -n -c /etc/supervisor/supervisord.conf
