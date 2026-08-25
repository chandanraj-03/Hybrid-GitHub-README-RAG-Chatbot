"""
Hybrid GitHub README RAG - Cloudflare Tunnel Runner with Auto-Render Registration
=================================================================================
Runs cloudflared tunnel on port 16036, extracts the public HTTPS URL,
and automatically registers it with your deployed Render backend.
Automatically downloads official cloudflared.exe if not already installed.
"""

import os
import sys
import re
import shutil
import subprocess
import requests
import threading
import urllib.request

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND_ENV_PATH = os.path.join(PROJECT_ROOT, "backend", ".env")
LOCAL_CLOUDFLARED = os.path.join(PROJECT_ROOT, "cloudflared.exe")
LAPTOP_PORT = 16036
CLOUDFLARED_DOWNLOAD_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"


def load_env():
    config = {}
    if os.path.exists(BACKEND_ENV_PATH):
        with open(BACKEND_ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    config[k.strip()] = v.strip()
    return config


def download_cloudflared():
    """Downloads official standalone cloudflared.exe into the project root."""
    print(YELLOW + "\n[*] Downloading official Cloudflare Tunnel executable (cloudflared.exe)..." + RESET)
    print(DIM + f"    Source: {CLOUDFLARED_DOWNLOAD_URL}" + RESET)
    print(DIM + f"    Target: {LOCAL_CLOUDFLARED}" + RESET)

    def progress_hook(count, block_size, total_size):
        if total_size > 0:
            percent = int(count * block_size * 100 / total_size)
            downloaded_mb = count * block_size / (1024 * 1024)
            total_mb = total_size / (1024 * 1024)
            sys.stdout.write(f"\r{CYAN}[*] Downloading: {percent}% ({downloaded_mb:.1f} MB / {total_mb:.1f} MB){RESET}")
            sys.stdout.flush()

    try:
        urllib.request.urlretrieve(CLOUDFLARED_DOWNLOAD_URL, LOCAL_CLOUDFLARED, reporthook=progress_hook)
        print(GREEN + f"\n[✓] Successfully downloaded cloudflared.exe!" + RESET)
        return LOCAL_CLOUDFLARED
    except Exception as exc:
        print(RED + f"\n[✗] Failed to download cloudflared: {exc}" + RESET)
        print(YELLOW + "    You can run manually: winget install Cloudflare.cloudflared" + RESET)
        return None


def get_cloudflared_path():
    """Locates cloudflared executable in project root or system PATH, or downloads it."""
    if os.path.exists(LOCAL_CLOUDFLARED):
        return LOCAL_CLOUDFLARED

    system_path = shutil.which("cloudflared")
    if system_path:
        return system_path

    # Not found, download it automatically
    return download_cloudflared()


def register_tunnel_with_render(tunnel_url: str, render_url: str, token: str):
    render_url = render_url.rstrip("/")
    endpoint = f"{render_url}/api/admin/register-tunnel"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {"tunnel_url": tunnel_url}

    try:
        r = requests.post(endpoint, json=payload, headers=headers, timeout=10.0)
        if r.status_code == 200:
            print(GREEN + "\n" + "=" * 70 + RESET)
            print(BOLD + GREEN + "  [✓] SUCCESS: Tunnel registered automatically with Render Backend!" + RESET)
            print(GREEN + f"      Render Backend : {render_url}" + RESET)
            print(GREEN + f"      Laptop Tunnel  : {tunnel_url}" + RESET)
            print(GREEN + "      Queries to Render will now process on your Laptop GPU for FREE!" + RESET)
            print(GREEN + "=" * 70 + "\n" + RESET)
        else:
            print(YELLOW + f"\n[!] Render responded with HTTP {r.status_code}: {r.text}" + RESET)
    except Exception as exc:
        print(YELLOW + f"\n[!] Could not auto-register with Render at {render_url}: {exc}" + RESET)
        print(DIM + "    You can still manually set LAPTOP_API_URL in Render Dashboard." + RESET)


def main():
    os.system("")
    print(CYAN + "=" * 70 + RESET)
    print(BOLD + CYAN + "     CLOUDFLARE QUICK TUNNEL + RENDER AUTO-SYNC" + RESET)
    print(CYAN + "=" * 70 + RESET)

    cfg = load_env()
    token = cfg.get("LAPTOP_API_TOKEN", "secret-laptop-token")
    render_url = cfg.get("RENDER_BACKEND_URL", "")

    if not render_url:
        print(YELLOW + "[i] Note: RENDER_BACKEND_URL is not saved in backend/.env yet." + RESET)
        print("    If your backend is already deployed on Render, enter its URL below.")
        print("    (Example: https://hybrid-github-rag-backend.onrender.com)")
        user_render = input(BOLD + "Render Backend URL (press Enter to skip): " + RESET).strip()
        if user_render:
            render_url = user_render
            try:
                with open(BACKEND_ENV_PATH, "a", encoding="utf-8") as f:
                    f.write(f"\nRENDER_BACKEND_URL={render_url}\n")
                print(GREEN + f"[✓] Saved RENDER_BACKEND_URL to backend/.env" + RESET)
            except Exception:
                pass

    cloudflared_bin = get_cloudflared_path()
    if not cloudflared_bin or not os.path.exists(cloudflared_bin):
        print(RED + "\n[✗] Could not find or download cloudflared.exe." + RESET)
        input("Press Enter to exit...")
        return

    print(CYAN + f"[*] Launching Cloudflare Tunnel using: {cloudflared_bin}" + RESET)
    print(CYAN + f"[*] Tunneling target: http://localhost:{LAPTOP_PORT}..." + RESET)

    cmd = [cloudflared_bin, "tunnel", "--url", f"http://localhost:{LAPTOP_PORT}"]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except Exception as e:
        print(RED + f"\n[✗] Error starting tunnel process: {e}" + RESET)
        input("Press Enter to exit...")
        return

    tunnel_url_found = False

    try:
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()

            if not tunnel_url_found:
                match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
                if match:
                    tunnel_url = match.group(0)
                    tunnel_url_found = True
                    print(BOLD + MAGENTA + f"\n[➔] Discovered Tunnel URL: {tunnel_url}" + RESET)
                    if render_url:
                        threading.Thread(
                            target=register_tunnel_with_render,
                            args=(tunnel_url, render_url, token),
                            daemon=True,
                        ).start()
    except KeyboardInterrupt:
        print(YELLOW + "\nStopping tunnel..." + RESET)
        proc.terminate()


if __name__ == "__main__":
    main()
