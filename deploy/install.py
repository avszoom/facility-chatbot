"""Install an already verified release on Amazon Linux. Run as root via SSM.

No credentials belong in this script, its arguments, or the release archive.
"""
from pathlib import Path
import os
import secrets
import shutil
import subprocess
import sys


def run(*args):
    subprocess.run(args, check=True)


def main():
    release = Path(sys.argv[1]).resolve()
    hostname = sys.argv[2]
    if not hostname or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789.-" for c in hostname):
        raise ValueError("Invalid public hostname")
    run("/opt/buildingops/venv/bin/pip", "install", "-r", str(release / "deploy/requirements.txt"))
    run("/opt/buildingops/venv/bin/pip", "install", "--no-deps", str(release))
    current = Path("/opt/buildingops/current")
    pending = Path("/opt/buildingops/current.new")
    pending.unlink(missing_ok=True)
    pending.symlink_to(release)
    pending.replace(current)
    env_path = Path("/etc/buildingops/application.env")
    if not env_path.exists():
        shutil.copyfile(release / "deploy/buildingops.env.example", env_path)
        env_path.chmod(0o600)
    # There is deliberately no seed_demo invocation: cloud starts empty.
    run("install", "-m", "644", str(release / "deploy/buildingops@.service"), "/etc/systemd/system/buildingops@.service")
    run("install", "-m", "644", str(release / "deploy/caddy.service"), "/etc/systemd/system/caddy.service")
    if subprocess.run(["id", "caddy"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
        run("useradd", "--system", "--home-dir", "/var/lib/caddy", "--create-home", "caddy")
    run("install", "-d", "-m", "750", "-o", "caddy", "-g", "caddy", "/etc/caddy", "/var/lib/caddy")
    credentials = Path("/etc/buildingops/reviewer-credentials")
    if not credentials.exists():
        fd = os.open(credentials, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write("reviewer:" + secrets.token_urlsafe(24) + "\n")
    username, password = credentials.read_text().strip().split(":", 1)
    password_hash = subprocess.check_output(
        ["/usr/local/bin/caddy", "hash-password"], input=(password + "\n").encode()
    ).decode().strip()
    caddyfile = f"""{hostname} {{
    encode zstd gzip
    basic_auth {{
        {username} {password_hash}
    }}
    header {{
        X-Content-Type-Options nosniff
        Referrer-Policy same-origin
        X-Frame-Options DENY
        -Server
    }}
    handle /api/* {{
        reverse_proxy 127.0.0.1:8000 {{
            flush_interval -1
        }}
    }}
    handle {{
        root * /opt/buildingops/current/frontend/dist
        try_files {{path}} /index.html
        file_server
    }}
}}
"""
    config = Path("/etc/caddy/Caddyfile")
    config.write_text(caddyfile)
    run("chown", "root:caddy", str(config))
    config.chmod(0o640)
    run("/usr/local/bin/caddy", "validate", "--config", str(config), "--adapter", "caddyfile")
    run("systemctl", "daemon-reload")
    for service in ["buildingops@scripts.run_operations", "buildingops@backend.app.scheduling.local_simulator", "caddy"]:
        run("systemctl", "enable", service)
        run("systemctl", "restart", service)
    print("Installed stage 1. Reviewer credentials are root-readable only; no credentials printed.")


if __name__ == "__main__":
    main()
