import os
import sys
import subprocess

# Change to project directory
os.chdir('/Users/hsharma5/Documents/Kimi/Workspaces/ICTOS_KB/ict-trading-os')

# Start uvicorn as a completely detached process
proc = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000', '--log-level', 'info'],
    stdout=open('backend.log', 'a'),
    stderr=subprocess.STDOUT,
    start_new_session=True,
    close_fds=True,
)

print(f"Started backend with PID {proc.pid}")
