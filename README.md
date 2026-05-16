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
│   ├── IREPS_scraping_gui.py      # Single-file CustomTkinter configuration and scraper portal
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

- Python 3.10, 3.11, 3.12, or 3.13 recommended. The dependency list has been updated for Python 3.13-compatible wheels and now uses the PyTorch CAPTCHA solver dependency that the scraper imports.
- Google Chrome installed.
- ChromeDriver-compatible browser automation support. The scraper uses `chromedriver-autoinstaller`.
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
python IREPS_scraping_gui.py
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

Run `build_exe.bat` on Windows to create a copy-paste portable build:

- `IREPS_Tenders_Portable/` - folder to copy to another Windows computer.
- `IREPS_Tenders_Portable.zip` - zipped copy of the same portable folder.
- `IREPS_Tenders_Portable/Start_IREPS_Tenders.bat` - launcher for the GUI EXE.
- `IREPS_Tenders_Portable/IREPS_scraping_gui.exe` - GUI/configuration editor.
- `IREPS_Tenders_Portable/IREPS_Tenders.exe` - scraper engine launched by the GUI.
- `IREPS_Tenders_Portable/Program_Files/` - runtime configuration, organization list, CAPTCHA model, and scraper support files.

Copy the whole `IREPS_Tenders_Portable` folder, or unzip `IREPS_Tenders_Portable.zip`, onto the target Windows computer and run `Start_IREPS_Tenders.bat` or `IREPS_scraping_gui.exe`. Keep `Program_Files` beside the EXE files; the GUI and scraper read/write `Configration.json`, `Organization_list.txt`, logs, temporary files, and output workbooks relative to the EXE folder. Google Chrome is still required on the target computer for Selenium browser automation.

## Troubleshooting

- **Dashboard cannot find data:** Start it from `Analysis/`, or update `directory_path` in `Analysis/script.py`.
- **Selenium/Chrome errors:** Confirm Chrome is installed and compatible with the ChromeDriver resolved by `chromedriver-autoinstaller`.
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
