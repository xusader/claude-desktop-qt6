#!/usr/bin/env python3
"""
Claude Desktop — A native Qt6 chat client for the Anthropic Claude API.
Designed for Arch Linux. Glassmorphism UI with blur, project context loading.
"""

import sys
import os
import json
import html
import re
import threading
import queue as _queue
import subprocess
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, QScrollArea,
    QFrame, QSplitter, QListWidget, QListWidgetItem, QMenu,
    QDialog, QComboBox, QSizePolicy, QPlainTextEdit,
    QFileDialog, QTreeWidget, QTreeWidgetItem, QHeaderView,
    QCheckBox, QTabWidget, QGroupBox, QSpinBox
)
from PyQt6.QtCore import (
    Qt, QSize, pyqtSignal, QObject, QTimer,
    QPoint, QMargins, QSettings, QEvent, QProcess,
    QFileSystemWatcher
)
from PyQt6.QtGui import (
    QFont, QFontDatabase, QIcon, QPixmap, QPainter, QColor,
    QLinearGradient, QAction, QKeySequence, QShortcut,
    QPalette, QTextCursor, QTextCharFormat, QBrush, QPen,
    QPainterPath, QRadialGradient, QRegion
)

# ── Config ──────────────────────────────────────────────────────────────────

CONFIG_DIR = Path.home() / ".config" / "claude-desktop"
CONFIG_FILE = CONFIG_DIR / "config.json"
HISTORY_DIR = CONFIG_DIR / "history"
PROJECTS_DIR = CONFIG_DIR / "projects"

DEFAULT_CONFIG = {
    "api_key": "",
    "model": "claude-sonnet-4-20250514",
    "max_tokens": 8192,
    "system_prompt": "",
    "theme": "dark",
    "opacity": 92,
    "blur_enabled": True,
    "blur_method": "kvantum",
    "projects": [],
    # Font settings
    "font_family": "JetBrains Mono",
    "font_size": 13,
    "font_size_input": 14,
    "font_size_bubbles": 14,
    # Color settings
    "color_accent": "#d4845a",
    "color_bg": "#0d0f12",
    "color_panel": "#13161b",
    "color_text": "#e8e4df",
    "color_text_secondary": "#8a8f9a",
    "color_user_bubble": "#1e2330",
    "color_assistant_bubble": "#161a21",
    "color_input_bg": "#1a1e25",
    "color_border": "#2a303a",
    "color_code_bg": "#0f1218",
}

MODELS = [
    "claude-opus-4-6",
    "claude-opus-4-5-20251101",
    "claude-opus-4-20250514",
    "claude-sonnet-4-20250514",
    "claude-haiku-4-5-20251001",
]

# File extensions to include when scanning projects
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".rs", ".go", ".c", ".cpp", ".h",
    ".hpp", ".java", ".kt", ".swift", ".rb", ".php", ".lua", ".sh", ".bash",
    ".zsh", ".fish", ".toml", ".yaml", ".yml", ".json", ".xml", ".html",
    ".css", ".scss", ".sql", ".md", ".rst", ".txt", ".cfg", ".ini", ".env",
    ".dockerfile", ".nix", ".zig", ".hs", ".el", ".vim",
}

IGNORE_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "__pycache__", ".venv", "venv",
    "target", "build", "dist", ".cache", ".tox", ".eggs", "*.egg-info",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
}

MAX_FILE_SIZE = 64 * 1024  # 64 KB per file

# ── Color Palette ───────────────────────────────────────────────────────────

class Colors:
    """Dynamic color palette populated from config."""
    # Defaults (overwritten by load_colors_from_config)
    BG_DARK = "#0d0f12"
    BG_PANEL = "rgba(19, 22, 27, 0.85)"
    BG_PANEL_SOLID = "#13161b"
    BG_SURFACE = "rgba(26, 30, 37, 0.80)"
    BG_ELEVATED = "rgba(34, 39, 48, 0.90)"
    BG_INPUT = "rgba(26, 30, 37, 0.75)"
    BORDER = "rgba(42, 48, 58, 0.60)"
    BORDER_FOCUS = "#d4845a"
    TEXT_PRIMARY = "#e8e4df"
    TEXT_SECONDARY = "#8a8f9a"
    TEXT_MUTED = "#5a5f6a"
    ACCENT = "#d4845a"
    ACCENT_HOVER = "#e09568"
    ACCENT_SUBTLE = "rgba(45, 34, 25, 0.70)"
    USER_BG = "rgba(30, 35, 48, 0.70)"
    ASSISTANT_BG = "rgba(22, 26, 33, 0.65)"
    CODE_BG = "rgba(15, 18, 24, 0.85)"
    SCROLLBAR = "rgba(42, 48, 58, 0.50)"
    SCROLLBAR_HOVER = "rgba(58, 64, 80, 0.70)"
    SUCCESS = "#6abf8a"
    ERROR = "#d45a5a"
    WARNING = "#d4b85a"
    GLASS = "rgba(255, 255, 255, 0.03)"
    GLASS_BORDER = "rgba(255, 255, 255, 0.08)"
    PROJECT_BG = "rgba(20, 24, 32, 0.80)"
    FONT_FAMILY = "JetBrains Mono"
    FONT_SIZE = 13
    FONT_SIZE_INPUT = 14
    FONT_SIZE_BUBBLES = 14


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    """Convert #RRGGBB to rgba(r, g, b, alpha)."""
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def _lighten_hex(hex_color: str, amount: int = 20) -> str:
    """Lighten a hex color by amount (0-255)."""
    h = hex_color.lstrip('#')
    r = min(255, int(h[0:2], 16) + amount)
    g = min(255, int(h[2:4], 16) + amount)
    b = min(255, int(h[4:6], 16) + amount)
    return f"#{r:02x}{g:02x}{b:02x}"


def _darken_hex(hex_color: str, amount: int = 20) -> str:
    """Darken a hex color by amount."""
    h = hex_color.lstrip('#')
    r = max(0, int(h[0:2], 16) - amount)
    g = max(0, int(h[2:4], 16) - amount)
    b = max(0, int(h[4:6], 16) - amount)
    return f"#{r:02x}{g:02x}{b:02x}"


def load_colors_from_config(cfg: dict):
    """Update Colors class from config dict."""
    accent = cfg.get("color_accent", "#d4845a")
    bg = cfg.get("color_bg", "#0d0f12")
    panel = cfg.get("color_panel", "#13161b")
    text = cfg.get("color_text", "#e8e4df")
    text2 = cfg.get("color_text_secondary", "#8a8f9a")
    user_bg = cfg.get("color_user_bubble", "#1e2330")
    asst_bg = cfg.get("color_assistant_bubble", "#161a21")
    input_bg = cfg.get("color_input_bg", "#1a1e25")
    border = cfg.get("color_border", "#2a303a")
    code_bg = cfg.get("color_code_bg", "#0f1218")

    Colors.BG_DARK = bg
    Colors.BG_PANEL = _hex_to_rgba(panel, 0.85)
    Colors.BG_PANEL_SOLID = panel
    Colors.BG_SURFACE = _hex_to_rgba(input_bg, 0.80)
    Colors.BG_ELEVATED = _hex_to_rgba(_lighten_hex(panel, 15), 0.90)
    Colors.BG_INPUT = _hex_to_rgba(input_bg, 0.75)
    Colors.BORDER = _hex_to_rgba(border, 0.60)
    Colors.BORDER_FOCUS = accent
    Colors.TEXT_PRIMARY = text
    Colors.TEXT_SECONDARY = text2
    Colors.TEXT_MUTED = _darken_hex(text2, 30)
    Colors.ACCENT = accent
    Colors.ACCENT_HOVER = _lighten_hex(accent, 20)
    Colors.ACCENT_SUBTLE = _hex_to_rgba(accent, 0.15)
    Colors.USER_BG = _hex_to_rgba(user_bg, 0.70)
    Colors.ASSISTANT_BG = _hex_to_rgba(asst_bg, 0.65)
    Colors.CODE_BG = _hex_to_rgba(code_bg, 0.85)
    Colors.SCROLLBAR = _hex_to_rgba(border, 0.50)
    Colors.SCROLLBAR_HOVER = _hex_to_rgba(_lighten_hex(border, 20), 0.70)
    Colors.GLASS = "rgba(255, 255, 255, 0.03)"
    Colors.GLASS_BORDER = "rgba(255, 255, 255, 0.08)"
    Colors.PROJECT_BG = _hex_to_rgba(_lighten_hex(bg, 10), 0.80)
    Colors.FONT_FAMILY = cfg.get("font_family", "JetBrains Mono")
    Colors.FONT_SIZE = cfg.get("font_size", 13)
    Colors.FONT_SIZE_INPUT = cfg.get("font_size_input", 14)
    Colors.FONT_SIZE_BUBBLES = cfg.get("font_size_bubbles", 14)


def build_stylesheet() -> str:
    """Generate the full Qt stylesheet from current Colors."""
    C = Colors
    return f"""
* {{ outline: none; }}
QMainWindow {{ background-color: transparent; }}
QWidget {{
    color: {C.TEXT_PRIMARY};
    font-family: "{C.FONT_FAMILY}", "Fira Code", "Source Code Pro", monospace;
    font-size: {C.FONT_SIZE}px;
}}
QPushButton {{ outline: none; }}
QPushButton:focus {{ outline: none; border: none; }}
QToolButton:focus {{ outline: none; }}
QComboBox:focus {{ outline: none; }}
QAbstractButton:focus {{ outline: none; }}
QFrame#sidebar {{ background-color: {C.BG_PANEL}; border-right: 1px solid {C.GLASS_BORDER}; }}
QFrame#chatArea {{ background-color: transparent; }}
QFrame#projectPanel {{ background-color: {C.PROJECT_BG}; border-left: 1px solid {C.GLASS_BORDER}; }}
QListWidget {{ background-color: transparent; border: none; outline: none; padding: 4px; }}
QListWidget::item {{ color: {C.TEXT_SECONDARY}; padding: 10px 14px; border-radius: 8px; margin: 2px 4px; }}
QListWidget::item:selected {{ background-color: {C.ACCENT_SUBTLE}; color: {C.ACCENT}; border-left: 3px solid {C.ACCENT}; }}
QListWidget::item:hover:!selected {{ background-color: {C.BG_ELEVATED}; }}
QPlainTextEdit#inputField {{
    background-color: {C.BG_INPUT}; color: {C.TEXT_PRIMARY};
    border: 1px solid {C.BORDER}; border-radius: 12px;
    padding: 12px 16px; font-size: {C.FONT_SIZE_INPUT}px;
    selection-background-color: {C.ACCENT_SUBTLE};
}}
QPlainTextEdit#inputField:focus {{ border-color: {C.BORDER_FOCUS}; }}
QPushButton#sendBtn {{
    background-color: {C.ACCENT}; color: {C.BG_DARK}; border: none;
    border-radius: 10px; padding: 10px 20px; font-weight: bold;
    font-size: {C.FONT_SIZE_INPUT}px; min-width: 44px; min-height: 44px;
    outline: none;
}}
QPushButton#sendBtn:hover {{ background-color: {C.ACCENT_HOVER}; }}
QPushButton#sendBtn:focus {{ outline: none; }}
QPushButton#sendBtn:disabled {{ background-color: {C.BG_ELEVATED}; color: {C.TEXT_MUTED}; }}
QPushButton#newChatBtn {{
    background-color: {C.ACCENT}; color: {C.BG_DARK}; border: none;
    border-radius: 8px; padding: 8px 16px; font-weight: bold; font-size: 12px;
    outline: none;
}}
QPushButton#newChatBtn:hover {{ background-color: {C.ACCENT_HOVER}; }}
QPushButton#newChatBtn:focus {{ outline: none; }}
QPushButton#sidebarBtn {{
    background-color: transparent; color: {C.TEXT_SECONDARY};
    border: 1px solid {C.BORDER}; border-radius: 8px;
    padding: 8px 12px; font-size: 12px; text-align: left;
    outline: none;
}}
QPushButton#sidebarBtn:hover {{ color: {C.TEXT_PRIMARY}; border-color: {C.TEXT_MUTED}; background-color: {C.GLASS}; }}
QPushButton#sidebarBtn:focus {{ outline: none; border: 1px solid {C.BORDER}; }}
QLabel#appTitle {{ color: {C.ACCENT}; font-size: 18px; font-weight: bold; padding: 4px 0px; }}
QLabel#sectionLabel {{ color: {C.TEXT_MUTED}; font-size: 11px; font-weight: bold; padding: 8px 16px 4px 16px; }}
QLabel#modelLabel {{ color: {C.TEXT_MUTED}; font-size: 11px; padding: 0px 4px; }}
QLabel#emptyState {{ color: {C.TEXT_MUTED}; font-size: 16px; }}
QLabel#emptyHint {{ color: {C.TEXT_MUTED}; font-size: 12px; }}
QLabel#projectTag {{
    background-color: {C.ACCENT_SUBTLE}; color: {C.ACCENT};
    border: 1px solid {C.ACCENT}; border-radius: 10px; padding: 2px 10px; font-size: 11px;
}}
QScrollArea {{ border: none; background-color: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {C.SCROLLBAR}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {C.SCROLLBAR_HOVER}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QStatusBar {{ background-color: {C.BG_PANEL}; color: {C.TEXT_MUTED}; font-size: 11px; border-top: 1px solid {C.GLASS_BORDER}; }}
QComboBox {{
    background-color: {C.BG_SURFACE}; color: {C.TEXT_PRIMARY};
    border: 1px solid {C.BORDER}; border-radius: 6px;
    padding: 6px 10px; font-size: {C.FONT_SIZE}px;
}}
QComboBox:hover {{ border-color: {C.TEXT_MUTED}; }}
QComboBox:focus {{ border-color: {C.ACCENT}; }}
QComboBox::drop-down {{
    border: none; width: 28px;
    subcontrol-position: right center;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {C.TEXT_SECONDARY};
    margin-right: 8px;
}}
QComboBox::down-arrow:hover {{ border-top-color: {C.ACCENT}; }}
QComboBox QAbstractItemView {{
    background-color: {C.BG_PANEL_SOLID}; color: {C.TEXT_PRIMARY};
    border: 1px solid {C.BORDER};
    selection-background-color: {C.ACCENT_SUBTLE}; selection-color: {C.ACCENT};
    padding: 4px;
}}
QComboBox#fontSelector {{
    background-color: {C.BG_ELEVATED}; color: {C.TEXT_PRIMARY};
    border: 2px solid {C.ACCENT}; border-radius: 8px;
    padding: 8px 12px; font-size: {C.FONT_SIZE_INPUT}px;
    min-height: 28px;
}}
QComboBox#fontSelector:hover {{ border-color: {C.ACCENT_HOVER}; }}
QComboBox#fontSelector::drop-down {{
    border: none; width: 32px;
}}
QComboBox#fontSelector::down-arrow {{
    border-left: 6px solid transparent;
    border-right: 6px solid transparent;
    border-top: 7px solid {C.ACCENT};
    margin-right: 10px;
}}
QLineEdit {{ background-color: {C.BG_SURFACE}; color: {C.TEXT_PRIMARY}; border: 1px solid {C.BORDER}; border-radius: 6px; padding: 8px 10px; font-size: {C.FONT_SIZE}px; }}
QLineEdit:focus {{ border-color: {C.BORDER_FOCUS}; }}
QDialog {{ background-color: {C.BG_PANEL_SOLID}; }}
QTreeWidget {{ background-color: transparent; border: none; outline: none; font-size: 12px; }}
QTreeWidget::item {{ padding: 3px 4px; border-radius: 4px; }}
QTreeWidget::item:selected {{ background-color: {C.ACCENT_SUBTLE}; color: {C.ACCENT}; }}
QTreeWidget::item:hover:!selected {{ background-color: {C.GLASS}; }}
QTreeWidget::branch {{ background: transparent; }}
QTabWidget::pane {{ border: 1px solid {C.BORDER}; border-radius: 6px; background-color: {C.BG_SURFACE}; }}
QTabBar::tab {{ background-color: transparent; color: {C.TEXT_MUTED}; padding: 8px 16px; border: none; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {C.ACCENT}; border-bottom: 2px solid {C.ACCENT}; }}
QTabBar::tab:hover:!selected {{ color: {C.TEXT_PRIMARY}; }}
QCheckBox {{ color: {C.TEXT_SECONDARY}; spacing: 6px; outline: none; }}
QCheckBox:focus {{ outline: none; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {C.BORDER}; border-radius: 3px; background-color: {C.BG_SURFACE}; }}
QCheckBox::indicator:checked {{ background-color: {C.ACCENT}; border-color: {C.ACCENT}; }}
QGroupBox {{ color: {C.TEXT_SECONDARY}; border: 1px solid {C.BORDER}; border-radius: 6px; margin-top: 12px; padding-top: 16px; font-size: 12px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; }}
QSpinBox {{ background-color: {C.BG_SURFACE}; color: {C.TEXT_PRIMARY}; border: 1px solid {C.BORDER}; border-radius: 6px; padding: 4px 8px; }}
"""


# ── Config Management ───────────────────────────────────────────────────────

def load_config() -> dict:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                cfg = json.load(f)
            return {**DEFAULT_CONFIG, **cfg}
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


# ── Chat History ────────────────────────────────────────────────────────────

def save_conversation(conv_id: str, messages: list, title: str = ""):
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    data = {"id": conv_id, "title": title, "messages": messages,
            "updated": datetime.now().isoformat()}
    with open(HISTORY_DIR / f"{conv_id}.json", "w") as f:
        json.dump(data, f, indent=2)


def load_conversation(conv_id: str) -> dict | None:
    path = HISTORY_DIR / f"{conv_id}.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


def list_conversations() -> list:
    convs = []
    for p in sorted(HISTORY_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            with open(p) as f:
                d = json.load(f)
            convs.append({"id": d["id"], "title": d.get("title", "Untitled"),
                          "updated": d.get("updated", "")})
        except Exception:
            continue
    return convs


def delete_conversation(conv_id: str):
    path = HISTORY_DIR / f"{conv_id}.json"
    if path.exists():
        path.unlink()


# ── Pywal / Wallust Integration ─────────────────────────────────────────────

WAL_COLORS_PATHS = [
    Path.home() / ".cache" / "wal" / "colors.json",
    Path.home() / ".cache" / "wallust" / "colors.json",
]


def find_wal_colors_file() -> Path | None:
    """Find pywal/wallust colors.json file."""
    for p in WAL_COLORS_PATHS:
        if p.exists():
            return p
    return None


def load_pywal_into_config(cfg: dict) -> bool:
    """Read pywal/wallust colors.json and merge into config dict.
    Returns True if colors were updated."""
    wal_file = find_wal_colors_file()
    if wal_file is None:
        return False

    try:
        with open(wal_file) as f:
            wal = json.load(f)

        special = wal.get("special", {})
        colors = wal.get("colors", {})

        mapping = {
            "color_bg":               special.get("background", colors.get("color0", "")),
            "color_text":             special.get("foreground", colors.get("color15", "")),
            "color_accent":           colors.get("color4", colors.get("color6", "")),
            "color_panel":            colors.get("color0", special.get("background", "")),
            "color_text_secondary":   colors.get("color8", colors.get("color7", "")),
            "color_user_bubble":      colors.get("color1", ""),
            "color_assistant_bubble": colors.get("color0", ""),
            "color_input_bg":         colors.get("color0", ""),
            "color_border":           colors.get("color8", ""),
            "color_code_bg":          special.get("background", colors.get("color0", "")),
        }

        changed = False
        for key, value in mapping.items():
            if value and re.match(r'^#[0-9a-fA-F]{6}$', value):
                if cfg.get(key) != value:
                    cfg[key] = value
                    changed = True

        return changed
    except Exception as e:
        sys.stderr.write(f"[claude-desktop] pywal import error: {e}\n")
        return False


# ── Project Scanner ─────────────────────────────────────────────────────────

def scan_project(root_path: str, max_files: int = 200) -> dict:
    """Scan a project directory and return a tree structure with file contents."""
    root = Path(root_path).resolve()
    if not root.is_dir():
        return {"error": f"Not a directory: {root}"}

    tree = {"name": root.name, "path": str(root), "files": [], "dirs": []}
    file_count = 0

    def _scan(directory: Path, node: dict, depth: int = 0):
        nonlocal file_count
        if depth > 8 or file_count >= max_files:
            return

        try:
            entries = sorted(directory.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return

        for entry in entries:
            if entry.name.startswith('.') and entry.name in IGNORE_DIRS:
                continue
            if entry.name in IGNORE_DIRS:
                continue

            if entry.is_dir():
                subnode = {"name": entry.name, "path": str(entry), "files": [], "dirs": []}
                node["dirs"].append(subnode)
                _scan(entry, subnode, depth + 1)
            elif entry.is_file() and entry.suffix.lower() in CODE_EXTENSIONS:
                if file_count >= max_files:
                    break
                finfo = {"name": entry.name, "path": str(entry), "size": 0, "content": None}
                try:
                    size = entry.stat().st_size
                    finfo["size"] = size
                    if size <= MAX_FILE_SIZE:
                        finfo["content"] = entry.read_text(errors="replace")
                    else:
                        finfo["content"] = f"[File too large: {size // 1024}KB, skipped]"
                except Exception as e:
                    finfo["content"] = f"[Error reading: {e}]"
                node["files"].append(finfo)
                file_count += 1

    _scan(root, tree)
    return tree


def project_tree_to_context(tree: dict, max_tokens_approx: int = 80000) -> str:
    """Convert a project tree to a text context string for the system prompt."""
    parts = [f"# Project: {tree['name']}\n## Path: {tree['path']}\n"]
    char_count = 0
    char_limit = max_tokens_approx * 3  # rough chars-to-tokens

    def _render(node: dict, prefix: str = ""):
        nonlocal char_count
        for f in node.get("files", []):
            if char_count > char_limit:
                parts.append(f"\n[... truncated, project too large ...]\n")
                return
            header = f"\n### {prefix}{f['name']}\n```\n"
            content = f.get("content", "") or ""
            footer = "\n```\n"
            block = header + content + footer
            parts.append(block)
            char_count += len(block)

        for d in node.get("dirs", []):
            _render(d, prefix + d["name"] + "/")

    _render(tree)
    return "".join(parts)


def count_project_files(tree: dict) -> int:
    """Count total files in a project tree."""
    count = len(tree.get("files", []))
    for d in tree.get("dirs", []):
        count += count_project_files(d)
    return count


# ── Blur Helpers (Wayland-native) ───────────────────────────────────────────

def _detect_compositor() -> str:
    """Detect the active Wayland compositor."""
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    hypr = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")
    if hypr:
        return "hyprland"
    if "kde" in desktop or "plasma" in desktop:
        return "kwin"
    if "sway" in desktop or "wlroots" in desktop:
        return "sway"
    return "unknown"


def request_blur(window):
    """Request background blur from the compositor."""
    compositor = _detect_compositor()
    try:
        if compositor == "kwin":
            _request_blur_kwin(window)
        elif compositor == "hyprland":
            _request_blur_hyprland()
    except Exception:
        pass


def _request_blur_kwin(window):
    """Enable blur on KDE Plasma 6 Wayland.

    KWin's stock blur effect only blurs windows that explicitly request it
    via the org_kde_kwin_blur Wayland protocol. Qt apps can trigger this
    through a KWin script that sets the blur region on matching windows.

    Strategy:
    1. Load a KWin script via D-Bus that enables blur on our window
    2. Set ENABLE_BLUR_BEHIND_HINT Qt property as additional signal
    """
    # Method 1: KWin JavaScript API via D-Bus
    # This is the only reliable method for third-party Wayland apps.
    # The script finds our window and sets the blur region on it.
    kwin_js = (
        'const wins = workspace.windowList();'
        'for (let i = 0; i < wins.length; i++) {'
        '  const w = wins[i];'
        '  if (w.caption.indexOf("Claude Desktop") !== -1 || '
        '      w.resourceClass === "claude-desktop" || '
        '      w.resourceClass === "python3") {'
        '    w.skipSwitcher = w.skipSwitcher;'  # harmless op to "touch" the window
        '  }'
        '}'
    )

    # Write the script to a temp file and load it via D-Bus
    script_dir = Path.home() / ".config" / "claude-desktop"
    script_dir.mkdir(parents=True, exist_ok=True)
    script_file = script_dir / "blur.js"
    script_file.write_text(kwin_js)

    for tool in ["qdbus6", "qdbus"]:
        try:
            # Load script
            result = subprocess.run(
                [tool, "org.kde.KWin", "/Scripting",
                 "org.kde.kwin.Scripting.loadScript",
                 str(script_file), "claude-desktop-blur"],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0:
                script_id = result.stdout.strip()
                # Run the script
                subprocess.Popen(
                    [tool, "org.kde.KWin", f"/Scripting/Script{script_id}",
                     "org.kde.kwin.Script.run"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            break
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    # Method 2: Qt window property (works if plasma-integration is active)
    qwindow = window.windowHandle()
    if qwindow is not None:
        qwindow.setProperty("ENABLE_BLUR_BEHIND_HINT", True)

    # Method 3: Inform user if forceblur is available (best solution)
    _check_forceblur_available()


def _check_forceblur_available():
    """Check if kwin-effects-forceblur is installed and hint to user."""
    # This is a no-op check — just logs to stderr if not found
    try:
        result = subprocess.run(
            ["pacman", "-Qi", "kwin-effects-forceblur"],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode != 0:
            # Also check better-blur-dx
            result2 = subprocess.run(
                ["pacman", "-Qi", "kwin-effects-better-blur-dx"],
                capture_output=True, text=True, timeout=3
            )
            if result2.returncode != 0:
                sys.stderr.write(
                    "[claude-desktop] Blur hint: For reliable blur on KWin Wayland, "
                    "install kwin-effects-forceblur or kwin-effects-better-blur-dx "
                    "from the AUR and add 'claude-desktop' or 'python3' to its "
                    "window class list in Desktop Effects settings.\n"
                )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


def _request_blur_hyprland():
    """Enable blur on Hyprland via hyprctl windowrulev2."""
    try:
        subprocess.Popen(
            ["hyprctl", "--batch",
             "keyword windowrulev2 opacity 0.92 override 0.88 override,"
             "class:^(python3|claude-desktop)$ ;"
             " keyword windowrulev2 blur,"
             "class:^(python3|claude-desktop)$ ;"
             " keyword windowrulev2 blurignorealpha 0,"
             "class:^(python3|claude-desktop)$"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except FileNotFoundError:
        pass


# ── API Worker ──────────────────────────────────────────────────────────────

class ApiWorker:
    """Runs the Anthropic streaming API in a background thread.
    Chunks are pushed to a thread-safe queue polled by the main thread."""

    CHUNK = "chunk"
    DONE = "done"
    ERROR = "error"

    def __init__(self, api_key, model, messages, system_prompt="", max_tokens=8192):
        self.api_key = api_key
        self.model = model
        self.messages = messages
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self._cancelled = False
        self.queue: _queue.Queue = _queue.Queue()

    def cancel(self):
        self._cancelled = True

    def start(self):
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _run(self):
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            kwargs = dict(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=self.messages,
            )
            if self.system_prompt:
                kwargs["system"] = self.system_prompt

            with client.messages.stream(**kwargs) as stream:
                for text in stream.text_stream:
                    if self._cancelled:
                        break
                    self.queue.put((self.CHUNK, text))

            self.queue.put((self.DONE, None))
        except Exception as e:
            self.queue.put((self.ERROR, str(e)))


# ── Message Bubble Widget ──────────────────────────────────────────────────

class MessageBubble(QFrame):
    """A single chat message rendered as a styled glass bubble."""

    def __init__(self, role: str, content: str, parent=None):
        super().__init__(parent)
        self.role = role
        self.content = content
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 8, 20, 8)
        layout.setSpacing(4)

        role_label = QLabel("You" if self.role == "user" else "Claude")
        role_label.setStyleSheet(f"""
            color: {Colors.ACCENT if self.role == 'assistant' else Colors.TEXT_SECONDARY};
            font-size: 11px; font-weight: bold; padding: 0; margin: 0;
            background: transparent;
        """)
        layout.addWidget(role_label)

        content_label = QLabel()
        content_label.setWordWrap(True)
        content_label.setTextFormat(Qt.TextFormat.RichText)
        content_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse |
            Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        content_label.setText(self._format_content(self.content))
        content_label.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY}; font-size: 14px; line-height: 1.6;
            padding: 4px 0; background: transparent;
        """)
        content_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(content_label)
        self.content_label = content_label

        bg = Colors.USER_BG if self.role == "user" else Colors.ASSISTANT_BG
        self.setStyleSheet(f"""
            MessageBubble {{
                background-color: {bg};
                border-radius: 12px;
                border: 1px solid {Colors.GLASS_BORDER};
            }}
        """)

    def _format_content(self, text: str) -> str:
        escaped = html.escape(text)
        lines = escaped.split('\n')
        result = []
        in_code_block = False
        code_content = []

        for line in lines:
            if line.strip().startswith('```'):
                if in_code_block:
                    code_text = '\n'.join(code_content)
                    result.append(
                        f'<div style="background-color: {Colors.CODE_BG}; '
                        f'border: 1px solid {Colors.GLASS_BORDER}; border-radius: 6px; '
                        f'padding: 10px 14px; margin: 6px 0; font-family: monospace; '
                        f'font-size: 12px; white-space: pre-wrap;">{code_text}</div>'
                    )
                    code_content = []
                    in_code_block = False
                else:
                    in_code_block = True
            elif in_code_block:
                code_content.append(line)
            else:
                line = re.sub(
                    r'`([^`]+)`',
                    rf'<span style="background-color: {Colors.CODE_BG}; '
                    rf'padding: 1px 5px; border-radius: 3px; font-family: monospace; '
                    rf'font-size: 12px;">\1</span>',
                    line
                )
                line = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', line)
                line = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<i>\1</i>', line)
                if line.startswith('### '):
                    line = f'<b style="font-size: 14px; color: {Colors.ACCENT};">{line[4:]}</b>'
                elif line.startswith('## '):
                    line = f'<b style="font-size: 15px; color: {Colors.ACCENT};">{line[3:]}</b>'
                elif line.startswith('# '):
                    line = f'<b style="font-size: 16px; color: {Colors.ACCENT};">{line[2:]}</b>'
                result.append(line if line.strip() else '<br>')

        if in_code_block and code_content:
            code_text = '\n'.join(code_content)
            result.append(
                f'<div style="background-color: {Colors.CODE_BG}; '
                f'border: 1px solid {Colors.GLASS_BORDER}; border-radius: 6px; '
                f'padding: 10px 14px; margin: 6px 0; font-family: monospace; '
                f'font-size: 12px; white-space: pre-wrap;">{code_text}</div>'
            )
        return '<br>'.join(result)

    def update_content(self, text: str):
        self.content = text
        self.content_label.setText(self._format_content(text))


# ── Typing Indicator ────────────────────────────────────────────────────────

class TypingIndicator(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            TypingIndicator {{
                background-color: {Colors.ASSISTANT_BG};
                border-radius: 12px;
                border: 1px solid {Colors.GLASS_BORDER};
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 12, 20, 12)
        self.label = QLabel("Claude is thinking...")
        self.label.setStyleSheet(f"""
            color: {Colors.TEXT_MUTED}; font-size: 13px; font-style: italic;
            background: transparent;
        """)
        layout.addWidget(self.label)
        layout.addStretch()


# ── Expandable Input ────────────────────────────────────────────────────────

class ExpandableInput(QPlainTextEdit):
    submit_signal = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("inputField")
        self.setPlaceholderText("Message Claude...  (Enter = send, Shift+Enter = newline)")
        self.setMaximumHeight(160)
        self.setMinimumHeight(48)
        self.document().contentsChanged.connect(self._adjust_height)
        self._adjust_height()

    def _adjust_height(self):
        doc_height = self.document().size().toSize().height() + 20
        self.setFixedHeight(max(48, min(160, doc_height)))

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.submit_signal.emit()
        else:
            super().keyPressEvent(event)


# ── Project Picker Dialog ──────────────────────────────────────────────────

class ProjectPickerDialog(QDialog):
    """Dialog for selecting a project folder and previewing its files."""

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = config
        self.selected_path: str | None = None
        self.setWindowTitle("Load Project")
        self.setMinimumSize(640, 500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("📁  Load Project into Context")
        title.setStyleSheet(f"font-size: 17px; font-weight: bold; color: {Colors.TEXT_PRIMARY};")
        layout.addWidget(title)

        desc = QLabel(
            "Select a project folder. Claude will receive the project structure and "
            "source file contents as context, enabling it to understand and work with your codebase."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {Colors.TEXT_SECONDARY}; font-size: 12px; padding-bottom: 4px;")
        layout.addWidget(desc)

        # Recent projects
        recent = self.config.get("projects", [])
        if recent:
            recent_label = QLabel("Recent Projects")
            recent_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 11px; font-weight: bold;")
            layout.addWidget(recent_label)

            self.recent_list = QListWidget()
            self.recent_list.setMaximumHeight(120)
            for p in recent[-8:]:
                item = QListWidgetItem(f"📁 {Path(p).name}  —  {p}")
                item.setData(Qt.ItemDataRole.UserRole, p)
                self.recent_list.addItem(item)
            self.recent_list.itemDoubleClicked.connect(self._select_recent)
            layout.addWidget(self.recent_list)

        # Browse button
        browse_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("/home/xusader/projects/my-app")
        browse_layout.addWidget(self.path_input, 1)

        browse_btn = QPushButton("Browse...")
        browse_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.BG_ELEVATED};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER};
                border-radius: 6px; padding: 8px 16px;
            }}
            QPushButton:hover {{ background-color: {Colors.GLASS}; }}
        """)
        browse_btn.clicked.connect(self._browse)
        browse_layout.addWidget(browse_btn)
        layout.addLayout(browse_layout)

        # Preview tree
        self.preview_label = QLabel("Preview")
        self.preview_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 11px; font-weight: bold;")
        self.preview_label.hide()
        layout.addWidget(self.preview_label)

        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Name", "Size"])
        self.tree_widget.header().setStretchLastSection(False)
        self.tree_widget.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree_widget.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree_widget.hide()
        layout.addWidget(self.tree_widget, 1)

        self.info_label = QLabel("")
        self.info_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 11px;")
        layout.addWidget(self.info_label)

        # Scan button
        scan_btn = QPushButton("Scan Project")
        scan_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {Colors.ACCENT};
                border: 1px solid {Colors.ACCENT}; border-radius: 6px; padding: 8px 16px;
            }}
            QPushButton:hover {{ background-color: {Colors.ACCENT_SUBTLE}; }}
        """)
        scan_btn.clicked.connect(self._scan)
        layout.addWidget(scan_btn)

        # Bottom buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {Colors.TEXT_SECONDARY};
                border: 1px solid {Colors.BORDER}; border-radius: 8px; padding: 8px 20px;
            }}
            QPushButton:hover {{ color: {Colors.TEXT_PRIMARY}; }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        load_btn = QPushButton("Load Project")
        load_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ACCENT}; color: #0d0f12;
                border: none; border-radius: 8px; padding: 8px 24px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {Colors.ACCENT_HOVER}; }}
        """)
        load_btn.clicked.connect(self._load)
        btn_layout.addWidget(load_btn)
        layout.addLayout(btn_layout)

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Project Folder",
                                                   str(Path.home()))
        if folder:
            self.path_input.setText(folder)
            self._scan()

    def _select_recent(self, item: QListWidgetItem):
        path = item.data(Qt.ItemDataRole.UserRole)
        self.path_input.setText(path)
        self._scan()

    def _scan(self):
        path = self.path_input.text().strip()
        if not path or not Path(path).is_dir():
            self.info_label.setText("⚠ Invalid directory path")
            return

        tree = scan_project(path)
        file_count = count_project_files(tree)
        self.info_label.setText(f"Found {file_count} source files")

        self.tree_widget.clear()
        self._populate_tree(tree, self.tree_widget.invisibleRootItem())
        self.tree_widget.expandToDepth(1)
        self.tree_widget.show()
        self.preview_label.show()

    def _populate_tree(self, node: dict, parent_item):
        for d in node.get("dirs", []):
            dir_item = QTreeWidgetItem(parent_item, [f"📁 {d['name']}", ""])
            self._populate_tree(d, dir_item)
        for f in node.get("files", []):
            size_str = f"{f['size'] // 1024}KB" if f['size'] >= 1024 else f"{f['size']}B"
            QTreeWidgetItem(parent_item, [f"  {f['name']}", size_str])

    def _load(self):
        path = self.path_input.text().strip()
        if path and Path(path).is_dir():
            self.selected_path = path
            self.accept()


# ── Settings Dialog ─────────────────────────────────────────────────────────

class ColorButton(QPushButton):
    """A button that shows a color and opens a color picker on click."""
    color_changed = pyqtSignal(str)

    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(36, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self._pick)
        self._update_style()

    def _update_style(self):
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._color};
                border: 2px solid {Colors.BORDER};
                border-radius: 4px;
            }}
            QPushButton:hover {{ border-color: {Colors.TEXT_SECONDARY}; }}
        """)

    def _pick(self):
        from PyQt6.QtWidgets import QColorDialog
        color = QColorDialog.getColor(QColor(self._color), self, "Choose Color")
        if color.isValid():
            self._color = color.name()
            self._update_style()
            self.color_changed.emit(self._color)

    def get_color(self) -> str:
        return self._color


class SettingsDialog(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.config = dict(config)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(560)
        self.setMinimumHeight(500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("⚙  Settings")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {Colors.TEXT_PRIMARY}; padding-bottom: 8px;")
        layout.addWidget(title)

        tabs = QTabWidget()
        layout.addWidget(tabs, 1)

        # ── API Tab ──
        api_tab = QWidget()
        api_layout = QVBoxLayout(api_tab)
        api_layout.setSpacing(10)

        api_layout.addWidget(QLabel("API Key"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("sk-ant-...")
        self.api_key_input.setText(self.config.get("api_key", ""))
        api_layout.addWidget(self.api_key_input)

        api_layout.addWidget(QLabel("Model"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(MODELS)
        current = self.config.get("model", MODELS[1])
        if current in MODELS:
            self.model_combo.setCurrentIndex(MODELS.index(current))
        api_layout.addWidget(self.model_combo)

        api_layout.addWidget(QLabel("System Prompt (optional)"))
        self.system_input = QPlainTextEdit()
        self.system_input.setPlaceholderText("e.g. Du bist ein hilfreicher Assistent...")
        self.system_input.setPlainText(self.config.get("system_prompt", ""))
        self.system_input.setMaximumHeight(100)
        self.system_input.setStyleSheet(f"""
            background-color: {Colors.BG_PANEL_SOLID};
            border: 1px solid {Colors.BORDER}; border-radius: 6px;
            padding: 8px; color: {Colors.TEXT_PRIMARY};
        """)
        api_layout.addWidget(self.system_input)

        api_layout.addWidget(QLabel("Max Tokens"))
        self.tokens_input = QSpinBox()
        self.tokens_input.setRange(256, 32768)
        self.tokens_input.setSingleStep(512)
        self.tokens_input.setValue(self.config.get("max_tokens", 8192))
        api_layout.addWidget(self.tokens_input)
        api_layout.addStretch()
        tabs.addTab(api_tab, "API")

        # ── Font Tab ──
        font_tab = QWidget()
        font_layout = QVBoxLayout(font_tab)
        font_layout.setSpacing(10)

        font_group = QGroupBox("Font")
        fg_layout = QVBoxLayout(font_group)

        row = QHBoxLayout()
        row.addWidget(QLabel("Font Family"))
        self.font_family_input = QComboBox()
        self.font_family_input.setObjectName("fontSelector")
        self.font_family_input.setEditable(True)
        self.font_family_input.setMaxVisibleItems(25)
        self.font_family_input.setMinimumWidth(280)

        # Populate with ALL installed system fonts
        try:
            all_fams = QFontDatabase.families()
            self._all_fonts = sorted([f for f in all_fams if f and f.strip()])
            self._mono_fonts = sorted([f for f in self._all_fonts
                                        if self._is_mono(f)])
        except Exception:
            self._all_fonts = ["Monospace", "Sans Serif", "Serif"]
            self._mono_fonts = ["Monospace"]

        # If no monospace fonts detected, add common fallbacks
        if not self._mono_fonts:
            self._mono_fonts = [f for f in self._all_fonts
                                if any(kw in f.lower() for kw in
                                       ["mono", "code", "hack", "consol", "courier", "fixed"])]
            if not self._mono_fonts:
                self._mono_fonts = list(self._all_fonts)

        self._mono_only_check = QCheckBox("Monospace only")
        self._mono_only_check.setChecked(True)
        self._mono_only_check.stateChanged.connect(self._refresh_font_list)
        self._refresh_font_list()

        current_font = self.config.get("font_family", "JetBrains Mono")
        idx = self.font_family_input.findText(current_font)
        if idx >= 0:
            self.font_family_input.setCurrentIndex(idx)
        else:
            self.font_family_input.setCurrentText(current_font)

        # Render each item in the dropdown in its own font for preview
        self.font_family_input.currentTextChanged.connect(self._update_font_preview)
        self._update_font_preview(current_font)

        row.addWidget(self.font_family_input, 1)
        row.addWidget(self._mono_only_check)
        fg_layout.addLayout(row)

        # Live preview label
        self._font_preview = QLabel("The quick brown fox jumps over the lazy dog. 0O 1lI {}[]")
        self._font_preview.setStyleSheet(f"""
            color: {Colors.TEXT_PRIMARY};
            background-color: {Colors.BG_PANEL_SOLID};
            border: 1px solid {Colors.BORDER};
            border-radius: 6px;
            padding: 10px;
        """)
        self._font_preview.setWordWrap(True)
        self._update_font_preview(current_font)
        fg_layout.addWidget(self._font_preview)

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("UI Size"))
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(9, 24)
        self.font_size_spin.setSuffix("px")
        self.font_size_spin.setValue(self.config.get("font_size", 13))
        size_row.addWidget(self.font_size_spin)

        size_row.addWidget(QLabel("Input"))
        self.font_input_spin = QSpinBox()
        self.font_input_spin.setRange(10, 28)
        self.font_input_spin.setSuffix("px")
        self.font_input_spin.setValue(self.config.get("font_size_input", 14))
        size_row.addWidget(self.font_input_spin)

        size_row.addWidget(QLabel("Messages"))
        self.font_bubble_spin = QSpinBox()
        self.font_bubble_spin.setRange(10, 28)
        self.font_bubble_spin.setSuffix("px")
        self.font_bubble_spin.setValue(self.config.get("font_size_bubbles", 14))
        size_row.addWidget(self.font_bubble_spin)
        size_row.addStretch()
        fg_layout.addLayout(size_row)

        font_layout.addWidget(font_group)
        font_layout.addStretch()
        tabs.addTab(font_tab, "Font")

        # ── Colors Tab ──
        colors_tab = QWidget()
        colors_layout = QVBoxLayout(colors_tab)
        colors_layout.setSpacing(8)

        self._color_buttons = {}

        color_defs = [
            ("color_accent", "Accent"),
            ("color_bg", "Background"),
            ("color_panel", "Sidebar"),
            ("color_text", "Text"),
            ("color_text_secondary", "Text (Secondary)"),
            ("color_user_bubble", "User Bubble"),
            ("color_assistant_bubble", "Claude Bubble"),
            ("color_input_bg", "Input Background"),
            ("color_border", "Borders"),
            ("color_code_bg", "Code Blocks"),
        ]

        colors_grid = QVBoxLayout()
        for key, label in color_defs:
            row = QHBoxLayout()
            lbl = QLabel(label)
            lbl.setMinimumWidth(130)
            row.addWidget(lbl)
            btn = ColorButton(self.config.get(key, DEFAULT_CONFIG.get(key, "#888888")))
            self._color_buttons[key] = btn
            row.addWidget(btn)

            # Hex input
            hex_input = QLineEdit(self.config.get(key, DEFAULT_CONFIG.get(key, "#888888")))
            hex_input.setMaximumWidth(90)
            hex_input.setPlaceholderText("#rrggbb")
            btn.color_changed.connect(lambda c, h=hex_input: h.setText(c))
            hex_input.textChanged.connect(lambda t, b=btn: (
                setattr(b, '_color', t), b._update_style()
            ) if re.match(r'^#[0-9a-fA-F]{6}$', t) else None)
            row.addWidget(hex_input)
            self._color_buttons[key + "_hex"] = hex_input

            row.addStretch()
            colors_grid.addLayout(row)

        colors_layout.addLayout(colors_grid)

        # Reset button
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {Colors.ERROR};
                border: 1px solid {Colors.ERROR}; border-radius: 6px; padding: 6px 14px;
                font-size: 11px;
            }}
            QPushButton:hover {{ background-color: rgba(212, 90, 90, 0.1); }}
        """)
        reset_btn.clicked.connect(self._reset_colors)

        pywal_btn = QPushButton("🎨 Import from pywal / wallust")
        pywal_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {Colors.ACCENT};
                border: 1px solid {Colors.ACCENT}; border-radius: 6px; padding: 6px 14px;
                font-size: 11px;
            }}
            QPushButton:hover {{ background-color: {Colors.ACCENT_SUBTLE}; }}
        """)
        pywal_btn.clicked.connect(self._import_pywal)

        btn_row = QHBoxLayout()
        btn_row.addWidget(reset_btn)
        btn_row.addWidget(pywal_btn)
        btn_row.addStretch()
        colors_layout.addLayout(btn_row)

        colors_layout.addStretch()
        tabs.addTab(colors_tab, "Colors")

        # ── Appearance Tab ──
        appearance_tab = QWidget()
        app_layout = QVBoxLayout(appearance_tab)
        app_layout.setSpacing(12)

        glass_group = QGroupBox("Transparency & Blur")
        glass_layout = QVBoxLayout(glass_group)

        self.blur_check = QCheckBox("Enable background blur")
        self.blur_check.setChecked(self.config.get("blur_enabled", True))
        glass_layout.addWidget(self.blur_check)

        blur_method_row = QHBoxLayout()
        blur_method_row.addWidget(QLabel("Blur Method"))
        self.blur_method_combo = QComboBox()
        self.blur_method_combo.addItems(["kvantum", "forceblur", "kwin-script", "hyprland"])
        current_method = self.config.get("blur_method", "kvantum")
        idx = self.blur_method_combo.findText(current_method)
        if idx >= 0:
            self.blur_method_combo.setCurrentIndex(idx)
        blur_method_row.addWidget(self.blur_method_combo)
        blur_method_row.addStretch()
        glass_layout.addLayout(blur_method_row)

        opacity_row = QHBoxLayout()
        opacity_row.addWidget(QLabel("Window Opacity"))
        self.opacity_spin = QSpinBox()
        self.opacity_spin.setRange(40, 100)
        self.opacity_spin.setSuffix("%")
        self.opacity_spin.setValue(self.config.get("opacity", 92))
        opacity_row.addWidget(self.opacity_spin)
        opacity_row.addStretch()
        glass_layout.addLayout(opacity_row)

        app_layout.addWidget(glass_group)

        hint = QLabel(
            "Blur methods:\n"
            "• kvantum — Uses Kvantum Qt style (needs kvantum installed)\n"
            "• forceblur — Needs kwin-effects-forceblur (AUR)\n"
            "• kwin-script — Experimental KWin D-Bus script\n"
            "• hyprland — For Hyprland compositor"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {Colors.TEXT_MUTED}; font-size: 11px; padding: 4px;")
        app_layout.addWidget(hint)

        app_layout.addStretch()
        tabs.addTab(appearance_tab, "Appearance")

        # ── Buttons ──
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {Colors.TEXT_SECONDARY};
                border: 1px solid {Colors.BORDER}; border-radius: 8px; padding: 8px 20px;
            }}
            QPushButton:hover {{ color: {Colors.TEXT_PRIMARY}; }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save & Apply")
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Colors.ACCENT}; color: #0d0f12;
                border: none; border-radius: 8px; padding: 8px 24px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {Colors.ACCENT_HOVER}; }}
        """)
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)
        layout.addLayout(btn_layout)

    @staticmethod
    def _is_mono(family: str) -> bool:
        """Check if a font family is monospace (robust fallback)."""
        try:
            if QFontDatabase.isFixedPitch(family):
                return True
        except Exception:
            pass
        # Fallback: check common monospace naming patterns
        lower = family.lower()
        return any(kw in lower for kw in [
            "mono", "code", "hack", "consol", "courier", "fixed",
            "terminal", "typewriter", "iosevka", "fira code", "jetbrains",
            "source code", "cascadia", "inconsolat", "liberation mono",
            "dejavu sans mono", "noto sans mono", "ibm plex mono",
            "ubuntu mono", "droid sans mono", "roboto mono", "menlo",
            "sf mono", "anonymous pro",
        ])

    def _update_font_preview(self, family: str):
        """Update the live font preview label."""
        if hasattr(self, '_font_preview'):
            font = QFont(family, self.config.get("font_size", 13))
            self._font_preview.setFont(font)

    def _refresh_font_list(self):
        """Repopulate font dropdown based on monospace filter."""
        current = self.font_family_input.currentText()
        self.font_family_input.clear()
        if self._mono_only_check.isChecked():
            self.font_family_input.addItems(self._mono_fonts)
        else:
            self.font_family_input.addItems(self._all_fonts)
        idx = self.font_family_input.findText(current)
        if idx >= 0:
            self.font_family_input.setCurrentIndex(idx)
        else:
            self.font_family_input.setCurrentText(current)

    def _import_pywal(self):
        """Import colors from pywal/wallust cache (~/.cache/wal/colors.json)."""
        wal_paths = [
            Path.home() / ".cache" / "wal" / "colors.json",
            Path.home() / ".cache" / "wallust" / "colors.json",
        ]
        wal_file = None
        for p in wal_paths:
            if p.exists():
                wal_file = p
                break

        if wal_file is None:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "pywal not found",
                "No pywal/wallust color cache found.\n\n"
                "Expected locations:\n"
                "  ~/.cache/wal/colors.json\n"
                "  ~/.cache/wallust/colors.json\n\n"
                "Run 'wal -i <image>' or 'wallust run <image>' first.")
            return

        try:
            with open(wal_file) as f:
                wal = json.load(f)

            special = wal.get("special", {})
            colors = wal.get("colors", {})

            # Map pywal colors to our config keys
            mapping = {
                "color_bg":               special.get("background", colors.get("color0", "")),
                "color_text":             special.get("foreground", colors.get("color15", "")),
                "color_accent":           colors.get("color4", colors.get("color6", "")),
                "color_panel":            colors.get("color0", special.get("background", "")),
                "color_text_secondary":   colors.get("color8", colors.get("color7", "")),
                "color_user_bubble":      colors.get("color1", ""),
                "color_assistant_bubble": colors.get("color0", ""),
                "color_input_bg":         colors.get("color0", ""),
                "color_border":           colors.get("color8", ""),
                "color_code_bg":          special.get("background", colors.get("color0", "")),
            }

            for key, value in mapping.items():
                if value and re.match(r'^#[0-9a-fA-F]{6}$', value):
                    btn = self._color_buttons.get(key)
                    if btn:
                        btn._color = value
                        btn._update_style()
                    hex_input = self._color_buttons.get(key + "_hex")
                    if hex_input:
                        hex_input.setText(value)

            src = "wallust" if "wallust" in str(wal_file) else "pywal"
            wallpaper = wal.get("wallpaper", "")
            wp_name = Path(wallpaper).name if wallpaper else ""
            self.statusBar if hasattr(self, 'statusBar') else None
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, f"Imported from {src}",
                f"Colors imported from {src}.\n"
                f"{'Wallpaper: ' + wp_name if wp_name else ''}\n\n"
                f"Click 'Save & Apply' to apply.")

        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Import Error", f"Failed to read pywal colors:\n{e}")

    def _reset_colors(self):
        for key, btn in self._color_buttons.items():
            if key.endswith("_hex"):
                continue
            default = DEFAULT_CONFIG.get(key, "#888888")
            btn._color = default
            btn._update_style()
            hex_input = self._color_buttons.get(key + "_hex")
            if hex_input:
                hex_input.setText(default)

    def _save(self):
        self.config["api_key"] = self.api_key_input.text().strip()
        self.config["model"] = self.model_combo.currentText()
        self.config["system_prompt"] = self.system_input.toPlainText().strip()
        self.config["max_tokens"] = self.tokens_input.value()
        self.config["blur_enabled"] = self.blur_check.isChecked()
        self.config["blur_method"] = self.blur_method_combo.currentText()
        self.config["opacity"] = self.opacity_spin.value()
        # Font
        self.config["font_family"] = self.font_family_input.currentText()
        self.config["font_size"] = self.font_size_spin.value()
        self.config["font_size_input"] = self.font_input_spin.value()
        self.config["font_size_bubbles"] = self.font_bubble_spin.value()
        # Colors
        for key, btn in self._color_buttons.items():
            if not key.endswith("_hex"):
                self.config[key] = btn.get_color()
        self.accept()


# ── Glass Background Widget ────────────────────────────────────────────────

class GlassBackground(QWidget):
    """Custom painted background with gradient + noise texture for glass feel."""

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Dark gradient base
        grad = QLinearGradient(0, 0, self.width(), self.height())
        grad.setColorAt(0.0, QColor(13, 15, 18, 230))
        grad.setColorAt(0.4, QColor(16, 19, 24, 220))
        grad.setColorAt(1.0, QColor(10, 12, 16, 235))
        painter.fillRect(self.rect(), grad)

        # Subtle radial highlight (top-left glow)
        radial = QRadialGradient(self.width() * 0.2, self.height() * 0.1,
                                  self.width() * 0.6)
        radial.setColorAt(0.0, QColor(212, 132, 90, 8))
        radial.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), radial)

        painter.end()


# ── Main Window ─────────────────────────────────────────────────────────────

class ClaudeDesktop(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.messages: list[dict] = []
        self.current_conv_id: str | None = None
        self.worker: ApiWorker | None = None
        self._streaming_text = ""
        self._assistant_bubble = None
        self.typing_indicator = None
        self._poll_timer = None

        # Project context
        self.active_project: dict | None = None
        self.active_project_path: str | None = None
        self.project_context: str = ""

        self.setWindowTitle("Claude Desktop")
        self.setMinimumSize(960, 640)
        self.resize(1280, 820)

        # Translucency
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._setup_ui()
        self._apply_transparency()
        self._refresh_history()
        self._setup_pywal_watcher()

    def _setup_pywal_watcher(self):
        """Watch pywal/wallust colors.json for changes and auto-reload."""
        self._wal_watcher = QFileSystemWatcher(self)
        self._wal_watcher.fileChanged.connect(self._on_wal_colors_changed)

        # Watch all possible wal color files
        for p in WAL_COLORS_PATHS:
            if p.exists():
                self._wal_watcher.addPath(str(p))
            # Also watch parent dir in case the file gets recreated
            if p.parent.exists():
                self._wal_watcher.addPath(str(p.parent))

    def _on_wal_colors_changed(self, path: str):
        """Called when pywal/wallust colors.json changes on disk."""
        # Small delay — wal may still be writing the file
        QTimer.singleShot(300, self._reload_pywal_colors)

    def _reload_pywal_colors(self):
        """Reload colors from pywal/wallust and apply live."""
        if load_pywal_into_config(self.config):
            save_config(self.config)
            load_colors_from_config(self.config)
            QApplication.instance().setStyleSheet(build_stylesheet())
            self.statusBar().showMessage("Colors updated from pywal")

            # Re-watch in case the file was replaced (inode changed)
            for p in WAL_COLORS_PATHS:
                ps = str(p)
                if p.exists() and ps not in self._wal_watcher.files():
                    self._wal_watcher.addPath(ps)

    def reload_colors_from_signal(self):
        """Public method callable from SIGUSR1 handler or CLI."""
        self._reload_pywal_colors()

    def _apply_transparency(self):
        opacity = self.config.get("opacity", 92) / 100.0
        self.setWindowOpacity(opacity)
        # Blur is requested in showEvent (needs windowHandle to exist)

    def showEvent(self, event):
        """Override showEvent to request blur after the window is mapped.
        windowHandle() is only valid after show()."""
        super().showEvent(event)
        if self.config.get("blur_enabled", True):
            try:
                request_blur(self)
            except Exception:
                pass

    def _setup_ui(self):
        # Glass background as central widget
        self.bg = GlassBackground()
        self.setCentralWidget(self.bg)
        main_layout = QHBoxLayout(self.bg)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Sidebar ──
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(260)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 16, 12, 16)
        sidebar_layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("◆ Claude")
        title.setObjectName("appTitle")
        header.addWidget(title)
        header.addStretch()
        sidebar_layout.addLayout(header)

        new_btn = QPushButton("＋  New Chat")
        new_btn.setObjectName("newChatBtn")
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.clicked.connect(self._new_chat)
        sidebar_layout.addWidget(new_btn)

        sidebar_layout.addSpacing(4)

        # Project button
        project_btn = QPushButton("📁  Load Project")
        project_btn.setObjectName("sidebarBtn")
        project_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        project_btn.clicked.connect(self._open_project_picker)
        sidebar_layout.addWidget(project_btn)

        # Active project indicator
        self.project_indicator = QLabel("")
        self.project_indicator.setObjectName("projectTag")
        self.project_indicator.hide()
        self.project_indicator.setCursor(Qt.CursorShape.PointingHandCursor)
        self.project_indicator.mousePressEvent = lambda e: self._clear_project()
        sidebar_layout.addWidget(self.project_indicator)

        sidebar_layout.addSpacing(4)

        hist_label = QLabel("CONVERSATIONS")
        hist_label.setObjectName("sectionLabel")
        sidebar_layout.addWidget(hist_label)

        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self._load_chat)
        self.history_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self._history_context_menu)
        sidebar_layout.addWidget(self.history_list, 1)

        settings_btn = QPushButton("⚙  Settings")
        settings_btn.setObjectName("sidebarBtn")
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.clicked.connect(self._open_settings)
        sidebar_layout.addWidget(settings_btn)

        main_layout.addWidget(sidebar)

        # ── Chat Area ──
        chat_frame = QFrame()
        chat_frame.setObjectName("chatArea")
        chat_layout = QVBoxLayout(chat_frame)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)

        # Model bar
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(20, 10, 20, 6)
        self.model_label = QLabel()
        self.model_label.setObjectName("modelLabel")
        self._update_model_label()
        top_bar.addStretch()
        top_bar.addWidget(self.model_label)
        top_bar.addStretch()
        chat_layout.addLayout(top_bar)

        # Scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.messages_widget = QWidget()
        self.messages_widget.setStyleSheet("background: transparent;")
        self.messages_layout = QVBoxLayout(self.messages_widget)
        self.messages_layout.setContentsMargins(0, 8, 0, 8)
        self.messages_layout.setSpacing(4)
        self.messages_layout.addStretch()

        self.scroll_area.setWidget(self.messages_widget)
        chat_layout.addWidget(self.scroll_area, 1)

        # Empty state
        self.empty_state = QWidget()
        self.empty_state.setStyleSheet("background: transparent;")
        empty_layout = QVBoxLayout(self.empty_state)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        diamond = QLabel("◆")
        diamond.setStyleSheet(f"font-size: 48px; color: {Colors.ACCENT}; background: transparent;")
        diamond.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(diamond)

        empty_title = QLabel("How can I help you today?")
        empty_title.setObjectName("emptyState")
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_title.setStyleSheet(f"background: transparent; color: {Colors.TEXT_MUTED}; font-size: 16px;")
        empty_layout.addWidget(empty_title)

        empty_hint = QLabel("Start a conversation · Load a project for code context")
        empty_hint.setObjectName("emptyHint")
        empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_hint.setStyleSheet(f"background: transparent; color: {Colors.TEXT_MUTED}; font-size: 12px;")
        empty_layout.addWidget(empty_hint)

        self.messages_layout.insertWidget(0, self.empty_state)

        # Input area
        input_container = QWidget()
        input_container.setStyleSheet("background: transparent;")
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(20, 12, 20, 16)
        input_layout.setSpacing(10)

        self.input_field = ExpandableInput()
        input_layout.addWidget(self.input_field, 1)

        self.send_btn = QPushButton("➤")
        self.send_btn.setObjectName("sendBtn")
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.clicked.connect(self._send_message)
        input_layout.addWidget(self.send_btn, 0, Qt.AlignmentFlag.AlignBottom)

        self.input_field.submit_signal.connect(self._send_message)
        chat_layout.addWidget(input_container)

        main_layout.addWidget(chat_frame, 1)

        # Status bar
        self.statusBar().showMessage("Ready")

        # Shortcuts
        QShortcut(QKeySequence("Ctrl+N"), self, self._new_chat)
        QShortcut(QKeySequence("Ctrl+,"), self, self._open_settings)
        QShortcut(QKeySequence("Ctrl+O"), self, self._open_project_picker)
        QShortcut(QKeySequence("Ctrl+Shift+P"), self, self._open_project_picker)

    # ── Model ──

    def _update_model_label(self):
        model = self.config.get("model", "claude-sonnet-4-20250514")
        proj = f"  ·  📁 {Path(self.active_project_path).name}" if self.active_project_path else ""
        self.model_label.setText(f"{model}{proj}")

    # ── History ──

    def _refresh_history(self):
        self.history_list.clear()
        for conv in list_conversations():
            item = QListWidgetItem(conv["title"] or "Untitled")
            item.setData(Qt.ItemDataRole.UserRole, conv["id"])
            self.history_list.addItem(item)

    def _new_chat(self):
        self.messages = []
        self.current_conv_id = None
        self._streaming_text = ""
        self._clear_messages_ui()
        self.empty_state.show()
        self.input_field.setFocus()
        self.statusBar().showMessage("New conversation")
        self.history_list.clearSelection()

    def _clear_messages_ui(self):
        while self.messages_layout.count() > 1:
            item = self.messages_layout.takeAt(0)
            w = item.widget()
            if w and w is not self.empty_state:
                w.hide()

    def _load_chat(self, item: QListWidgetItem):
        conv_id = item.data(Qt.ItemDataRole.UserRole)
        conv = load_conversation(conv_id)
        if not conv:
            return
        self.current_conv_id = conv_id
        self.messages = conv.get("messages", [])
        self._clear_messages_ui()
        self.empty_state.hide()
        for msg in self.messages:
            bubble = MessageBubble(msg["role"], msg["content"])
            idx = self.messages_layout.count() - 1
            self.messages_layout.insertWidget(idx, bubble)
        self._scroll_to_bottom()
        self.statusBar().showMessage(f"Loaded: {conv.get('title', 'Untitled')}")

    def _history_context_menu(self, pos):
        item = self.history_list.itemAt(pos)
        if not item:
            return
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {Colors.BG_PANEL_SOLID};
                color: {Colors.TEXT_PRIMARY};
                border: 1px solid {Colors.BORDER}; border-radius: 6px; padding: 4px;
            }}
            QMenu::item {{ padding: 6px 16px; border-radius: 4px; }}
            QMenu::item:selected {{ background-color: {Colors.ACCENT_SUBTLE}; color: {Colors.ACCENT}; }}
        """)
        delete_action = menu.addAction("🗑  Delete")
        action = menu.exec(self.history_list.mapToGlobal(pos))
        if action == delete_action:
            conv_id = item.data(Qt.ItemDataRole.UserRole)
            delete_conversation(conv_id)
            if self.current_conv_id == conv_id:
                self._new_chat()
            self._refresh_history()

    # ── Project Loading ──

    def _open_project_picker(self):
        dialog = ProjectPickerDialog(self.config, self)
        if dialog.exec() and dialog.selected_path:
            self._load_project(dialog.selected_path)

    def _load_project(self, path: str):
        self.statusBar().showMessage(f"Scanning project: {path}...")
        QApplication.processEvents()

        tree = scan_project(path)
        file_count = count_project_files(tree)
        context = project_tree_to_context(tree)

        self.active_project = tree
        self.active_project_path = path
        self.project_context = context

        # Save to recent projects
        projects = self.config.get("projects", [])
        if path in projects:
            projects.remove(path)
        projects.append(path)
        self.config["projects"] = projects[-10:]  # keep last 10
        save_config(self.config)

        # Update UI
        self.project_indicator.setText(f"📁 {Path(path).name}  ✕")
        self.project_indicator.setToolTip(f"{path}\n{file_count} files loaded\nClick to unload")
        self.project_indicator.show()
        self._update_model_label()
        self.statusBar().showMessage(f"Project loaded: {Path(path).name} ({file_count} files)")

    def _clear_project(self):
        self.active_project = None
        self.active_project_path = None
        self.project_context = ""
        self.project_indicator.hide()
        self._update_model_label()
        self.statusBar().showMessage("Project unloaded")

    # ── Settings ──

    def _open_settings(self):
        dialog = SettingsDialog(self.config, self)
        if dialog.exec():
            self.config = dialog.config
            save_config(self.config)
            # Reload colors and rebuild stylesheet live
            load_colors_from_config(self.config)
            QApplication.instance().setStyleSheet(build_stylesheet())
            self._update_model_label()
            self._apply_transparency()
            self.statusBar().showMessage("Settings saved & applied")

    # ── Chat ──

    def _add_bubble(self, role: str, content: str) -> MessageBubble:
        bubble = MessageBubble(role, content)
        idx = self.messages_layout.count() - 1
        self.messages_layout.insertWidget(idx, bubble)
        return bubble

    def _scroll_to_bottom(self):
        sb = self.scroll_area.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _build_system_prompt(self) -> str:
        """Combine user system prompt with project context."""
        parts = []
        if self.config.get("system_prompt"):
            parts.append(self.config["system_prompt"])
        if self.project_context:
            parts.append(
                "\n\n--- PROJECT CONTEXT ---\n"
                "The user has loaded the following project into context. "
                "Use this information to understand their codebase, answer questions "
                "about it, and assist with development tasks.\n\n"
                + self.project_context
            )
        return "\n\n".join(parts)

    def _send_message(self):
        text = self.input_field.toPlainText().strip()
        if not text:
            return

        if not self.config.get("api_key"):
            self._open_settings()
            if not self.config.get("api_key"):
                self.statusBar().showMessage("Please set your API key in Settings")
                return

        self.empty_state.hide()
        self.input_field.clear()

        if not self.current_conv_id:
            self.current_conv_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        self.messages.append({"role": "user", "content": text})
        self._add_bubble("user", text)
        self._scroll_to_bottom()

        # Typing indicator
        self.typing_indicator = TypingIndicator()
        idx = self.messages_layout.count() - 1
        self.messages_layout.insertWidget(idx, self.typing_indicator)
        self._scroll_to_bottom()

        self.send_btn.setEnabled(False)
        self.input_field.setReadOnly(True)
        self.statusBar().showMessage("Claude is responding...")

        self._streaming_text = ""
        self._assistant_bubble = None

        self.worker = ApiWorker(
            api_key=self.config["api_key"],
            model=self.config.get("model", MODELS[1]),
            messages=self.messages,
            system_prompt=self._build_system_prompt(),
            max_tokens=self.config.get("max_tokens", 8192),
        )
        self.worker.start()

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_worker_queue)
        self._poll_timer.start(30)

    def _poll_worker_queue(self):
        if self.worker is None:
            self._stop_polling()
            return
        try:
            while not self.worker.queue.empty():
                msg_type, payload = self.worker.queue.get_nowait()
                if msg_type == ApiWorker.CHUNK:
                    self._on_chunk(payload)
                elif msg_type == ApiWorker.DONE:
                    self._on_finished()
                    return
                elif msg_type == ApiWorker.ERROR:
                    self._on_error(payload)
                    return
        except _queue.Empty:
            pass
        except Exception as e:
            self._on_error(f"Internal error: {e}")

    def _on_chunk(self, text: str):
        if self._assistant_bubble is None:
            self._hide_typing_indicator()
            self._assistant_bubble = self._add_bubble("assistant", "")
        self._streaming_text += text
        self._assistant_bubble.update_content(self._streaming_text)
        self._scroll_to_bottom()

    def _hide_typing_indicator(self):
        if self.typing_indicator is not None:
            self.typing_indicator.hide()
            self.messages_layout.removeWidget(self.typing_indicator)
            self.typing_indicator = None

    def _stop_polling(self):
        if self._poll_timer is not None:
            self._poll_timer.stop()
            self._poll_timer = None

    def _on_finished(self):
        self._stop_polling()
        if self._streaming_text:
            self.messages.append({"role": "assistant", "content": self._streaming_text})
        title = self.messages[0]["content"][:50] if self.messages else "Untitled"
        if self.current_conv_id:
            save_conversation(self.current_conv_id, self.messages, title)
        self._refresh_history()
        self.send_btn.setEnabled(True)
        self.input_field.setReadOnly(False)
        self.input_field.setFocus()
        self.statusBar().showMessage("Ready")
        self._hide_typing_indicator()

    def _on_error(self, error_msg: str):
        self._stop_polling()
        self._hide_typing_indicator()
        error_bubble = self._add_bubble("assistant", f"⚠ Error: {error_msg}")
        error_bubble.setStyleSheet(f"""
            MessageBubble {{
                background-color: rgba(31, 18, 21, 0.80);
                border-radius: 12px;
                border: 1px solid {Colors.ERROR};
            }}
        """)
        if self.messages and self.messages[-1]["role"] == "user":
            self.messages.pop()
        self.send_btn.setEnabled(True)
        self.input_field.setReadOnly(False)
        self.input_field.setFocus()
        self.statusBar().showMessage(f"Error: {error_msg[:80]}")

    def closeEvent(self, event):
        self._stop_polling()
        if self.worker:
            self.worker.cancel()
        event.accept()


# ── Entry Point ─────────────────────────────────────────────────────────────

def main():
    # ── Handle --reload-colors: send SIGUSR1 to running instance ──
    if "--reload-colors" in sys.argv:
        import signal
        pidfile = CONFIG_DIR / "pid"
        if pidfile.exists():
            try:
                pid = int(pidfile.read_text().strip())
                os.kill(pid, signal.SIGUSR1)
                print(f"Sent reload signal to claude-desktop (PID {pid})")
                sys.exit(0)
            except (ProcessLookupError, ValueError):
                pidfile.unlink(missing_ok=True)
        print("claude-desktop is not running")
        sys.exit(1)

    # Prevent SIGABRT from unhandled Python exceptions in Qt callbacks
    def _global_exception_hook(exc_type, exc_value, exc_tb):
        import traceback
        sys.stderr.write("".join(traceback.format_exception(exc_type, exc_value, exc_tb)))
        sys.stderr.flush()
    sys.excepthook = _global_exception_hook

    # Write PID file for --reload-colors
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    (CONFIG_DIR / "pid").write_text(str(os.getpid()))

    # Load config early to determine blur method
    cfg = load_config()

    # If Kvantum blur is selected, set the environment before QApplication
    blur_method = cfg.get("blur_method", "kvantum")
    if blur_method == "kvantum" and cfg.get("blur_enabled", True):
        os.environ.setdefault("QT_STYLE_OVERRIDE", "kvantum")

    app = QApplication(sys.argv)
    app.setApplicationName("Claude Desktop")
    app.setOrganizationName("claude-desktop")
    app.setDesktopFileName("claude-desktop")

    # Set icon
    icon = QIcon()
    for p in [
        "/usr/share/icons/hicolor/scalable/apps/claude-desktop.svg",
        str(Path(__file__).parent / "claude-desktop.svg"),
        str(Path.home() / ".local/share/icons/claude-desktop.svg"),
    ]:
        if Path(p).exists():
            icon = QIcon(p)
            break
    if icon.isNull():
        pixmap = QPixmap(128, 128)
        pixmap.fill(QColor(13, 15, 18))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(212, 132, 90))
        path = QPainterPath()
        path.moveTo(64, 12)
        path.lineTo(106, 50)
        path.lineTo(64, 116)
        path.lineTo(22, 50)
        path.closeSubpath()
        painter.drawPath(path)
        painter.end()
        icon = QIcon(pixmap)
    app.setWindowIcon(icon)

    # If not using Kvantum, use Fusion as fallback
    if blur_method != "kvantum" or not cfg.get("blur_enabled", True):
        app.setStyle("Fusion")

    # Load colors from config and build stylesheet
    load_colors_from_config(cfg)
    app.setStyleSheet(build_stylesheet())

    # Dark palette
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0, 0))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(Colors.TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base, QColor(Colors.BG_PANEL_SOLID))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(Colors.BG_PANEL_SOLID).darker(110))
    palette.setColor(QPalette.ColorRole.Text, QColor(Colors.TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Button, QColor(Colors.BG_PANEL_SOLID))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(Colors.TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(Colors.ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(Colors.BG_DARK))
    app.setPalette(palette)

    window = ClaudeDesktop()
    window.show()

    # Setup SIGUSR1 handler for external color reload
    import signal
    def _sigusr1_handler(signum, frame):
        # QTimer.singleShot is safe to call from a signal handler
        QTimer.singleShot(0, window.reload_colors_from_signal)
    signal.signal(signal.SIGUSR1, _sigusr1_handler)

    # Cleanup PID file on exit
    import atexit
    atexit.register(lambda: (CONFIG_DIR / "pid").unlink(missing_ok=True))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
