"""Windows 11-style configuration editor for the IREPS scraper.

This file is intentionally self-contained so the packaged
``configuration-editor.exe`` can use the same Fluent / Mica-inspired visual
language as ``scraping_gui.py`` while editing the scraper's on-disk files:

* ``Program_Files/Configration.json``
* ``Program_Files/Organization_list.txt``
"""

# =======================
# BOOTSTRAP  (must be first)
# =======================
import multiprocessing
multiprocessing.freeze_support()

import ctypes
import json
import os
import subprocess
import sys
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any

import customtkinter as ctk


# =======================
# WINDOWS 11 DPI
# =======================
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── Fonts ─────────────────────────────────────────────────────────────
FONT_TITLE  = ("Segoe UI Variable Display", 22, "bold")
FONT_HEADER = ("Segoe UI Variable Text",    13, "bold")
FONT_BODY   = ("Segoe UI Variable Text",    12)
FONT_SMALL  = ("Segoe UI Variable Small",   11)
FONT_MONO   = ("Cascadia Code",             11)

# ── Colours ───────────────────────────────────────────────────────────
ACCENT       = "#0078D4"
ACCENT_HOVER = "#106EBE"
SUCCESS      = "#0E7A0D"
WARNING      = "#CA5010"
ERROR_CLR    = "#C42B1C"

APP_TITLE = "IREPS Configuration Editor"
CONFIG_FILENAME = "Configration.json"
ORGANIZATION_FILENAME = "Organization_list.txt"
SCRAPER_FILENAME = "IREPS_Tenders.py"
TOGGLE_FIELDS = {"browser", "adb_device", "captcha_manual_input"}
LIST_FIELDS = {"notification_emailids", "receiver_emailids"}
SECRET_FIELDS = {"sender_email_password", "otp"}
SECTION_GROUPS = [
    ("Experience", "Browser, device, and CAPTCHA interaction modes.", ["browser", "adb_device", "captcha_manual_input"]),
    ("Connectivity", "Paths, mobile number, and Android bridge connection details.", ["adb_device_ip", "mobile_no", "dump_location", "excel_file_path"]),
    ("Notifications", "Sender account and recipient lists for operational emails.", ["sender_email_id", "sender_email_password", "notification_emailids", "receiver_emailids"]),
    ("Runtime signals", "OTP and internal state values used by the scraper.", ["otp_date", "otp", "signal_datelog", "signal_ireps"]),
]


# =======================
# DATA STORE
# =======================
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
            file.write("\n")

    def load_organizations(self) -> str:
        if not self.organization_path.exists():
            raise FileNotFoundError(f"Organization list not found: {self.organization_path}")
        return self.organization_path.read_text(encoding="utf-8")

    def save_organizations(self, content: str) -> None:
        self.program_files_dir.mkdir(parents=True, exist_ok=True)
        self.organization_path.write_text(content.rstrip() + "\n", encoding="utf-8")

    @staticmethod
    def count_active_organizations(content: str) -> int:
        return sum(1 for line in content.splitlines() if line.strip() and not line.lstrip().startswith("#"))

    @staticmethod
    def count_organization_rows(content: str) -> int:
        return sum(1 for line in content.splitlines() if ":" in line.lstrip("# "))


# =======================
# PORTAL STATUS CARD (same visual language as scraping_gui.py)
# =======================
class PortalCard(ctk.CTkFrame):
    _STATUS_COLORS = {
        "enabled":   (SUCCESS,   "#0A5C0A"),
        "disabled":  ("#888888", "#3A3A3A"),
        "comment":   ("#666666", "#2A2A2A"),
    }

    def __init__(self, parent, name: str, enabled: bool = True, **kwargs):
        super().__init__(parent, corner_radius=8, **kwargs)
        self.name = name
        self.enabled = tk.BooleanVar(value=enabled)
        self.grid_columnconfigure(2, weight=1)

        self._cb = ctk.CTkCheckBox(
            self, text="", variable=self.enabled,
            width=20, checkbox_width=16, checkbox_height=16,
            command=self._on_toggle)
        self._cb.grid(row=0, column=0, padx=(8, 4), pady=6)

        self._dot = ctk.CTkLabel(self, text="●", font=("Segoe UI", 13),
                                  text_color="#888888", width=16)
        self._dot.grid(row=0, column=1, padx=(0, 4))

        ctk.CTkLabel(self, text=name, font=FONT_BODY, anchor="w").grid(
            row=0, column=2, sticky="w", padx=2)

        self._badge = ctk.CTkLabel(self, text="enabled", font=FONT_SMALL,
                                    fg_color="#555555", corner_radius=6,
                                    text_color="#CCCCCC", width=72)
        self._badge.grid(row=0, column=3, padx=(6, 8))
        self._on_toggle()

    def _on_toggle(self):
        status = "enabled" if self.enabled.get() else "disabled"
        light, dark = self._STATUS_COLORS[status]
        self._dot.configure(text_color=light)
        self._badge.configure(text=status, fg_color=dark, text_color=light)


# =======================
# HELPERS — labelled row and section separator
# =======================
def _lbl_row(parent, row, label, widget_factory, **grid_kw):
    """Place a right-aligned label + widget in a 2-column grid row."""
    ctk.CTkLabel(parent, text=label, font=FONT_BODY, anchor="e").grid(
        row=row, column=0, padx=(16, 8), pady=6, sticky="e")
    w = widget_factory(parent)
    w.grid(row=row, column=1, padx=(0, 16), pady=6, sticky="ew", **grid_kw)
    return w


def _section(parent, row, text):
    ctk.CTkLabel(parent, text=text, font=FONT_HEADER,
                  text_color="#888888").grid(
        row=row, column=0, columnspan=2, padx=16, pady=(14, 2), sticky="w")


def _label_for_key(key: str) -> str:
    return key.replace("_", " ").title()


# =======================
# MAIN APPLICATION WINDOW
# =======================
class App(ctk.CTk):
    """Configuration editor shell using the same design as the scraper GUI."""

    def __init__(self, store: ConfigStore):
        super().__init__()
        self.store = store
        self.data = self.store.load_config()
        self.organization_content = self.store.load_organizations()
        self.field_widgets: dict[str, tuple[str, Any]] = {}
        self._portal_cards: dict[str, PortalCard] = {}
        self._log_line_count = 0

        self.title(APP_TITLE)
        self.geometry("1080x740")
        self.minsize(880, 600)
        self._set_windows_icon()
        self._set_win11_title_bar()
        self._build_ui()
        self._populate_portal_cards()
        self._refresh_stats()
        self._set_status("Ready")
        self._append_log("Configuration editor ready.", "INFO")

    # ── Windows integration ───────────────────────────────────────────
    def _set_windows_icon(self):
        icon_path = self.store.app_dir / "app_logo.ico"
        if sys.platform.startswith("win") and icon_path.exists():
            self.iconbitmap(str(icon_path))

    def _set_win11_title_bar(self):
        try:
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 38, ctypes.byref(ctypes.c_int(2)), ctypes.sizeof(ctypes.c_int))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 20, ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int))
        except Exception:
            pass

    # ── UI construction ───────────────────────────────────────────────
    def _build_ui(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        top = ctk.CTkFrame(self, height=56, corner_radius=0,
                            fg_color=("#E5E5E5", "#1A1A1A"))
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top, text="IREPS Configuration Editor",
                      font=FONT_TITLE).grid(row=0, column=0, padx=20, pady=12, sticky="w")

        self._theme_btn = ctk.CTkButton(
            top, text="☀  Light", width=88, height=30, font=FONT_SMALL,
            fg_color="transparent", border_width=1, command=self._toggle_theme)
        self._theme_btn.grid(row=0, column=2, padx=6, pady=12)

        ctk.CTkButton(top, text="↻  Reload", width=88, height=30,
                       font=FONT_SMALL, fg_color="transparent", border_width=1,
                       command=self.reload_all).grid(row=0, column=3, padx=6, pady=12)

        ctk.CTkButton(top, text="💾  Save all", width=96, height=30,
                       font=FONT_SMALL, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                       command=self.save_all).grid(row=0, column=4, padx=6, pady=12)

        ctk.CTkButton(top, text="📁  Files", width=82, height=30,
                       font=FONT_SMALL, fg_color="transparent", border_width=1,
                       command=self._open_program_files).grid(row=0, column=5, padx=(6, 16), pady=12)

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=12, pady=(6, 0))
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=0)
        content.grid_columnconfigure(1, weight=1)

        self._build_left_panel(content)
        self._build_right_panel(content)

        self._status_bar = ctk.CTkLabel(
            self, text="Ready", font=FONT_SMALL, anchor="w", height=24,
            fg_color=("#DCDCDC", "#141414"), text_color=("#555555", "#888888"))
        self._status_bar.grid(row=2, column=0, sticky="ew")

    def _build_left_panel(self, content):
        left = ctk.CTkFrame(content, width=340, corner_radius=12)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 8))
        left.grid_rowconfigure(2, weight=1)
        left.grid_columnconfigure(0, weight=1)
        left.grid_propagate(False)

        stats = ctk.CTkFrame(left, fg_color="transparent")
        stats.grid(row=0, column=0, sticky="ew", padx=12, pady=(14, 4))
        stats.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self._stat_settings = self._make_stat(stats, "Settings", "0", 0)
        self._stat_active = self._make_stat(stats, "Active", "0", 1)
        self._stat_total = self._make_stat(stats, "Total", "0", 2)
        self._stat_saved = self._make_stat(stats, "Saved", "No", 3)

        self._progress = ctk.CTkProgressBar(left, height=6, corner_radius=3)
        self._progress.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        self._progress.set(1)

        cards_outer = ctk.CTkScrollableFrame(left, label_text="Organizations",
                                              label_font=FONT_HEADER,
                                              corner_radius=8)
        cards_outer.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self._cards_frame = cards_outer

        btn_row = ctk.CTkFrame(left, fg_color="transparent")
        btn_row.grid(row=3, column=0, pady=(0, 14), padx=12)

        self._save_btn = ctk.CTkButton(
            btn_row, text="💾  Save all", width=130, height=38,
            font=FONT_HEADER, fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self.save_all)
        self._save_btn.pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btn_row, text="↻  Reload", width=94, height=38,
            font=FONT_HEADER, fg_color="#555555", hover_color="#3A3A3A",
            command=self.reload_all).pack(side="left")

    def _build_right_panel(self, content):
        right = ctk.CTkFrame(content, corner_radius=12)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(right, fg_color="transparent", height=36)
        hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 2))
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(hdr, text="Configuration Workspace",
                      font=FONT_HEADER, anchor="w").grid(row=0, column=0, sticky="w")

        ctk.CTkButton(hdr, text="Save JSON", width=86, height=26,
                       font=FONT_SMALL, fg_color="transparent", border_width=1,
                       command=self.save_config).grid(row=0, column=1, padx=(0, 6))
        ctk.CTkButton(hdr, text="Save Orgs", width=86, height=26,
                       font=FONT_SMALL, fg_color="transparent", border_width=1,
                       command=self.save_organizations).grid(row=0, column=2)

        self.tabs = ctk.CTkTabview(right, corner_radius=8)
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.tabs.add("Configuration")
        self.tabs.add("Organizations")
        self.tabs.add("File Content")
        self.tabs.add("Live Log")
        self._build_configuration_tab()
        self._build_organizations_tab()
        self._build_file_content_tab()
        self._build_log_tab()

    def _make_stat(self, parent, label, value, col):
        f = ctk.CTkFrame(parent, corner_radius=8)
        f.grid(row=0, column=col, padx=4, pady=2, sticky="ew")
        ctk.CTkLabel(f, text=label, font=FONT_SMALL,
                      text_color="#888888").pack(pady=(6, 0))
        lbl = ctk.CTkLabel(f, text=value, font=FONT_HEADER)
        lbl.pack(pady=(0, 6))
        return lbl

    # ── Tabs ──────────────────────────────────────────────────────────
    def _build_configuration_tab(self):
        tab = self.tabs.tab("Configuration")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        scroll = ctk.CTkScrollableFrame(tab, corner_radius=8)
        scroll.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        scroll.grid_columnconfigure(1, weight=1)

        rendered_keys: set[str] = set()
        row = 0
        for title, _subtitle, keys in SECTION_GROUPS:
            available_keys = [key for key in keys if key in self.data]
            if not available_keys:
                continue
            _section(scroll, row, title)
            row += 1
            for key in available_keys:
                self._add_config_control(scroll, row, key)
                rendered_keys.add(key)
                row += 1

        extra_keys = [key for key in self.data if key not in rendered_keys]
        if extra_keys:
            _section(scroll, row, "Additional settings")
            row += 1
            for key in extra_keys:
                self._add_config_control(scroll, row, key)
                row += 1

        ctk.CTkLabel(tab, text="Edits are written to Program_Files/Configration.json.",
                      font=FONT_SMALL, text_color="#666666").grid(
            row=1, column=0, padx=16, pady=(0, 10), sticky="w")

    def _add_config_control(self, parent, row: int, key: str):
        value = self.data.get(key, "")
        if key in TOGGLE_FIELDS:
            variable = tk.StringVar(value=str(value))
            widget = _lbl_row(parent, row, _label_for_key(key),
                lambda p: ctk.CTkOptionMenu(p, values=["0", "1"], variable=variable, width=90))
            self.field_widgets[key] = ("toggle", variable)
            return widget
        if isinstance(value, list) or key in LIST_FIELDS:
            textbox = _lbl_row(parent, row, _label_for_key(key),
                lambda p: ctk.CTkTextbox(p, height=74, font=FONT_MONO, corner_radius=8))
            textbox.insert("1.0", "\n".join(str(item) for item in value) if isinstance(value, list) else str(value))
            self.field_widgets[key] = ("list", textbox)
            return textbox
        show = "●" if key in SECRET_FIELDS else None
        entry = _lbl_row(parent, row, _label_for_key(key),
            lambda p: ctk.CTkEntry(p, height=32, corner_radius=8, show=show))
        entry.insert(0, "" if value is None else str(value))
        self.field_widgets[key] = ("entry", entry)
        return entry

    def _build_organizations_tab(self):
        tab = self.tabs.tab("Organizations")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            tab,
            text="Maintain one organization per line. Prefix a line with # to disable it during scraping.",
            font=FONT_SMALL, text_color="#888888", anchor="w").grid(
            row=0, column=0, sticky="ew", padx=16, pady=(12, 4))

        self.organization_editor = ctk.CTkTextbox(tab, font=FONT_MONO, wrap="none", corner_radius=8)
        self.organization_editor.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))
        self.organization_editor.insert("1.0", self.organization_content)

        btn_frame = ctk.CTkFrame(tab, fg_color="transparent")
        btn_frame.grid(row=2, column=0, pady=(0, 10), sticky="e", padx=12)
        ctk.CTkButton(btn_frame, text="Apply sidebar toggles", width=142,
                       font=FONT_SMALL, fg_color="transparent", border_width=1,
                       command=self._apply_sidebar_toggles_to_text).pack(side="left", padx=6)
        ctk.CTkButton(btn_frame, text="Reload organizations", width=142,
                       font=FONT_SMALL, fg_color="transparent", border_width=1,
                       command=self.reload_organizations).pack(side="left", padx=6)
        ctk.CTkButton(btn_frame, text="Save organizations", width=136,
                       font=FONT_SMALL, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                       command=self.save_organizations).pack(side="left", padx=6)

    def _build_file_content_tab(self):
        tab = self.tabs.tab("File Content")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Raw file preview", font=FONT_HEADER).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(header, text="Refresh preview", width=118, height=26,
                       font=FONT_SMALL, fg_color="transparent", border_width=1,
                       command=self._refresh_file_preview).grid(row=0, column=1)

        self.file_preview = ctk.CTkTextbox(tab, font=FONT_MONO, wrap="none", corner_radius=8)
        self.file_preview.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self._refresh_file_preview()

    def _build_log_tab(self):
        tab = self.tabs.tab("Live Log")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        log_hdr = ctk.CTkFrame(tab, fg_color="transparent", height=36)
        log_hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 2))
        log_hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(log_hdr, text="Live Log",
                      font=FONT_HEADER, anchor="w").grid(row=0, column=0, sticky="w")

        self._autoscroll = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(log_hdr, text="Auto-scroll", variable=self._autoscroll,
                         font=FONT_SMALL, width=100, height=26,
                         checkbox_width=16, checkbox_height=16).grid(
            row=0, column=1, padx=(0, 4))

        ctk.CTkButton(log_hdr, text="Clear", width=56, height=26,
                       font=FONT_SMALL, fg_color="transparent", border_width=1,
                       command=self._clear_log).grid(row=0, column=2)

        ctk.CTkButton(log_hdr, text="Export", width=62, height=26,
                       font=FONT_SMALL, fg_color="transparent", border_width=1,
                       command=self._export_log).grid(row=0, column=3, padx=(6, 0))

        self._log_box = ctk.CTkTextbox(
            tab, font=FONT_MONO, wrap="word", state="disabled",
            corner_radius=8, border_width=0,
            fg_color=("#F0F0F0", "#161616"),
            text_color=("#1A1A1A", "#D4D4D4"))
        self._log_box.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self._apply_log_tags()

    # ── Data collection and persistence ───────────────────────────────
    def _collect_config(self) -> dict[str, Any]:
        updated = dict(self.data)
        for key, (kind, widget) in self.field_widgets.items():
            if kind == "toggle":
                updated[key] = widget.get()
            elif kind == "list":
                raw = widget.get("1.0", "end-1c")
                updated[key] = [line.strip() for line in raw.replace(",", "\n").splitlines() if line.strip()]
            else:
                updated[key] = widget.get()
        return updated

    def save_all(self):
        self.save_config(show_dialog=False)
        self.save_organizations(show_dialog=False)
        self._refresh_file_preview()
        self._stat_saved.configure(text="Yes")
        self._set_status("All configuration files saved.")
        self._append_log("Saved Configration.json and Organization_list.txt.", "INFO")
        messagebox.showinfo(APP_TITLE, "All configuration files saved successfully.", parent=self)

    def save_config(self, show_dialog: bool = True):
        self.data = self._collect_config()
        self.store.save_config(self.data)
        self._refresh_stats()
        self._refresh_file_preview()
        self._set_status("Configration.json saved.")
        self._append_log(f"Saved configuration to {self.store.config_path}", "INFO")
        if show_dialog:
            messagebox.showinfo(APP_TITLE, "Configuration saved successfully.", parent=self)

    def save_organizations(self, show_dialog: bool = True):
        content = self.organization_editor.get("1.0", "end-1c")
        self.store.save_organizations(content)
        self.organization_content = content.strip()
        self._populate_portal_cards()
        self._refresh_stats()
        self._refresh_file_preview()
        self._set_status("Organization_list.txt saved.")
        self._append_log(f"Saved organizations to {self.store.organization_path}", "INFO")
        if show_dialog:
            messagebox.showinfo(APP_TITLE, "Organization list saved successfully.", parent=self)

    def reload_all(self):
        self.data = self.store.load_config()
        self.organization_content = self.store.load_organizations()
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
        self.organization_editor.delete("1.0", "end")
        self.organization_editor.insert("1.0", self.organization_content)
        self._populate_portal_cards()
        self._refresh_stats()
        self._refresh_file_preview()
        self._stat_saved.configure(text="No")
        self._set_status("Reloaded from disk.")
        self._append_log("Reloaded configuration and organization files from disk.", "INFO")

    def reload_organizations(self):
        self.organization_content = self.store.load_organizations()
        self.organization_editor.delete("1.0", "end")
        self.organization_editor.insert("1.0", self.organization_content)
        self._populate_portal_cards()
        self._refresh_stats()
        self._refresh_file_preview()
        self._set_status("Organizations reloaded.")
        self._append_log("Organization list reloaded from disk.", "INFO")

    # ── Organization cards and previews ───────────────────────────────
    def _populate_portal_cards(self):
        if not hasattr(self, "_cards_frame"):
            return
        for widget in self._cards_frame.winfo_children():
            widget.destroy()
        self._portal_cards.clear()
        for line in self.organization_content.splitlines():
            stripped = line.strip()
            if not stripped or ":" not in stripped.lstrip("# "):
                continue
            enabled = not stripped.startswith("#")
            name = stripped.lstrip("# ").split(":", 1)[1].strip() or stripped.lstrip("# ")
            card = PortalCard(self._cards_frame, name, enabled=enabled)
            card.pack(fill="x", padx=4, pady=3)
            self._portal_cards[name] = card

    def _apply_sidebar_toggles_to_text(self):
        enabled_by_name = {name: card.enabled.get() for name, card in self._portal_cards.items()}
        lines_out = []
        for line in self.organization_editor.get("1.0", "end-1c").splitlines():
            stripped = line.strip()
            if not stripped or ":" not in stripped.lstrip("# "):
                lines_out.append(line)
                continue
            raw = stripped.lstrip("# ")
            org_name = raw.split(":", 1)[1].strip() or raw
            enabled = enabled_by_name.get(org_name, not stripped.startswith("#"))
            lines_out.append(raw if enabled else f"#{raw}")
        self.organization_editor.delete("1.0", "end")
        self.organization_editor.insert("1.0", "\n".join(lines_out))
        self.organization_content = self.organization_editor.get("1.0", "end-1c")
        self._refresh_stats()
        self._append_log("Applied sidebar enabled/disabled states to organization text.", "INFO")

    def _refresh_file_preview(self):
        if not hasattr(self, "file_preview"):
            return
        config_text = json.dumps(self._collect_config(), indent=4)
        org_text = self.organization_editor.get("1.0", "end-1c") if hasattr(self, "organization_editor") else self.organization_content
        preview = (
            f"# {self.store.config_path}\n"
            f"{config_text}\n\n"
            f"# {self.store.organization_path}\n"
            f"{org_text}\n"
        )
        self.file_preview.configure(state="normal")
        self.file_preview.delete("1.0", "end")
        self.file_preview.insert("1.0", preview)
        self.file_preview.configure(state="disabled")

    def _refresh_stats(self):
        content = self.organization_editor.get("1.0", "end-1c") if hasattr(self, "organization_editor") else self.organization_content
        self._stat_settings.configure(text=str(len(self.data)))
        self._stat_active.configure(text=str(ConfigStore.count_active_organizations(content)))
        self._stat_total.configure(text=str(ConfigStore.count_organization_rows(content)))

    # ── Log helpers ───────────────────────────────────────────────────
    def _append_log(self, msg: str, level: str = "INFO"):
        if not hasattr(self, "_log_box"):
            return
        stamp = datetime.now().strftime("%H:%M:%S")
        line = f"{stamp}  {level:<8}  {msg}\n"
        self._log_box.configure(state="normal")
        self._log_box.insert("end", line, level)
        self._log_line_count += 1
        if self._log_line_count > 1000:
            self._log_box.delete("1.0", "2.0")
            self._log_line_count -= 1
        if self._autoscroll.get():
            self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def _apply_log_tags(self):
        self._log_box.tag_config("INFO", foreground="#D4D4D4")
        self._log_box.tag_config("WARNING", foreground=WARNING)
        self._log_box.tag_config("ERROR", foreground=ERROR_CLR)

    def _clear_log(self):
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")
        self._log_line_count = 0

    def _export_log(self):
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Export log",
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as file:
            file.write(self._log_box.get("1.0", "end"))
        self._append_log(f"Exported log to {path}", "INFO")

    # ── Shell helpers ─────────────────────────────────────────────────
    def _toggle_theme(self):
        if ctk.get_appearance_mode() == "Dark":
            ctk.set_appearance_mode("light")
            self._theme_btn.configure(text="🌙  Dark")
        else:
            ctk.set_appearance_mode("dark")
            self._theme_btn.configure(text="☀  Light")

    def _open_program_files(self):
        path = self.store.program_files_dir
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            messagebox.showerror(APP_TITLE, f"Unable to open {path}: {exc}", parent=self)

    def _set_status(self, msg: str):
        if hasattr(self, "_status_bar"):
            self._status_bar.configure(text=msg)

    def _on_close(self):
        if messagebox.askokcancel(APP_TITLE, "Close the configuration editor?", parent=self):
            self.destroy()


def launch() -> None:
    app_dir = Path(__file__).resolve().parent
    store = ConfigStore(app_dir)
    app = App(store)
    app.mainloop()


if __name__ == "__main__":
    launch()
