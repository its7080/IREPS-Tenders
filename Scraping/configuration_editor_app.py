"""Modern Windows desktop configuration portal for the IREPS scraper.

The UI is intentionally built around small reusable widgets so the editor can grow
without becoming another monolithic Tkinter script.  It keeps the original editor
capabilities (edit Configration.json, edit Organization_list.txt, and show help)
while adding a responsive CustomTkinter shell, live log console, and background
scraper launcher.
"""

from __future__ import annotations

import json
import queue
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from tkinter import StringVar, messagebox
from typing import Any

import customtkinter as ctk


APP_TITLE = "IREPS Tender Control Center"
CONFIG_FILENAME = "Configration.json"
ORGANIZATION_FILENAME = "Organization_list.txt"
SCRAPER_FILENAME = "IREPS_Tenders.py"
TOGGLE_FIELDS = {"browser", "adb_device", "captcha_manual_input"}
LIST_FIELDS = {"notification_emailids", "receiver_emailids"}
SECRET_FIELDS = {"sender_email_password", "otp"}

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class ConfigStore:
    """Read and write the JSON and organization files used by the scraper."""

    def __init__(self, app_dir: Path) -> None:
        self.app_dir = app_dir
        self.program_files_dir = app_dir / "Program_Files"
        self.config_path = self.program_files_dir / CONFIG_FILENAME
        self.organization_path = self.program_files_dir / ORGANIZATION_FILENAME
        self.scraper_path = app_dir / SCRAPER_FILENAME

    def load_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        with self.config_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def save_config(self, data: dict[str, Any]) -> None:
        self.program_files_dir.mkdir(parents=True, exist_ok=True)
        with self.config_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)

    def load_organizations(self) -> str:
        if not self.organization_path.exists():
            raise FileNotFoundError(f"Organization list not found: {self.organization_path}")
        return self.organization_path.read_text(encoding="utf-8")

    def save_organizations(self, content: str) -> None:
        self.program_files_dir.mkdir(parents=True, exist_ok=True)
        self.organization_path.write_text(content.strip(), encoding="utf-8")

    @staticmethod
    def count_active_organizations(content: str) -> int:
        return sum(1 for line in content.splitlines() if line.strip() and not line.lstrip().startswith("#"))


class StatusCard(ctk.CTkFrame):
    """Compact portal card used in the left rail status area."""

    def __init__(self, master: ctk.CTkBaseClass, title: str, value: str, accent: str) -> None:
        super().__init__(master, corner_radius=18, fg_color=("#EEF3F8", "#172033"))
        self.grid_columnconfigure(0, weight=1)
        self.accent = ctk.CTkFrame(self, width=4, corner_radius=4, fg_color=accent)
        self.accent.grid(row=0, column=0, rowspan=2, sticky="nsw", padx=(12, 8), pady=14)
        self.title_label = ctk.CTkLabel(
            self,
            text=title.upper(),
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=("#5B6472", "#9DA8BA"),
            anchor="w",
        )
        self.title_label.grid(row=0, column=0, sticky="ew", padx=(28, 12), pady=(14, 0))
        self.value_label = ctk.CTkLabel(
            self,
            text=value,
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            anchor="w",
        )
        self.value_label.grid(row=1, column=0, sticky="ew", padx=(28, 12), pady=(0, 14))

    def set_value(self, value: str) -> None:
        self.value_label.configure(text=value)


class SettingsSection(ctk.CTkFrame):
    """Reusable settings card that hosts labeled controls."""

    def __init__(self, master: ctk.CTkBaseClass, title: str, subtitle: str) -> None:
        super().__init__(master, corner_radius=22, fg_color=("#F7F9FC", "#111827"))
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            self,
            text=title,
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=22, pady=(18, 0))
        ctk.CTkLabel(
            self,
            text=subtitle,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=("#697386", "#AAB4C3"),
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=22, pady=(2, 12))
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 18))
        self.body.grid_columnconfigure(1, weight=1)


class ScraperRunner:
    """Run the scraper in a background thread and stream output to a queue."""

    def __init__(self, store: ConfigStore, log_queue: queue.Queue[tuple[str, str]]) -> None:
        self.store = store
        self.log_queue = log_queue
        self.process: subprocess.Popen[str] | None = None
        self.thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def start(self) -> bool:
        if self.is_running:
            self.log_queue.put(("warning", "Scraper is already running."))
            return False
        self.thread = threading.Thread(target=self._run, name="IREPSScraperRunner", daemon=True)
        self.thread.start()
        return True

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.log_queue.put(("warning", "Stop requested. Terminating scraper process..."))
            self.process.terminate()

    def _run(self) -> None:
        if not self.store.scraper_path.exists():
            self.log_queue.put(("error", f"Scraper file not found: {self.store.scraper_path}"))
            return

        command = [sys.executable, str(self.store.scraper_path)]
        self.log_queue.put(("info", f"Starting scraper: {' '.join(command)}"))
        started_at = datetime.now()

        try:
            self.process = subprocess.Popen(
                command,
                cwd=str(self.store.app_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            if self.process.stdout:
                for line in self.process.stdout:
                    self.log_queue.put(("output", line.rstrip()))
            return_code = self.process.wait()
            elapsed = datetime.now() - started_at
            if return_code == 0:
                self.log_queue.put(("success", f"Scraper finished successfully in {elapsed}."))
            else:
                self.log_queue.put(("error", f"Scraper exited with code {return_code} after {elapsed}."))
        except Exception as exc:
            self.log_queue.put(("error", f"Unable to run scraper: {exc}"))
        finally:
            self.process = None


class IREPSControlCenter(ctk.CTk):
    """CustomTkinter application shell for scraper configuration and operations."""

    def __init__(self, store: ConfigStore) -> None:
        super().__init__()
        self.store = store
        self.data = self.store.load_config()
        self.organization_content = self.store.load_organizations()
        self.field_widgets: dict[str, tuple[str, Any]] = {}
        self.log_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.runner = ScraperRunner(store, self.log_queue)
        self.progress_active = False

        self.title(APP_TITLE)
        self.geometry("1280x780")
        self.minsize(1080, 680)
        self.configure(fg_color=("#EAF0F7", "#0B1020"))
        self._set_windows_icon()
        self._build_layout()
        self._refresh_status_cards()
        self._log("success", "Control Center ready.")
        self.after(120, self._drain_log_queue)

    def _set_windows_icon(self) -> None:
        icon_path = self.store.app_dir / "app_logo.ico"
        if sys.platform.startswith("win") and icon_path.exists():
            self.iconbitmap(str(icon_path))

    def _build_layout(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self._build_workspace()

    def _build_sidebar(self) -> None:
        self.sidebar = ctk.CTkFrame(self, width=310, corner_radius=0, fg_color=("#F8FBFF", "#0F172A"))
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(8, weight=1)
        self.sidebar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.sidebar,
            text="IREPS",
            font=ctk.CTkFont(family="Segoe UI Variable Display", size=34, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=26, pady=(30, 0))
        ctk.CTkLabel(
            self.sidebar,
            text="Tender Control Center",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color=("#536173", "#A7B0C0"),
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=28, pady=(0, 24))

        self.config_card = StatusCard(self.sidebar, "Configuration", "Loaded", "#60A5FA")
        self.config_card.grid(row=2, column=0, sticky="ew", padx=20, pady=7)
        self.org_card = StatusCard(self.sidebar, "Organizations", "0 active", "#34D399")
        self.org_card.grid(row=3, column=0, sticky="ew", padx=20, pady=7)
        self.scraper_card = StatusCard(self.sidebar, "Scraper", "Idle", "#F59E0B")
        self.scraper_card.grid(row=4, column=0, sticky="ew", padx=20, pady=7)
        self.theme_card = StatusCard(self.sidebar, "Theme", ctk.get_appearance_mode(), "#A78BFA")
        self.theme_card.grid(row=5, column=0, sticky="ew", padx=20, pady=7)

        action_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        action_frame.grid(row=6, column=0, sticky="ew", padx=20, pady=(18, 8))
        action_frame.grid_columnconfigure((0, 1), weight=1)
        self.run_button = ctk.CTkButton(
            action_frame,
            text="▶ Run Scraper",
            height=42,
            corner_radius=14,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            command=self.start_scraper,
        )
        self.run_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.stop_button = ctk.CTkButton(
            action_frame,
            text="■ Stop",
            height=42,
            corner_radius=14,
            fg_color=("#E11D48", "#BE123C"),
            hover_color=("#BE123C", "#9F1239"),
            state="disabled",
            command=self.stop_scraper,
        )
        self.stop_button.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        preferences = ctk.CTkFrame(self.sidebar, corner_radius=18, fg_color=("#EEF3F8", "#172033"))
        preferences.grid(row=7, column=0, sticky="ew", padx=20, pady=10)
        preferences.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(preferences, text="Appearance", font=ctk.CTkFont(size=14, weight="bold"), anchor="w").grid(
            row=0, column=0, sticky="ew", padx=16, pady=(14, 4)
        )
        self.appearance_menu = ctk.CTkOptionMenu(
            preferences,
            values=["System", "Dark", "Light"],
            command=self.change_appearance,
        )
        self.appearance_menu.set("System")
        self.appearance_menu.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))
        self.scaling_menu = ctk.CTkOptionMenu(
            preferences,
            values=["90%", "100%", "110%", "125%"],
            command=self.change_scaling,
        )
        self.scaling_menu.set("100%")
        self.scaling_menu.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 16))

        ctk.CTkLabel(
            self.sidebar,
            text=f"Config: {self.store.config_path}",
            wraplength=250,
            justify="left",
            text_color=("#687385", "#8995A8"),
            font=ctk.CTkFont(size=11),
        ).grid(row=9, column=0, sticky="sew", padx=24, pady=24)

    def _build_workspace(self) -> None:
        self.workspace = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.workspace.grid(row=0, column=1, sticky="nsew", padx=24, pady=24)
        self.workspace.grid_columnconfigure(0, weight=1)
        self.workspace.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self.workspace, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text="Fluent operations portal",
            font=ctk.CTkFont(family="Segoe UI Variable Display", size=30, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            header,
            text="Configure, validate, launch, and monitor IREPS tender automation without freezing the desktop UI.",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color=("#526071", "#AEB7C6"),
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", pady=(2, 0))

        self.progress = ctk.CTkProgressBar(header, width=220, mode="indeterminate")
        self.progress.grid(row=0, column=1, rowspan=2, sticky="e", padx=(16, 0))
        self.progress.set(0)

        self.tabs = ctk.CTkTabview(self.workspace, corner_radius=24, segmented_button_selected_color="#2563EB")
        self.tabs.grid(row=1, column=0, sticky="nsew")
        self.tabs.add("Configuration")
        self.tabs.add("Organizations")
        self.tabs.add("Activity")
        self.tabs.add("Help")
        self._build_configuration_tab()
        self._build_organizations_tab()
        self._build_activity_tab()
        self._build_help_tab()

    def _build_configuration_tab(self) -> None:
        tab = self.tabs.tab("Configuration")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        scroll.grid_columnconfigure(0, weight=1)

        sections = [
            ("Experience", "Browser, device, and CAPTCHA interaction modes.", ["browser", "adb_device", "captcha_manual_input"]),
            ("Connectivity", "Paths, phone number, and Android bridge connection details.", ["adb_device_ip", "mobile_no", "dump_location", "excel_file_path"]),
            ("Notifications", "Sender account and recipient lists for operational emails.", ["sender_email_id", "sender_email_password", "notification_emailids", "receiver_emailids"]),
            ("Runtime signals", "OTP and internal state values used by the scraper.", ["otp_date", "otp", "signal_datelog", "signal_ireps"]),
        ]

        rendered_keys: set[str] = set()
        row = 0
        for title, subtitle, keys in sections:
            available_keys = [key for key in keys if key in self.data]
            if not available_keys:
                continue
            section = SettingsSection(scroll, title, subtitle)
            section.grid(row=row, column=0, sticky="ew", pady=(0, 14))
            self._populate_section(section, available_keys)
            rendered_keys.update(available_keys)
            row += 1

        extra_keys = [key for key in self.data if key not in rendered_keys]
        if extra_keys:
            section = SettingsSection(scroll, "Additional settings", "Any future configuration values are preserved here.")
            section.grid(row=row, column=0, sticky="ew", pady=(0, 14))
            self._populate_section(section, extra_keys)

        button_bar = ctk.CTkFrame(tab, fg_color="transparent")
        button_bar.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 18))
        button_bar.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(button_bar, text="Reload", height=40, corner_radius=14, command=self.reload_all).grid(
            row=0, column=1, padx=8
        )
        ctk.CTkButton(
            button_bar,
            text="Save Configuration",
            height=40,
            corner_radius=14,
            font=ctk.CTkFont(weight="bold"),
            command=self.save_config,
        ).grid(row=0, column=2, padx=(8, 0))

    def _populate_section(self, section: SettingsSection, keys: list[str]) -> None:
        for row, key in enumerate(keys):
            label = ctk.CTkLabel(
                section.body,
                text=self._label_for_key(key),
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w",
            )
            label.grid(row=row, column=0, sticky="nw", padx=(4, 16), pady=8)
            value = self.data.get(key, "")
            if key in TOGGLE_FIELDS:
                variable = StringVar(value=str(value))
                control = ctk.CTkSegmentedButton(section.body, values=["0", "1"], variable=variable)
                control.grid(row=row, column=1, sticky="ew", pady=7)
                self.field_widgets[key] = ("toggle", variable)
            elif isinstance(value, list) or key in LIST_FIELDS:
                textbox = ctk.CTkTextbox(section.body, height=92, corner_radius=14, font=ctk.CTkFont(family="Cascadia Mono", size=12))
                textbox.insert("1.0", "\n".join(str(item) for item in value) if isinstance(value, list) else str(value))
                textbox.grid(row=row, column=1, sticky="ew", pady=7)
                self.field_widgets[key] = ("list", textbox)
            else:
                entry = ctk.CTkEntry(
                    section.body,
                    height=38,
                    corner_radius=14,
                    show="•" if key in SECRET_FIELDS else None,
                )
                entry.insert(0, "" if value is None else str(value))
                entry.grid(row=row, column=1, sticky="ew", pady=7)
                self.field_widgets[key] = ("entry", entry)

    def _build_organizations_tab(self) -> None:
        tab = self.tabs.tab("Organizations")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(
            tab,
            text="Maintain one organization per line. Prefix a line with # to skip it during scraping.",
            text_color=("#526071", "#AEB7C6"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 8))
        self.organization_editor = ctk.CTkTextbox(
            tab,
            corner_radius=18,
            font=ctk.CTkFont(family="Cascadia Mono", size=13),
            wrap="none",
        )
        self.organization_editor.grid(row=1, column=0, sticky="nsew", padx=18, pady=8)
        self.organization_editor.insert("1.0", self.organization_content)
        actions = ctk.CTkFrame(tab, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=18, pady=(8, 18))
        actions.grid_columnconfigure(0, weight=1)
        ctk.CTkButton(actions, text="Reload Organizations", height=40, corner_radius=14, command=self.reload_organizations).grid(
            row=0, column=1, padx=8
        )
        ctk.CTkButton(
            actions,
            text="Save Organizations",
            height=40,
            corner_radius=14,
            font=ctk.CTkFont(weight="bold"),
            command=self.save_organizations,
        ).grid(row=0, column=2, padx=(8, 0))

    def _build_activity_tab(self) -> None:
        tab = self.tabs.tab("Activity")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)
        toolbar = ctk.CTkFrame(tab, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 8))
        toolbar.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            toolbar,
            text="Live logging panel",
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(toolbar, text="Clear", width=100, height=36, corner_radius=12, command=self.clear_logs).grid(
            row=0, column=1
        )
        self.log_view = ctk.CTkTextbox(
            tab,
            corner_radius=18,
            font=ctk.CTkFont(family="Cascadia Mono", size=12),
            wrap="word",
        )
        self.log_view.grid(row=1, column=0, sticky="nsew", padx=18, pady=(8, 18))
        self.log_view.configure(state="disabled")

    def _build_help_tab(self) -> None:
        tab = self.tabs.tab("Help")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        help_frame = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        help_frame.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)
        help_frame.grid_columnconfigure(0, weight=1)
        help_text = (
            "How to use this portal\n\n"
            "1. Configuration\n"
            "   Update scraper settings, email recipients, runtime paths, OTP values, and mode toggles.\n\n"
            "2. Organizations\n"
            "   Keep each organization as 'number: name'. Prefix a line with # to ignore it.\n\n"
            "3. Run Scraper\n"
            "   Save your changes first, then click Run Scraper. Output streams to the Activity tab while the process runs in the background.\n\n"
            "4. Appearance\n"
            "   Use the sidebar controls to switch between System, Dark, and Light modes or adjust scaling for Windows displays.\n\n"
            "Operational note\n"
            "   Store production passwords, OTPs, mobile numbers, and recipient lists outside version control whenever possible."
        )
        ctk.CTkLabel(
            help_frame,
            text=help_text,
            justify="left",
            anchor="nw",
            font=ctk.CTkFont(family="Segoe UI", size=15),
            wraplength=820,
        ).grid(row=0, column=0, sticky="nsew")

    @staticmethod
    def _label_for_key(key: str) -> str:
        return key.replace("_", " ").title()

    def _collect_config(self) -> dict[str, Any]:
        updated = dict(self.data)
        for key, (kind, widget) in self.field_widgets.items():
            if kind == "toggle":
                updated[key] = widget.get()
            elif kind == "list":
                raw = widget.get("1.0", "end-1c")
                updated[key] = [line.strip() for line in raw.splitlines() if line.strip()]
            else:
                updated[key] = widget.get()
        return updated

    def save_config(self) -> None:
        self.data = self._collect_config()
        self.store.save_config(self.data)
        self._refresh_status_cards()
        self._log("success", f"Saved configuration to {self.store.config_path}")
        messagebox.showinfo(APP_TITLE, "Configuration saved successfully.")

    def save_organizations(self) -> None:
        content = self.organization_editor.get("1.0", "end-1c")
        self.store.save_organizations(content)
        self.organization_content = content.strip()
        self._refresh_status_cards()
        self._log("success", f"Saved organizations to {self.store.organization_path}")
        messagebox.showinfo(APP_TITLE, "Organization list saved successfully.")

    def reload_all(self) -> None:
        self.data = self.store.load_config()
        for key, (kind, widget) in self.field_widgets.items():
            value = self.data.get(key, "")
            if kind == "toggle":
                widget.set(str(value))
            elif kind == "list":
                widget.delete("1.0", "end")
                widget.insert("1.0", "\n".join(str(item) for item in value) if isinstance(value, list) else str(value))
            else:
                widget.delete(0, "end")
                widget.insert(0, "" if value is None else str(value))
        self._refresh_status_cards()
        self._log("info", "Configuration reloaded from disk.")

    def reload_organizations(self) -> None:
        self.organization_content = self.store.load_organizations()
        self.organization_editor.delete("1.0", "end")
        self.organization_editor.insert("1.0", self.organization_content)
        self._refresh_status_cards()
        self._log("info", "Organization list reloaded from disk.")

    def start_scraper(self) -> None:
        self.save_config_without_dialog()
        started = self.runner.start()
        if started:
            self.tabs.set("Activity")
            self.run_button.configure(state="disabled")
            self.stop_button.configure(state="normal")
            self.scraper_card.set_value("Running")
            self.progress.start()
            self.progress_active = True

    def stop_scraper(self) -> None:
        self.runner.stop()

    def save_config_without_dialog(self) -> None:
        self.data = self._collect_config()
        self.store.save_config(self.data)
        self._refresh_status_cards()
        self._log("info", "Configuration auto-saved before scraper launch.")

    def change_appearance(self, mode: str) -> None:
        ctk.set_appearance_mode(mode)
        self.theme_card.set_value(mode)
        self._log("info", f"Appearance changed to {mode}.")

    def change_scaling(self, value: str) -> None:
        ctk.set_widget_scaling(int(value.replace("%", "")) / 100)
        self._log("info", f"Interface scaling changed to {value}.")

    def clear_logs(self) -> None:
        self.log_view.configure(state="normal")
        self.log_view.delete("1.0", "end")
        self.log_view.configure(state="disabled")

    def _refresh_status_cards(self) -> None:
        org_count = ConfigStore.count_active_organizations(self.organization_content)
        self.config_card.set_value("Loaded")
        self.org_card.set_value(f"{org_count} active")
        self.theme_card.set_value(ctk.get_appearance_mode())

    def _drain_log_queue(self) -> None:
        while not self.log_queue.empty():
            level, message = self.log_queue.get_nowait()
            self._log(level, message)
        if not self.runner.is_running and self.progress_active:
            self.progress.stop()
            self.progress.set(0)
            self.progress_active = False
            self.run_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            self.scraper_card.set_value("Idle")
        self.after(120, self._drain_log_queue)

    def _log(self, level: str, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {
            "success": "✓",
            "warning": "!",
            "error": "×",
            "output": "│",
            "info": "•",
        }.get(level, "•")
        if hasattr(self, "log_view"):
            self.log_view.configure(state="normal")
            self.log_view.insert("end", f"[{timestamp}] {prefix} {message}\n")
            self.log_view.see("end")
            self.log_view.configure(state="disabled")


def launch() -> None:
    app_dir = Path(__file__).resolve().parent
    store = ConfigStore(app_dir)
    app = IREPSControlCenter(store)
    app.mainloop()


if __name__ == "__main__":
    launch()
