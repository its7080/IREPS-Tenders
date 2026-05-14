# IREPS Tenders Automation

IREPS Tenders Automation is a Python project for collecting Indian Railways E-Procurement System (IREPS) tender information, merging the scraped tender data into Excel workbooks, sending result notifications, and visualizing tender trends in a Dash dashboard.

The repository contains two related applications:

- **Scraping application** (`Scraping/`): uses Selenium and helper utilities to open IREPS, log in with a mobile OTP flow, iterate configured organizations and zones, download/parse tender details, write Excel outputs, merge workbooks, and send summary emails.
- **Analysis dashboard** (`Analysis/`): reads generated Excel files and serves a local Dash dashboard with tender tables, metric cards, filters, and charts.

> **Security note:** The current repository contains local runtime configuration files. Before sharing, deploying, or publishing this project, move credentials, mobile numbers, OTPs, SMTP passwords, and recipient lists out of tracked files and into environment variables or an ignored local config file.

## Repository layout

```text
.
├── Analysis/
│   ├── data/                     # Sample/previous merged IREPS Excel files
│   └── script.py                 # Dash dashboard
├── Scraping/
│   ├── IREPS_Tenders.py          # Main scraper/orchestrator
│   ├── configuration-editor.py   # Modern CustomTkinter configuration portal
│   └── Program_Files/
│       ├── Configration.json     # Runtime configuration
│       ├── Organization_list.txt # Enabled/disabled organization list
│       ├── captcha_model.pth     # CAPTCHA model weights
│       ├── captcha_solver.py     # CAPTCHA training/prediction utilities
│       └── scraping_library.py   # Shared scraper helpers
├── docs/
│   ├── CONFIGURATION.md          # Configuration reference
│   └── DASHBOARD.md              # Dashboard usage notes
├── Commands.md                   # Minimal setup commands
├── run_menu.bat                  # Windows menu runner for venv-backed scripts
└── requirements.txt              # Unified project dependency list
```

## Prerequisites

The project was written for a desktop automation environment and has several external runtime requirements:

- Python 3.10+ recommended.
- Playwright Chromium runtime installed. Install Python dependencies, then run `python -m playwright install chromium` once on the target machine.
- Internet access to reach IREPS.
- A valid IREPS guest/mobile OTP workflow.
- Optional: Android Debug Bridge (`adb`) if OTP retrieval is configured through a connected Android device.
- Optional: Tesseract/PDF tooling depending on the parsing mode and environment.
- Optional: Windows environment for the prebuilt `.exe` files and Windows-specific dependencies in the pinned requirements.

## Installation

Create and activate a virtual environment, then install dependencies.

### Windows PowerShell

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Linux/macOS shell

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

The project now uses one unified dependency file at the repository root. Install dependencies from the root before running either the scraper or the dashboard.

### Windows menu runner

Windows users can also launch the menu-based runner from the repository root:

```bat
run_menu.bat
```

The menu uses `venv` as the virtual environment folder, can create/update that environment, installs `requirements.txt`, and launches the configuration editor, scraper, dashboard, CAPTCHA utility, or an activated command prompt.

## Configuration

The scraper reads its runtime settings from:

- `Scraping/Program_Files/Configration.json`
- `Scraping/Program_Files/Organization_list.txt`

Use the modern CustomTkinter GUI portal when running in a desktop environment:

```bash
cd Scraping
python configuration-editor.py
```

The portal supports dark/light mode, status cards, tabbed settings, live log streaming, and a threaded scraper launcher. You can also edit the files manually. See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for a field-by-field overview and organization-list format.

## Running the scraper

From the `Scraping/` directory:

```bash
python IREPS_Tenders.py
```

High-level execution flow:

1. Load configuration and active organizations.
2. Reset internal run signals in the configuration file.
3. Check internet connectivity.
4. Optionally check/connect an Android device through ADB.
5. Open IREPS with Selenium/Chrome.
6. Validate OTP and log in.
7. Iterate configured organizations and available zones.
8. Download and parse tender data.
9. Write organization/zone workbooks and merged master workbooks.
10. Send notification/result email when configured and triggered.

Generated outputs are written under configured dump locations and under `Scraping/Program_Files/`.

## Running the dashboard

The dashboard expects Excel files in `Analysis/data/` and should be started from the `Analysis/` directory because the data directory is currently configured as a relative path.

```bash
cd Analysis
python script.py
```

Then open the local Dash URL printed in the terminal, typically:

```text
http://127.0.0.1:8050/
```

See [docs/DASHBOARD.md](docs/DASHBOARD.md) for expected columns and dashboard behavior.

## Data format

Generated workbooks are expected to contain tender records with columns such as:

- `Zone`
- `Dept.`
- `Tender No.`
- `Tender Title`
- `Type`
- `Due Date/Time`
- `Due Days`
- `Advertised Value`
- `Doc Link`
- `Bidding type`
- `Bidding System`
- `Date Time Of Uploading Tender`
- `Pre-Bid Conference Date Time`
- `Earnest Money (Rs.)`
- `Contract Type`
- `Get Date`

The dashboard de-duplicates rows by `Tender No.`.

## Packaging notes

The repository includes prebuilt Windows executables:

- `Scraping/IREPS_Tenders.exe`
- `Scraping/configuration-editor.exe`

The dependency files also include `pyinstaller`, so these executables were likely built from the Python scripts. If rebuilding, prefer doing so in a clean virtual environment that matches the target operating system.

## Troubleshooting

- **Dashboard cannot find data:** Start it from `Analysis/`, or update `directory_path` in `Analysis/script.py`.
- **Playwright/Chromium errors:** Run `python -m playwright install chromium` and confirm the machine can launch Chromium in headed or headless mode.
- **OTP/login fails:** Confirm `mobile_no`, OTP date, OTP value, and ADB/manual OTP settings in `Configration.json`.
- **ADB device not detected:** Confirm USB debugging is enabled, the device is trusted, and `adb devices` lists it.
- **No organizations are scraped:** Confirm active lines in `Organization_list.txt` are not commented with `#` and follow `number: name` format.
- **Emails fail:** Confirm SMTP credentials, sender, recipients, network access, and provider security settings.

## Maintenance recommendations

- Move secrets out of tracked files.
- Add automated tests around Excel parsing/merging and dashboard data loading.
- Avoid import-time writes to configuration files where possible.
- Consider splitting scraper settings into environment-specific local config files.
- Add `.gitignore` rules for generated logs, temp downloads, local dumps, and credentials.
