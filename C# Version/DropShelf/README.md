# DropShelf

A lightweight, always-on-top clipboard shelf for Windows. Drop files, copy text, or paste URLs — DropShelf keeps them pinned on the side of your screen until you need them.

---

## Features

### Core Shelf
- **Clipboard monitoring** — anything you copy (text, files, URLs) is automatically added to the shelf
- **Drag & drop** — drag files, folders, or URLs directly onto the shelf
- **Virtual shell objects** — drag and drop special Windows items like **This PC**, **Recycle Bin**, **Control Panel**, and network locations; they display with their real shell icon and name
- **Three item types** — Files, URLs, and plain Text, each with a distinct icon and info line
- **Info sub-label** — shows file size (e.g. `1.4 MB`), folder item count (e.g. `Folder • 12 items`), domain for URLs (e.g. `github.com`), or character count for text
- **Image thumbnails** — image files (`.png`, `.jpg`, `.gif`, `.bmp`, `.webp`, `.tiff`, `.ico`) show a live pixel thumbnail instead of a generic icon
- **Real shell icons** — all other files, folders, drives, and virtual shell objects show their actual Windows shell icon
- **Deduplication** — re-copying the same item moves it to the top instead of creating a duplicate

### Organization
- **Favorites** — star any item to pin it permanently; favorites survive a "Clear All"
- **Tags** — add comma-separated tags to any item for easy searching
- **Search** — live search across content and tags
- **Filter** — filter the shelf to show only Files, URLs, or Text
- **Sort** — sort by Newest, Oldest, Name (A–Z), Type, Size, or Most Used, in either direction
- **Tabs** — switch between All Items, Favorites, and History

### Clipboard History
- Keeps a rolling history of everything you've copied (up to 200 entries by default)
- History tab shows type, content preview, and timestamp
- One-click to push any history entry back onto the main shelf
- History size is configurable (set to 0 to disable)

### Bulk Operations
- **Select mode** — toggle a checkbox on every item for bulk actions
- **Select All**, **Delete Selected**, **Favorite Selected**
- **Undo** — single-level undo for deleted items

### Item Actions
Each item row has four quick-action buttons:

| Button | Action |
|--------|--------|
| ▶ / ↗ / ⎘ | Open file, open URL in browser, or copy text to clipboard |
| ☆ / ★ | Toggle favorite |
| ✎ | Edit content (text items) and manage tags |
| × | Remove from shelf (favorites stay in the Favorites tab) |

Right-clicking any item opens a context menu with additional options: Copy to Clipboard, Open File / Reveal in Explorer, Open in Browser, Generate QR Code, Edit/Tags, Add to Favorites, and Delete.

### Persistence & Export
- Shelf contents and favorites are saved automatically to disk
- **Export** — save all items to a `.json` file
- **Import** — load items from a previously exported `.json` file
- Data is written atomically (temp file → rename) to prevent corruption
- A `.bak` backup of `favorites.json` is kept at all times

### System Integration
- **Global hotkey** — press `Ctrl+Shift+X` (configurable) to show/hide the shelf from anywhere
- **System tray** — minimize to tray; click or double-click the tray icon to restore
- **Run on startup** — optional Windows registry integration to launch at login
- **Frameless, always-on-top** — sits unobtrusively on the right edge of your screen

---

## Requirements

- Windows 10 or later
- [.NET 8.0 Runtime](https://dotnet.microsoft.com/download/dotnet/8.0) (or build with the SDK)

---

## Building

```bash
git clone https://github.com/yourname/dropshelf.git
cd dropshelf
dotnet build -c Release
```

Or open `DropShelf.sln` in Visual Studio 2022 and press **Build → Build Solution**.

### Publishing a standalone executable

```bash
dotnet publish -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true
```

The resulting `DropShelf.exe` is in `bin\Release\net8.0-windows\win-x64\publish\` and requires no separate .NET installation.

---

## Usage

### First launch
The window appears on the right side of your screen. Start copying things — they appear automatically.

### Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Shift+X` | Toggle show/hide (global, works when minimized to tray) |
| `Ctrl+Z` | Undo last deletion |
| `Ctrl+F` | Focus the search bar |
| `Ctrl+H` | Switch to History tab |
| `Escape` | Exit select mode |

The global hotkey can be changed in **Settings → Hotkey**.

### Adding items
- **Copy anything** with `Ctrl+C` — it lands on the shelf automatically
- **Drag files or folders** from Explorer onto the shelf
- **Drag a URL** from your browser's address bar or a link on a page
- **Drag virtual shell objects** like This PC or Recycle Bin directly from the desktop or Explorer's navigation pane

### Favorites
Click ☆ on any item to star it. Starred items:
- Show with a gold border
- Are kept when you click "Clear All"
- Appear in the **Favorites** tab
- Are hidden (not deleted) when you click × from the All Items tab — they remain safe in Favorites

### Removing items
- Click **×** on an item in **All Items** — if it's a favorite it's hidden from the main view but stays in Favorites; otherwise it's deleted with undo support
- Click **×** on an item in **Favorites** — removes the favorite flag; the item moves back to All Items

---

## Settings

Open Settings with the **⚙** button in the header.

| Setting | Description |
|---------|-------------|
| Toggle hotkey | Key combo to show/hide the shelf globally |
| Monitor clipboard | Turn automatic clipboard capture on/off |
| Close to system tray | Whether the × button hides or quits |
| Run on startup | Register with Windows registry to launch at login |
| History size | Max clipboard history entries (0 = disabled) |

---

## Data files

All data is stored in `%APPDATA%\DropShelf\`:

| File | Contents |
|------|----------|
| `favorites.json` | All shelf items (both favorited and regular) |
| `settings.json` | App preferences |
| `history.json` | Clipboard history log |
| `dropshelf.log` | Application log for debugging |

---

## License

MIT
