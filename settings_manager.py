"""
Hybrid GitHub README RAG - Settings Manager
===========================================
Interactive console utility to view and configure environment settings
for backend/.env and laptop/.env.
"""

import os
import sys
import requests

BACKEND_ENV_PATH = os.path.join(os.path.dirname(__file__), "backend", ".env")
LAPTOP_ENV_PATH = os.path.join(os.path.dirname(__file__), "laptop", ".env")

# ANSI Color codes
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def load_env_dict(path):
    config = {}
    if not os.path.exists(path):
        return config
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                config[k.strip()] = v.strip()
    return config


def save_env_dict(path, config):
    lines = []
    keys_written = set()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("#") or not stripped:
                    lines.append(line)
                elif "=" in stripped:
                    k, _ = stripped.split("=", 1)
                    k = k.strip()
                    if k in config:
                        lines.append(f"{k}={config[k]}\n")
                        keys_written.add(k)
                    else:
                        lines.append(line)
    for k, v in config.items():
        if k not in keys_written:
            lines.append(f"{k}={v}\n")

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def display_current_settings():
    b_cfg = load_env_dict(BACKEND_ENV_PATH)
    l_cfg = load_env_dict(LAPTOP_ENV_PATH)

    print(CYAN + "=" * 65 + RESET)
    print(BOLD + "             CURRENT CONFIGURATION & SETTINGS" + RESET)
    print(CYAN + "=" * 65 + RESET)
    print(BOLD + "1. GitHub Knowledge Base:" + RESET)
    print(f"   • Repository URL : {b_cfg.get('GITHUB_REPO_URL', 'Not set')}")
    print(f"   • Target Branch  : {b_cfg.get('GITHUB_BRANCH', 'Default branch')}")
    print(f"   • GitHub Token   : {'***' + b_cfg.get('GITHUB_TOKEN')[-4:] if b_cfg.get('GITHUB_TOKEN') else 'None (Public repos)'}")
    print()
    print(BOLD + "2. Local Laptop LLM Service:" + RESET)
    print(f"   • Local Model    : {l_cfg.get('LOCAL_MODEL_NAME', 'Qwen/Qwen2.5-0.5B-Instruct')}")
    print(f"   • Device Mode    : {l_cfg.get('DEVICE', 'auto')}")
    print(f"   • Laptop Port    : {l_cfg.get('PORT', '6036')}")
    print(f"   • Laptop Auth    : {l_cfg.get('LAPTOP_API_TOKEN', 'secret-laptop-token')}")
    print(f"   • Local Timeout  : {b_cfg.get('LOCAL_LLM_TIMEOUT', '25.0')}s")
    print(f"   • Laptop URL     : {b_cfg.get('LAPTOP_API_URL', 'http://localhost:6036')}")
    print()
    print(BOLD + "3. Cloud Fallback Keys:" + RESET)
    print(f"   • Gemini API Key : {'Configured ✓' if b_cfg.get('GEMINI_API_KEY') else 'Not set (Optional)'}")
    print(f"   • Grok API Key   : {'Configured ✓' if b_cfg.get('GROK_API_KEY') else 'Not set (Optional)'}")
    print(f"   • OpenRouter Key : {'Configured ✓' if b_cfg.get('OPENROUTER_API_KEY') else 'Not set (Optional)'}")
    print(f"   • Cascade Order  : {b_cfg.get('FALLBACK_CASCADE_ORDER', 'local,gemini,grok,openrouter')}")
    print(CYAN + "=" * 65 + RESET + "\n")


def update_setting(key, value, target="backend"):
    path = BACKEND_ENV_PATH if target == "backend" else LAPTOP_ENV_PATH
    cfg = load_env_dict(path)
    cfg[key] = value
    save_env_dict(path, cfg)
    print(GREEN + f"[✓] Updated {key} = '{value}'" + RESET)


def test_services():
    l_cfg = load_env_dict(LAPTOP_ENV_PATH)
    laptop_port = l_cfg.get("PORT", "6036")
    print(CYAN + "\n[*] Testing service health..." + RESET)
    # 1. Laptop server
    try:
        r = requests.get(f"http://127.0.0.1:{laptop_port}/health", timeout=3.0)
        if r.status_code == 200:
            data = r.json()
            print(GREEN + f"[✓] Laptop LLM Service (Port {laptop_port}): ONLINE (Model: {data.get('model')})" + RESET)
        else:
            print(YELLOW + f"[!] Laptop LLM Service returned status {r.status_code}" + RESET)
    except Exception:
        print(RED + f"[✗] Laptop LLM Service (Port {laptop_port}): OFFLINE" + RESET)

    # 2. Backend server
    try:
        r = requests.get("http://127.0.0.1:8080/api/health", timeout=3.0)
        if r.status_code == 200:
            data = r.json()
            print(GREEN + f"[✓] Backend Server (Port 8080): ONLINE (Indexed chunks: {data.get('indexed_chunks')})" + RESET)
        else:
            print(YELLOW + f"[!] Backend Server returned status {r.status_code}" + RESET)
    except Exception:
        print(RED + "[✗] Backend Server (Port 8080): OFFLINE" + RESET)
    print()


def main():
    os.system("")
    while True:
        display_current_settings()
        print(BOLD + "Configure Options:" + RESET)
        print("  [1] Change Knowledge Base GitHub Repository URL")
        print("  [2] Set/Update Google Gemini API Key")
        print("  [3] Set/Update xAI Grok API Key")
        print("  [4] Set/Update OpenRouter API Key")
        print("  [5] Change Local Model or Device Mode (CUDA/CPU)")
        print("  [6] Change Local LLM Port & Timeout")
        print("  [7] Test Service Connectivity (Health Probe)")
        print("  [0] Back / Exit")
        print()

        choice = input(BOLD + CYAN + "Select an option [0-7]: " + RESET).strip()

        if choice == "0":
            break
        elif choice == "1":
            val = input("Enter new GitHub Repo URL (e.g. https://github.com/facebook/react): ").strip()
            if val:
                update_setting("GITHUB_REPO_URL", val, "backend")
        elif choice == "2":
            val = input("Enter Gemini API Key (or empty to clear): ").strip()
            update_setting("GEMINI_API_KEY", val, "backend")
        elif choice == "3":
            val = input("Enter Grok API Key (or empty to clear): ").strip()
            update_setting("GROK_API_KEY", val, "backend")
        elif choice == "4":
            val = input("Enter OpenRouter API Key (or empty to clear): ").strip()
            update_setting("OPENROUTER_API_KEY", val, "backend")
        elif choice == "5":
            print("\nAvailable models (or enter custom HuggingFace identifier):")
            print("  1. Qwen/Qwen2.5-0.5B-Instruct (Default, fast & lightweight)")
            print("  2. TinyLlama/TinyLlama-1.1B-Chat-v1.0")
            print("  3. Qwen/Qwen2.5-1.5B-Instruct")
            m_choice = input("Enter model identifier or number [1-3]: ").strip()
            m_map = {
                "1": "Qwen/Qwen2.5-0.5B-Instruct",
                "2": "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
                "3": "Qwen/Qwen2.5-1.5B-Instruct",
            }
            chosen_model = m_map.get(m_choice, m_choice)
            if chosen_model:
                update_setting("LOCAL_MODEL_NAME", chosen_model, "laptop")
        elif choice == "6":
            port_val = input("Enter laptop port [default 6036]: ").strip()
            if port_val:
                update_setting("PORT", port_val, "laptop")
                update_setting("LAPTOP_API_URL", f"http://localhost:{port_val}", "backend")
            to_val = input("Enter timeout in seconds (e.g. 25.0): ").strip()
            if to_val:
                update_setting("LOCAL_LLM_TIMEOUT", to_val, "backend")
        elif choice == "7":
            test_services()

        input(DIM + "\nPress Enter to continue..." + RESET)


if __name__ == "__main__":
    main()
