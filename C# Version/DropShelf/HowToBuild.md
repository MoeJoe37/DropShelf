# DropShelf for Windows — C# / WPF Port

A faithful recreation of the Python/PyQt6 DropShelf app, ported to C# WPF (.NET 8).

## Features (matching the original)
- **Drag & Drop** — Drop files, text, or URLs onto the shelf window
- **Clipboard monitoring** — Auto-captures clipboard text, URLs, and files
- **Favorites** — Star items; favorited items persist across sessions
- **Tabs** — All Items / Favorites / History
- **Search** — Search by content or tags
- **Filter** — Filter by type: All / Files / URLs / Text
- **Sort** — Sort by newest, oldest, name, type, size, or most used (with asc/desc toggle)
- **Edit & Tags** — Edit text items and assign comma-separated tags
- **Bulk selection** — Select, delete, or favorite multiple items at once
- **Undo delete** — Ctrl+Z restores last deleted batch
- **Clear All** — Removes all non-favorite items
- **Export / Import** — JSON export and import
- **Statistics** — Overview and most-used items
- **QR Code** — Right-click any URL item → Generate QR Code
- **Global hotkey** — Ctrl+Shift+X toggles window (configurable in Settings)
- **System Tray** — Close to tray with double-click to restore
- **Run on startup** — Optional Windows registry startup entry
- **Single instance** — Second launch shows the existing window
- **Dark theme** — Matches the original Python app's color scheme
- **Persistent storage** — All data saved to `%APPDATA%\DropShelf\`

## Keyboard Shortcuts
| Shortcut | Action |
|---|---|
| `Ctrl+Shift+X` | Toggle window (global) |
| `Ctrl+F` | Focus search box |
| `Ctrl+Z` | Undo last delete |
| `Ctrl+A` | Select all visible items |
| `Delete` | Delete selected items |
| `Escape` | Exit selection mode |
| `Ctrl+H` | Switch to History tab |

## Requirements
- **Windows 10 or 11**
- **.NET 8.0 SDK** — [Download here](https://dotnet.microsoft.com/download/dotnet/8)

## Build & Run

```batch
cd DropShelf
dotnet restore
dotnet run
```

Or build a standalone executable:
```batch
dotnet publish -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -o publish\
```

The published `.exe` in the `publish\` folder can be run on any Windows 10/11 machine without .NET installed.

## Adding a Custom Icon
Place an `icon.ico` file in the project folder and it will be used as the application icon.

## Data Files
All data is saved in `%APPDATA%\DropShelf\`:
- `settings.json` — App settings
- `favorites.json` — All shelf items
- `history.json` — Clipboard history
- `dropshelf.log` — Application log

## Notes
- The app requires admin rights for global hotkey on some systems
- QR Code generation uses the `QRCoder` NuGet package (auto-restored)
- Window is always 360px wide; height is resizable
