"""
Hybrid GitHub README RAG - Interactive Terminal Chatbot
======================================================
Provides a direct terminal chat interface with:
 - Interactive prompt with multi-turn conversation memory
 - Structured source citations per response
 - Slash commands: /repo, /sync, /status, /clear, /help, /exit
 - Automatic backend discovery & connection validation
"""

import sys
import os
import time
import requests

BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:18080")

# ANSI Color codes for Windows Command Prompt & PowerShell
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def print_banner():
    print(CYAN + "=" * 70 + RESET)
    print(BOLD + CYAN + "   🤖 HYBRID GITHUB README RAG - INTERACTIVE TERMINAL CHATBOT" + RESET)
    print(CYAN + "=" * 70 + RESET)
    print(DIM + f" Connected Backend : {BACKEND_URL}" + RESET)
    print(DIM + " Grounded in       : GitHub Repository README.md Only" + RESET)
    print(DIM + " Inference Cascade : Local Laptop LLM -> Cloud Fallback Providers" + RESET)
    print(CYAN + "-" * 70 + RESET)
    print(YELLOW + " Special Commands:" + RESET)
    print("   " + BOLD + "/repo <url>" + RESET + "  -> Switch target repository & index README")
    print("   " + BOLD + "/sync" + RESET + "        -> Re-sync & refresh current README")
    print("   " + BOLD + "/status" + RESET + "      -> View repository & model status")
    print("   " + BOLD + "/clear" + RESET + "       -> Clear current conversation context")
    print("   " + BOLD + "/help" + RESET + "        -> Display this command list")
    print("   " + BOLD + "exit / quit" + RESET + "  -> Exit chatbot")
    print(CYAN + "=" * 70 + RESET + "\n")


def check_backend_health():
    try:
        r = requests.get(f"{BACKEND_URL}/api/health", timeout=3.0)
        if r.status_code == 200:
            data = r.json()
            return True, data.get("indexed_chunks", 0)
    except Exception:
        pass
    return False, 0


def fetch_github_status():
    try:
        r = requests.get(f"{BACKEND_URL}/api/github/status", timeout=3.0)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        return {"error": str(e)}
    return {}


def sync_repository(repo_url: str, branch: str = None, token: str = None):
    payload = {"repo_url": repo_url, "force": True}
    if branch:
        payload["branch"] = branch
    if token:
        payload["token"] = token

    print(YELLOW + f"[*] Fetching and indexing README for '{repo_url}'..." + RESET)
    try:
        r = requests.post(f"{BACKEND_URL}/api/github/sync", json=payload, timeout=20.0)
        if r.status_code == 200:
            data = r.json()
            print(GREEN + f"[✓] {data.get('message', 'Synchronized successfully.')}" + RESET)
            print(DIM + f"    SHA: {data.get('sha')} | Chunks indexed: {data.get('chunks_indexed')}" + RESET)
        else:
            print(RED + f"[✗] Sync failed ({r.status_code}): {r.text}" + RESET)
    except Exception as e:
        print(RED + f"[✗] Connection error during sync: {e}" + RESET)


def ask_question(question: str, conversation_history: list):
    payload = {
        "message": question,
        "conversation": conversation_history[-6:],  # Keep recent turns
    }

    try:
        t0 = time.time()
        r = requests.post(f"{BACKEND_URL}/api/chat", json=payload, timeout=40.0)
        elapsed = round(time.time() - t0, 2)

        if r.status_code == 200:
            res = r.json()
            answer = res.get("answer", "")
            provider = res.get("provider", "unknown")
            model = res.get("model", "")
            failover = res.get("failover", False)
            sources = res.get("sources", [])

            # Display provider tag
            if provider == "local":
                badge = GREEN + f"[🤖 LOCAL LLM ({model}) - {elapsed}s]" + RESET
            else:
                badge = MAGENTA + f"[☁️ CLOUD FALLBACK: {provider.upper()} ({model}) - {elapsed}s]" + RESET

            print(f"\n{badge}")
            print(BOLD + "\n" + answer.strip() + RESET + "\n")

            # Display citations
            if sources:
                print(DIM + "📚 Sources Grounding:" + RESET)
                for s in sources:
                    sec = s.get("section", "Overview")
                    filename = s.get("file", "README.md")
                    print(DIM + f"   • {filename} ➔ {sec}" + RESET)
            print()

            # Append to history
            conversation_history.append({"role": "user", "content": question})
            conversation_history.append({"role": "assistant", "content": answer})

        else:
            err_msg = r.text
            try:
                err_msg = r.json().get("detail", err_msg)
            except Exception:
                pass
            print(RED + f"\n[✗] Error ({r.status_code}): {err_msg}\n" + RESET)

    except requests.exceptions.Timeout:
        print(RED + "\n[✗] Request timed out. Backend or LLM provider took too long to respond.\n" + RESET)
    except Exception as e:
        print(RED + f"\n[✗] Failed to communicate with backend: {e}\n" + RESET)


def main():
    # Enable ANSI escape sequence processing on Windows command prompt
    os.system("")

    print_banner()

    # Check backend connectivity
    is_healthy, chunks = check_backend_health()
    if not is_healthy:
        print(RED + f"[!] Warning: Cannot reach Backend API at {BACKEND_URL}" + RESET)
        print(YELLOW + "    Make sure the backend server is running (e.g. run 'start_backend_server.bat').\n" + RESET)
    else:
        status_info = fetch_github_status()
        active_repo = status_info.get("repo_url", "tiangolo/fastapi")
        print(GREEN + f"[✓] Backend Connected | Active Knowledge Base: {active_repo} ({chunks} chunks)" + RESET + "\n")

    conversation_history = []

    while True:
        try:
            prompt_str = BOLD + CYAN + "You > " + RESET
            user_input = input(prompt_str).strip()

            if not user_input:
                continue

            if user_input.lower() in ["exit", "quit", "q"]:
                print(YELLOW + "\nGoodbye! 👋\n" + RESET)
                break

            if user_input.lower() in ["/help", "help", "?"]:
                print("\n" + YELLOW + "Commands Available:" + RESET)
                print("  /repo <url>    - Switch and index a new GitHub repo README")
                print("  /sync          - Force re-fetch current repository README")
                print("  /status        - Check repository and service status")
                print("  /clear         - Clear conversation context history")
                print("  exit           - Exit chatbot\n")
                continue

            if user_input.lower() == "/clear":
                conversation_history.clear()
                print(GREEN + "[✓] Conversation history cleared.\n" + RESET)
                continue

            if user_input.lower() == "/status":
                status_info = fetch_github_status()
                print("\n" + CYAN + "--- Knowledge Base & Status ---" + RESET)
                print(f"  Repo URL:        {status_info.get('repo_url', 'N/A')}")
                print(f"  Branch:          {status_info.get('branch', 'default')}")
                print(f"  README SHA:      {status_info.get('sha', 'N/A')}")
                print(f"  Indexed Chunks:  {status_info.get('chunk_count', 0)}")
                print(f"  Status:          {status_info.get('status', 'N/A')}")
                print(CYAN + "-------------------------------\n" + RESET)
                continue

            if user_input.lower() == "/sync":
                status_info = fetch_github_status()
                current_url = status_info.get("repo_url")
                if current_url:
                    sync_repository(current_url)
                else:
                    print(YELLOW + "[!] No repository currently set. Use /repo <url>" + RESET)
                continue

            if user_input.startswith("/repo"):
                parts = user_input.split(maxsplit=1)
                if len(parts) < 2:
                    print(YELLOW + "[!] Please provide a repo URL: /repo https://github.com/owner/repo" + RESET)
                else:
                    new_repo = parts[1].strip()
                    sync_repository(new_repo)
                continue

            # Regular question
            ask_question(user_input, conversation_history)

        except (KeyboardInterrupt, EOFError):
            print(YELLOW + "\n\nSession terminated. Goodbye! 👋\n" + RESET)
            break


if __name__ == "__main__":
    main()
