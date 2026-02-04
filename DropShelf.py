import sys
import os
import json
import keyboard
import subprocess
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QLabel, QPushButton, QScrollArea, QFrame, QHBoxLayout,
                             QSizePolicy, QDialog, QLineEdit, QSystemTrayIcon, QMenu, 
                             QFileIconProvider, QStyle, QCheckBox)
from PyQt6.QtCore import Qt, QMimeData, QUrl, QSize, QPoint, pyqtSignal, QFileInfo, QEvent
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtGui import QDrag, QPixmap, QIcon, QAction, QColor, QDesktopServices, QCursor, QPainter, QKeySequence

# --- Constants ---
APP_ID = "DropShelf"
SETTINGS_FILE = "dropshelf_settings.json"
FAVORITES_FILE = "dropshelf_favorites.json"
DEFAULT_HOTKEY = "ctrl+shift+x"
ICON_CANDIDATES = ["pic.ico", "icon.ico", "pic.png", "icon.png"]

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def find_icon():
    for name in ICON_CANDIDATES:
        p = resource_path(name)
        if os.path.exists(p):
            return name
    return ICON_CANDIDATES[0]

ICON_NAME = find_icon()

class ClickableLabel(QLabel):
    clicked = pyqtSignal()
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

class DraggableItem(QFrame):
    def __init__(self, data_type, content, parent=None, is_favorite=False, hidden_from_main=False):
        super().__init__(parent)
        self.data_type = data_type # 'file', 'text', 'url'
        self.content = content
        self.parent_shelf = parent
        self.is_favorite = is_favorite
        self.hidden_from_main = hidden_from_main
        self.init_ui()
        
    def init_ui(self):
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.update_style()

        # Layout: [Text] [Spacer] [Icon] [Star] [Close]
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 5, 5, 5)
        layout.setSpacing(8)

        # 1. Text Info (Left)
        self.text_label = QLabel()
        self.text_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #e0e0e0;")
        
        display_text = str(self.content)
        if self.data_type == 'file':
            display_text = os.path.basename(self.content)
        
        # Truncate long text for display
        font_metrics = self.text_label.fontMetrics()
        elided_text = font_metrics.elidedText(display_text, Qt.TextElideMode.ElideRight, 180)
        self.text_label.setText(elided_text)
        self.text_label.setToolTip(str(self.content))
        layout.addWidget(self.text_label, 1) # Stretch factor 1

        # 2. Icon / Preview (Right of text)
        self.icon_label = ClickableLabel()
        self.icon_label.setFixedSize(32, 32)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.icon_label.clicked.connect(self.handle_open)
        self.set_preview()
        layout.addWidget(self.icon_label)

        # 3. Favorite Star Button
        self.star_btn = QPushButton("★" if self.is_favorite else "☆")
        self.star_btn.setFixedSize(24, 24)
        self.star_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.star_btn.clicked.connect(self.toggle_favorite)
        self.update_star_style()
        layout.addWidget(self.star_btn)

        # 4. Close Button
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.request_removal)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #888;
                border: none;
                font-weight: bold;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: #ff4d4d;
                color: white;
            }
        """)
        layout.addWidget(self.close_btn)

        self.setLayout(layout)
        self.setFixedHeight(60)

    def update_style(self):
        border_color = "#FFD700" if self.is_favorite else "#3d3d3d"
        bg_color = "#332b00" if self.is_favorite else "#2b2b2b"
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border-radius: 8px;
                border: 1px solid {border_color};
            }}
            QFrame:hover {{
                background-color: #3a3a3a;
                border: 1px solid #505050;
            }}
            QLabel {{ border: none; background: transparent; }}
        """)

    def update_star_style(self):
        color = "#FFD700" if self.is_favorite else "#666"
        self.star_btn.setText("★" if self.is_favorite else "☆")
        self.star_btn.setStyleSheet(f"""
            QPushButton {{
                color: {color};
                border: none;
                background: transparent;
                font-size: 16px;
            }}
            QPushButton:hover {{ color: #FFEA00; }}
        """)

    def set_preview(self):
        if self.data_type == 'file':
            file_info = QFileInfo(self.content)
            icon_provider = QFileIconProvider()
            icon = icon_provider.icon(file_info)
            if not icon.isNull():
                self.icon_label.setPixmap(icon.pixmap(32, 32))
            else:
                self.icon_label.setText("📄")
        elif self.data_type == 'url':
            self.icon_label.setText("🔗")
            self.icon_label.setStyleSheet("font-size: 20px; border: none; background: transparent;")
            self.icon_label.setToolTip("Click to Open Link")
        else: # Text
            self.icon_label.setText("T")
            self.icon_label.setStyleSheet("font-size: 20px; color: #4CAF50; border: none; background: transparent;")

    def toggle_favorite(self):
        self.is_favorite = not self.is_favorite
        # If we unfavorite something that was hidden from main, show it again in main
        if not self.is_favorite and self.hidden_from_main:
             self.hidden_from_main = False
             
        self.update_style()
        self.update_star_style()
        if self.parent_shelf:
            self.parent_shelf.save_favorites()
            self.parent_shelf.refresh_visibility()

    def request_removal(self):
        if self.parent_shelf:
            self.parent_shelf.handle_item_deletion_request(self)

    def handle_open(self):
        if self.data_type == 'url':
            QDesktopServices.openUrl(QUrl(self.content))
        elif self.data_type == 'file':
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.content))

    def handle_open_location(self):
        if self.data_type == 'file' and os.path.exists(self.content):
            folder = os.path.dirname(self.content)
            if sys.platform == 'win32':
                subprocess.Popen(['explorer', '/select,', os.path.normpath(self.content)])
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def handle_copy(self):
        clipboard = QApplication.clipboard()
        mime_data = QMimeData()
        
        if self.data_type == 'file':
            url = QUrl.fromLocalFile(self.content)
            mime_data.setUrls([url])
            mime_data.setText(self.content)
        else:
            mime_data.setText(self.content)
            
        clipboard.setMimeData(mime_data)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #333; color: white; border: 1px solid #555; }
            QMenu::item { padding: 5px 20px; }
            QMenu::item:selected { background-color: #555; }
        """)
        
        open_action = QAction("Open", self)
        open_action.triggered.connect(self.handle_open)
        menu.addAction(open_action)
        
        copy_action = QAction("Copy", self)
        copy_action.triggered.connect(self.handle_copy)
        menu.addAction(copy_action)

        if self.data_type == 'file':
            loc_action = QAction("Open File Location", self)
            loc_action.triggered.connect(self.handle_open_location)
            menu.addAction(loc_action)

        fav_action = QAction("Remove from Favorites" if self.is_favorite else "Add to Favorites", self)
        fav_action.triggered.connect(self.toggle_favorite)
        menu.addAction(fav_action)

        menu.exec(event.globalPos())

    def mouseMoveEvent(self, event):
        if event.buttons() != Qt.MouseButton.LeftButton:
            return
        
        drag = QDrag(self)
        mime_data = QMimeData()

        if self.data_type == 'file':
            url = QUrl.fromLocalFile(self.content)
            mime_data.setUrls([url])
        elif self.data_type == 'url':
            mime_data.setUrls([QUrl(self.content)])
            mime_data.setText(self.content)
        else:
            mime_data.setText(self.content)

        mime_data.setData("application/x-dropshelf-item", str(id(self)).encode('utf-8'))

        drag.setMimeData(mime_data)
        pixmap = self.grab()
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.position().toPoint())
        
        drag.exec(Qt.DropAction.MoveAction | Qt.DropAction.CopyAction)

class HotkeyRecorder(QLineEdit):
    def __init__(self, current_hotkey, parent=None):
        super().__init__(current_hotkey, parent)
        self.setPlaceholderText("Press keys (e.g. Ctrl+Shift+X)")
        self.setReadOnly(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            QLineEdit { 
                background-color: #3a3a3a; 
                color: #4CAF50; 
                border: 2px solid #555; 
                padding: 5px; 
                border-radius: 4px; 
                font-weight: bold;
                font-size: 14px;
            }
            QLineEdit:focus { border: 2px solid #4CAF50; }
        """)

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
            return
        modifiers = event.modifiers()
        parts = []
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            parts.append("ctrl")
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            parts.append("shift")
        if modifiers & Qt.KeyboardModifier.AltModifier:
            parts.append("alt")
        if modifiers & Qt.KeyboardModifier.MetaModifier:
            parts.append("windows")

        key_text = QKeySequence(key).toString().lower()
        if key_text:
            parts.append(key_text)

        if parts:
            result = "+".join(parts)
            self.setText(result)

class SettingsDialog(QDialog):
    def __init__(self, current_hotkey, exit_min_to_tray, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DropShelf Settings")
        self.setFixedSize(320, 200)
        self.setStyleSheet("""
            QDialog { background-color: #2b2b2b; color: white; }
            QLabel { color: #ccc; }
            QPushButton { background-color: #4CAF50; color: white; border: none; padding: 8px; border-radius: 4px; }
            QPushButton:hover { background-color: #45a049; }
            QCheckBox { color: #ccc; }
            QCheckBox::indicator { width: 18px; height: 18px; }
        """)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Current Hotkey:"))
        
        self.hotkey_input = HotkeyRecorder(current_hotkey)
        layout.addWidget(self.hotkey_input)
        layout.addWidget(QLabel("Click the green box to capture hotkey"))
        
        layout.addSpacing(10)
        self.cb_exit_tray = QCheckBox("Exit button minimizes to system tray")
        self.cb_exit_tray.setChecked(exit_min_to_tray)
        layout.addWidget(self.cb_exit_tray)
        
        layout.addStretch()
        self.save_btn = QPushButton("Save & Close")
        self.save_btn.clicked.connect(self.accept)
        layout.addWidget(self.save_btn)

    def get_settings(self):
        return {
            "hotkey": self.hotkey_input.text(),
            "exit_min_to_tray": self.cb_exit_tray.isChecked()
        }

class DropShelfWindow(QMainWindow):
    toggle_hotkey_signal = pyqtSignal()
    restore_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("DropShelf")
        
        icon_path = resource_path(ICON_NAME)
        if os.path.exists(icon_path):
            self.app_icon = QIcon(icon_path)
        else:
            pix = QPixmap(64, 64)
            pix.fill(QColor("#4CAF50"))
            painter = QPainter(pix)
            painter.setPen(QColor("white"))
            painter.drawText(0, 0, 64, 64, Qt.AlignmentFlag.AlignCenter, "DS")
            painter.end()
            self.app_icon = QIcon(pix)

        QApplication.setWindowIcon(self.app_icon)
        self.setWindowIcon(self.app_icon)

        self.hotkey = DEFAULT_HOTKEY
        self.exit_min_to_tray = False
        self.load_settings()
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        screen = QApplication.primaryScreen().availableGeometry()
        w, h = 360, 600
        x = screen.width() - w - 20
        y = (screen.height() - h) // 2
        self.setGeometry(x, y, w, h)

        self.setAcceptDrops(True)
        self.init_ui()
        self.setup_system_tray()
        self.setup_hotkey()
        self.setup_clipboard_monitor()
        self.load_favorites() 

        self.toggle_hotkey_signal.connect(self.toggle_visibility)
        self.restore_signal.connect(self.showNormal)
        self.restore_signal.connect(self.activateWindow)

        self.local_server = QLocalServer()
        try:
            if self.local_server.isListening():
                self.local_server.close()
            self.local_server.listen(APP_ID)
        except Exception:
            try:
                socket_path = os.path.join(os.path.abspath("."), APP_ID)
                if os.path.exists(socket_path):
                    os.remove(socket_path)
                self.local_server.listen(APP_ID)
            except Exception:
                pass
        self.local_server.newConnection.connect(self.handle_new_connection)

    def handle_new_connection(self):
        socket = self.local_server.nextPendingConnection()
        if socket.waitForReadyRead(100):
            msg = socket.readAll().data().decode('utf-8')
            if msg == "SHOW":
                self.restore_signal.emit()
        socket.disconnectFromServer()

    def init_ui(self):
        self.central_widget = QWidget()
        self.central_widget.setObjectName("CentralWidget")
        self.central_widget.setStyleSheet("""
            QWidget#CentralWidget {
                background-color: rgba(30, 30, 30, 245);
                border: 1px solid #444;
                border-radius: 15px;
            }
        """)
        self.setCentralWidget(self.central_widget)

        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # --- Header ---
        header_layout = QHBoxLayout()
        header_layout.setSpacing(5)

        title_label = QLabel("DropShelf")
        title_label.setStyleSheet("color: #aaa; font-weight: bold; font-family: sans-serif;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        def create_header_btn(text, tooltip, callback):
            btn = QPushButton(text)
            btn.setFixedSize(28, 28)
            btn.setToolTip(tooltip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(callback)
            btn.setStyleSheet("""
                QPushButton { background: transparent; color: #888; border: none; font-size: 14px; border-radius: 4px; }
                QPushButton:hover { background: #444; color: white; }
            """)
            return btn

        self.btn_clear = create_header_btn("🗑", "Clear (Keeps Favorites)", self.clear_shelf)
        header_layout.addWidget(self.btn_clear)
        self.btn_settings = create_header_btn("⚙", "Settings", self.open_settings)
        header_layout.addWidget(self.btn_settings)
        self.btn_tray = create_header_btn("▼", "Minimize to Tray", self.minimize_to_tray)
        header_layout.addWidget(self.btn_tray)
        self.btn_minimize = create_header_btn("─", "Minimize", self.showMinimized)
        header_layout.addWidget(self.btn_minimize)
        
        self.btn_close = create_header_btn("✕", "Exit App", self.handle_exit_click)
        self.btn_close.setStyleSheet("""
            QPushButton { background: transparent; color: #888; border: none; font-size: 14px; border-radius: 4px; }
            QPushButton:hover { background: #d32f2f; color: white; }
        """)
        header_layout.addWidget(self.btn_close)

        main_layout.addLayout(header_layout)
        
        # Apply initial settings to UI
        self.apply_ui_settings()

        # --- Tabs ---
        self.tab_layout = QHBoxLayout()
        self.tab_layout.setSpacing(10)
        self.tab_layout.setContentsMargins(5, 0, 5, 0)
        
        self.btn_tab_all = QPushButton("All Items")
        self.btn_tab_fav = QPushButton("Favorites")
        
        for btn in [self.btn_tab_all, self.btn_tab_fav]:
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(25)
            btn.clicked.connect(self.on_tab_click)
            
        self.tab_layout.addWidget(self.btn_tab_all)
        self.tab_layout.addWidget(self.btn_tab_fav)
        main_layout.addLayout(self.tab_layout)
        
        self.current_tab = "all"
        self.update_tab_styles()

        # --- Scroll Area ---
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                border: none;
                background: #2b2b2b;
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical { background: #555; border-radius: 3px; }
        """)

        self.scroll_content = QWidget()
        self.scroll_content.setStyleSheet("background: transparent;")
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_layout.setSpacing(8)

        self.scroll.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll)

        self.empty_label = QLabel("Drag items here\nor Copy (Ctrl+C)")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: #666; font-style: italic; margin-top: 20px;")
        self.scroll_layout.addWidget(self.empty_label)

    def apply_ui_settings(self):
        if self.exit_min_to_tray:
            self.btn_close.hide()
            self.btn_tray.setToolTip("Minimize to Tray (Safety Mode)")
            # In safety mode, tray button is the primary "close" visual for the top bar
        else:
            self.btn_close.show()
            self.btn_tray.setToolTip("Minimize to Tray")

    def handle_exit_click(self):
        if self.exit_min_to_tray:
            self.minimize_to_tray()
        else:
            self.close_app()

    def on_tab_click(self):
        sender = self.sender()
        if sender == self.btn_tab_all:
            self.current_tab = "all"
        else:
            self.current_tab = "fav"
        self.update_tab_styles()
        self.refresh_visibility()

    def update_tab_styles(self):
        active_style = """
            QPushButton { 
                background-color: #4CAF50; 
                color: white; 
                border: none; 
                border-radius: 4px;
                font-weight: bold;
            }
        """
        inactive_style = """
            QPushButton { 
                background-color: transparent; 
                color: #888; 
                border: 1px solid #444; 
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #3a3a3a; }
        """
        
        self.btn_tab_all.setStyleSheet(active_style if self.current_tab == "all" else inactive_style)
        self.btn_tab_fav.setStyleSheet(active_style if self.current_tab == "fav" else inactive_style)

    def refresh_visibility(self):
        has_visible_items = False
        
        for i in range(self.scroll_layout.count()):
            item = self.scroll_layout.itemAt(i)
            widget = item.widget()
            
            if isinstance(widget, DraggableItem):
                should_show = False
                if self.current_tab == "fav":
                    if widget.is_favorite:
                        should_show = True
                else:
                    if not widget.hidden_from_main:
                        should_show = True
                
                if should_show:
                    widget.show()
                    has_visible_items = True
                else:
                    widget.hide()
        
        if not has_visible_items:
            self.empty_label.show()
            if self.current_tab == "fav":
                self.empty_label.setText("No Favorites yet")
            else:
                self.empty_label.setText("Drag items here\nor Copy (Ctrl+C)")
        else:
            self.empty_label.hide()

    def handle_item_deletion_request(self, item):
        # Safety Measurement: Unfavoriting or "Deleting" from Favorites tab 
        # now always restores it to the main list first instead of wiping it.
        if self.current_tab == "fav":
            item.is_favorite = False
            item.hidden_from_main = False # Restore to "All Items"
            item.update_style()
            item.update_star_style()
            
            self.refresh_visibility()
            self.save_favorites()
        else:
            # In All Items tab
            if item.is_favorite:
                # Keep it in Favorites, but hide from the "Clipboard" view
                item.hidden_from_main = True
                self.refresh_visibility()
                self.save_favorites()
            else:
                # Not a favorite, delete permanently
                self.remove_item(item)

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    data = json.load(f)
                    self.hotkey = data.get("hotkey", DEFAULT_HOTKEY)
                    self.exit_min_to_tray = data.get("exit_min_to_tray", False)
            except:
                pass

    def save_settings(self):
        data = {
            "hotkey": self.hotkey,
            "exit_min_to_tray": self.exit_min_to_tray
        }
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(data, f)

    def open_settings(self):
        dlg = SettingsDialog(self.hotkey, self.exit_min_to_tray, self)
        if dlg.exec():
            results = dlg.get_settings()
            self.hotkey = results["hotkey"]
            self.exit_min_to_tray = results["exit_min_to_tray"]
            self.save_settings()
            self.setup_hotkey()
            self.apply_ui_settings()

    def setup_hotkey(self):
        try:
            keyboard.unhook_all()
            keyboard.add_hotkey(self.hotkey, lambda: self.toggle_hotkey_signal.emit())
        except Exception as e:
            print(f"Error setting hotkey: {e}")

    def toggle_visibility(self):
        if self.isVisible():
            if self.isMinimized():
                self.showNormal()
                self.activateWindow()
            else:
                self.hide()
        else:
            self.showNormal()
            self.activateWindow()

    def setup_system_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(self.app_icon)
        tray_menu = QMenu()
        show_action = QAction("Show DropShelf", self)
        show_action.triggered.connect(self.showNormal)
        tray_menu.addAction(show_action)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close_app)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_click)
        try:
            self.tray_icon.setToolTip("DropShelf")
        except Exception:
            pass
        self.tray_icon.show()

    def on_tray_click(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_visibility()

    def minimize_to_tray(self):
        self.hide()
        self.tray_icon.showMessage(
            "DropShelf",
            f"App minimized to tray. Press {self.hotkey} to open.",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )

    def close_app(self):
        self.save_favorites()
        keyboard.unhook_all()
        try:
            self.tray_icon.hide()
        except Exception:
            pass
        QApplication.quit()

    def clear_shelf(self):
        to_remove = []
        for i in range(self.scroll_layout.count()):
            widget = self.scroll_layout.itemAt(i).widget()
            if isinstance(widget, DraggableItem):
                if widget.is_favorite:
                    widget.hidden_from_main = True
                else:
                    to_remove.append(widget)
        for widget in to_remove:
            self.remove_item(widget)
        self.save_favorites()
        self.refresh_visibility()

    def setup_clipboard_monitor(self):
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.on_clipboard_change)

    def on_clipboard_change(self):
        mime = self.clipboard.mimeData()
        if mime.hasUrls():
            urls = mime.urls()
            for url in urls:
                if url.isLocalFile():
                    path = url.toLocalFile()
                    self.add_item('file', path)
            return
        if mime.hasText():
            text = mime.text().strip()
            if text:
                is_url = text.startswith(('http://', 'https://', 'www.'))
                self.add_item('url' if is_url else 'text', text)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-dropshelf-item"):
            event.accept()
        elif event.mimeData().hasUrls() or event.mimeData().hasText():
            event.accept()
            self.central_widget.setStyleSheet("""
                QWidget#CentralWidget {
                    background-color: rgba(45, 45, 50, 250);
                    border: 2px dashed #4CAF50;
                    border-radius: 15px;
                }
            """)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.reset_style()

    def dropEvent(self, event):
        self.reset_style()
        mime = event.mimeData()
        if mime.hasFormat("application/x-dropshelf-item"):
            try:
                item_id = int(mime.data("application/x-dropshelf-item").data().decode('utf-8'))
                source_widget = None
                for i in range(self.scroll_layout.count()):
                    w = self.scroll_layout.itemAt(i).widget()
                    if w and id(w) == item_id:
                        source_widget = w
                        break
                if source_widget:
                    drop_pos = event.position().toPoint()
                    drop_pos = self.scroll_content.mapFrom(self, drop_pos)
                    insert_index = -1
                    for i in range(self.scroll_layout.count()):
                        w = self.scroll_layout.itemAt(i).widget()
                        if w and w != self.empty_label:
                            if drop_pos.y() < w.y() + w.height() / 2:
                                insert_index = i
                                break
                    if insert_index == -1:
                        insert_index = self.scroll_layout.count() - 1 
                    self.scroll_layout.removeWidget(source_widget)
                    self.scroll_layout.insertWidget(insert_index, source_widget)
                    event.accept()
                    self.save_favorites()
                    return
            except Exception as e:
                print("Reorder error:", e)
        if mime.hasUrls():
            for url in mime.urls():
                file_path = url.toLocalFile()
                if file_path:
                    self.add_item('file', file_path)
        elif mime.hasText():
            text = mime.text()
            if text.startswith(('http://', 'https://')):
                self.add_item('url', text)
            else:
                self.add_item('text', text)
        event.acceptProposedAction()

    def reset_style(self):
        self.central_widget.setStyleSheet("""
            QWidget#CentralWidget {
                background-color: rgba(30, 30, 30, 245);
                border: 1px solid #444;
                border-radius: 15px;
            }
        """)

    def add_item(self, dtype, content, is_favorite=False, hidden_from_main=False):
        if not is_favorite and self.current_tab == "fav":
            self.current_tab = "all"
            self.update_tab_styles()
        existing_widget = None
        for i in range(self.scroll_layout.count()):
            w = self.scroll_layout.itemAt(i).widget()
            if isinstance(w, DraggableItem):
                if w.content == content and w.data_type == dtype:
                    existing_widget = w
                    break
        if existing_widget:
            if not is_favorite and existing_widget.is_favorite:
                is_favorite = True
            hidden_from_main = False
            self.scroll_layout.removeWidget(existing_widget)
            existing_widget.deleteLater()
        item = DraggableItem(dtype, content, parent=self, is_favorite=is_favorite, hidden_from_main=hidden_from_main)
        self.scroll_layout.insertWidget(0, item) 
        self.refresh_visibility()
        if not (is_favorite and hidden_from_main): 
            self.save_favorites()

    def remove_item(self, item_widget):
        self.scroll_layout.removeWidget(item_widget)
        item_widget.deleteLater()
        self.refresh_visibility()
        self.save_favorites()

    def save_favorites(self):
        favorites = []
        for i in range(self.scroll_layout.count()):
            w = self.scroll_layout.itemAt(i).widget()
            if isinstance(w, DraggableItem) and w.is_favorite:
                favorites.append({
                    "type": w.data_type,
                    "content": w.content,
                    "hidden_from_main": w.hidden_from_main
                })
        try:
            with open(FAVORITES_FILE, 'w') as f:
                json.dump(favorites, f)
        except Exception as e:
            print(f"Error saving favorites: {e}")

    def load_favorites(self):
        if not os.path.exists(FAVORITES_FILE):
            return
        try:
            with open(FAVORITES_FILE, 'r') as f:
                favorites = json.load(f)
                for fav in reversed(favorites):
                    is_hidden = fav.get('hidden_from_main', False)
                    self.add_item(fav['type'], fav['content'], is_favorite=True, hidden_from_main=is_hidden)
        except Exception as e:
            print(f"Error loading favorites: {e}")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            delta = QPoint(event.globalPosition().toPoint() - self.old_pos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

if __name__ == '__main__':
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    socket = QLocalSocket()
    socket.connectToServer(APP_ID)
    if socket.waitForConnected(500):
        socket.write("SHOW".encode('utf-8'))
        socket.waitForBytesWritten(1000)
        sys.exit(0)
    font = app.font()
    font.setPointSize(10)
    app.setFont(font)
    window = DropShelfWindow()
    window.show()
    sys.exit(app.exec())