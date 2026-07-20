# MT5 bridge without Windows: the Windows MT5 terminal + Windows Python + our
# Flask bridge run under Wine inside this Linux container. cloudflared runs as
# a compose sidecar. You log into the terminal from any browser via noVNC.
#
# IMPORTANT: x86_64 only. On an Apple Silicon Mac, Docker would emulate x86
# (slow, fragile) — host this on a cheap x86 Linux VPS instead (~$5/mo).
#
# First run: `docker compose -f docker-compose.mt5.yml up`, open
# http://localhost:6080, log the terminal into your broker, enable Algo
# Trading (Ctrl+E). The wine prefix persists in a named volume, so login
# and installation survive restarts.

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    WINEPREFIX=/root/.wine \
    WINEARCH=win64 \
    WINEDEBUG=-all \
    DISPLAY=:99

# Wine (WineHQ stable), virtual display, VNC + noVNC, supervisor.
RUN apt-get update && apt-get install -y --no-install-recommends \
        wget ca-certificates gnupg2 software-properties-common \
        xvfb x11vnc novnc websockify supervisor curl unzip \
    && dpkg --add-architecture i386 \
    && mkdir -p /etc/apt/keyrings \
    && wget -qO /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key \
    && wget -qNP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/ubuntu/dists/jammy/winehq-jammy.sources \
    && apt-get update \
    && apt-get install -y --install-recommends winehq-stable \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Installers are fetched at container FIRST RUN (not build) so the image stays
# small and the downloads land in the persistent wine volume:
#   - mt5setup.exe   from MetaQuotes (or your broker's build)
#   - python-3.12 amd64 installer from python.org
# See entrypoint.sh.

# The bridge source is bind-mounted from the repo (see compose) so `git pull`
# on the host updates it without rebuilding the image.
COPY entrypoint.sh /entrypoint.sh
COPY supervisord.conf /etc/supervisor/conf.d/mt5.conf
RUN chmod +x /entrypoint.sh

# 5000 bridge (Wine Flask), 6080 noVNC (browser login to the terminal)
EXPOSE 5000 6080

ENTRYPOINT ["/entrypoint.sh"]
