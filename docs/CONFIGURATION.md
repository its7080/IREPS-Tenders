# Scraper Configuration Guide

The scraper is configured with two files under `Scraping/Program_Files/`:

- `Configration.json` controls runtime behavior.
- `Organization_list.txt` controls which IREPS organizations are scraped.

> The filename is currently spelled `Configration.json` in the code. Rename it only if the Python references are updated at the same time.

## Editing configuration

### GUI editor

From the `Scraping/` directory, run:

```bash
python IREPS_scraping_gui.py
```

The modern single-file editor provides:

- the same top bar, left status panel, organization-card list, right workspace, and bottom status bar layout as `scraping_gui.py`
- tabbed configuration and organization editors
- a live log tab with export/clear controls
- background scraper launch controls that keep the UI responsive
- dark/light mode and quick output-folder access

### Manual editing

You can also edit both files directly in a text editor. Keep JSON syntax valid and avoid trailing commas.

## `Configration.json` fields

| Field | Purpose |
| --- | --- |
| `browser` | Browser mode. In the scraper, `0` enables headless Chrome and other values run visible Chrome. |
| `adb_device` | Enables/disables Android Debug Bridge integration for OTP-related workflows. |
| `captcha_manual_input` | Controls whether CAPTCHA is handled manually or through the automated solver path. |
| `adb_device_ip` | IP address used when connecting to an Android device over ADB. |
| `sender_email_id` | Sender email address for notifications. Treat as secret/runtime config. |
| `sender_email_password` | Sender email password or app password. Treat as secret/runtime config. |
| `notification_emailids` | Email addresses for operational notifications. |
| `receiver_emailids` | Email addresses that receive final result messages. |
| `dump_location` | Directory where merged output workbooks are copied/written. |
| `mobile_no` | Mobile number used for IREPS guest login/OTP. Treat as sensitive. |
| `otp_date` | Date associated with the current OTP value. |
| `otp` | OTP value used during login. Treat as sensitive and short-lived. |
| `signal_datelog` | Internal signal value reset by the scraper at startup. |
| `signal_ireps` | Internal signal value reset by the scraper at startup. |

## Organization list format

`Organization_list.txt` uses one organization per line:

```text
10: RAIL VIKAS NIGAM LIMITED
15: IRCON INTERNATIONAL LIMITED
```

Comment out an organization with `#`:

```text
#18: KOLKATA METRO RAIL CORPORATION LTD
```

Rules:

- Keep the format as `organization_number: organization_name`.
- Lines beginning with `#` are ignored.
- Blank lines are ignored.
- The organization number must match the value expected by the IREPS organization dropdown.

## Working-directory expectations

Run the scraper and configuration editor from the `Scraping/` directory unless paths are made absolute. Several paths are currently relative to that application folder.

## Secret-management recommendation

Do not commit production values for:

- SMTP usernames/passwords
- OTPs
- mobile numbers
- recipient lists
- ADB/device IP addresses
- internal dump paths

Recommended future approaches:

1. Keep a safe `Configration.example.json` in Git.
2. Add the real `Configration.json` to `.gitignore`.
3. Load secrets from environment variables or a local untracked `.env` file.
4. Rotate any credentials that were committed historically.
