"""Single-file CustomTkinter control center for the IREPS scraper.

This module replaces the previous split configuration editor files with one
entry point that keeps configuration editing, organization-list editing, live
logs, and scraper launching together in a layout matching ``scraping_gui.py``:
a compact top toolbar, left status/organization panel, right work area, and a
bottom status bar.
"""

from __future__ import annotations

import ctypes
import datetime as dt
import json
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any

import customtkinter as ctk


APP_TITLE = "IREPS Tender Scraper"
CONFIG_FILENAME = "Configration.json"
ORGANIZATION_FILENAME = "Organization_list.txt"
SCRAPER_FILENAME = "IREPS_Tenders.py"
TOGGLE_FIELDS = {"browser", "adb_device", "captcha_manual_input"}
LIST_FIELDS = {"notification_emailids", "receiver_emailids"}
SECRET_FIELDS = {"sender_email_password", "otp"}

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

FONT_TITLE = ("Segoe UI Variable Display", 22, "bold")
FONT_HEADER = ("Segoe UI Variable Text", 13, "bold")
FONT_BODY = ("Segoe UI Variable Text", 12)
FONT_SMALL = ("Segoe UI Variable Small", 11)
FONT_MONO = ("Cascadia Code", 11)

ACCENT = "#0078D4"
ACCENT_HOVER = "#106EBE"
SUCCESS = "#0E7A0D"
WARNING = "#CA5010"
ERROR_CLR = "#C42B1C"


class ConfigStore:
    """Read and write scraper configuration files from Program_Files."""

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
        self.organization_path.write_text(content.strip() + "\n", encoding="utf-8")

    @staticmethod
    def active_organizations(content: str) -> list[str]:
        return [line.strip() for line in content.splitlines() if line.strip() and not line.lstrip().startswith("#")]


class PortalCard(ctk.CTkFrame):
    """Organization status card matching the card style in scraping_gui.py."""

    _STATUS_COLORS = {
        "active": (SUCCESS, "#0A5C0A"),
        "disabled": ("#666666", "#2A2A2A"),
        "running": (ACCENT, "#1557A0"),
        "done": (SUCCESS, "#0A5C0A"),
        "error": (ERROR_CLR, "#8B1C13"),
    }

    def __init__(self, parent: ctk.CTkBaseClass, name: str, enabled: bool = True) -> None:
        super().__init__(parent, corner_radius=8)
        self.name = name
        self.enabled = tk.BooleanVar(value=enabled)
        self.grid_columnconfigure(2, weight=1)

        self._cb = ctk.CTkCheckBox(
            self,
            text="",
            variable=self.enabled,
            width=20,
            checkbox_width=16,
            checkbox_height=16,
            command=self._on_toggle,
        )
        self._cb.grid(row=0, column=0, padx=(8, 4), pady=6)

        self._dot = ctk.CTkLabel(self, text="●", font=("Segoe UI", 13), text_color="#888888", width=16)
        self._dot.grid(row=0, column=1, padx=(0, 4))

        ctk.CTkLabel(self, text=name, font=FONT_BODY, anchor="w").grid(row=0, column=2, sticky="w", padx=2)

        self._badge = ctk.CTkLabel(
            self,
            text="active" if enabled else "disabled",
            font=FONT_SMALL,
            fg_color="#555555",
            corner_radius=6,
            text_color="#CCCCCC",
            width=72,
        )
        self._badge.grid(row=0, column=3, padx=(6, 8))
        self.set_status("active" if enabled else "disabled")

    def _on_toggle(self) -> None:
        self.set_status("active" if self.enabled.get() else "disabled")

    def set_status(self, status: str) -> None:
        light, dark = self._STATUS_COLORS.get(status, self._STATUS_COLORS["disabled"])
        self._dot.configure(text_color=light)
        self._badge.configure(text=status, fg_color=dark, text_color=light)


class ScraperRunner:
    """Run IREPS_Tenders.py in a worker thread and stream stdout to the GUI."""

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
        self.thread = threading.Thread(target=self._run, name="IREPS-scraper", daemon=True)
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

        command = [sys.executable, "-u", str(self.store.scraper_path)]
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        started_at = dt.datetime.now()
        self.log_queue.put(("info", f"Starting scraper: {' '.join(command)}"))
        try:
            self.process = subprocess.Popen(
                command,
                cwd=str(self.store.app_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
            )
            if self.process.stdout:
                for line in self.process.stdout:
                    self.log_queue.put(("output", line.rstrip()))
            return_code = self.process.wait()
            elapsed = dt.datetime.now() - started_at
            if return_code == 0:
                self.log_queue.put(("success", f"Scraper finished successfully in {elapsed}."))
            else:
                self.log_queue.put(("error", f"Scraper exited with code {return_code} after {elapsed}."))
        except Exception as exc:
            self.log_queue.put(("error", f"Unable to run scraper: {exc}"))
        finally:
            self.process = None


class IREPSScrapingGUI(ctk.CTk):
    """Single-window editor/launcher with the same layout as scraping_gui.py."""

    def __init__(self, store: ConfigStore) -> None:
        super().__init__()
        self.store = store
        self.data = self.store.load_config()
        self.organization_content = self.store.load_organizations()
        self.field_widgets: dict[str, tuple[str, Any]] = {}
        self.log_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.runner = ScraperRunner(store, self.log_queue)
        self.portal_cards: dict[str, PortalCard] = {}
        self.log_line_count = 0
        self.running = False
        self.start_time = 0.0

        self.title(APP_TITLE)
        self.geometry("1080x740")
        self.minsize(880, 600)
        self._set_windows_style()
        self._build_ui()
        self._populate_portal_cards()
        self._refresh_stats()
        self._append_log("=== IREPS GUI ready ===", "INFO")
        self.after(120, self._drain_log_queue)
        self.after(1000, self._poll_timer)

    def _set_windows_style(self) -> None:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
        try:
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 38, ctypes.byref(ctypes.c_int(2)), ctypes.sizeof(ctypes.c_int))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int))
        except Exception:
            pass
        icon_path = self.store.app_dir / "app_logo.ico"
        if sys.platform.startswith("win") and icon_path.exists():
            self.iconbitmap(str(icon_path))

    def _build_ui(self) -> None:
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        top = ctk.CTkFrame(self, height=56, corner_radius=0, fg_color=("#E5E5E5", "#1A1A1A"))
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(top, text="IREPS Tender Scraper", font=FONT_TITLE).grid(row=0, column=0, padx=20, pady=12, sticky="w")

        self.browser_var = tk.BooleanVar(value=str(self.data.get("browser", "1")) == "1")
        ctk.CTkCheckBox(
            top,
            text="Browser",
            variable=self.browser_var,
            font=FONT_SMALL,
            checkbox_width=16,
            checkbox_height=16,
            command=self._quick_browser_toggle,
        ).grid(row=0, column=3, padx=8, pady=12)

        self.theme_btn = ctk.CTkButton(
            top,
            text="☀  Light",
            width=88,
            height=30,
            font=FONT_SMALL,
            fg_color="transparent",
            border_width=1,
            command=self._toggle_theme,
        )
        self.theme_btn.grid(row=0, column=4, padx=6, pady=12)

        ctk.CTkButton(
            top,
            text="💾  Save",
            width=88,
            height=30,
            font=FONT_SMALL,
            fg_color="transparent",
            border_width=1,
            command=self.save_all,
        ).grid(row=0, column=5, padx=6, pady=12)

        ctk.CTkButton(
            top,
            text="📁  Output",
            width=88,
            height=30,
            font=FONT_SMALL,
            fg_color="transparent",
            border_width=1,
            command=self._open_output,
        ).grid(row=0, column=6, padx=(6, 16), pady=12)

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=12, pady=(6, 0))
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=0)
        content.grid_columnconfigure(1, weight=1)

        self._build_left_panel(content)
        self._build_right_panel(content)

        self.status_bar = ctk.CTkLabel(
            self,
            text="Ready",
            font=FONT_SMALL,
            anchor="w",
            height=24,
            fg_color=("#DCDCDC", "#141414"),
            text_color=("#555555", "#888888"),
        )
        self.status_bar.grid(row=2, column=0, sticky="ew")

    def _build_left_panel(self, parent: ctk.CTkBaseClass) -> None:
        left = ctk.CTkFrame(parent, width=340, corner_radius=12)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 8))
        left.grid_rowconfigure(2, weight=1)
        left.grid_columnconfigure(0, weight=1)
        left.grid_propagate(False)

        stats = ctk.CTkFrame(left, fg_color="transparent")
        stats.grid(row=0, column=0, sticky="ew", padx=12, pady=(14, 4))
        stats.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self.stat_portals = self._make_stat(stats, "Orgs", "0", 0)
        self.stat_config = self._make_stat(stats, "Config", "OK", 1)
        self.stat_elapsed = self._make_stat(stats, "Elapsed", "00:00", 2)
        self.stat_workers = self._make_stat(stats, "Workers", str(self.data.get("max_org_workers", "—")), 3)

        self.progress = ctk.CTkProgressBar(left, height=6, corner_radius=3, mode="determinate")
        self.progress.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        self.progress.set(0)

        self.cards_frame = ctk.CTkScrollableFrame(left, label_text="Organizations", label_font=FONT_HEADER, corner_radius=8)
        self.cards_frame.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 8))

        btn_row = ctk.CTkFrame(left, fg_color="transparent")
        btn_row.grid(row=3, column=0, pady=(0, 14), padx=12)
        self.start_btn = ctk.CTkButton(
            btn_row,
            text="▶  Start Scraping",
            width=150,
            height=38,
            font=FONT_HEADER,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            command=self.start_scraper,
        )
        self.start_btn.pack(side="left", padx=(0, 8))
        self.stop_btn = ctk.CTkButton(
            btn_row,
            text="■  Stop",
            width=80,
            height=38,
            font=FONT_HEADER,
            fg_color="#555555",
            hover_color="#3A3A3A",
            state="disabled",
            command=self.stop_scraper,
        )
        self.stop_btn.pack(side="left")

    def _build_right_panel(self, parent: ctk.CTkBaseClass) -> None:
        right = ctk.CTkFrame(parent, corner_radius=12)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(right, fg_color="transparent", height=36)
        hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 2))
        hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(hdr, text="Control Workspace", font=FONT_HEADER, anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkButton(hdr, text="Reload", width=62, height=26, font=FONT_SMALL, fg_color="transparent", border_width=1, command=self.reload_all).grid(row=0, column=1, padx=(0, 6))
        ctk.CTkButton(hdr, text="Clear Log", width=74, height=26, font=FONT_SMALL, fg_color="transparent", border_width=1, command=self.clear_log).grid(row=0, column=2, padx=(0, 6))
        ctk.CTkButton(hdr, text="Export", width=62, height=26, font=FONT_SMALL, fg_color="transparent", border_width=1, command=self.export_log).grid(row=0, column=3)

        self.tabs = ctk.CTkTabview(right, corner_radius=8)
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.tabs.add("Configuration")
        self.tabs.add("Organizations")
        self.tabs.add("Live Log")
        self.tabs.add("Help")
        self._build_configuration_tab()
        self._build_organizations_tab()
        self._build_log_tab()
        self._build_help_tab()

    def _build_configuration_tab(self) -> None:
        tab = self.tabs.tab("Configuration")
        tab.grid_rowconfigure(0, weight=1)
        tab.grid_columnconfigure(0, weight=1)
        frame = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        frame.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        frame.grid_columnconfigure(1, weight=1)
        for row, key in enumerate(self.data):
            self._add_config_row(frame, row, key, self.data[key])

    def _add_config_row(self, parent: ctk.CTkBaseClass, row: int, key: str, value: Any) -> None:
        ctk.CTkLabel(parent, text=key.replace("_", " ").title(), font=FONT_BODY, anchor="e").grid(row=row, column=0, padx=(16, 8), pady=6, sticky="e")
        if key in TOGGLE_FIELDS:
            widget = ctk.CTkOptionMenu(parent, values=["0", "1"], width=90)
            widget.set(str(value))
            kind = "entry"
        elif key in LIST_FIELDS:
            widget = ctk.CTkTextbox(parent, height=72, font=FONT_BODY)
            text = "\n".join(str(item) for item in value) if isinstance(value, list) else str(value)
            widget.insert("1.0", text)
            kind = "list"
        else:
            show = "•" if key in SECRET_FIELDS else None
            widget = ctk.CTkEntry(parent, show=show, font=FONT_BODY)
            widget.insert(0, "" if value is None else str(value))
            kind = "entry"
        widget.grid(row=row, column=1, padx=(0, 16), pady=6, sticky="ew")
        self.field_widgets[key] = (kind, widget)

    def _build_organizations_tab(self) -> None:
        tab = self.tabs.tab("Organizations")
        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            tab,
            text="Edit Organization_list.txt directly. Prefix a line with # to disable that organization.",
            font=FONT_SMALL,
            text_color="#888888",
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        self.organization_editor = ctk.CTkTextbox(tab, font=FONT_MONO, wrap="none", corner_radius=8)
        self.organization_editor.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.organization_editor.insert("1.0", self.organization_content)

    def _build_log_tab(self) -> None:
        tab = self.tabs.tab("Live Log")
        tab.grid_rowconfigure(1, weight=1)
        tab.grid_columnconfigure(0, weight=1)
        options = ctk.CTkFrame(tab, fg_color="transparent")
        options.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 2))
        options.grid_columnconfigure(0, weight=1)
        self.autoscroll = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(options, text="Auto-scroll", variable=self.autoscroll, font=FONT_SMALL, width=100, height=26, checkbox_width=16, checkbox_height=16).grid(row=0, column=1, padx=(0, 4))
        self.log_filter = tk.StringVar(value="All")
        ctk.CTkOptionMenu(options, variable=self.log_filter, values=["All", "Warnings & Errors", "Errors only"], width=148, height=26, font=FONT_SMALL).grid(row=0, column=2)
        self.log_box = ctk.CTkTextbox(
            tab,
            font=FONT_MONO,
            wrap="word",
            state="disabled",
            corner_radius=8,
            border_width=0,
            fg_color=("#F0F0F0", "#161616"),
            text_color=("#1A1A1A", "#D4D4D4"),
        )
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self._apply_log_tags()

    def _build_help_tab(self) -> None:
        tab = self.tabs.tab("Help")
        tab.grid_rowconfigure(0, weight=1)
        tab.grid_columnconfigure(0, weight=1)
        help_text = (
            "IREPS Tender Scraper GUI\n\n"
            "• Save writes Configration.json and Organization_list.txt.\n"
            "• Start Scraping auto-saves first, then launches IREPS_Tenders.py in the background.\n"
            "• The left panel mirrors scraping_gui.py with stat cards, organization cards, progress, and Start/Stop controls.\n"
            "• Use the Live Log tab to monitor scraper output and export troubleshooting logs.\n\n"
            "Security note: keep passwords, OTPs, mobile numbers, and recipient lists out of shared commits whenever possible."
        )
        ctk.CTkLabel(tab, text=help_text, justify="left", anchor="nw", font=ctk.CTkFont(family="Segoe UI", size=15), wraplength=760).grid(row=0, column=0, sticky="nsew", padx=18, pady=18)

    def _make_stat(self, parent: ctk.CTkBaseClass, label: str, value: str, col: int) -> ctk.CTkLabel:
        frame = ctk.CTkFrame(parent, corner_radius=8)
        frame.grid(row=0, column=col, padx=4, pady=2, sticky="ew")
        ctk.CTkLabel(frame, text=label, font=FONT_SMALL, text_color="#888888").pack(pady=(6, 0))
        stat = ctk.CTkLabel(frame, text=value, font=FONT_HEADER)
        stat.pack(pady=(0, 6))
        return stat

    def _populate_portal_cards(self) -> None:
        for child in self.cards_frame.winfo_children():
            child.destroy()
        self.portal_cards.clear()
        active_lines = set(ConfigStore.active_organizations(self.organization_content))
        for line in self.organization_content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") and ":" not in stripped:
                continue
            enabled = stripped in active_lines
            name = stripped.lstrip("#").strip()
            card = PortalCard(self.cards_frame, name, enabled=enabled)
            card.pack(fill="x", padx=4, pady=3)
            self.portal_cards[name] = card

    def _collect_config(self) -> dict[str, Any]:
        updated = dict(self.data)
        for key, (kind, widget) in self.field_widgets.items():
            if kind == "list":
                raw = widget.get("1.0", "end-1c")
                updated[key] = [line.strip() for line in raw.replace(",", "\n").splitlines() if line.strip()]
            elif key == "max_org_workers":
                value = widget.get().strip()
                updated[key] = int(value) if value.isdigit() else value
            else:
                updated[key] = widget.get()
        return updated

    def _collect_organizations(self) -> str:
        lines: list[str] = []
        card_states = {name: card.enabled.get() for name, card in self.portal_cards.items()}
        for line in self.organization_editor.get("1.0", "end-1c").splitlines():
            stripped = line.strip()
            name = stripped.lstrip("#").strip()
            if name in card_states and name:
                lines.append(name if card_states[name] else f"#{name}")
            else:
                lines.append(line.rstrip())
        return "\n".join(lines).strip()

    def save_all(self) -> None:
        self.data = self._collect_config()
        self.data["browser"] = "1" if self.browser_var.get() else "0"
        self.store.save_config(self.data)
        self.organization_content = self._collect_organizations()
        self.store.save_organizations(self.organization_content)
        self._populate_portal_cards()
        self._refresh_stats()
        self._append_log(f"Saved configuration to {self.store.config_path}", "INFO")
        self._append_log(f"Saved organizations to {self.store.organization_path}", "INFO")
        self._set_status("Configuration and organizations saved.")

    def reload_all(self) -> None:
        self.data = self.store.load_config()
        self.organization_content = self.store.load_organizations()
        for key, (kind, widget) in self.field_widgets.items():
            value = self.data.get(key, "")
            if kind == "list":
                widget.delete("1.0", "end")
                widget.insert("1.0", "\n".join(str(item) for item in value) if isinstance(value, list) else str(value))
            else:
                if hasattr(widget, "delete"):
                    widget.delete(0, "end")
                    widget.insert(0, "" if value is None else str(value))
                elif hasattr(widget, "set"):
                    widget.set(str(value))
        self.browser_var.set(str(self.data.get("browser", "1")) == "1")
        self.organization_editor.delete("1.0", "end")
        self.organization_editor.insert("1.0", self.organization_content)
        self._populate_portal_cards()
        self._refresh_stats()
        self._append_log("Reloaded files from disk.", "INFO")
        self._set_status("Reloaded from disk.")

    def start_scraper(self) -> None:
        if self.runner.is_running:
            return
        self.save_all()
        self.running = True
        self.start_time = time.time()
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal", text="■  Stop", fg_color="#555555", hover_color="#3A3A3A")
        self.tabs.set("Live Log")
        self._set_status("Scraping in progress…")
        if self.runner.start():
            for card in self.portal_cards.values():
                if card.enabled.get():
                    card.set_status("running")

    def stop_scraper(self) -> None:
        self.runner.stop()
        self.stop_btn.configure(state="disabled", text="⏳  Stopping…", fg_color=WARNING, hover_color=WARNING)
        self._set_status("Stop requested — terminating scraper process…")

    def _drain_log_queue(self) -> None:
        while not self.log_queue.empty():
            level, message = self.log_queue.get_nowait()
            tag = "INFO"
            if level == "error":
                tag = "ERROR"
            elif level == "warning":
                tag = "WARNING"
            self._append_log(message, tag)
        if self.running and not self.runner.is_running:
            self.running = False
            self.progress.stop()
            self.progress.configure(mode="determinate")
            self.progress.set(1)
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled", text="■  Stop", fg_color="#555555", hover_color="#3A3A3A")
            for card in self.portal_cards.values():
                if card.enabled.get():
                    card.set_status("done")
            self._set_status("Scraper finished. Check Live Log for details.")
        self.after(120, self._drain_log_queue)

    def _append_log(self, text: str, tag: str = "INFO") -> None:
        if self.log_filter.get() == "Warnings & Errors" and tag == "INFO":
            return
        if self.log_filter.get() == "Errors only" and tag != "ERROR":
            return
        timestamp = dt.datetime.now().strftime("%H:%M:%S")
        prefix = {"ERROR": "×", "WARNING": "!", "INFO": "•"}.get(tag, "•")
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"{timestamp}  {prefix}  {text.rstrip()}\n", tag)
        self.log_line_count += 1
        if self.log_line_count > 1000:
            self.log_box.delete("1.0", "2.0")
            self.log_line_count -= 1
        if self.autoscroll.get():
            self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def clear_log(self) -> None:
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self.log_line_count = 0

    def export_log(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export log",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"ireps_gui_log_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as file:
            file.write(self.log_box.get("1.0", "end"))
        self._set_status(f"Log exported → {os.path.basename(path)}")

    def _refresh_stats(self) -> None:
        org_count = len(ConfigStore.active_organizations(self.organization_content))
        self.stat_portals.configure(text=str(org_count))
        self.stat_config.configure(text="OK")
        self.stat_workers.configure(text=str(self.data.get("max_org_workers", "—")))

    def _poll_timer(self) -> None:
        if self.running and self.start_time:
            elapsed = int(time.time() - self.start_time)
            minutes, seconds = divmod(elapsed, 60)
            hours, minutes = divmod(minutes, 60)
            self.stat_elapsed.configure(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}")
        self.after(1000, self._poll_timer)

    def _apply_log_tags(self) -> None:
        dark = ctk.get_appearance_mode() == "Dark"
        info_fg = "#D4D4D4" if dark else "#1A1A1A"
        self.log_box.tag_config("ERROR", foreground=ERROR_CLR)
        self.log_box.tag_config("WARNING", foreground=WARNING)
        self.log_box.tag_config("INFO", foreground=info_fg)

    def _toggle_theme(self) -> None:
        new_mode = "light" if ctk.get_appearance_mode() == "Dark" else "dark"
        ctk.set_appearance_mode(new_mode)
        self.theme_btn.configure(text="🌙  Dark" if new_mode == "light" else "☀  Light")
        self._apply_log_tags()

    def _quick_browser_toggle(self) -> None:
        self.data["browser"] = "1" if self.browser_var.get() else "0"
        widget_info = self.field_widgets.get("browser")
        if widget_info:
            _, widget = widget_info
            widget.set(self.data["browser"])

    def _open_output(self) -> None:
        path = str(self.data.get("dump_location") or self.store.program_files_dir)
        os.makedirs(path, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def _set_status(self, text: str) -> None:
        self.status_bar.configure(text=f"  {text}")

    def _on_close(self) -> None:
        if self.runner.is_running:
            if not messagebox.askyesno("Scraping in progress", "A scrape is currently running.\n\nClose anyway?", icon="warning", parent=self):
                return
            self.runner.stop()
        self.destroy()


def launch() -> None:
    app_dir = Path(__file__).resolve().parent
    app = IREPSScrapingGUI(ConfigStore(app_dir))
    app.mainloop()


def main() -> None:
    launch()


if __name__ == "__main__":
    main()
