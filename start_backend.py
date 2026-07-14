import os
import sys
import subprocess

# Change to the project directory (this script's own location), so the launcher
# works from any checkout instead of a machine-specific hardcoded path.
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Start uvicorn as a completely detached process
proc = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000', '--log-level', 'info'],
    stdout=open('backend.log', 'a'),
    stderr=subprocess.STDOUT,
    start_new_session=True,
    close_fds=True,
)

print(f"Started backend with PID {proc.pid}")
