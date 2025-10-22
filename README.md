# AzSubSpray

Quick script to rapidly enumerate available Azure subscriptions provided a list of valid credentials.
Use cases include:
- Lateral movement attempts after password spraying
- Pivot to cloud infrastructure following on-prem compromise

The tool supports custom client ID and User-Agent headers for CAP bypasses.

```
== AzSubspray ==
usage: azsubspray.py [-h] [--client-id CLIENT_ID] [--user-agent USER_AGENT] userpassfile

Spray Azure accounts to list subscriptions via ROPC.

positional arguments:
  userpassfile          File with username:password per line

options:
  -h, --help            show this help message and exit
  --client-id CLIENT_ID
                        Override the Azure AD client ID
  --user-agent USER_AGENT
                        Custom User-Agent for subscription request
```