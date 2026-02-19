using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using Microsoft.Win32;

namespace DropShelf
{
    public partial class MainWindow : Window
    {
        // ── State ──────────────────────────────────────────────────────────────
        public AppSettings Settings { get; private set; } = new();

        private string _currentTab    = "all";
        private string _currentFilter = "all";
        private string _currentSort   = "newest";
        private bool   _sortAscending = false;
        private string _searchQuery   = "";
        private bool   _selectionMode = false;

        // Guard: prevents event handlers from running before the window is fully loaded
        private bool _isLoaded = false;

        private readonly List<List<ShelfItem>> _undoStack = new();
        private readonly List<HistoryEntry>    _history   = new();
        private string? _lastClipText;

        // ── Infrastructure ────────────────────────────────────────────────────
        private HotkeyManager?                    _hotkey;
        private ClipboardMonitor?                 _clipMonitor;
        private System.Windows.Forms.NotifyIcon?  _tray;

        // ── Window drag state ─────────────────────────────────────────────────
        private Point _windowDragStart;
        private bool  _windowDragging;

        // ═════════════════════════════════════════════════════════════════════
        public MainWindow()
        {
            InitializeComponent();
            Settings = DataManager.LoadSettings();

            Loaded += OnWindowLoaded;

            MainBorder.MouseLeftButtonDown += MainBorder_MouseLeftButtonDown;
            MouseLeftButtonUp += (_, _) => { _windowDragging = false; ReleaseMouseCapture(); };
            MouseMove         += MainBorder_MouseMove;

            KeyDown   += Window_KeyDown;
            DragEnter += MainWindow_DragEnter;
            DragLeave += MainWindow_DragLeave;
            Drop      += MainWindow_Drop;
        }

        // ── Window loaded ─────────────────────────────────────────────────────
        private void OnWindowLoaded(object sender, RoutedEventArgs e)
        {
            // InitializeComponent() already ran in the constructor, so all XAML-triggered
            // SelectionChanged / TextChanged events have already fired.  It is now safe
            // to unlock the guard flag so every subsystem below works normally.
            _isLoaded = true;

            // Restore or default window position
            var workArea = SystemParameters.WorkArea;
            if (Settings.WindowX >= 0 && Settings.WindowY >= 0 &&
                Settings.WindowX < workArea.Width && Settings.WindowY < workArea.Height)
            {
                Left   = Settings.WindowX;
                Top    = Settings.WindowY;
                Height = Math.Max(300, Settings.WindowHeight);
            }
            else
            {
                Left = workArea.Width - Width - 20;
                Top  = (workArea.Height - Height) / 2;
            }

            // Each subsystem is isolated — one failure won't block the rest
            TryInit("HotkeyManager",        InitHotkey);
            TryInit("ClipboardMonitor",     InitClipboard);
            TryInit("SystemTray",           SetupTray);
            TryInit("LoadData",             LoadData);
            TryInit("HistoryTabVisibility", UpdateHistoryTabVisibility);
        }

        private static void TryInit(string name, Action action)
        {
            try { action(); }
            catch (Exception ex) { DataManager.Log($"[Init:{name}] {ex}"); }
        }

        // ── Hotkey ────────────────────────────────────────────────────────────
        private void InitHotkey()
        {
            _hotkey = new HotkeyManager(this);
            _hotkey.Initialize();
            _hotkey.Register(Settings.Hotkey);
            _hotkey.HotkeyPressed += () => Dispatcher.Invoke(ToggleWindow);
        }

        public void ReRegisterHotkey()
        {
            try { _hotkey?.Register(Settings.Hotkey); }
            catch (Exception ex) { DataManager.Log($"ReRegisterHotkey: {ex.Message}"); }
        }

        // ── Clipboard ─────────────────────────────────────────────────────────
        private void InitClipboard()
        {
            _clipMonitor = new ClipboardMonitor();
            _clipMonitor.Initialize(this);
            _clipMonitor.ClipboardChanged += () => Dispatcher.Invoke(OnClipboardChanged);
        }

        // ── System tray ────────────────────────────────────────────────────────
        private void SetupTray()
        {
            _tray = new System.Windows.Forms.NotifyIcon
            {
                Text    = "DropShelf",
                Visible = true
            };

            try
            {
                string? exePath = System.Diagnostics.Process.GetCurrentProcess().MainModule?.FileName;
                _tray.Icon = exePath != null
                    ? System.Drawing.Icon.ExtractAssociatedIcon(exePath)
                    : System.Drawing.SystemIcons.Application;
            }
            catch { _tray.Icon = System.Drawing.SystemIcons.Application; }

            // Single-click OR double-click both restore the window.
            // DoubleClick fires after two Click events, so we guard with IsVisible
            // to avoid toggling twice – ShowWindow is idempotent so it's safe.
            _tray.Click       += (_, _) => Dispatcher.Invoke(ShowWindow);
            _tray.DoubleClick += (_, _) => Dispatcher.Invoke(ShowWindow);

            var menu = new System.Windows.Forms.ContextMenuStrip();

            var showItem = new System.Windows.Forms.ToolStripMenuItem("Show");
            showItem.Click += (_, _) => Dispatcher.Invoke(ShowWindow);
            menu.Items.Add(showItem);

            var settingsItem = new System.Windows.Forms.ToolStripMenuItem("Settings");
            settingsItem.Click += (_, _) => Dispatcher.Invoke(OpenSettings);
            menu.Items.Add(settingsItem);

            menu.Items.Add(new System.Windows.Forms.ToolStripSeparator());

            var quitItem = new System.Windows.Forms.ToolStripMenuItem("Quit");
            quitItem.Click += (_, _) => Dispatcher.Invoke(ForceQuit);
            menu.Items.Add(quitItem);

            _tray.ContextMenuStrip = menu;
        }

        // ── Window visibility ──────────────────────────────────────────────────
        public void ShowWindow()
        {
            Show();
            WindowState = WindowState.Normal;
            Activate();
            Focus();
        }

        private void MinimizeToTray()
        {
            Hide();
            _tray?.ShowBalloonTip(2000, "DropShelf",
                $"Running in tray — press {Settings.Hotkey} to open.",
                System.Windows.Forms.ToolTipIcon.Info);
        }

        private void ToggleWindow()
        {
            if (IsVisible) MinimizeToTray();
            else           ShowWindow();
        }

        private void ForceQuit()
        {
            TrySaveAll();
            try { _tray!.Visible = false; _tray.Dispose(); } catch { }
            try { _hotkey?.Dispose(); }                       catch { }
            Application.Current.Shutdown();
        }

        // ── Data loading ──────────────────────────────────────────────────────
        private void LoadData()
        {
            var saved = DataManager.LoadHistory();
            int keep  = Settings.MaxHistory > 0 ? Settings.MaxHistory : 0;
            _history.AddRange(saved.TakeLast(keep));

            var items = DataManager.LoadItems();
            items.Reverse();   // reversed → newest will end up at top via InsertAtTop
            foreach (var item in items)
                AddItemCard(item, insertAtTop: false);

            RefreshVisibility();
        }

        // ── Item management ───────────────────────────────────────────────────
        /// <summary>Safely returns all ItemCard widgets. Returns empty list if panel not ready.</summary>
        private List<ItemCard> GetAllCards()
        {
            if (ItemsPanel == null) return new List<ItemCard>();
            return ItemsPanel.Children.OfType<ItemCard>().ToList();
        }

        public void AddItem(
            ItemType      type,
            string        content,
            bool          isFavorite        = false,
            bool          hiddenFromMain    = false,
            List<string>? tags              = null,
            DateTime?     dateAdded         = null,
            int           useCount          = 0,
            string        shellDisplayName  = "")
        {
            if (string.IsNullOrWhiteSpace(content) || ItemsPanel == null) return;

            // Deduplicate
            var existing = GetAllCards()
                .FirstOrDefault(c => c.Item.Content == content && c.Item.Type == type);
            if (existing != null)
            {
                if (!isFavorite && existing.Item.IsFavorite) isFavorite = true;
                hiddenFromMain = false;
                // Preserve stored display name if we don't have a newer one
                if (string.IsNullOrEmpty(shellDisplayName))
                    shellDisplayName = existing.Item.ShellDisplayName;
                ItemsPanel.Children.Remove(existing);
            }

            var item = new ShelfItem
            {
                Type             = type,
                Content          = content,
                ShellDisplayName = shellDisplayName,
                IsFavorite       = isFavorite,
                HiddenFromMain   = hiddenFromMain,
                Tags             = tags ?? new List<string>(),
                DateAdded        = dateAdded ?? DateTime.Now,
                UseCount         = useCount
            };
            AddItemCard(item, insertAtTop: true);
            RefreshVisibility();

            if (!(isFavorite && hiddenFromMain))
                SaveItems();
        }

        private void AddItemCard(ShelfItem item, bool insertAtTop)
        {
            if (ItemsPanel == null) return;
            var card = new ItemCard(item, this);
            if (_selectionMode) card.SetSelectionMode(true);
            if (insertAtTop) ItemsPanel.Children.Insert(0, card);
            else             ItemsPanel.Children.Add(card);
        }

        public void ToggleFavorite(ItemCard card)
        {
            card.Item.IsFavorite = !card.Item.IsFavorite;
            if (!card.Item.IsFavorite) card.Item.HiddenFromMain = false;
            card.UpdateStyle();
            card.UpdateStarStyle();
            RefreshVisibility();
            SaveItems();
        }

        public void RequestRemoval(ItemCard card)
        {
            if (ItemsPanel == null) return;

            if (_currentTab == "fav")
            {
                card.Item.IsFavorite     = false;
                card.Item.HiddenFromMain = false;
                card.UpdateStyle();
                card.UpdateStarStyle();
                SaveItems();
                RefreshVisibility();
                return;
            }

            if (card.Item.IsFavorite)
            {
                card.Item.HiddenFromMain = true;
                SaveItems();
                RefreshVisibility();
                return;
            }

            // Non-favorite — delete with undo
            _undoStack.Add(new List<ShelfItem> { CloneItem(card.Item) });
            UndoBtn.IsEnabled = true;
            ItemsPanel.Children.Remove(card);
            RefreshVisibility();
            SaveItems();
        }

        private static ShelfItem CloneItem(ShelfItem src) => new()
        {
            Type           = src.Type,
            Content        = src.Content,
            IsFavorite     = src.IsFavorite,
            HiddenFromMain = src.HiddenFromMain,
            Tags           = new List<string>(src.Tags),
            DateAdded      = src.DateAdded,
            UseCount       = src.UseCount
        };

        // ── Visibility / filtering ─────────────────────────────────────────────
        private void RefreshVisibility()
        {
            if (!_isLoaded || ItemsPanel == null) return;

            bool hasVisible = false;
            foreach (var card in GetAllCards())
            {
                bool show = ShouldShow(card);
                card.Visibility = show ? Visibility.Visible : Visibility.Collapsed;
                if (show) hasVisible = true;
            }
            EmptyLabel.Visibility = hasVisible ? Visibility.Collapsed : Visibility.Visible;
        }

        private bool ShouldShow(ItemCard card)
        {
            if (_currentTab == "fav" && !card.Item.IsFavorite)    return false;
            if (_currentTab == "all" && card.Item.HiddenFromMain) return false;

            if (_currentFilter == "file" && card.Item.Type != ItemType.File) return false;
            if (_currentFilter == "url"  && card.Item.Type != ItemType.Url)  return false;
            if (_currentFilter == "text" && card.Item.Type != ItemType.Text) return false;

            if (!string.IsNullOrEmpty(_searchQuery))
            {
                bool contentMatch = card.Item.Content
                    .Contains(_searchQuery, StringComparison.OrdinalIgnoreCase);
                bool tagMatch = card.Item.Tags
                    .Any(t => t.Contains(_searchQuery, StringComparison.OrdinalIgnoreCase));
                if (!contentMatch && !tagMatch) return false;
            }
            return true;
        }

        // ── Sorting ────────────────────────────────────────────────────────────
        private void SortItems()
        {
            if (!_isLoaded || ItemsPanel == null) return;

            var cards = GetAllCards();
            foreach (var c in cards) ItemsPanel.Children.Remove(c);

            IEnumerable<ItemCard> ordered = _currentSort switch
            {
                "oldest" => cards.OrderBy(c => c.Item.DateAdded),
                "name"   => cards.OrderBy(c => c.Item.Content, StringComparer.OrdinalIgnoreCase),
                "type"   => cards.OrderBy(c => c.Item.Type.ToString()),
                "size"   => cards.OrderByDescending(c => GetFileSize(c.Item)),
                "used"   => cards.OrderByDescending(c => c.Item.UseCount),
                _        => cards.OrderByDescending(c => c.Item.DateAdded)
            };

            var sorted = ordered.ToList();
            if (_sortAscending) sorted.Reverse();
            foreach (var card in sorted) ItemsPanel.Children.Add(card);
            RefreshVisibility();
        }

        private static long GetFileSize(ShelfItem item)
        {
            if (item.Type != ItemType.File) return 0;
            if (File.Exists(item.Content)) return new FileInfo(item.Content).Length;
            // Treat directories as 0 for sort purposes (folder size is expensive)
            if (Directory.Exists(item.Content)) return 0;
            return 0;
        }

        // ── Tabs ───────────────────────────────────────────────────────────────
        private void SwitchTab(string tab)
        {
            _currentTab = tab;
            UpdateTabStyles();

            bool showHistory = tab == "history";
            MainScrollViewer.Visibility   = showHistory ? Visibility.Collapsed : Visibility.Visible;
            HistoryScrollViewer.Visibility = showHistory ? Visibility.Visible : Visibility.Collapsed;

            if (tab == "history") RebuildHistoryDisplay();
            else                  RefreshVisibility();
        }

        private void UpdateTabStyles()
        {
            if (!_isLoaded) return;
            // Use FindResource (not Resources[]) so it searches App resources + merged dictionaries,
            // not just the window's own local ResourceDictionary. Using Resources[] returns null for
            // keys defined outside the window, which resets the button to the default unstyled look.
            TabAll.Style     = (Style)FindResource(_currentTab == "all"     ? "TabButtonActive" : "TabButtonInactive");
            TabFav.Style     = (Style)FindResource(_currentTab == "fav"     ? "TabButtonActive" : "TabButtonInactive");
            TabHistory.Style = (Style)FindResource(_currentTab == "history" ? "TabButtonActive" : "TabButtonInactive");
        }

        public void UpdateHistoryTabVisibility()
        {
            if (!_isLoaded) return;
            TabHistory.Visibility = Settings.MaxHistory > 0 ? Visibility.Visible : Visibility.Collapsed;
            if (_currentTab == "history" && Settings.MaxHistory == 0)
                SwitchTab("all");
        }

        // ── History ────────────────────────────────────────────────────────────
        private void AddToHistory(string type, string content)
        {
            if (Settings.MaxHistory == 0) return;
            _history.Add(new HistoryEntry { Type = type, Content = content, Time = DateTime.Now });
            while (_history.Count > Settings.MaxHistory) _history.RemoveAt(0);
            DataManager.SaveHistory(_history);
            if (_currentTab == "history") RebuildHistoryDisplay();
        }

        private void RebuildHistoryDisplay()
        {
            if (HistoryPanel == null || HistoryEmptyLabel == null) return;
            HistoryPanel.Children.Clear();

            if (_history.Count == 0 || Settings.MaxHistory == 0)
            {
                HistoryEmptyLabel.Text = Settings.MaxHistory > 0
                    ? "No clipboard history yet." : "History is disabled.";
                HistoryPanel.Children.Add(HistoryEmptyLabel);
                return;
            }

            foreach (var entry in Enumerable.Reverse(_history))
            {
                var row = new Border
                {
                    Background      = new SolidColorBrush(Color.FromRgb(43, 43, 43)),
                    BorderBrush     = new SolidColorBrush(Color.FromRgb(68, 68, 68)),
                    BorderThickness = new Thickness(1),
                    CornerRadius    = new CornerRadius(6),
                    Height          = 40,
                    Margin          = new Thickness(0, 0, 0, 4)
                };

                var grid = new Grid { Margin = new Thickness(8, 4, 8, 4) };
                grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(50) });
                grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
                grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
                grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(26) });

                void Col(int col, UIElement el) { Grid.SetColumn(el, col); grid.Children.Add(el); }

                Col(0, new TextBlock
                {
                    Text = entry.Type.ToUpper(),
                    Foreground = new SolidColorBrush(Color.FromRgb(76, 175, 80)),
                    FontSize = 10, FontWeight = FontWeights.Bold,
                    VerticalAlignment = VerticalAlignment.Center
                });

                string raw = entry.Type == "file" ? Path.GetFileName(entry.Content) : entry.Content;
                Col(1, new TextBlock
                {
                    Text = raw.Length > 60 ? raw[..60] + "…" : raw,
                    Foreground = new SolidColorBrush(Color.FromRgb(224, 224, 224)),
                    FontSize = 11, TextTrimming = TextTrimming.CharacterEllipsis,
                    VerticalAlignment = VerticalAlignment.Center
                });

                Col(2, new TextBlock
                {
                    Text = entry.Time.ToString("MM-dd HH:mm"),
                    Foreground = new SolidColorBrush(Color.FromRgb(136, 136, 136)),
                    FontSize = 10, Margin = new Thickness(0, 0, 6, 0),
                    VerticalAlignment = VerticalAlignment.Center
                });

                var addBtn = new Button
                {
                    Content         = "+",
                    Width = 22, Height = 22,
                    Background      = new SolidColorBrush(Color.FromRgb(76, 175, 80)),
                    Foreground      = Brushes.White,
                    BorderThickness = new Thickness(0),
                    FontSize        = 14,
                    Cursor          = Cursors.Hand,
                    ToolTip         = "Add to shelf"
                };
                var cap = entry;
                addBtn.Click += (_, _) => AddItem(ShelfItem.ParseType(cap.Type), cap.Content);
                Col(3, addBtn);

                row.Child = grid;
                HistoryPanel.Children.Add(row);
            }
        }

        // ── Clipboard monitor ──────────────────────────────────────────────────
        private void OnClipboardChanged()
        {
            if (!Settings.MonitorClipboard) return;
            try
            {
                if (Clipboard.ContainsFileDropList())
                {
                    var files = Clipboard.GetFileDropList();
                    foreach (string? fp in files)
                    {
                        if (fp == null) continue;
                        // Trim whitespace AND null bytes that Windows sometimes appends to
                        // clipboard file paths — these cause File.Exists() to return false
                        // even though the file is present on disk.
                        string clean = fp.Trim().TrimEnd('\0', '\r', '\n').Trim();
                        if (!string.IsNullOrEmpty(clean))
                        {
                            AddToHistory("file", clean);
                            AddItem(ItemType.File, clean);
                        }
                    }
                    return;
                }

                // Virtual shell objects (This PC, Recycle Bin, …) don't produce a
                // FileDropList — they only appear in the "Shell IDList Array" format.
                var clipData = Clipboard.GetDataObject();
                if (clipData != null && clipData.GetDataPresent("Shell IDList Array"))
                {
                    var shellItems = ShellHelper.TryGetShellItems(clipData);
                    foreach (var (parseName, displayName) in shellItems)
                    {
                        string clean = parseName.Trim().TrimEnd('\0').Trim();
                        if (!string.IsNullOrEmpty(clean))
                        {
                            AddToHistory("file", clean);
                            AddItem(ItemType.File, clean, shellDisplayName: displayName);
                        }
                    }
                    if (shellItems.Count > 0) return;
                }
                if (Clipboard.ContainsText())
                {
                    string text = Clipboard.GetText().Trim();
                    if (string.IsNullOrEmpty(text) || text == _lastClipText) return;
                    _lastClipText = text;
                    bool isUrl = text.StartsWith("http://", StringComparison.OrdinalIgnoreCase)
                              || text.StartsWith("https://", StringComparison.OrdinalIgnoreCase)
                              || text.StartsWith("www.",     StringComparison.OrdinalIgnoreCase);
                    var type = isUrl ? ItemType.Url : ItemType.Text;
                    AddToHistory(isUrl ? "url" : "text", text);
                    AddItem(type, text);
                }
            }
            catch (Exception ex) { DataManager.Log($"ClipboardChanged: {ex.Message}"); }
        }

        // ── Bulk selection ─────────────────────────────────────────────────────
        private void ToggleSelectionMode()
        {
            _selectionMode         = !_selectionMode;
            SelectModeBtn.Content  = _selectionMode ? "Exit" : "Select";
            var vis = _selectionMode ? Visibility.Visible : Visibility.Collapsed;
            SelectAllBtn.Visibility     = vis;
            DeleteSelectedBtn.Visibility = vis;
            FavSelectedBtn.Visibility   = vis;
            foreach (var card in GetAllCards()) card.SetSelectionMode(_selectionMode);
        }

        private void ExitSelectionMode() { if (_selectionMode) ToggleSelectionMode(); }

        private void SelectAllItems()
        {
            if (!_selectionMode) return;
            foreach (var card in GetAllCards())
                if (card.Visibility == Visibility.Visible)
                    card.ForceSelect(true);
        }

        private void DeleteSelectedItems()
        {
            if (!_selectionMode || ItemsPanel == null) return;
            var selected = GetAllCards().Where(c => c.IsSelected).ToList();
            if (selected.Count == 0) return;

            if (MessageBox.Show($"Delete {selected.Count} item(s)?", "Confirm Delete",
                MessageBoxButton.YesNo, MessageBoxImage.Question) != MessageBoxResult.Yes) return;

            _undoStack.Add(selected.Select(c => CloneItem(c.Item)).ToList());
            UndoBtn.IsEnabled = true;
            foreach (var card in selected) ItemsPanel.Children.Remove(card);
            ExitSelectionMode();
            RefreshVisibility();
            SaveItems();
        }

        private void UndoDelete()
        {
            if (_undoStack.Count == 0) return;
            var batch = _undoStack[^1];
            _undoStack.RemoveAt(_undoStack.Count - 1);
            foreach (var item in batch)
                AddItem(item.Type, item.Content, item.IsFavorite, item.HiddenFromMain,
                        item.Tags, item.DateAdded, item.UseCount);
            UndoBtn.IsEnabled = _undoStack.Count > 0;
        }

        // ── Persistence ────────────────────────────────────────────────────────
        public void SaveItems()
        {
            if (ItemsPanel == null) return;
            DataManager.SaveItems(GetAllCards().Select(c => c.Item));
        }

        public void SaveSettings()
        {
            Settings.WindowX      = Left;
            Settings.WindowY      = Top;
            Settings.WindowHeight = Height;
            DataManager.SaveSettings(Settings);
        }

        private void TrySaveAll()
        {
            try { SaveItems(); }    catch (Exception ex) { DataManager.Log($"SaveItems on exit: {ex.Message}"); }
            try { SaveSettings(); } catch (Exception ex) { DataManager.Log($"SaveSettings on exit: {ex.Message}"); }
        }

        // ── Export / Import ────────────────────────────────────────────────────
        public void ExportItems()
        {
            var dlg = new SaveFileDialog
            {
                Filter   = "JSON Files (*.json)|*.json",
                FileName = "dropshelf_export.json"
            };
            if (dlg.ShowDialog() != true) return;
            try
            {
                SaveItems();
                File.Copy(DataManager.FavoritesFile, dlg.FileName, overwrite: true);
                MessageBox.Show($"Exported {GetAllCards().Count} items.", "Success",
                    MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Export failed: {ex.Message}", "Error",
                    MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        public void ImportItems()
        {
            var dlg = new OpenFileDialog { Filter = "JSON Files (*.json)|*.json" };
            if (dlg.ShowDialog() != true) return;
            try
            {
                var raw = System.Text.Json.JsonSerializer.Deserialize<
                    List<System.Text.Json.JsonElement>>(File.ReadAllText(dlg.FileName));
                int count = 0;
                if (raw != null)
                    foreach (var el in raw)
                    {
                        try
                        {
                            string  type    = el.TryGetProperty("type",    out var t) ? t.GetString() ?? "text" : "text";
                            string  content = el.TryGetProperty("content", out var c) ? c.GetString() ?? ""     : "";
                            bool    isFav   = el.TryGetProperty("is_favorite",      out var f) && f.GetBoolean();
                            bool    hidden  = el.TryGetProperty("hidden_from_main", out var h) && h.GetBoolean();
                            int     uc      = el.TryGetProperty("use_count", out var u) ? u.GetInt32() : 0;
                            var     tags    = new List<string>();
                            if (el.TryGetProperty("tags", out var tg) &&
                                tg.ValueKind == System.Text.Json.JsonValueKind.Array)
                                foreach (var tag in tg.EnumerateArray())
                                    if (tag.GetString() is string s) tags.Add(s);
                            DateTime? da = null;
                            if (el.TryGetProperty("date_added", out var daEl) &&
                                DateTime.TryParse(daEl.GetString(), out var dt))
                                da = dt;
                            AddItem(ShelfItem.ParseType(type), content, isFav, hidden, tags, da, uc);
                            count++;
                        }
                        catch { }
                    }
                MessageBox.Show($"Imported {count} items.", "Success",
                    MessageBoxButton.OK, MessageBoxImage.Information);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Import failed: {ex.Message}", "Error",
                    MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        public void OpenStats()    => new StatsDialog(GetAllCards().Select(c => c.Item).ToList(), this).ShowDialog();
        public void OpenSettings() => new SettingsDialog(this).ShowDialog();

        // ── Drag & Drop ────────────────────────────────────────────────────────
        private void MainWindow_DragEnter(object sender, DragEventArgs e)
        {
            if (e.Data.GetDataPresent("DropShelfItem") ||
                e.Data.GetDataPresent(DataFormats.FileDrop) ||
                e.Data.GetDataPresent(DataFormats.UnicodeText) ||
                e.Data.GetDataPresent(DataFormats.Text) ||
                e.Data.GetDataPresent("Shell IDList Array"))  // virtual shell objects
            {
                e.Effects = DragDropEffects.Copy;
                MainBorder.BorderBrush     = new SolidColorBrush(Color.FromRgb(76, 175, 80));
                MainBorder.BorderThickness = new Thickness(2);
                e.Handled = true;
            }
        }

        private void MainWindow_DragLeave(object sender, DragEventArgs e)
        {
            MainBorder.BorderBrush     = new SolidColorBrush(Color.FromRgb(68, 68, 68));
            MainBorder.BorderThickness = new Thickness(1);
        }

        private void MainWindow_Drop(object sender, DragEventArgs e)
        {
            MainBorder.BorderBrush     = new SolidColorBrush(Color.FromRgb(68, 68, 68));
            MainBorder.BorderThickness = new Thickness(1);

            // Internal reorder
            if (e.Data.GetDataPresent("DropShelfItem") &&
                e.Data.GetData("DropShelfItem") is ItemCard dragged &&
                ItemsPanel != null)
            {
                var dropPos = e.GetPosition(ItemsPanel);
                int insertAt = 0;
                foreach (var card in GetAllCards())
                {
                    var pos = card.TranslatePoint(new Point(0, 0), ItemsPanel);
                    if (dropPos.Y > pos.Y + card.ActualHeight / 2)
                        insertAt = ItemsPanel.Children.IndexOf(card) + 1;
                }
                ItemsPanel.Children.Remove(dragged);
                ItemsPanel.Children.Insert(Math.Min(insertAt, ItemsPanel.Children.Count), dragged);
                SaveItems();
                return;
            }

            // External files (real paths via CF_HDROP)
            if (e.Data.GetDataPresent(DataFormats.FileDrop))
            {
                foreach (string f in (string[])e.Data.GetData(DataFormats.FileDrop))
                {
                    string clean = f.Trim().TrimEnd('\0', '\r', '\n').Trim();
                    if (!string.IsNullOrEmpty(clean))
                        AddItem(ItemType.File, clean);
                }
                return;
            }

            // Virtual shell objects (This PC, Recycle Bin, network shares, …)
            // Only appear in "Shell IDList Array" — never in FileDrop.
            if (e.Data.GetDataPresent("Shell IDList Array"))
            {
                var shellItems = ShellHelper.TryGetShellItems(e.Data);
                foreach (var (parseName, displayName) in shellItems)
                {
                    string clean = parseName.Trim().TrimEnd('\0').Trim();
                    if (!string.IsNullOrEmpty(clean))
                        AddItem(ItemType.File, clean, shellDisplayName: displayName);
                }
                if (shellItems.Count > 0) return;
            }

            // Text / URL
            string? text = e.Data.GetData(DataFormats.UnicodeText) as string
                        ?? e.Data.GetData(DataFormats.Text) as string;
            if (!string.IsNullOrWhiteSpace(text))
            {
                text = text.Trim();
                bool isUrl = text.StartsWith("http://", StringComparison.OrdinalIgnoreCase)
                          || text.StartsWith("https://", StringComparison.OrdinalIgnoreCase)
                          || text.StartsWith("www.",     StringComparison.OrdinalIgnoreCase);
                AddItem(isUrl ? ItemType.Url : ItemType.Text, text);
            }
        }

        // ── Window drag (frameless) ────────────────────────────────────────────
        private void MainBorder_MouseLeftButtonDown(object sender, MouseButtonEventArgs e)
        {
            if (e.OriginalSource is Button || e.OriginalSource is CheckBox) return;
            _windowDragStart = e.GetPosition(this);
            _windowDragging  = true;
            CaptureMouse();
        }

        private void MainBorder_MouseMove(object sender, MouseEventArgs e)
        {
            if (!_windowDragging || e.LeftButton != MouseButtonState.Pressed) return;
            var pos = e.GetPosition(this);
            Left += pos.X - _windowDragStart.X;
            Top  += pos.Y - _windowDragStart.Y;
        }

        // ── Keyboard shortcuts ─────────────────────────────────────────────────
        private void Window_KeyDown(object sender, KeyEventArgs e)
        {
            bool ctrl = (Keyboard.Modifiers & ModifierKeys.Control) != 0;
            switch (e.Key)
            {
                case Key.F      when ctrl: SearchBox.Focus();       e.Handled = true; break;
                case Key.Z      when ctrl: UndoDelete();             e.Handled = true; break;
                case Key.A      when ctrl: SelectAllItems();         e.Handled = true; break;
                case Key.Delete:           DeleteSelectedItems();    e.Handled = true; break;
                case Key.Escape:           ExitSelectionMode();      e.Handled = true; break;
                case Key.H when ctrl:
                    if (Settings.MaxHistory > 0) SwitchTab("history");
                    e.Handled = true; break;
            }
        }

        // ── XAML event handlers ────────────────────────────────────────────────
        private void SettingsBtn_Click(object s, RoutedEventArgs e)  => OpenSettings();
        private void MinimizeBtn_Click(object s, RoutedEventArgs e)  => MinimizeToTray();
        private void CloseBtn_Click(object s, RoutedEventArgs e)
        {
            if (Settings.CloseToTray) MinimizeToTray();
            else                      ForceQuit();
        }

        private void SearchBox_TextChanged(object s, TextChangedEventArgs e)
        {
            if (!_isLoaded) return;
            _searchQuery = SearchBox.Text.Trim();
            RefreshVisibility();
        }

        private void ClearSearch_Click(object s, RoutedEventArgs e) => SearchBox.Clear();

        private void FilterCombo_SelectionChanged(object s, SelectionChangedEventArgs e)
        {
            // Guard: fires during XAML initialization before ItemsPanel is ready
            if (!_isLoaded) return;
            string[] filters = { "all", "file", "url", "text" };
            _currentFilter = filters[FilterCombo.SelectedIndex];
            RefreshVisibility();
        }

        private void SortCombo_SelectionChanged(object s, SelectionChangedEventArgs e)
        {
            // Guard: fires during XAML initialization before ItemsPanel is ready
            if (!_isLoaded) return;
            string[] sorts = { "newest", "oldest", "name", "type", "size", "used" };
            _currentSort = sorts[SortCombo.SelectedIndex];
            SortItems();
        }

        private void SortDirBtn_Click(object s, RoutedEventArgs e)
        {
            if (!_isLoaded) return;
            _sortAscending     = !_sortAscending;
            SortDirBtn.Content = _sortAscending ? "↑" : "↓";
            SortItems();
        }

        private void TabAll_Click(object s, RoutedEventArgs e)     => SwitchTab("all");
        private void TabFav_Click(object s, RoutedEventArgs e)     => SwitchTab("fav");
        private void TabHistory_Click(object s, RoutedEventArgs e) => SwitchTab("history");

        private void SelectModeBtn_Click(object s, RoutedEventArgs e)     => ToggleSelectionMode();
        private void SelectAllBtn_Click(object s, RoutedEventArgs e)      => SelectAllItems();
        private void DeleteSelectedBtn_Click(object s, RoutedEventArgs e) => DeleteSelectedItems();

        private void FavSelectedBtn_Click(object s, RoutedEventArgs e)
        {
            foreach (var card in GetAllCards().Where(c => c.IsSelected && !c.Item.IsFavorite))
                ToggleFavorite(card);
        }

        private void ClearBtn_Click(object s, RoutedEventArgs e)
        {
            if (ItemsPanel == null) return;
            if (MessageBox.Show("Remove all non-favorite items?", "Clear Shelf",
                MessageBoxButton.YesNo, MessageBoxImage.Question) != MessageBoxResult.Yes) return;

            var toRemove = new List<ItemCard>();
            foreach (var card in GetAllCards())
            {
                if (card.Item.IsFavorite) card.Item.HiddenFromMain = true;
                else                      toRemove.Add(card);
            }
            foreach (var card in toRemove) ItemsPanel.Children.Remove(card);
            SaveItems();
            RefreshVisibility();
        }

        private void UndoBtn_Click(object s, RoutedEventArgs e) => UndoDelete();

        // ── Lifecycle ──────────────────────────────────────────────────────────
        protected override void OnClosed(EventArgs e)
        {
            TrySaveAll();
            base.OnClosed(e);
        }

        protected override void OnStateChanged(EventArgs e)
        {
            if (WindowState == WindowState.Minimized) MinimizeToTray();
            base.OnStateChanged(e);
        }
    }
}
