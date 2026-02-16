import sys
import os
import json
import logging
import platform
import subprocess
from collections import deque
from datetime import datetime
from enum import Enum

import keyboard
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QHBoxLayout, QSizePolicy, QDialog, QLineEdit,
    QSystemTrayIcon, QMenu, QFileIconProvider, QStyle, QCheckBox, QTextEdit,
    QComboBox, QMessageBox, QFileDialog, QGridLayout, QDialogButtonBox,
    QTabWidget, QSplitter, QListWidget, QListWidgetItem, QInputDialog,
    QSpinBox, QFormLayout, QGroupBox
)
from PyQt6.QtCore import (
    Qt, QMimeData, QUrl, QSize, QPoint, pyqtSignal, QFileInfo, QEvent,
    QTimer, QThread, pyqtSignal as Signal
)
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtGui import (
    QDrag, QPixmap, QIcon, QAction, QColor, QDesktopServices, QCursor,
    QPainter, QKeySequence, QShortcut, QImage, QFont, QPalette
)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtSvgWidgets import QSvgWidget

try:
    import winreg
except ImportError:
    winreg = None

try:
    import qrcode
    from qrcode.image.pil import PilImage
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

try:
    import urllib.request
    import urllib.parse
    import html.parser
    HAS_URL_FETCH = True
except ImportError:
    HAS_URL_FETCH = False

# ─── Logging ──────────────────────────────────────────────────────────────────
def get_data_dir():
    """Get platform-specific data directory with robust error handling"""
    try:
        sys_name = platform.system()
        if sys_name == 'Windows':
            base = os.environ.get('APPDATA', os.path.expanduser('~'))
        elif sys_name == 'Darwin':
            base = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support')
        else:  # Linux and other Unix-like systems
            base = os.environ.get('XDG_DATA_HOME', os.path.join(os.path.expanduser('~'), '.local', 'share'))
        
        data_dir = os.path.join(base, 'DropShelf')
        os.makedirs(data_dir, exist_ok=True)
        
        # Verify directory is writable
        test_file = os.path.join(data_dir, '.write_test')
        try:
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
        except (OSError, PermissionError):
            # Fallback to user home directory if primary location not writable
            fallback_dir = os.path.join(os.path.expanduser('~'), '.dropshelf')
            os.makedirs(fallback_dir, exist_ok=True)
            return fallback_dir
        
        return data_dir
    except Exception as e:
        # Ultimate fallback to current directory
        print(f"Data directory error: {e}")
        fallback = os.path.join(os.getcwd(), 'dropshelf_data')
        os.makedirs(fallback, exist_ok=True)
        return fallback

DATA_DIR = get_data_dir()
LOG_FILE = os.path.join(DATA_DIR, 'dropshelf.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger('DropShelf')

# ─── Constants ────────────────────────────────────────────────────────────────
APP_ID = "DropShelf"
SETTINGS_FILE  = os.path.join(DATA_DIR, 'settings.json')
FAVORITES_FILE = os.path.join(DATA_DIR, 'favorites.json')
TEMPLATES_FILE = os.path.join(DATA_DIR, 'templates.json')
HISTORY_FILE   = os.path.join(DATA_DIR, 'history.json')
DEFAULT_HOTKEY  = "ctrl+shift+x"
ICON_CANDIDATES = ["pic.ico", "icon.ico", "pic.png", "icon.png"]
MAX_HISTORY     = 200

class ItemType(str, Enum):
    TEXT = 'text'
    URL  = 'url'
    FILE = 'file'

# ─── Theme System ─────────────────────────────────────────────────────────────
THEMES = {
    'dark': {
        'bg_window':   'rgba(30, 30, 30, 245)',
        'bg_card':     '#2b2b2b',
        'bg_card_fav': '#332b00',
        'bg_card_sel': '#1a3a52',
        'bg_input':    '#3a3a3a',
        'bg_btn':      '#3a3a3a',
        'bg_btn_hover':'#4a4a4a',
        'border':      '#444',
        'border_fav':  '#FFD700',
        'border_sel':  '#2196F3',
        'text':        '#e0e0e0',
        'text_dim':    '#888',
        'text_label':  'white',
        'accent':      '#4CAF50',
        'accent_hover':'#388E3C',
        'danger':      '#d32f2f',
        'danger_hover':'#b71c1c',
        'tab_active':  '#4CAF50',
        'tag_color':   '#4CAF50',
        'window_border': '#444',
    }
}

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ─── Icon Loading ─────────────────────────────────────────────────────────────
ICON_EXPLICIT_PATH = r"C:\Users\MoeJoe\Desktop\myapps\dropshelf\icon.ico"

def load_app_icon():
    """
    Load the application icon with a priority chain:
      1. Explicit project path (C:\\Users\\MoeJoe\\Desktop\\myapps\\dropshelf\\icon.ico)
      2. Bundled resource path (supports PyInstaller _MEIPASS)
      3. Qt built-in computer icon as final fallback
    Returns a QIcon ready to be applied to any widget, dialog, or tray.
    """
    # 1. Explicit hardcoded project path
    if os.path.exists(ICON_EXPLICIT_PATH):
        return QIcon(ICON_EXPLICIT_PATH)

    # 2. Bundled / alongside-the-script candidates
    for name in ICON_CANDIDATES:
        candidate = resource_path(name)
        if os.path.exists(candidate):
            return QIcon(candidate)

    # 3. Qt built-in fallback — always works even without any icon file
    from PyQt6.QtWidgets import QApplication, QStyle
    app = QApplication.instance()
    if app:
        return app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
    return QIcon()


def find_icon():
    for name in ICON_CANDIDATES:
        if os.path.exists(resource_path(name)):
            return name
    return ICON_CANDIDATES[0]

ICON_NAME = find_icon()

# ─── Platform: Startup ────────────────────────────────────────────────────────
def is_startup_enabled():
    if platform.system() != 'Windows' or winreg is None:
        return False
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Run",
                             0, winreg.KEY_READ)
        winreg.QueryValueEx(key, APP_ID)
        key.Close()
        return True
    except (FileNotFoundError, OSError):
        return False

def set_startup(enable):
    if platform.system() != 'Windows' or winreg is None:
        return
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
        if enable:
            path = f'"{sys.executable}"'
            if not getattr(sys, 'frozen', False):
                path = f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'
            winreg.SetValueEx(key, APP_ID, 0, winreg.REG_SZ, path)
        else:
            try:
                winreg.DeleteValue(key, APP_ID)
            except FileNotFoundError:
                pass
        key.Close()
    except Exception as e:
        log.exception(f"Startup error: {e}")

# ─── URL Title Fetcher (Background Thread) ────────────────────────────────────
class TitleFetcher(QThread):
    title_fetched = Signal(str, str)  # url, title

    class _TitleParser(html.parser.HTMLParser):
        def __init__(self):
            super().__init__()
            self.in_title = False
            self.title = ""
        def handle_starttag(self, tag, attrs):
            if tag.lower() == 'title':
                self.in_title = True
        def handle_data(self, data):
            if self.in_title:
                self.title += data
        def handle_endtag(self, tag):
            if tag.lower() == 'title':
                self.in_title = False

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self):
        if not HAS_URL_FETCH:
            return
        try:
            req = urllib.request.Request(self.url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=4) as resp:
                raw = resp.read(8192).decode('utf-8', errors='ignore')
            parser = self._TitleParser()
            parser.feed(raw)
            title = parser.title.strip()
            if title:
                self.title_fetched.emit(self.url, title)
        except Exception:
            pass

# ─── Hotkey Capture Widget ────────────────────────────────────────────────────
class HotkeyCaptureEdit(QLineEdit):
    """Press a key combination to record it instead of typing."""
    def __init__(self, current_hotkey="", parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setText(current_hotkey)
        self.setPlaceholderText("Click here, then press your key combo…")
        self._current = current_hotkey

    def keyPressEvent(self, event):
        try:
            key = event.key()
            mods = event.modifiers()

            # Ignore lone modifiers
            if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt,
                       Qt.Key.Key_Meta, Qt.Key.Key_unknown):
                return

            parts = []
            if mods & Qt.KeyboardModifier.ControlModifier:
                parts.append("ctrl")
            if mods & Qt.KeyboardModifier.AltModifier:
                parts.append("alt")
            if mods & Qt.KeyboardModifier.ShiftModifier:
                parts.append("shift")

            key_str = QKeySequence(key).toString().lower()
            if key_str and key_str not in ('', 'ctrl', 'alt', 'shift', 'meta'):
                parts.append(key_str)

            if len(parts) >= 2:   # require at least one modifier + one key
                self._current = "+".join(parts)
                self.setText(self._current)
        except Exception as e:
            log.exception(f"Hotkey capture error: {e}")

    def get_hotkey(self):
        return self._current

# ─── Edit Dialog ──────────────────────────────────────────────────────────────
class EditDialog(QDialog):
    def __init__(self, item_type, content, tags, theme, parent=None):
        super().__init__(parent)
        self.item_type = item_type
        self.theme = theme
        self.setWindowTitle("Edit Item")
        self.setModal(True)
        self.setFixedSize(520, 420)
        self._build_ui(content, tags)
        self._apply_theme()

    def _build_ui(self, content, tags):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        title = QLabel("Edit Item")
        title.setStyleSheet("font-size: 18px; font-weight: bold; padding-bottom: 4px;")
        layout.addWidget(title)

        content_group = QGroupBox("Content")
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(6)

        if self.item_type == ItemType.TEXT:
            self.text_edit = QTextEdit()
            self.text_edit.setPlainText(content)
            self.text_edit.setMinimumHeight(120)
            content_layout.addWidget(self.text_edit)
        else:
            self.text_edit = None
            type_row = QHBoxLayout()
            type_lbl = QLabel("Type:")
            type_lbl.setStyleSheet("font-weight: normal; font-size: 12px;")
            type_val = QLabel(self.item_type.value.upper())
            type_val.setStyleSheet("font-weight: bold; font-size: 13px;")
            type_row.addWidget(type_lbl)
            type_row.addStretch()
            type_row.addWidget(type_val)
            content_layout.addLayout(type_row)
            content_display = str(content)
            if len(content_display) > 120:
                content_display = content_display[:117] + "..."
            content_lbl = QLabel(content_display)
            content_lbl.setWordWrap(True)
            content_lbl.setStyleSheet("font-size: 12px;")
            content_layout.addWidget(content_lbl)

        content_group.setLayout(content_layout)
        layout.addWidget(content_group)

        tags_group = QGroupBox("Tags")
        tags_layout = QVBoxLayout()
        tags_layout.setContentsMargins(12, 12, 12, 12)
        tags_layout.setSpacing(6)
        tags_hint = QLabel("Separate multiple tags with commas  (e.g. work, important, todo)")
        tags_hint.setStyleSheet("font-size: 11px; font-style: italic;")
        tags_layout.addWidget(tags_hint)
        self.tags_input = QLineEdit()
        self.tags_input.setText(", ".join(tags) if tags else "")
        self.tags_input.setPlaceholderText("work, important, project...")
        self.tags_input.setFixedHeight(32)
        tags_layout.addWidget(self.tags_input)
        tags_group.setLayout(tags_layout)
        layout.addWidget(tags_group)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setFixedWidth(100)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        save_btn = QPushButton("Save")
        save_btn.setFixedHeight(36)
        save_btn.setFixedWidth(100)
        save_btn.setObjectName("SaveBtn")
        save_btn.clicked.connect(self.accept)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)
        self.setLayout(layout)

    def _apply_theme(self):
        t = THEMES[self.theme]
        self.setStyleSheet(f"""
            QDialog {{ background: rgba(30,30,30,245); color: {t['text']}; }}
            QLabel {{ color: {t['text']}; border: none; font-size: 12px; }}
            QGroupBox {{
                color: white; border: 1px solid {t['border']}; border-radius: 8px;
                margin-top: 10px; padding-top: 12px; font-weight: bold;
            }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 5px; color: white; }}
            QTextEdit {{
                background: {t['bg_card']}; color: {t['text']};
                border: 1px solid {t['border']}; border-radius: 6px; padding: 8px; font-size: 12px;
            }}
            QTextEdit:focus {{ border: 1px solid {t['accent']}; }}
            QLineEdit {{
                background: {t['bg_input']}; color: {t['text']};
                border: 1px solid {t['border']}; border-radius: 6px; padding: 6px; font-size: 12px;
            }}
            QLineEdit:focus {{ border: 1px solid {t['accent']}; }}
            QPushButton {{
                background: {t['bg_btn']}; color: white;
                border: none; border-radius: 6px; padding: 8px 16px;
                font-weight: bold; font-size: 13px;
            }}
            QPushButton:hover {{ background: {t['bg_btn_hover']}; }}
            QPushButton#SaveBtn {{ background: {t['accent']}; }}
            QPushButton#SaveBtn:hover {{ background: {t['accent_hover']}; }}
        """)

    def get_content(self):
        return self.text_edit.toPlainText() if self.text_edit else None

    def get_tags(self):
        raw = self.tags_input.text().strip()
        return [tag.strip() for tag in raw.split(',') if tag.strip()] if raw else []

# ─── Templates Dialog ─────────────────────────────────────────────────────────
class TemplatesDialog(QDialog):
    template_inserted = Signal(str)

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Templates - Removed')
        self.setFixedSize(360,120)
        layout = QVBoxLayout()
        msg = QLabel('Template functionality has been removed.')
        msg.setWordWrap(True)
        layout.addWidget(msg)
        btn = QPushButton('Close')
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
        self.setLayout(layout)

class StatsDialog(QDialog):
    def __init__(self, items_data, theme, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DropShelf Statistics")
        self.setWindowIcon(load_app_icon())
        self.setModal(True)
        self.setFixedSize(520, 480)
        t = THEMES[theme]
        self.setStyleSheet(f"""
            QDialog {{ 
                background: {t['bg_window']}; 
                color: {t['text']}; 
            }}
            QLabel {{ 
                color: {t['text']}; 
                border: none; 
            }}
            QGroupBox {{
                color: {t['text']};
                border: 1px solid {t['border']};
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 12px;
                font-weight: bold;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 5px;
            }}
            QListWidget {{ 
                background: {t['bg_card']}; 
                color: {t['text']}; 
                border: 1px solid {t['border']}; 
                border-radius: 6px; 
                padding: 8px;
                font-size: 12px;
            }}
            QListWidget::item {{ 
                padding: 8px 10px;
                border-radius: 4px;
                margin: 2px 0px;
            }}
            QListWidget::item:hover {{ 
                background: {t['bg_input']}; 
            }}
            QPushButton {{ 
                background: {t['bg_btn']}; 
                color: white; 
                border: none; 
                border-radius: 6px; 
                padding: 10px 24px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{ 
                background: {t['bg_btn_hover']}; 
            }}
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Title
        title = QLabel("Usage Statistics")
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; padding-bottom: 8px; color: {t['text']};")
        layout.addWidget(title)
        
        # Calculate statistics
        total_items = len(items_data)
        total_uses = sum(i.get('use_count', 0) for i in items_data)
        favorites_count = sum(1 for i in items_data if i.get('is_favorite', False))
        
        type_counts = {}
        for i in items_data:
            tp = i.get('type', 'unknown')
            type_counts[tp] = type_counts.get(tp, 0) + 1

        # Overview section
        overview_group = QGroupBox("Overview")
        overview_layout = QVBoxLayout()
        overview_layout.setContentsMargins(12, 12, 12, 12)
        overview_layout.setSpacing(8)
        
        overview_stats = [
            ("Total Items:", f"{total_items}"),
            ("Total Uses:", f"{total_uses}"),
            ("Favorites:", f"{favorites_count}"),
        ]
        
        for label, value in overview_stats:
            row = QHBoxLayout()
            label_widget = QLabel(label)
            label_widget.setStyleSheet("font-weight: normal; font-size: 12px;")
            value_widget = QLabel(value)
            value_widget.setStyleSheet(f"font-weight: bold; font-size: 13px; color: {t['accent']};")
            row.addWidget(label_widget)
            row.addStretch()
            row.addWidget(value_widget)
            overview_layout.addLayout(row)
        
        # Type breakdown
        if type_counts:
            type_row = QHBoxLayout()
            type_label = QLabel("By Type:")
            type_label.setStyleSheet("font-weight: normal; font-size: 12px;")
            type_value = QLabel(" • ".join(f"{k.upper()}: {v}" for k, v in type_counts.items()))
            type_value.setStyleSheet("font-size: 11px;")
            type_row.addWidget(type_label)
            type_row.addStretch()
            overview_layout.addLayout(type_row)
            overview_layout.addWidget(type_value)
        
        overview_group.setLayout(overview_layout)
        layout.addWidget(overview_group)
        
        # Most used items section
        most_used_group = QGroupBox("Most Used Items (Top 15)")
        most_used_layout = QVBoxLayout()
        most_used_layout.setContentsMargins(12, 12, 12, 12)

        sorted_items = sorted(items_data, key=lambda x: x.get('use_count', 0), reverse=True)

        lw = QListWidget()
        lw.setMinimumHeight(200)
        for item in sorted_items[:15]:
            count = item.get('use_count', 0)
            if count == 0:
                continue
            content = str(item.get('content', ''))
            item_type = item.get('type', '').upper()
            
            # Truncate long content
            if len(content) > 45:
                content = content[:42] + "..."
            
            # Format: [Uses] TYPE — Content
            list_text = f"[{count}×]  {item_type}  •  {content}"
            lw.addItem(list_text)
        
        if lw.count() == 0:
            lw.addItem("No items have been used yet")
        
        most_used_layout.addWidget(lw)
        most_used_group.setLayout(most_used_layout)
        layout.addWidget(most_used_group)

        # Close button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        
        self.setLayout(layout)

# ─── Settings Dialog ──────────────────────────────────────────────────────────
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setWindowTitle("DropShelf Settings")
        self.setWindowIcon(load_app_icon())
        self.setModal(True)
        self.setFixedSize(380, 520)
        self._build_ui()
        self._apply_theme()
        log.info(f"Settings dialog opened - Current history size: {self.parent_window.max_history}")

    def _build_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Title
        title = QLabel("Settings")
        title.setStyleSheet("font-size: 18px; font-weight: bold; padding-bottom: 8px;")
        layout.addWidget(title)

        # Hotkey section
        hotkey_group = QGroupBox("Hotkey")
        hotkey_layout = QVBoxLayout()
        hotkey_layout.setContentsMargins(12, 16, 12, 12)
        hotkey_layout.setSpacing(6)
        self.hotkey_edit = HotkeyCaptureEdit(self.parent_window.hotkey)
        hotkey_layout.addWidget(QLabel("Toggle hotkey:"))
        hotkey_layout.addWidget(self.hotkey_edit)
        hotkey_group.setLayout(hotkey_layout)
        layout.addWidget(hotkey_group)

        # General options section
        general_group = QGroupBox("General")
        general_layout = QVBoxLayout()
        general_layout.setContentsMargins(12, 16, 12, 16)
        general_layout.setSpacing(10)
        
        self.cb_clipboard = QCheckBox("Monitor clipboard")
        self.cb_clipboard.setChecked(self.parent_window.monitor_clipboard)
        general_layout.addWidget(self.cb_clipboard)

        self.cb_close_tray = QCheckBox("Close to system tray")
        self.cb_close_tray.setChecked(self.parent_window.close_to_tray)
        general_layout.addWidget(self.cb_close_tray)

        self.cb_startup = QCheckBox("Run on startup")
        self.cb_startup.setChecked(is_startup_enabled())
        general_layout.addWidget(self.cb_startup)
        
        # History size row
        history_row = QHBoxLayout()
        history_row.setSpacing(8)
        history_row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        history_label = QLabel("History size:")
        history_row.addWidget(history_label)
        
        self.history_spin = QSpinBox()
        self.history_spin.setMinimum(0)
        self.history_spin.setMaximum(1000)
        # Set the value from parent window
        current_value = self.parent_window.max_history
        self.history_spin.setValue(current_value)
        self.history_spin.setToolTip("Set to 0 to disable history tracking")
        self.history_spin.setFixedWidth(70)
        self.history_spin.setFixedHeight(28)
        # Make it fully editable
        self.history_spin.setKeyboardTracking(True)
        self.history_spin.setWrapping(False)
        self.history_spin.setButtonSymbols(QSpinBox.ButtonSymbols.UpDownArrows)
        # Allow typing directly
        self.history_spin.lineEdit().setReadOnly(False)
        self.history_spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Ensure text is visible
        self.history_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        log.info(f"SpinBox initialized with value: {current_value}")
        
        history_row.addWidget(self.history_spin)
        history_row.addStretch()
        general_layout.addLayout(history_row)
        
        general_group.setLayout(general_layout)
        layout.addWidget(general_group)

        # Quick actions section  
        actions_group = QGroupBox("Quick Actions")
        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(12, 16, 12, 12)
        actions_layout.setSpacing(8)
        
        for label, slot in [("Stats", self.parent_window.open_stats),
                           ("Export", self.parent_window.export_items),
                           ("Import", self.parent_window.import_items)]:
            btn = QPushButton(label)
            btn.setFixedHeight(32)
            btn.clicked.connect(slot)
            actions_layout.addWidget(btn)
        
        actions_group.setLayout(actions_layout)
        layout.addWidget(actions_group)

        layout.addStretch()

        # Save/Cancel buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        for label, slot in [("Cancel", self.reject), ("Save", self._save_and_close)]:
            btn = QPushButton(label)
            btn.setFixedHeight(36)
            btn.clicked.connect(slot)
            btn_row.addWidget(btn)
        layout.addLayout(btn_row)
        
        self.setLayout(layout)

    def _apply_theme(self):
        t = THEMES[self.parent_window.current_theme]
        self.setStyleSheet(f"""
            QDialog {{ 
                background: {t['bg_window']}; 
                color: {t['text']}; 
            }}
            QLabel {{ 
                color: white;
                font-size: 12px;
            }}
            QGroupBox {{
                color: white;
                border: 1px solid {t['border']};
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 5px;
                color: white;
            }}
            QLineEdit {{
                background: {t['bg_input']}; 
                color: white;
                border: 1px solid {t['border']}; 
                border-radius: 6px; 
                padding: 6px;
                font-size: 13px;
                selection-background-color: {t['accent']};
                selection-color: white;
            }}
            QLineEdit:focus {{
                border: 1px solid {t['accent']};
            }}
            QSpinBox {{
                background: {t['bg_input']}; 
                color: white;
                border: 1px solid {t['border']}; 
                border-radius: 6px; 
                padding: 4px 6px;
                padding-right: 22px;
                font-size: 13px;
                font-weight: bold;
                min-height: 20px;
            }}
            QSpinBox:focus {{
                border: 1px solid {t['accent']};
            }}
            QSpinBox::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top right;
                background: {t['bg_btn']};
                border-left: 1px solid {t['border']};
                border-top-right-radius: 5px;
                width: 18px;
                height: 12px;
            }}
            QSpinBox::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                background: {t['bg_btn']};
                border-left: 1px solid {t['border']};
                border-bottom-right-radius: 5px;
                width: 18px;
                height: 12px;
            }}
            QSpinBox::up-button:hover {{
                background: {t['bg_btn_hover']};
            }}
            QSpinBox::down-button:hover {{
                background: {t['bg_btn_hover']};
            }}
            QSpinBox::up-arrow {{
                image: none;
                width: 7px;
                height: 7px;
                border-left: 3px solid transparent;
                border-right: 3px solid transparent;
                border-bottom: 4px solid white;
                margin-bottom: 1px;
            }}
            QSpinBox::down-arrow {{
                image: none;
                width: 7px;
                height: 7px;
                border-left: 3px solid transparent;
                border-right: 3px solid transparent;
                border-top: 4px solid white;
                margin-top: 1px;
            }}
            QCheckBox {{ 
                color: white;
                spacing: 6px;
                font-size: 12px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {t['border']};
                border-radius: 3px;
                background: {t['bg_input']};
            }}
            QCheckBox::indicator:checked {{
                background: {t['accent']};
                border: 1px solid {t['accent']};
            }}
            QPushButton {{
                background: {t['bg_btn']}; 
                color: white;
                border: none; 
                border-radius: 6px; 
                padding: 8px 16px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{ 
                background: {t['bg_btn_hover']}; 
            }}
        """)

    def _save_and_close(self):
        try:
            old_hotkey = self.parent_window.hotkey
            new_hotkey = self.hotkey_edit.get_hotkey()

            self.parent_window.monitor_clipboard = self.cb_clipboard.isChecked()
            self.parent_window.close_to_tray = self.cb_close_tray.isChecked()
            old_history_size = self.parent_window.max_history
            self.parent_window.max_history = self.history_spin.value()
            
            log.info(f"History size changed from {old_history_size} to {self.parent_window.max_history}")
            
            # Handle history size change
            if self.parent_window.max_history != old_history_size:
                if self.parent_window.max_history == 0:
                    self.parent_window.clipboard_history = deque(maxlen=1)
                else:
                    self.parent_window.clipboard_history = deque(
                        list(self.parent_window.clipboard_history)[:self.parent_window.max_history],
                        maxlen=self.parent_window.max_history
                    )
                self.parent_window._update_history_tab_visibility()

            if new_hotkey and new_hotkey != old_hotkey:
                try:
                    keyboard.remove_hotkey(old_hotkey)
                except Exception:
                    pass
                self.parent_window.hotkey = new_hotkey
                self.parent_window.setup_hotkey()

            set_startup(self.cb_startup.isChecked())
            self.parent_window.save_settings()
            self.accept()
        except Exception as e:
            log.exception(f"Settings save error: {e}")
            QMessageBox.warning(self, "Error", f"Failed to save settings: {e}")



# ─── Clickable Label (for icons) ──────────────────────────────────────────────
class ClickableLabel(QLabel):
    clicked = Signal()
    def mousePressEvent(self, event):
        try:
            if event.button() == Qt.MouseButton.LeftButton:
                self.clicked.emit()
            super().mousePressEvent(event)
        except Exception as e:
            log.exception(f"Label click error: {e}")

# ─── Draggable Item ───────────────────────────────────────────────────────────
class DraggableItem(QFrame):
    def __init__(self, dtype, content, shelf, is_favorite=False, hidden_from_main=False,
                 tags=None, date_added=None, use_count=0):
        super().__init__()
        # Convert dtype to ItemType if it's a string
        if isinstance(dtype, str):
            self.data_type = ItemType(dtype)
        else:
            self.data_type = dtype
        
        self.content = content
        self.shelf = shelf
        self.is_favorite = is_favorite
        self.hidden_from_main = hidden_from_main
        self.tags = tags or []
        self.date_added = date_added or datetime.now().isoformat()
        self.use_count = use_count
        self.is_selected = False
        self._init_ui()

    def _init_ui(self):
        try:
            self.setFrameShape(QFrame.Shape.StyledPanel)
            self.update_style()

            layout = QHBoxLayout()
            layout.setContentsMargins(12, 6, 8, 6)
            layout.setSpacing(4)

            # Selection checkbox (hidden by default)
            self.select_checkbox = QCheckBox()
            self.select_checkbox.setVisible(False)
            self.select_checkbox.stateChanged.connect(self._on_selection_changed)
            layout.addWidget(self.select_checkbox)

            # Text + info stacked vertically
            text_block = QVBoxLayout()
            text_block.setSpacing(2)
            text_block.setContentsMargins(0, 0, 0, 0)

            self.text_label = QLabel()
            self.text_label.setStyleSheet("font-size: 12px; font-weight: bold; background: transparent; border: none;")
            display_text = str(self.content)
            if self.data_type == ItemType.FILE:
                display_text = os.path.basename(self.content)
            fm = self.text_label.fontMetrics()
            self.text_label.setText(fm.elidedText(display_text, Qt.TextElideMode.ElideRight, 160))
            self.text_label.setToolTip(str(self.content))
            text_block.addWidget(self.text_label)

            # Info sub-label (size / char count / domain)
            self.info_label = QLabel()
            self.info_label.setStyleSheet("font-size: 10px; color: #888; background: transparent; border: none;")
            self._update_info_label()
            text_block.addWidget(self.info_label)

            text_widget = QWidget()
            text_widget.setLayout(text_block)
            text_widget.setStyleSheet("background: transparent; border: none;")
            layout.addWidget(text_widget, 1)

            # Spacer before icon group
            layout.addSpacing(4)

            # Icon
            self.icon_label = ClickableLabel()
            self.icon_label.setFixedSize(30, 30)
            self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.icon_label.setCursor(Qt.CursorShape.PointingHandCursor)
            self.icon_label.clicked.connect(self._handle_open)
            self._set_preview()
            layout.addWidget(self.icon_label)

            layout.addSpacing(4)

            # Star button
            self.star_btn = QPushButton("★" if self.is_favorite else "☆")
            self.star_btn.setFixedSize(28, 28)
            self.star_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.star_btn.clicked.connect(self.toggle_favorite)
            self._update_star_style()
            layout.addWidget(self.star_btn)

            layout.addSpacing(2)

            # Edit button
            self.edit_btn = QPushButton("✎")
            self.edit_btn.setFixedSize(28, 28)
            self.edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.edit_btn.setToolTip("Edit / Tags")
            self.edit_btn.clicked.connect(self._edit_item)
            layout.addWidget(self.edit_btn)

            layout.addSpacing(2)

            # Close button
            self.close_btn = QPushButton("×")
            self.close_btn.setFixedSize(28, 28)
            self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.close_btn.clicked.connect(self._request_removal)
            layout.addWidget(self.close_btn)

            self.setLayout(layout)
            self.setFixedHeight(66)
            self._apply_button_styles()
            self._refresh_tooltip()

            if self.data_type == ItemType.URL:
                self._fetch_url_title()
        except Exception as e:
            log.exception(f"Item UI init error: {e}")

    def _refresh_tooltip(self):
        try:
            tooltip_parts = [f"Type: {self.data_type.value}"]
            if self.data_type == ItemType.FILE and os.path.exists(self.content):
                size_bytes = os.path.getsize(self.content)
                if size_bytes < 1024:
                    size_str = f"{size_bytes} B"
                elif size_bytes < 1024*1024:
                    size_str = f"{size_bytes/1024:.1f} KB"
                else:
                    size_str = f"{size_bytes/(1024*1024):.1f} MB"
                tooltip_parts.append(f"Size: {size_str}")

            tooltip_parts.append(f"Content: {self.content}")
            if self.tags:
                tooltip_parts.append(f"Tags: {', '.join(self.tags)}")
            tooltip_parts.append(f"Used: {self.use_count}x")
            tooltip_parts.append(f"Added: {self.date_added[:10]}")
            self.setToolTip("\n".join(tooltip_parts))
        except Exception as e:
            log.exception(f"Tooltip refresh error: {e}")

    def _apply_button_styles(self):
        try:
            t = THEMES[self.shelf.current_theme]
            # min-height:0; min-width:0; padding:0 overrides the global app stylesheet
            # so the fixed 28×28 size is respected and the icon is never clipped
            self.close_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {t['text_dim']};
                    border: none; font-weight: bold;
                    font-size: 17px; border-radius: 14px;
                    min-height: 0; min-width: 0; padding: 0;
                }}
                QPushButton:hover {{ background: {t['danger']}; color: white; }}
            """)
            self.edit_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {t['text_dim']};
                    border: none; font-size: 15px; border-radius: 14px;
                    min-height: 0; min-width: 0; padding: 0;
                }}
                QPushButton:hover {{ background: {t['accent']}; color: white; }}
            """)
        except Exception as e:
            log.exception(f"Button style error: {e}")

    def _update_info_label(self):
        """Show size / char count / domain under the item name."""
        try:
            info = ""
            if self.data_type == ItemType.FILE:
                if os.path.exists(self.content):
                    size_bytes = os.path.getsize(self.content)
                    if size_bytes < 1024:
                        info = f"{size_bytes} B"
                    elif size_bytes < 1024 * 1024:
                        info = f"{size_bytes / 1024:.1f} KB"
                    else:
                        info = f"{size_bytes / (1024 * 1024):.1f} MB"
                else:
                    info = "file not found"
            elif self.data_type == ItemType.URL:
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(str(self.content))
                    info = parsed.netloc or str(self.content)[:40]
                except Exception:
                    info = str(self.content)[:40]
            else:
                char_count = len(str(self.content))
                info = f"{char_count} chars"
            if hasattr(self, 'info_label'):
                self.info_label.setText(info)
        except Exception as e:
            log.exception(f"Info label update error: {e}")

    def _update_tags_display(self):
        self._update_info_label()

    def _update_info_display(self):
        self._update_info_label()


    def _set_preview(self):
        try:
            t = THEMES[self.shelf.current_theme]
            if self.data_type == ItemType.FILE:
                if self.content.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')):
                    try:
                        pixmap = QPixmap(self.content)
                        if not pixmap.isNull():
                            self.icon_label.setPixmap(pixmap.scaled(36, 36,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation))
                            self.icon_label.setStyleSheet(f"border: 1px solid {t['border']}; background: transparent; border-radius: 4px;")
                            return
                    except Exception:
                        pass
                fi = QFileInfo(self.content)
                icon = QFileIconProvider().icon(fi)
                if not icon.isNull():
                    self.icon_label.setPixmap(icon.pixmap(36, 36))
                else:
                    self.icon_label.setText("📄")
                    self.icon_label.setStyleSheet(f"font-size: 24px; border: 1px solid {t['border']}; background: {t['bg_btn']}; border-radius: 6px;")
            elif self.data_type == ItemType.URL:
                self.icon_label.setText("🔗")
                self.icon_label.setStyleSheet(f"font-size: 24px; border: 1px solid {t['border']}; background: {t['bg_btn']}; border-radius: 6px;")
                self.icon_label.setToolTip("Click to open link")
            else:
                self.icon_label.setText("T")
                self.icon_label.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {t['accent']}; border: 1px solid {t['border']}; background: {t['bg_btn']}; border-radius: 6px;")
        except Exception as e:
            log.exception(f"Preview set error: {e}")

    def _fetch_url_title(self):
        try:
            fetcher = TitleFetcher(str(self.content), self)
            fetcher.title_fetched.connect(self._on_title_fetched)
            fetcher.start()
            self._title_fetcher = fetcher
        except Exception as e:
            log.exception(f"URL title fetch error: {e}")

    def _on_title_fetched(self, url, title):
        try:
            if str(self.content) == url:
                fm = self.text_label.fontMetrics()
                self.text_label.setText(fm.elidedText(title, Qt.TextElideMode.ElideRight, 180))
                self.text_label.setToolTip(f"{title}\n{url}")
        except Exception as e:
            log.exception(f"Title update error: {e}")

    def update_style(self):
        try:
            t = THEMES[self.shelf.current_theme]
            if self.is_selected:
                bg, border = t['bg_card_sel'], t['border_sel']
            elif self.is_favorite:
                bg, border = t['bg_card_fav'], t['border_fav']
            else:
                bg, border = t['bg_card'], t['border']
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: {bg}; border-radius: 8px; border: 1px solid {border};
                }}
                QFrame:hover {{
                    background-color: {t['bg_input']}; border: 1px solid {t['accent']};
                }}
                QLabel {{ border: none; background: transparent; }}
            """)
        except Exception as e:
            log.exception(f"Style update error: {e}")

    def _update_star_style(self):
        try:
            t = THEMES[self.shelf.current_theme]
            color = t['border_fav'] if self.is_favorite else t['text_dim']
            self.star_btn.setText("★" if self.is_favorite else "☆")
            self.star_btn.setStyleSheet(f"""
                QPushButton {{
                    color: {color}; border: none; background: transparent;
                    font-size: 17px; border-radius: 14px;
                    min-height: 0; min-width: 0; padding: 0;
                }}
                QPushButton:hover {{ color: #FFEA00; background: {t['bg_btn']}; }}
            """)
        except Exception as e:
            log.exception(f"Star style error: {e}")

    def toggle_favorite(self):
        try:
            self.is_favorite = not self.is_favorite
            if not self.is_favorite:
                self.hidden_from_main = False
            self.update_style()
            self._update_star_style()
            if self.shelf:
                self.shelf.save_favorites()
                self.shelf.refresh_visibility()
        except Exception as e:
            log.exception(f"Toggle favorite error: {e}")

    def set_selection_mode(self, enabled):
        try:
            self.select_checkbox.setVisible(enabled)
            if not enabled:
                self.select_checkbox.setChecked(False)
        except Exception as e:
            log.exception(f"Selection mode error: {e}")

    def _on_selection_changed(self, state):
        try:
            self.is_selected = (state == Qt.CheckState.Checked.value)
            self.update_style()
        except Exception as e:
            log.exception(f"Selection change error: {e}")

    def _edit_item(self):
        try:
            dialog = EditDialog(self.data_type, self.content, self.tags,
                                self.shelf.current_theme, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_content = dialog.get_content()
                if new_content is not None and self.data_type == ItemType.TEXT:
                    self.content = new_content
                    fm = self.text_label.fontMetrics()
                    self.text_label.setText(fm.elidedText(new_content, Qt.TextElideMode.ElideRight, 180))
                self.tags = dialog.get_tags()
                self._update_tags_display()
                self._refresh_tooltip()
                if self.shelf:
                    self.shelf.save_favorites()
        except Exception as e:
            log.exception(f"Edit item error: {e}")

    def _handle_open(self):
        try:
            self.use_count += 1
            self._refresh_tooltip()
            if self.shelf:
                self.shelf.save_favorites()

            if self.data_type == ItemType.URL:
                QDesktopServices.openUrl(QUrl(str(self.content)))
            elif self.data_type == ItemType.FILE:
                # Normalize path for cross-platform compatibility
                file_path = os.path.normpath(self.content)
                if not os.path.exists(file_path):
                    QMessageBox.warning(self, "File Not Found", 
                                      f"The file no longer exists:\n{file_path}")
                    return
                
                if platform.system() == 'Windows':
                    os.startfile(file_path)
                elif platform.system() == 'Darwin':
                    subprocess.run(['open', file_path], check=False)
                else:  # Linux and other Unix-like systems
                    subprocess.run(['xdg-open', file_path], check=False)
            else:
                QApplication.clipboard().setText(str(self.content))
        except Exception as e:
            log.exception(f"Handle open error: {e}")
            QMessageBox.warning(self, "Error", f"Failed to open: {e}")

    def _request_removal(self):
        try:
            if self.shelf:
                self.shelf.handle_item_deletion_request(self)
        except Exception as e:
            log.exception(f"Request removal error: {e}")

    def contextMenuEvent(self, event):
        try:
            t = THEMES[self.shelf.current_theme]
            menu = QMenu(self)
            menu.setStyleSheet(f"""
                QMenu {{ 
                    background: {t['bg_input']}; 
                    color: {t['text']}; 
                    border: 1px solid {t['border']}; 
                    border-radius: 8px;
                    padding: 6px;
                }}
                QMenu::item {{ 
                    padding: 8px 24px; 
                    border-radius: 5px;
                    margin: 2px 4px;
                }}
                QMenu::item:selected {{ 
                    background: {t['accent']}; 
                    color: white; 
                }}
                QMenu::separator {{
                    height: 1px;
                    background: {t['border']};
                    margin: 6px 8px;
                }}
            """)

            copy_action = QAction("Copy to Clipboard", self)
            copy_action.triggered.connect(lambda: QApplication.clipboard().setText(str(self.content)))
            menu.addAction(copy_action)

            if self.data_type == ItemType.URL:
                open_action = QAction("Open in Browser", self)
                open_action.triggered.connect(self._handle_open)
                menu.addAction(open_action)

                # QR Code for URLs
                if HAS_QRCODE:
                    qr_action = QAction("Generate QR Code", self)
                    qr_action.triggered.connect(self._show_qr_code)
                    menu.addAction(qr_action)

            if self.data_type == ItemType.FILE:
                reveal_action = QAction("Reveal in Explorer", self)
                reveal_action.triggered.connect(self._reveal_in_explorer)
                menu.addAction(reveal_action)

            menu.addSeparator()
            edit_action = QAction("Edit / Tags", self)
            edit_action.triggered.connect(self._edit_item)
            menu.addAction(edit_action)

            fav_label = "Remove Favorite" if self.is_favorite else "Add to Favorites"
            fav_action = QAction(fav_label, self)
            fav_action.triggered.connect(self.toggle_favorite)
            menu.addAction(fav_action)

            menu.addSeparator()
            del_action = QAction("Delete", self)
            del_action.triggered.connect(self._request_removal)
            menu.addAction(del_action)

            menu.exec(event.globalPos())
        except Exception as e:
            log.exception(f"Context menu error: {e}")

    def _show_qr_code(self):
        if not HAS_QRCODE:
            QMessageBox.information(self, "Missing Library",
                                    "Install the 'qrcode[pil]' package to use QR codes.")
            return
        try:
            import io
            qr = qrcode.QRCode(box_size=6, border=2)
            qr.add_data(str(self.content))
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            buf.seek(0)

            pixmap = QPixmap()
            pixmap.loadFromData(buf.read())

            dlg = QDialog(self)
            dlg.setWindowTitle("QR Code")
            lbl = QLabel()
            lbl.setPixmap(pixmap)
            layout = QVBoxLayout()
            layout.addWidget(lbl)
            
            url_label = QLabel(str(self.content))
            url_label.setWordWrap(True)
            layout.addWidget(url_label)
            
            close = QPushButton("Close")
            close.clicked.connect(dlg.accept)
            layout.addWidget(close)
            dlg.setLayout(layout)
            dlg.exec()
        except Exception as e:
            log.exception(f"QR code error: {e}")
            QMessageBox.warning(self, "Error", f"QR generation failed: {e}")

    def _reveal_in_explorer(self):
        try:
            file_path = os.path.normpath(self.content)
            if not os.path.exists(file_path):
                QMessageBox.warning(self, "File Not Found", 
                                  f"The file no longer exists:\n{file_path}")
                return
            
            if platform.system() == 'Windows':
                subprocess.run(['explorer', '/select,', file_path], check=False)
            elif platform.system() == 'Darwin':
                subprocess.run(['open', '-R', file_path], check=False)
            else:  # Linux and other Unix-like systems
                # Try different file managers for Linux
                file_dir = os.path.dirname(file_path)
                for fm in ['nautilus', 'dolphin', 'thunar', 'nemo', 'caja']:
                    if subprocess.run(['which', fm], capture_output=True).returncode == 0:
                        subprocess.run([fm, file_dir], check=False)
                        return
                # Fallback to xdg-open
                subprocess.run(['xdg-open', file_dir], check=False)
        except Exception as e:
            log.exception(f"Reveal error: {e}")
            QMessageBox.warning(self, "Error", f"Failed to reveal file: {e}")

    def mousePressEvent(self, event):
        try:
            if event.button() == Qt.MouseButton.LeftButton and not self.shelf.selection_mode:
                drag = QDrag(self)
                mime = QMimeData()
                mime.setData("application/x-dropshelf-item", str(id(self)).encode('utf-8'))
                drag.setMimeData(mime)
                drag.exec(Qt.DropAction.MoveAction)
            super().mousePressEvent(event)
        except Exception as e:
            log.exception(f"Mouse press error: {e}")

    def refresh_theme(self):
        try:
            self.update_style()
            self._update_star_style()
            self._update_info_label()
            self._apply_button_styles()
            self._set_preview()
        except Exception as e:
            log.exception(f"Theme refresh error: {e}")


# ─── Main Window ──────────────────────────────────────────────────────────────
class DropShelfWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DropShelf")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowIcon(load_app_icon())

        # State
        self.monitor_clipboard   = True
        self.current_tab         = "all"
        self.hotkey              = DEFAULT_HOTKEY
        self.undo_stack          = []
        self.selection_mode      = False
        self.current_filter      = "all"
        self.current_sort        = "newest"
        self.sort_ascending      = False  # Default to descending
        self.search_query        = ""
        self.current_theme       = "dark"
        self.close_to_tray       = True
        self.max_history         = MAX_HISTORY
        self.clipboard_history   = deque(maxlen=MAX_HISTORY)
        self.window_geometry     = None
        self._templates_dialog   = None

        try:
            self.load_settings()
            self.clipboard_history   = deque(maxlen=max(1, self.max_history))  # Minimum 1 to avoid issues
            self.load_history()
            self._init_ui()
            self.setup_tray_icon()
            self.setup_hotkey()
            self.setup_local_server()
            self.load_favorites()
            self.setup_clipboard_monitor()
            self.setup_shortcuts()
            self.restore_window_geometry()
            self._update_history_tab_visibility()
        except Exception as e:
            log.exception(f"Initialization error: {e}")

    # ── UI Construction ───────────────────────────────────────────────────────
    def _init_ui(self):
        try:
            # Position window on screen (right side, vertically centered) — matches reference code
            screen = QApplication.primaryScreen().availableGeometry()
            w, h = 360, 600
            x = screen.width() - w - 20
            y = (screen.height() - h) // 2
            self.setGeometry(x, y, w, h)

            self.central_widget = QWidget()
            self.central_widget.setObjectName("CentralWidget")
            self.setCentralWidget(self.central_widget)

            main_layout = QVBoxLayout()
            main_layout.setContentsMargins(10, 12, 10, 12)
            main_layout.setSpacing(6)

            # Header row
            header = QHBoxLayout()
            self.title_label = QLabel("DropShelf")
            self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
            header.addWidget(self.title_label)
            header.addStretch()

            # Header buttons with cleaner icons
            for tooltip, symbol, slot in [
                ("Settings",  "⚙",  self.open_settings),
                ("Minimize",  "−",  self.minimize_to_tray),
                ("Close",     "×",  self.close_app_or_tray),
            ]:
                btn = QPushButton(symbol)
                btn.setFixedSize(30, 30)
                btn.setToolTip(tooltip)
                btn.clicked.connect(slot)
                header.addWidget(btn)

            main_layout.addLayout(header)

            # Search
            search_row = QHBoxLayout()
            search_row.setSpacing(6)
            self.search_input = QLineEdit()
            self.search_input.setPlaceholderText("Search items or tags...")
            self.search_input.setFixedHeight(32)
            self.search_input.textChanged.connect(self._on_search_changed)
            search_row.addWidget(self.search_input)
            clr = QPushButton("×")
            clr.setFixedSize(32, 32)
            clr.setStyleSheet("font-size: 18px; font-weight: bold;")
            clr.clicked.connect(self.search_input.clear)
            search_row.addWidget(clr)
            main_layout.addLayout(search_row)

            # Filter & Sort
            ctrl_row = QHBoxLayout()
            ctrl_row.setSpacing(6)
            ctrl_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
            
            self.filter_combo = QComboBox()
            self.filter_combo.addItems(["All Types", "Files", "URLs", "Text"])
            self.filter_combo.setFixedHeight(32)
            self.filter_combo.currentIndexChanged.connect(self._on_filter_changed)
            ctrl_row.addWidget(QLabel("Filter:"))
            ctrl_row.addWidget(self.filter_combo)
            
            ctrl_row.addSpacing(12)
            
            self.sort_combo = QComboBox()
            self.sort_combo.addItems(["Newest First", "Oldest First", "Name (A-Z)", "Type", "Size", "Most Used"])
            self.sort_combo.setFixedHeight(32)
            self.sort_combo.currentIndexChanged.connect(self._on_sort_changed)
            ctrl_row.addWidget(QLabel("Sort:"))
            ctrl_row.addWidget(self.sort_combo)
            
            # Sort direction toggle button - centered with combo boxes
            self.sort_direction_btn = QPushButton("↓")
            self.sort_direction_btn.setFixedSize(32, 32)
            self.sort_direction_btn.setToolTip("Toggle sort direction")
            self.sort_direction_btn.setStyleSheet("font-size: 16px; font-weight: bold;")
            self.sort_direction_btn.clicked.connect(self._toggle_sort_direction)
            ctrl_row.addWidget(self.sort_direction_btn)
            
            ctrl_row.addStretch()
            main_layout.addLayout(ctrl_row)

            # Tabs
            tab_row = QHBoxLayout()
            self.tab_buttons = {}
            for key, label in [("all", "All Items"), ("fav", "Favorites"), ("history", "History")]:
                btn = QPushButton(label)
                btn.clicked.connect(lambda checked, k=key: self.switch_tab(k))
                tab_row.addWidget(btn)
                self.tab_buttons[key] = btn
            tab_row.addStretch()
            main_layout.addLayout(tab_row)
            self._update_tab_styles()

            # Bulk controls
            bulk_row = QHBoxLayout()
            bulk_row.setSpacing(6)
            self.select_mode_btn = QPushButton("Select")
            self.select_mode_btn.setFixedHeight(28)
            self.select_mode_btn.setMaximumWidth(80)
            self.select_mode_btn.clicked.connect(self.toggle_selection_mode)
            bulk_row.addWidget(self.select_mode_btn)
            
            self.select_all_btn = QPushButton("All")
            self.select_all_btn.setFixedHeight(28)
            self.select_all_btn.setMaximumWidth(60)
            self.select_all_btn.clicked.connect(self.select_all_items)
            self.select_all_btn.setVisible(False)
            bulk_row.addWidget(self.select_all_btn)
            
            self.delete_selected_btn = QPushButton("Delete")
            self.delete_selected_btn.setFixedHeight(28)
            self.delete_selected_btn.setMaximumWidth(70)
            self.delete_selected_btn.clicked.connect(self.delete_selected_items)
            self.delete_selected_btn.setVisible(False)
            bulk_row.addWidget(self.delete_selected_btn)
            
            self.fav_selected_btn = QPushButton("Favorite")
            self.fav_selected_btn.setFixedHeight(28)
            self.fav_selected_btn.setMaximumWidth(80)
            self.fav_selected_btn.clicked.connect(self.favorite_selected_items)
            self.fav_selected_btn.setVisible(False)
            bulk_row.addWidget(self.fav_selected_btn)
            
            bulk_row.addStretch()
            main_layout.addLayout(bulk_row)

            # Scroll area (main shelf)
            self.scroll_area = QScrollArea()
            self.scroll_area.setWidgetResizable(True)
            self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
            self.scroll_content = QWidget()
            # No width constraints - items handle their own text eliding
            self.scroll_layout = QVBoxLayout()
            self.scroll_layout.setSpacing(6)
            self.scroll_layout.setContentsMargins(2, 4, 2, 4)
            self.scroll_content.setLayout(self.scroll_layout)
            self.scroll_area.setWidget(self.scroll_content)
            self.empty_label = QLabel("Drop files, text, or URLs here\nor use clipboard monitoring")
            self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.scroll_layout.addWidget(self.empty_label)
            self.scroll_layout.addStretch()
            main_layout.addWidget(self.scroll_area)

            # History scroll area
            self.history_area = QScrollArea()
            self.history_area.setWidgetResizable(True)
            self.history_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.history_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.history_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
            self.history_content = QWidget()
            # No width constraints - items handle their own text eliding
            self.history_layout = QVBoxLayout()
            self.history_layout.setSpacing(4)
            self.history_layout.setContentsMargins(0, 0, 0, 0)
            self.history_content.setLayout(self.history_layout)
            self.history_area.setWidget(self.history_content)
            self.history_empty_label = QLabel("No clipboard history yet.")
            self.history_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.history_layout.addWidget(self.history_empty_label)
            self.history_layout.addStretch()
            self.history_area.setVisible(False)
            main_layout.addWidget(self.history_area)

            # Bottom actions
            bottom = QHBoxLayout()
            self.clear_btn = QPushButton("Clear All")
            self.clear_btn.clicked.connect(self.clear_shelf)
            bottom.addWidget(self.clear_btn)
            self.undo_btn = QPushButton("Undo")
            self.undo_btn.clicked.connect(self.undo_delete)
            self.undo_btn.setEnabled(False)
            bottom.addWidget(self.undo_btn)
            bottom.addStretch()
            main_layout.addLayout(bottom)

            self.central_widget.setLayout(main_layout)
            self.setAcceptDrops(True)
            # Lock width to prevent auto-resizing - matching reference code
            self.setMinimumWidth(360)
            self.setMaximumWidth(360)
            # Set size policy to prevent horizontal expansion
            size_policy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
            self.setSizePolicy(size_policy)
            self.resize(360, 600)  # Reference code dimensions: 360×600
            self.apply_theme()
        except Exception as e:
            log.exception(f"UI init error: {e}")

    def _update_history_tab_visibility(self):
        """Show/hide history tab based on max_history setting"""
        try:
            if self.max_history == 0:
                # Hide history tab
                if "history" in self.tab_buttons:
                    self.tab_buttons["history"].setVisible(False)
                # Switch away from history tab if currently on it
                if self.current_tab == "history":
                    self.switch_tab("all")
            else:
                # Show history tab
                if "history" in self.tab_buttons:
                    self.tab_buttons["history"].setVisible(True)
        except Exception as e:
            log.exception(f"History tab visibility error: {e}")

    # ── Theme ─────────────────────────────────────────────────────────────────
    def apply_theme(self):
        try:
            t = THEMES[self.current_theme]
            self.central_widget.setStyleSheet(f"""
                QWidget#CentralWidget {{
                    background-color: {t['bg_window']};
                    border: 1px solid {t['window_border']};
                    border-radius: 15px;
                }}
                QLabel {{ color: {t['text_label']}; }}
                QLineEdit, QComboBox {{
                    background-color: {t['bg_input']}; color: {t['text']};
                    border: 1px solid {t['border']}; border-radius: 6px; padding: 6px;
                    font-size: 12px;
                }}
                QLineEdit:focus, QComboBox:focus {{ border: 1px solid {t['accent']}; }}
                QComboBox::drop-down {{ border: none; }}
                QComboBox QAbstractItemView {{
                    background: {t['bg_input']}; color: {t['text']};
                    selection-background-color: {t['accent']};
                }}
                QPushButton {{
                    background-color: {t['bg_btn']}; color: {t['text_label']};
                    border: none; border-radius: 8px; font-size: 13px;
                }}
                QPushButton:hover {{ background-color: {t['bg_btn_hover']}; }}
                QScrollArea {{ border: none; background: transparent; }}
                QScrollBar:vertical {{
                    background: transparent; width: 6px; border-radius: 3px;
                    margin: 2px 0;
                }}
                QScrollBar::handle:vertical {{
                    background: #555; border-radius: 3px; min-height: 20px;
                }}
                QScrollBar::handle:vertical:hover {{ background: #777; }}
                QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
                QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
            """)

            self.title_label.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {t['text_label']};")
            self.empty_label.setStyleSheet(f"color: {t['text_dim']}; font-size: 14px; padding: 40px;")
            self.history_empty_label.setStyleSheet(f"color: {t['text_dim']}; font-size: 13px; padding: 40px;")

            self.clear_btn.setStyleSheet(f"""
                QPushButton {{ background: {t['danger']}; color: white; border: none;
                    border-radius: 8px; padding: 8px 15px; font-size: 13px; font-weight: bold; }}
                QPushButton:hover {{ background: {t['danger_hover']}; }}
            """)
            self.undo_btn.setStyleSheet(f"""
                QPushButton {{ background: {t['bg_btn']}; color: {t['text_label']}; border: none;
                    border-radius: 8px; padding: 8px 15px; font-size: 13px; }}
                QPushButton:hover:enabled {{ background: {t['bg_btn_hover']}; }}
                QPushButton:disabled {{ color: {t['text_dim']}; }}
            """)
            self.select_mode_btn.setStyleSheet(f"""
                QPushButton {{ background: {t['bg_btn']}; color: {t['text_label']}; border: none;
                    border-radius: 5px; padding: 5px 10px; font-size: 12px; }}
                QPushButton:hover {{ background: {t['bg_btn_hover']}; }}
            """)
            for b in (self.select_all_btn, self.delete_selected_btn, self.fav_selected_btn):
                b.setStyleSheet(self.select_mode_btn.styleSheet())

            self._update_tab_styles()
            # Refresh all item widgets
            for item in self._get_all_items():
                item.refresh_theme()
            self._rebuild_history_display()
        except Exception as e:
            log.exception(f"Apply theme error: {e}")

    def toggle_theme(self):
        # Theme toggle disabled - dark theme only
        pass

    # ── Tabs ──────────────────────────────────────────────────────────────────
    def switch_tab(self, tab):
        try:
            self.current_tab = tab
            self._update_tab_styles()
            self.scroll_area.setVisible(tab != "history")
            self.history_area.setVisible(tab == "history")
            if tab == "history":
                self._rebuild_history_display()
            else:
                self.refresh_visibility()
        except Exception as e:
            log.exception(f"Switch tab error: {e}")

    def _update_tab_styles(self):
        try:
            t = THEMES[self.current_theme]
            active = f"""
                QPushButton {{ background: {t['tab_active']}; color: white; border: none;
                    border-radius: 8px; padding: 8px 15px; font-size: 13px; font-weight: bold; }}
            """
            inactive = f"""
                QPushButton {{ background: {t['bg_btn']}; color: {t['text_label']}; border: none;
                    border-radius: 8px; padding: 8px 15px; font-size: 13px; }}
                QPushButton:hover {{ background: {t['bg_btn_hover']}; }}
            """
            for key, btn in self.tab_buttons.items():
                btn.setStyleSheet(active if key == self.current_tab else inactive)
        except Exception as e:
            log.exception(f"Update tab styles error: {e}")

    # ── Visibility & Filtering ────────────────────────────────────────────────
    def refresh_visibility(self):
        try:
            has_items = False
            for item in self._get_all_items():
                visible = self._should_show_item(item)
                item.setVisible(visible)
                if visible:
                    has_items = True
            self.empty_label.setVisible(not has_items)
        except Exception as e:
            log.exception(f"Refresh visibility error: {e}")

    def _should_show_item(self, item):
        try:
            # Tab filter
            if self.current_tab == "fav" and not item.is_favorite:
                return False
            if self.current_tab == "all" and item.hidden_from_main:
                return False

            # Type filter
            if self.current_filter == "file" and item.data_type != ItemType.FILE:
                return False
            if self.current_filter == "url" and item.data_type != ItemType.URL:
                return False
            if self.current_filter == "text" and item.data_type != ItemType.TEXT:
                return False

            # Search
            if self.search_query:
                content_match = self.search_query.lower() in str(item.content).lower()
                tag_match = any(self.search_query.lower() in tag.lower() for tag in item.tags)
                if not (content_match or tag_match):
                    return False

            return True
        except Exception as e:
            log.exception(f"Should show item error: {e}")
            return True

    def _on_filter_changed(self, index):
        try:
            filters = ["all", "file", "url", "text"]
            self.current_filter = filters[index]
            self.refresh_visibility()
        except Exception as e:
            log.exception(f"Filter changed error: {e}")

    def _on_sort_changed(self, index):
        try:
            sorts = ["newest", "oldest", "name", "type", "size", "used"]
            self.current_sort = sorts[index]
            self._sort_items()
        except Exception as e:
            log.exception(f"Sort changed error: {e}")

    def _sort_items(self):
        try:
            # Get all items
            items = self._get_all_items()
            
            # Remove them from layout (but don't delete them!)
            for item in items:
                self.scroll_layout.removeWidget(item)

            # Sort based on current_sort
            if self.current_sort == "newest":
                items.sort(key=lambda x: x.date_added, reverse=not self.sort_ascending)
            elif self.current_sort == "oldest":
                items.sort(key=lambda x: x.date_added, reverse=self.sort_ascending)
            elif self.current_sort == "name":
                items.sort(key=lambda x: str(x.content).lower(), reverse=self.sort_ascending)
            elif self.current_sort == "type":
                items.sort(key=lambda x: x.data_type.value, reverse=self.sort_ascending)
            elif self.current_sort == "size":
                def get_size(item):
                    if item.data_type == ItemType.FILE and os.path.exists(item.content):
                        return os.path.getsize(item.content)
                    return 0
                items.sort(key=get_size, reverse=not self.sort_ascending)
            elif self.current_sort == "used":
                items.sort(key=lambda x: x.use_count, reverse=not self.sort_ascending)

            # Re-insert items at the beginning (before empty_label and stretch)
            for idx, item in enumerate(items):
                self.scroll_layout.insertWidget(idx, item)
                item.show()
            
            # Now apply filters to hide items that don't match
            self.refresh_visibility()
        except Exception as e:
            log.exception(f"Sort items error: {e}")

    def _toggle_sort_direction(self):
        """Toggle sort direction between ascending and descending"""
        try:
            self.sort_ascending = not self.sort_ascending
            self.sort_direction_btn.setText("↑" if self.sort_ascending else "↓")
            self._sort_items()
        except Exception as e:
            log.exception(f"Toggle sort direction error: {e}")

    def _on_search_changed(self, text):
        try:
            self.search_query = text.strip()
            self.refresh_visibility()
        except Exception as e:
            log.exception(f"Search changed error: {e}")

    # ── History ───────────────────────────────────────────────────────────────
    def _rebuild_history_display(self):
        try:
            # Clear history display
            while self.history_layout.count() > 0:
                item = self.history_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            if not self.clipboard_history or self.max_history == 0:
                self.history_empty_label = QLabel("No clipboard history yet." if self.max_history > 0 else "History is disabled.")
                self.history_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                t = THEMES[self.current_theme]
                self.history_empty_label.setStyleSheet(f"color: {t['text_dim']}; font-size: 13px; padding: 40px;")
                self.history_layout.addWidget(self.history_empty_label)
                self.history_layout.addStretch()
                return

            t = THEMES[self.current_theme]
            for entry in reversed(list(self.clipboard_history)):
                row = QFrame()
                row.setStyleSheet(f"""
                    QFrame {{ background: {t['bg_card']}; border: 1px solid {t['border']}; border-radius: 6px; }}
                    QFrame:hover {{ background: {t['bg_input']}; }}
                """)
                row_layout = QHBoxLayout()
                row_layout.setContentsMargins(8, 4, 8, 4)

                type_lbl = QLabel(entry["type"].upper())
                type_lbl.setFixedWidth(50)
                type_lbl.setStyleSheet(f"color: {t['accent']}; font-size: 10px; font-weight: bold;")
                row_layout.addWidget(type_lbl)

                content_str = str(entry["content"])
                if entry["type"] == "file":
                    content_str = os.path.basename(content_str)
                content_lbl = QLabel(content_str[:60] + ("…" if len(content_str) > 60 else ""))
                content_lbl.setStyleSheet(f"color: {t['text']}; font-size: 11px;")
                row_layout.addWidget(content_lbl, 1)

                time_str = entry.get("time", "")[:16].replace("T", " ")
                time_lbl = QLabel(time_str)
                time_lbl.setStyleSheet(f"color: {t['text_dim']}; font-size: 10px;")
                row_layout.addWidget(time_lbl)

                add_btn = QPushButton("+")
                add_btn.setFixedSize(22, 22)
                add_btn.setToolTip("Add to shelf")
                add_btn.setStyleSheet(f"background: {t['accent']}; color: white; border: none; border-radius: 11px; font-size: 14px;")
                add_btn.clicked.connect(lambda _, e=entry: self.add_item(e["type"], e["content"]))
                row_layout.addWidget(add_btn)

                row.setLayout(row_layout)
                row.setFixedHeight(40)
                self.history_layout.addWidget(row)

            self.history_layout.addStretch()
        except Exception as e:
            log.exception(f"Rebuild history error: {e}")

    def load_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for entry in data:
                    self.clipboard_history.append(entry)
            except Exception:
                log.exception("History load error")

    def save_history(self):
        """Save history with atomic write to prevent corruption"""
        try:
            if self.max_history == 0:
                return
            
            # Atomic write
            temp_file = HISTORY_FILE + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.clipboard_history), f, indent=2)
            
            if os.path.exists(HISTORY_FILE):
                os.remove(HISTORY_FILE)
            os.rename(temp_file, HISTORY_FILE)
        except Exception as e:
            log.exception("History save error")
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass

    # ── Clipboard Monitor ─────────────────────────────────────────────────────
    def setup_clipboard_monitor(self):
        try:
            self.clipboard = QApplication.clipboard()
            self.clipboard.dataChanged.connect(self._on_clipboard_change)
        except Exception as e:
            log.exception(f"Clipboard monitor setup error: {e}")

    def _on_clipboard_change(self):
        if not self.monitor_clipboard:
            return
        try:
            mime = self.clipboard.mimeData()
            if mime.hasUrls():
                for url in mime.urls():
                    if url.isLocalFile():
                        path = url.toLocalFile()
                        if self.max_history > 0:
                            self._add_to_history("file", path)
                        self.add_item(ItemType.FILE, path)
                return
            if mime.hasText():
                text = mime.text().strip()
                if text:
                    is_url = text.startswith(('http://', 'https://', 'www.'))
                    t = ItemType.URL if is_url else ItemType.TEXT
                    if self.max_history > 0:
                        self._add_to_history(t.value, text)
                    self.add_item(t, text)
        except Exception as e:
            log.exception(f"Clipboard change error: {e}")

    def _add_to_history(self, dtype, content):
        try:
            if self.max_history == 0:
                return
            self.clipboard_history.append({
                "type": dtype,
                "content": content,
                "time": datetime.now().isoformat()
            })
            self.save_history()
            if self.current_tab == "history":
                self._rebuild_history_display()
        except Exception as e:
            log.exception(f"Add to history error: {e}")

    # ── Item Management ───────────────────────────────────────────────────────
    def _get_all_items(self):
        """Helper method to get all DraggableItem widgets from layout"""
        return [self.scroll_layout.itemAt(i).widget()
                for i in range(self.scroll_layout.count())
                if isinstance(self.scroll_layout.itemAt(i).widget(), DraggableItem)]
    
    def add_item(self, dtype, content, is_favorite=False, hidden_from_main=False,
                 tags=None, date_added=None, use_count=0):
        try:
            if not is_favorite and self.current_tab == "fav":
                self.current_tab = "all"
                self._update_tab_styles()

            # Properly handle dtype comparison
            dtype_enum = ItemType(dtype) if isinstance(dtype, str) else dtype

            # Deduplication
            for w in self._get_all_items():
                if w.content == content and w.data_type == dtype_enum:
                    if not is_favorite and w.is_favorite:
                        is_favorite = True
                    hidden_from_main = False
                    self.scroll_layout.removeWidget(w)
                    w.deleteLater()
                    break

            item = DraggableItem(dtype, content, self,
                                 is_favorite=is_favorite,
                                 hidden_from_main=hidden_from_main,
                                 tags=tags or [],
                                 date_added=date_added,
                                 use_count=use_count)
            self.scroll_layout.insertWidget(0, item)

            if self.selection_mode:
                item.set_selection_mode(True)

            self.refresh_visibility()
            if not (is_favorite and hidden_from_main):
                self.save_favorites()
        except Exception as e:
            log.exception(f"Add item error: {e}")

    def remove_item(self, item_widget):
        try:
            self.scroll_layout.removeWidget(item_widget)
            item_widget.deleteLater()
            self.refresh_visibility()
            self.save_favorites()
        except Exception as e:
            log.exception(f"Remove item error: {e}")

    def handle_item_deletion_request(self, item_widget):
        try:
            if self.current_tab == "fav":
                # In Favorites tab: X removes from favorites but keeps item in All Items
                item_widget.is_favorite = False
                item_widget.hidden_from_main = False
                item_widget.update_style()
                item_widget._update_star_style()
                self.save_favorites()
                self.refresh_visibility()
            else:
                # In All Items tab
                if item_widget.is_favorite:
                    # Favorite items are only hidden from "All Items", they remain in Favorites
                    item_widget.hidden_from_main = True
                    self.save_favorites()
                    self.refresh_visibility()
                else:
                    # Non-favorite items are deleted permanently with undo support
                    self.undo_stack.append([{
                        'type': item_widget.data_type.value,
                        'content': item_widget.content,
                        'is_favorite': item_widget.is_favorite,
                        'hidden_from_main': item_widget.hidden_from_main,
                        'tags': item_widget.tags,
                        'date_added': item_widget.date_added,
                        'use_count': item_widget.use_count,
                    }])
                    self.undo_btn.setEnabled(True)
                    self.remove_item(item_widget)
        except Exception as e:
            log.exception(f"Delete request error: {e}")

    def undo_delete(self):
        try:
            if not self.undo_stack:
                return
            for entry in self.undo_stack.pop():
                self.add_item(entry['type'], entry['content'],
                              is_favorite=entry['is_favorite'],
                              hidden_from_main=entry['hidden_from_main'],
                              tags=entry.get('tags', []),
                              date_added=entry.get('date_added'),
                              use_count=entry.get('use_count', 0))
            self.undo_btn.setEnabled(len(self.undo_stack) > 0)
        except Exception as e:
            log.exception(f"Undo error: {e}")

    # ── Bulk Operations ───────────────────────────────────────────────────────
    def toggle_selection_mode(self):
        try:
            self.selection_mode = not self.selection_mode
            self.select_mode_btn.setText("Exit" if self.selection_mode else "Select")
            for b in (self.select_all_btn, self.delete_selected_btn, self.fav_selected_btn):
                b.setVisible(self.selection_mode)
            for item in self._get_all_items():
                item.set_selection_mode(self.selection_mode)
        except Exception as e:
            log.exception(f"Toggle selection error: {e}")

    def _exit_selection_mode(self):
        try:
            if self.selection_mode:
                self.toggle_selection_mode()
        except Exception as e:
            log.exception(f"Exit selection error: {e}")

    def select_all_items(self):
        try:
            if not self.selection_mode:
                return
            for item in self._get_all_items():
                if item.isVisible():
                    item.select_checkbox.setChecked(True)
        except Exception as e:
            log.exception(f"Select all error: {e}")

    def delete_selected_items(self):
        try:
            if not self.selection_mode:
                return
            selected = [item for item in self._get_all_items() if item.is_selected]
            if not selected:
                return
            if QMessageBox.question(self, "Confirm Delete",
                                    f"Delete {len(selected)} item(s)?",
                                    QMessageBox.StandardButton.Yes |
                                    QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return
            batch = [{'type': w.data_type.value, 'content': w.content,
                      'is_favorite': w.is_favorite, 'hidden_from_main': w.hidden_from_main,
                      'tags': w.tags, 'date_added': w.date_added, 'use_count': w.use_count}
                     for w in selected]
            self.undo_stack.append(batch)
            self.undo_btn.setEnabled(True)
            for w in selected:
                self.remove_item(w)
            self._exit_selection_mode()
        except Exception as e:
            log.exception(f"Delete selected error: {e}")

    def favorite_selected_items(self):
        try:
            for item in self._get_all_items():
                if item.is_selected and not item.is_favorite:
                    item.toggle_favorite()
        except Exception as e:
            log.exception(f"Favorite selected error: {e}")

    def clear_shelf(self):
        try:
            if QMessageBox.question(self, "Clear Shelf",
                                    "Remove all non-favorite items?",
                                    QMessageBox.StandardButton.Yes |
                                    QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
                return
            to_remove = []
            for item in self._get_all_items():
                if item.is_favorite:
                    item.hidden_from_main = True
                else:
                    to_remove.append(item)
            for item in to_remove:
                self.remove_item(item)
            self.save_favorites()
            self.refresh_visibility()
        except Exception as e:
            log.exception(f"Clear shelf error: {e}")

    # ── Persistence ───────────────────────────────────────────────────────────
    def save_favorites(self):
        """Save favorites with atomic write to prevent corruption"""
        try:
            data = [{'type': w.data_type.value, 'content': w.content,
                     'is_favorite': w.is_favorite, 'hidden_from_main': w.hidden_from_main,
                     'tags': w.tags, 'date_added': w.date_added, 'use_count': w.use_count}
                    for w in self._get_all_items()]
            
            # Atomic write: write to temp file then rename
            temp_file = FAVORITES_FILE + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            # Atomic rename (works on all platforms)
            if os.path.exists(FAVORITES_FILE):
                backup_file = FAVORITES_FILE + '.bak'
                if os.path.exists(backup_file):
                    os.remove(backup_file)
                os.rename(FAVORITES_FILE, backup_file)
            os.rename(temp_file, FAVORITES_FILE)
        except Exception as e:
            log.exception("Save favorites error")
            # Try to clean up temp file
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass

    def load_favorites(self):
        if not os.path.exists(FAVORITES_FILE):
            return
        try:
            with open(FAVORITES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for entry in reversed(data):
                self.add_item(entry['type'], entry['content'],
                              is_favorite=entry.get('is_favorite', False),
                              hidden_from_main=entry.get('hidden_from_main', False),
                              tags=entry.get('tags', []),
                              date_added=entry.get('date_added'),
                              use_count=entry.get('use_count', 0))
        except Exception:
            log.exception("Load favorites error")

    def save_settings(self):
        """Save settings with atomic write to prevent corruption"""
        try:
            settings = {
                'monitor_clipboard': self.monitor_clipboard,
                'hotkey': self.hotkey,
                'theme': self.current_theme,
                'close_to_tray': self.close_to_tray,
                'max_history': self.max_history,
                'window_geometry': {
                    'x': self.x(), 'y': self.y(),
                    'width': self.width(), 'height': self.height()
                }
            }
            
            # Atomic write
            temp_file = SETTINGS_FILE + '.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2)
            
            if os.path.exists(SETTINGS_FILE):
                os.remove(SETTINGS_FILE)
            os.rename(temp_file, SETTINGS_FILE)
        except Exception as e:
            log.exception("Save settings error")
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass

    def load_settings(self):
        if not os.path.exists(SETTINGS_FILE):
            log.info("No settings file found, using defaults")
            return
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                s = json.load(f)
            self.monitor_clipboard = s.get('monitor_clipboard', True)
            self.hotkey = s.get('hotkey', DEFAULT_HOTKEY)
            self.current_theme = s.get('theme', 'dark')
            self.close_to_tray = s.get('close_to_tray', True)
            self.max_history = s.get('max_history', MAX_HISTORY)
            self.window_geometry = s.get('window_geometry')
            log.info(f"Settings loaded - History size: {self.max_history}")
        except Exception as e:
            log.exception("Load settings error")
            # Set defaults on error
            self.max_history = MAX_HISTORY

    def restore_window_geometry(self):
        try:
            if self.window_geometry:
                # Only restore position and height, force width to 360px
                self.setGeometry(self.window_geometry['x'], self.window_geometry['y'],
                                 360, self.window_geometry['height'])
        except Exception as e:
            log.exception(f"Restore geometry error: {e}")

    # ── Export / Import ───────────────────────────────────────────────────────
    def export_items(self):
        try:
            filename, _ = QFileDialog.getSaveFileName(self, "Export Items",
                                                      "dropshelf_export.json",
                                                      "JSON Files (*.json)")
            if not filename:
                return
            items = [{'type': w.data_type.value, 'content': w.content,
                      'is_favorite': w.is_favorite, 'hidden_from_main': w.hidden_from_main,
                      'tags': w.tags, 'date_added': w.date_added, 'use_count': w.use_count}
                     for w in self._get_all_items()]
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(items, f, indent=2)
            QMessageBox.information(self, "Success", f"Exported {len(items)} items.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Export failed: {e}")

    def import_items(self):
        try:
            filename, _ = QFileDialog.getOpenFileName(self, "Import Items", "",
                                                      "JSON Files (*.json)")
            if not filename:
                return
            with open(filename, 'r', encoding='utf-8') as f:
                items = json.load(f)
            count = 0
            for item in items:
                self.add_item(item['type'], item['content'],
                              is_favorite=item.get('is_favorite', False),
                              hidden_from_main=item.get('hidden_from_main', False),
                              tags=item.get('tags', []),
                              date_added=item.get('date_added'),
                              use_count=item.get('use_count', 0))
                count += 1
            QMessageBox.information(self, "Success", f"Imported {count} items.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Import failed: {e}")

    # ── Dialogs ───────────────────────────────────────────────────────────────
    def open_settings(self):
        try:
            SettingsDialog(self).exec()
        except Exception as e:
            log.exception(f"Open settings error: {e}")

    def open_templates(self):
        try:
            if self._templates_dialog is None or not self._templates_dialog.isVisible():
                self._templates_dialog = TemplatesDialog(self.current_theme, self)
                self._templates_dialog.template_inserted.connect(
                    lambda txt: self.add_item(ItemType.TEXT, txt))
            self._templates_dialog.show()
            self._templates_dialog.raise_()
        except Exception as e:
            log.exception(f"Open templates error: {e}")

    def open_stats(self):
        try:
            items_data = [{'type': w.data_type.value, 'content': w.content,
                          'use_count': w.use_count, 'is_favorite': w.is_favorite}
                         for w in self._get_all_items()]
            StatsDialog(items_data, self.current_theme, self).exec()
        except Exception as e:
            log.exception(f"Open stats error: {e}")

    # ── Keyboard Shortcuts ────────────────────────────────────────────────────
    def setup_shortcuts(self):
        try:
            QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(
                lambda: self.search_input.setFocus())
            QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(self.undo_delete)
            QShortcut(QKeySequence("Delete"), self).activated.connect(self.delete_selected_items)
            QShortcut(QKeySequence("Ctrl+A"), self).activated.connect(self.select_all_items)
            QShortcut(QKeySequence("Escape"), self).activated.connect(self._exit_selection_mode)
            QShortcut(QKeySequence("Ctrl+H"), self).activated.connect(
                lambda: self.switch_tab("history") if self.max_history > 0 else None)
        except Exception as e:
            log.exception(f"Setup shortcuts error: {e}")

    # ── System Tray ───────────────────────────────────────────────────────────
    def setup_tray_icon(self):
        try:
            self.tray_icon = QSystemTrayIcon(self)
            self.tray_icon.setIcon(load_app_icon())

            menu = QMenu()
            t = THEMES[self.current_theme]
            menu.setStyleSheet(f"""
                QMenu {{ 
                    background: {t['bg_input']}; 
                    color: {t['text']}; 
                    border: 1px solid {t['border']}; 
                    border-radius: 8px;
                    padding: 6px;
                }}
                QMenu::item {{ 
                    padding: 8px 24px; 
                    border-radius: 5px;
                    margin: 2px 4px;
                }}
                QMenu::item:selected {{ 
                    background: {t['accent']}; 
                    color: white; 
                }}
                QMenu::separator {{
                    height: 1px;
                    background: {t['border']};
                    margin: 6px 8px;
                }}
            """)
            
            for label, slot in [("Show", self.show_window),
                                 ("Settings", self.open_settings),
                                 (None, None),
                                 ("Quit", self._force_quit)]:
                if label is None:
                    menu.addSeparator()
                else:
                    a = QAction(label, self)
                    a.triggered.connect(slot)
                    menu.addAction(a)

            self.tray_icon.setContextMenu(menu)
            self.tray_icon.activated.connect(
                lambda r: self.toggle_window() if r == QSystemTrayIcon.ActivationReason.Trigger else None)
            self.tray_icon.show()
        except Exception as e:
            log.exception(f"Tray icon setup error: {e}")

    def setup_hotkey(self):
        """Setup global hotkey with platform-specific handling"""
        try:
            keyboard.add_hotkey(self.hotkey, self.toggle_window)
            log.info(f"Hotkey registered: {self.hotkey}")
        except Exception as e:
            log.warning(f"Hotkey setup error (this may require elevated permissions on some systems): {e}")
            # Hotkey may fail on some Linux configurations or without admin rights
            # App will still work, just without global hotkey

    def toggle_window(self):
        try:
            if self.isVisible():
                self.minimize_to_tray()
            else:
                self.show_window()
        except Exception as e:
            log.exception(f"Toggle window error: {e}")

    def show_window(self):
        try:
            self.show()
            self.activateWindow()
            self.raise_()
        except Exception as e:
            log.exception(f"Show window error: {e}")

    def minimize_to_tray(self):
        try:
            self.hide()
            self.tray_icon.showMessage("DropShelf",
                                       f"Minimized to tray. Press {self.hotkey} to open.",
                                       QSystemTrayIcon.MessageIcon.Information, 2000)
        except Exception as e:
            log.exception(f"Minimize error: {e}")

    def close_app_or_tray(self):
        try:
            if self.close_to_tray:
                self.minimize_to_tray()
            else:
                self._force_quit()
        except Exception as e:
            log.exception(f"Close app error: {e}")

    def _force_quit(self):
        try:
            self.save_favorites()
            self.save_settings()
            keyboard.unhook_all()
            try:
                self.tray_icon.hide()
            except Exception:
                pass
            QApplication.quit()
        except Exception as e:
            log.exception(f"Force quit error: {e}")

    # kept for compatibility
    def close_app(self):
        self._force_quit()

    # ── Single-instance server ────────────────────────────────────────────────
    def setup_local_server(self):
        try:
            self.server = QLocalServer(self)
            self.server.listen(APP_ID)
            self.server.newConnection.connect(self._handle_new_connection)
        except Exception as e:
            log.exception(f"Local server setup error: {e}")

    def _handle_new_connection(self):
        try:
            client = self.server.nextPendingConnection()
            if client:
                client.waitForReadyRead(1000)
                data = client.readAll().data().decode('utf-8')
                if data == "SHOW":
                    self.show_window()
        except Exception as e:
            log.exception(f"Handle connection error: {e}")

    # ── Drag & Drop ───────────────────────────────────────────────────────────
    def dragEnterEvent(self, event):
        try:
            if (event.mimeData().hasFormat("application/x-dropshelf-item") or
                    event.mimeData().hasUrls() or event.mimeData().hasText()):
                event.accept()
                self._highlight_drop(True)
            else:
                event.ignore()
        except Exception as e:
            log.exception(f"Drag enter error: {e}")
            event.ignore()

    def dragLeaveEvent(self, event):
        try:
            self._highlight_drop(False)
        except Exception as e:
            log.exception(f"Drag leave error: {e}")

    def dropEvent(self, event):
        try:
            self._highlight_drop(False)
            mime = event.mimeData()
            
            # Internal reorder
            if mime.hasFormat("application/x-dropshelf-item"):
                try:
                    item_id = int(mime.data("application/x-dropshelf-item").data().decode('utf-8'))
                    for i in range(self.scroll_layout.count()):
                        w = self.scroll_layout.itemAt(i).widget()
                        if w and id(w) == item_id:
                            drop_pos = self.scroll_content.mapFrom(self, event.position().toPoint())
                            insert_index = self.scroll_layout.count() - 1
                            for j in range(self.scroll_layout.count()):
                                wj = self.scroll_layout.itemAt(j).widget()
                                if wj and wj != self.empty_label:
                                    if drop_pos.y() < wj.y() + wj.height() / 2:
                                        insert_index = j
                                        break
                            self.scroll_layout.removeWidget(w)
                            self.scroll_layout.insertWidget(insert_index, w)
                            event.accept()
                            self.save_favorites()
                            return
                except Exception as e:
                    log.exception(f"Reorder error: {e}")
                    
            # External files/URLs
            if mime.hasUrls():
                for url in mime.urls():
                    fp = url.toLocalFile()
                    if fp:
                        self.add_item(ItemType.FILE, fp)
                    else:
                        # Non-local URL (e.g. dragged from browser)
                        url_str = url.toString()
                        if url_str:
                            self.add_item(ItemType.URL, url_str)
                event.acceptProposedAction()
            elif mime.hasText():
                text = mime.text().strip()
                if text:
                    t = ItemType.URL if text.startswith(('http://', 'https://', 'www.')) else ItemType.TEXT
                    self.add_item(t, text)
                event.acceptProposedAction()
        except Exception as e:
            log.exception(f"Drop event error: {e}")
            event.ignore()

    def _highlight_drop(self, on):
        try:
            t = THEMES[self.current_theme]
            if on:
                self.central_widget.setStyleSheet(f"""
                    QWidget#CentralWidget {{
                        background-color: {t['bg_window']};
                        border: 2px dashed {t['accent']};
                        border-radius: 15px;
                    }}
                """)
            else:
                self.apply_theme()
        except Exception as e:
            log.exception(f"Highlight drop error: {e}")

    # ── Window drag ───────────────────────────────────────────────────────────
    def mousePressEvent(self, event):
        try:
            if event.button() == Qt.MouseButton.LeftButton:
                self._old_pos = event.globalPosition().toPoint()
        except Exception as e:
            log.exception(f"Mouse press error: {e}")

    def mouseMoveEvent(self, event):
        try:
            if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, '_old_pos'):
                delta = event.globalPosition().toPoint() - self._old_pos
                self.move(self.x() + delta.x(), self.y() + delta.y())
                self._old_pos = event.globalPosition().toPoint()
        except Exception as e:
            log.exception(f"Mouse move error: {e}")

    def resizeEvent(self, event):
        """Override resize to enforce fixed width of 360px"""
        try:
            # Always maintain 360px width, allow height to change
            if event.size().width() != 360:
                self.resize(360, event.size().height())
            super().resizeEvent(event)
        except Exception as e:
            log.exception(f"Resize event error: {e}")

    def closeEvent(self, event):
        try:
            self.save_settings()
            event.accept()
        except Exception as e:
            log.exception(f"Close event error: {e}")
            event.accept()


# ─── Entry point ──────────────────────────────────────────────────────────────
if __name__ == '__main__':
    try:
        # Platform-specific initialization
        system = platform.system()
        
        if system == "Windows":
            try:
                import ctypes
                # Set app ID for Windows taskbar
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
                # Enable DPI awareness for Windows
                try:
                    ctypes.windll.shcore.SetProcessDpiAwareness(1)
                except Exception:
                    pass
            except Exception:
                pass
        elif system == "Darwin":
            # macOS specific settings
            try:
                # Enable high DPI support
                os.environ['QT_ENABLE_HIGHDPI_SCALING'] = '1'
            except Exception:
                pass
        else:  # Linux
            # Linux specific settings
            try:
                # Enable better font rendering on Linux
                os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'
            except Exception:
                pass

        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)
        app.setWindowIcon(load_app_icon())
        
        # Platform-specific font selection
        font = app.font()
        if system == "Windows":
            font.setFamily("Segoe UI")
        elif system == "Darwin":
            font.setFamily("SF Pro Text")
        else:  # Linux
            font.setFamily("Ubuntu")
        font.setPointSize(10)
        app.setFont(font)
        
        # Global stylesheet with platform-aware fonts
        font_families = {
            'Windows': "'Segoe UI', Arial, sans-serif",
            'Darwin': "'SF Pro Text', 'Helvetica Neue', Arial, sans-serif",
            'Linux': "'Ubuntu', 'Roboto', 'DejaVu Sans', Arial, sans-serif"
        }.get(system, "'Segoe UI', 'Helvetica Neue', Arial, sans-serif")
        
        app.setStyleSheet(f'''
            QWidget {{ font-family: {font_families}; font-size: 10pt; }}
            QPushButton {{ padding: 4px 10px; border-radius: 6px; border: none; }}
            QLineEdit, QTextEdit {{ padding: 6px; border-radius: 6px; }}
            QFrame {{ border-radius: 6px; }}
            QLabel {{ padding: 0px; }}
            QToolButton {{ padding: 4px; }}
            QScrollArea {{ padding: 0px; margin: 0px; }}
        ''')

        # Single instance check
        socket = QLocalSocket()
        socket.connectToServer(APP_ID)
        if socket.waitForConnected(500):
            socket.write("SHOW".encode('utf-8'))
            socket.waitForBytesWritten(1000)
            log.info("Another instance already running, showing existing window")
            sys.exit(0)

        log.info(f"Starting DropShelf on {system}")
        window = DropShelfWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        log.exception(f"Application error: {e}")
        sys.exit(1)