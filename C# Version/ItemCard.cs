using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;

namespace DropShelf
{
    public class ItemCard : Border
    {
        public ShelfItem Item { get; }
        public bool IsSelected { get; private set; }

        private bool       _selectionMode;
        private MainWindow _shelf;

        // UI elements
        private CheckBox   _checkBox   = null!;
        private TextBlock  _mainLabel  = null!;
        private TextBlock  _infoLabel  = null!;
        private Button     _iconBtn    = null!;
        private Button     _starBtn    = null!;
        private Button     _editBtn    = null!;
        private Button     _closeBtn   = null!;
        private StackPanel _tagsPanel  = null!;

        // ─────────────────────────────────────────────────────────────────────
        public ItemCard(ShelfItem item, MainWindow shelf)
        {
            Item   = item;
            _shelf = shelf;

            CornerRadius    = new CornerRadius(8);
            BorderThickness = new Thickness(1);
            Margin          = new Thickness(0, 0, 0, 6);
            Cursor          = Cursors.Arrow;
            AllowDrop       = true;
            Tag             = this;

            BuildUI();
            UpdateStyle();
            SetupDragDrop();
        }

        // ── UI construction ───────────────────────────────────────────────────
        private void BuildUI()
        {
            // 7 columns: checkbox | preview | text | open-btn | star | edit | close
            var grid = new Grid { Margin = new Thickness(8, 6, 8, 6) };
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });           // 0 checkbox
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });           // 1 preview
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) }); // 2 text
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });           // 3 open btn
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });           // 4 star
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });           // 5 edit
            grid.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });           // 6 close

            // ── Col 0: Checkbox ──────────────────────────────────────────────
            _checkBox = new CheckBox
            {
                VerticalAlignment = VerticalAlignment.Center,
                Visibility        = Visibility.Collapsed,
                Style             = (Style)Application.Current.Resources["DarkCheckBox"],
                Margin            = new Thickness(0, 0, 6, 0)
            };
            _checkBox.Checked   += (_, _) => { IsSelected = true;  UpdateStyle(); };
            _checkBox.Unchecked += (_, _) => { IsSelected = false; UpdateStyle(); };
            Set(grid, _checkBox, 0);

            // ── Col 1: File / type preview icon ──────────────────────────────
            var preview = BuildPreview();
            Set(grid, preview, 1);

            // ── Col 2: Text block (name + info + tags) ───────────────────────
            var textStack = new StackPanel
            {
                VerticalAlignment = VerticalAlignment.Center,
                Margin            = new Thickness(6, 0, 4, 0)
            };

            _mainLabel = new TextBlock
            {
                FontSize      = 12,
                FontWeight    = FontWeights.Bold,
                Foreground    = new SolidColorBrush(Color.FromRgb(224, 224, 224)),
                TextTrimming  = TextTrimming.CharacterEllipsis,
                Background    = Brushes.Transparent
            };
            UpdateMainLabel();
            textStack.Children.Add(_mainLabel);

            _infoLabel = new TextBlock
            {
                FontSize   = 10,
                Foreground = new SolidColorBrush(Color.FromRgb(136, 136, 136)),
                Background = Brushes.Transparent
            };
            UpdateInfoLabel();
            textStack.Children.Add(_infoLabel);

            _tagsPanel = new StackPanel
            {
                Orientation = Orientation.Horizontal,
                Margin      = new Thickness(0, 2, 0, 0)
            };
            UpdateTagsDisplay();
            textStack.Children.Add(_tagsPanel);

            Set(grid, textStack, 2);

            // ── Col 3: Open / copy button ─────────────────────────────────────
            _iconBtn         = MakeSmallBtn(GetActionIcon(), 28, 28);
            _iconBtn.Click  += (_, _) => HandleOpen();
            _iconBtn.ToolTip = Item.Type switch
            {
                ItemType.File => "Open file",
                ItemType.Url  => "Open in browser",
                _             => "Copy to clipboard"
            };
            Set(grid, _iconBtn, 3);

            // ── Col 4: Star ───────────────────────────────────────────────────
            _starBtn        = MakeSmallBtn(Item.IsFavorite ? "★" : "☆", 26, 26);
            _starBtn.FontSize = 16;
            _starBtn.Click  += (_, _) => _shelf.ToggleFavorite(this);
            Set(grid, _starBtn, 4);
            UpdateStarStyle();

            // ── Col 5: Edit ───────────────────────────────────────────────────
            _editBtn        = MakeSmallBtn("✎", 26, 26);
            _editBtn.ToolTip = "Edit / Tags";
            _editBtn.Click  += (_, _) => EditItem();
            Set(grid, _editBtn, 5);

            // ── Col 6: Close ──────────────────────────────────────────────────
            _closeBtn            = MakeSmallBtn("×", 26, 26);
            _closeBtn.FontSize   = 16;
            _closeBtn.FontWeight = FontWeights.Bold;
            _closeBtn.Click     += (_, _) => _shelf.RequestRemoval(this);
            Set(grid, _closeBtn, 6);

            Child = grid;

            ContextMenu = BuildContextMenu();
            ToolTip     = Item.Content;
        }

        private static void Set(Grid g, UIElement el, int col)
        {
            Grid.SetColumn(el, col);
            g.Children.Add(el);
        }

        // ── Preview icon builder ──────────────────────────────────────────────
        /// <summary>
        /// For image files: loads a real thumbnail.
        /// For other files: extracts the real Windows shell icon (same as Explorer shows).
        /// For URLs: a coloured globe badge. For text: a document badge.
        /// </summary>
        private UIElement BuildPreview()
        {
            const int SIZE = 36;

            if (Item.Type == ItemType.File)
            {
                // For image files, show a real pixel thumbnail
                var imgBmp = TryGetImageThumbnail(Item.Content, SIZE);
                if (imgBmp != null)
                {
                    return new Image
                    {
                        Source              = imgBmp,
                        Width               = SIZE,
                        Height              = SIZE,
                        Stretch             = Stretch.UniformToFill,
                        VerticalAlignment   = VerticalAlignment.Center,
                        HorizontalAlignment = HorizontalAlignment.Center,
                        SnapsToDevicePixels = true,
                        Clip                = new System.Windows.Media.RectangleGeometry(
                                                  new Rect(0, 0, SIZE, SIZE), 4, 4)
                    };
                }

                // For all other files — real, folder, AND virtual shell objects —
                // use ShellHelper.GetIcon which goes through SHParseDisplayName→PIDL
                // →SHGFI_PIDL, the only API path that reliably returns the real icon
                // for virtual objects like "This PC" and "Recycle Bin".
                var shellBmp = ShellHelper.GetIcon(Item.Content);
                if (shellBmp != null)
                {
                    return new Image
                    {
                        Source              = shellBmp,
                        Width               = SIZE,
                        Height              = SIZE,
                        Stretch             = Stretch.Uniform,
                        VerticalAlignment   = VerticalAlignment.Center,
                        HorizontalAlignment = HorizontalAlignment.Center,
                        SnapsToDevicePixels = true
                    };
                }
            }

            // Fallback badge for all types (and files when icon extraction fails)
            return BuildBadge(SIZE);
        }

        private static readonly HashSet<string> _imageExtensions = new(StringComparer.OrdinalIgnoreCase)
        {
            ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".tif", ".ico"
        };

        /// <summary>Loads a scaled-down thumbnail BitmapSource for image files.</summary>
        private static BitmapSource? TryGetImageThumbnail(string path, int size)
        {
            try
            {
                string ext = Path.GetExtension(path);
                if (!_imageExtensions.Contains(ext)) return null;
                if (!File.Exists(path)) return null;

                var bmp = new BitmapImage();
                bmp.BeginInit();
                bmp.UriSource        = new Uri(path, UriKind.Absolute);
                bmp.DecodePixelWidth = size * 2; // decode at 2× for HiDPI sharpness
                bmp.CacheOption      = BitmapCacheOption.OnLoad;
                bmp.CreateOptions    = BitmapCreateOptions.IgnoreColorProfile;
                bmp.EndInit();
                bmp.Freeze();
                return bmp;
            }
            catch
            {
                return null;
            }
        }

        private Border BuildBadge(int size)
        {
            (string emoji, Color bg, Color fg) = Item.Type switch
            {
                ItemType.File => ("📄", Color.FromRgb(60, 70, 90),  Color.FromRgb(130, 170, 255)),
                ItemType.Url  => ("🔗", Color.FromRgb(40, 70, 60),  Color.FromRgb(100, 200, 140)),
                _             => ("📋", Color.FromRgb(60, 55, 30),  Color.FromRgb(230, 190, 80))
            };

            var border = new Border
            {
                Width               = size,
                Height              = size,
                CornerRadius        = new CornerRadius(6),
                Background          = new SolidColorBrush(bg),
                VerticalAlignment   = VerticalAlignment.Center,
                HorizontalAlignment = HorizontalAlignment.Center
            };
            border.Child = new TextBlock
            {
                Text                = emoji,
                FontSize            = size * 0.55,
                HorizontalAlignment = HorizontalAlignment.Center,
                VerticalAlignment   = VerticalAlignment.Center
            };
            return border;
        }

        // Shell icon extraction is handled by ShellHelper.GetIcon()

        // ── Small action icon (the "open/copy" button content) ────────────────
        private string GetActionIcon() => Item.Type switch
        {
            ItemType.File => "▶",
            ItemType.Url  => "↗",
            _             => "⎘"
        };

        // ── Label helpers ─────────────────────────────────────────────────────
        public void UpdateMainLabel()
        {
            if (Item.Type == ItemType.File)
            {
                string p = Item.Content;

                // ShellDisplayName is stored at capture time (from the live PIDL) and
                // is always correct.  Use it when available — this covers virtual shell
                // objects whose ::{GUID} path cannot be re-resolved at display time.
                if (!string.IsNullOrEmpty(Item.ShellDisplayName))
                {
                    _mainLabel.Text = Item.ShellDisplayName;
                    return;
                }

                // For virtual paths with no stored display name, resolve via shell.
                if (ShellHelper.IsVirtualPath(p))
                {
                    _mainLabel.Text = ShellHelper.GetDisplayName(p);
                    return;
                }

                // Real folders — use shell display name for localised label
                if (Directory.Exists(p))
                {
                    _mainLabel.Text = ShellHelper.GetDisplayName(p);
                    return;
                }

                // Regular files — just use the filename
                _mainLabel.Text = Path.GetFileName(p.TrimEnd(
                    System.IO.Path.DirectorySeparatorChar,
                    System.IO.Path.AltDirectorySeparatorChar));
            }
            else
            {
                _mainLabel.Text = Item.Content;
            }
        }

        private void UpdateInfoLabel()
        {
            if (Item.Type == ItemType.File)
            {
                string path = Item.Content;
                if (ShellHelper.IsVirtualPath(path))
                    _infoLabel.Text = "Shell object";
                else if (File.Exists(path))
                    _infoLabel.Text = FormatFileSize(new FileInfo(path).Length);
                else if (Directory.Exists(path))
                    _infoLabel.Text = ShellHelper.GetFolderInfo(path);
                else
                    _infoLabel.Text = "Not found";
                return;
            }
            _infoLabel.Text = Item.Type switch
            {
                ItemType.Url  => GetDomain(Item.Content),
                ItemType.Text => $"{Item.Content.Length} chars",
                _             => ""
            };
        }

        private static string FormatFileSize(long bytes)
        {
            if (bytes < 1024)             return $"{bytes} B";
            if (bytes < 1024 * 1024)      return $"{bytes / 1024.0:F1} KB";
            if (bytes < 1024L * 1024 * 1024) return $"{bytes / (1024.0 * 1024):F1} MB";
            return $"{bytes / (1024.0 * 1024 * 1024):F1} GB";
        }

        private static string GetDomain(string url)
        {
            try { return new Uri(url).Host; }
            catch { return url.Length > 30 ? url[..30] + "…" : url; }
        }

        public void UpdateTagsDisplay()
        {
            _tagsPanel.Children.Clear();
            foreach (var tag in Item.Tags)
            {
                var pill = new Border
                {
                    Background      = new SolidColorBrush(Color.FromArgb(40, 76, 175, 80)),
                    BorderBrush     = new SolidColorBrush(Color.FromRgb(76, 175, 80)),
                    BorderThickness = new Thickness(1),
                    CornerRadius    = new CornerRadius(3),
                    Margin          = new Thickness(0, 0, 4, 0),
                    Padding         = new Thickness(4, 1, 4, 1)
                };
                pill.Child = new TextBlock
                {
                    Text       = tag,
                    FontSize   = 9,
                    Foreground = new SolidColorBrush(Color.FromRgb(76, 175, 80))
                };
                _tagsPanel.Children.Add(pill);
            }
        }

        // ── Style helpers ─────────────────────────────────────────────────────
        public void UpdateStyle()
        {
            (Background, BorderBrush) = IsSelected
                ? (new SolidColorBrush(Color.FromRgb(26, 58, 82)),
                   (Brush)new SolidColorBrush(Color.FromRgb(33, 150, 243)))
                : Item.IsFavorite
                ? (new SolidColorBrush(Color.FromRgb(51, 43, 0)),
                   new SolidColorBrush(Color.FromRgb(255, 215, 0)))
                : (new SolidColorBrush(Color.FromRgb(43, 43, 43)),
                   new SolidColorBrush(Color.FromRgb(68, 68, 68)));
        }

        public void UpdateStarStyle()
        {
            _starBtn.Content    = Item.IsFavorite ? "★" : "☆";
            _starBtn.Foreground = Item.IsFavorite
                ? new SolidColorBrush(Color.FromRgb(255, 215, 0))
                : Brushes.White;
        }

        // ── Selection ─────────────────────────────────────────────────────────
        public void SetSelectionMode(bool enabled)
        {
            _selectionMode         = enabled;
            _checkBox.Visibility   = enabled ? Visibility.Visible : Visibility.Collapsed;
            if (!enabled) { _checkBox.IsChecked = false; IsSelected = false; }
        }

        public void ForceSelect(bool selected)
        {
            _checkBox.IsChecked = selected;
            IsSelected          = selected;
            UpdateStyle();
        }

        // ── Context menu ──────────────────────────────────────────────────────
        private ContextMenu BuildContextMenu()
        {
            var menu = new ContextMenu();

            var copy = new MenuItem { Header = "Copy to Clipboard" };
            copy.Click += (_, _) => Clipboard.SetText(Item.Content);
            menu.Items.Add(copy);

            if (Item.Type == ItemType.Url)
            {
                var open = new MenuItem { Header = "Open in Browser" };
                open.Click += (_, _) => HandleOpen();
                menu.Items.Add(open);

                var qr = new MenuItem { Header = "Generate QR Code" };
                qr.Click += (_, _) => ShowQrCode();
                menu.Items.Add(qr);
            }

            if (Item.Type == ItemType.File)
            {
                var open = new MenuItem { Header = "Open File" };
                open.Click += (_, _) => HandleOpen();
                menu.Items.Add(open);

                var reveal = new MenuItem { Header = "Reveal in Explorer" };
                reveal.Click += (_, _) => RevealInExplorer();
                menu.Items.Add(reveal);
            }

            menu.Items.Add(new Separator());

            var edit = new MenuItem { Header = "Edit / Tags" };
            edit.Click += (_, _) => EditItem();
            menu.Items.Add(edit);

            var fav = new MenuItem { Header = Item.IsFavorite ? "Remove Favorite" : "Add to Favorites" };
            fav.Click += (_, _) => _shelf.ToggleFavorite(this);
            menu.Items.Add(fav);

            menu.Items.Add(new Separator());

            var del = new MenuItem { Header = "Delete" };
            del.Foreground = new SolidColorBrush(Color.FromRgb(255, 100, 100));
            del.Click += (_, _) => _shelf.RequestRemoval(this);
            menu.Items.Add(del);

            return menu;
        }

        // ── Button factory ────────────────────────────────────────────────────
        private Button MakeSmallBtn(string content, int w, int h) => new Button
        {
            Content         = content,
            Width           = w,
            Height          = h,
            Background      = new SolidColorBrush(Color.FromRgb(58, 58, 58)),
            Foreground      = Brushes.White,
            BorderThickness = new Thickness(0),
            FontFamily      = new FontFamily("Segoe UI"),
            Margin          = new Thickness(2, 0, 0, 0),
            Cursor          = Cursors.Hand,
            Template        = CreateSmallBtnTemplate()
        };

        private static ControlTemplate CreateSmallBtnTemplate()
        {
            var t      = new ControlTemplate(typeof(Button));
            var border = new FrameworkElementFactory(typeof(Border));
            border.SetValue(Border.CornerRadiusProperty, new CornerRadius(6));
            border.SetValue(Border.BackgroundProperty,
                new TemplateBindingExtension(Button.BackgroundProperty));
            var cp = new FrameworkElementFactory(typeof(ContentPresenter));
            cp.SetValue(ContentPresenter.HorizontalAlignmentProperty, HorizontalAlignment.Center);
            cp.SetValue(ContentPresenter.VerticalAlignmentProperty,   VerticalAlignment.Center);
            border.AppendChild(cp);
            t.VisualTree = border;
            return t;
        }

        // ── Actions ───────────────────────────────────────────────────────────
        private void HandleOpen()
        {
            Item.UseCount++;
            ToolTip = $"{Item.Content}\nUses: {Item.UseCount}";
            _shelf.SaveItems();

            try
            {
                switch (Item.Type)
                {
                    case ItemType.Url:
                    case ItemType.File:
                        // Sanitize path: strip null bytes / stray whitespace from clipboard.
                        string filePath = Item.Content.Trim().TrimEnd('\0', '\r', '\n').Trim();

                        // Virtual shell paths (::{GUID}) have no filesystem entry —
                        // skip the exists-check and hand them straight to the shell.
                        bool isVirtual = ShellHelper.IsVirtualPath(filePath);
                        if (!isVirtual && Item.Type == ItemType.File
                                      && !File.Exists(filePath)
                                      && !Directory.Exists(filePath))
                        {
                            MessageBox.Show($"Item not found:\n{filePath}", "Not Found",
                                MessageBoxButton.OK, MessageBoxImage.Warning);
                            return;
                        }
                        System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo
                        {
                            FileName        = filePath,
                            UseShellExecute = true
                        });
                        break;

                    default:
                        Clipboard.SetText(Item.Content);
                        break;
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Could not open item:\n{ex.Message}", "Error",
                    MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void EditItem()
        {
            var dlg = new EditDialog(Item, Window.GetWindow(this) ?? _shelf);
            if (dlg.ShowDialog() == true)
            {
                if (Item.Type == ItemType.Text && dlg.NewContent != null)
                {
                    Item.Content = dlg.NewContent;
                    UpdateMainLabel();
                }
                Item.Tags = dlg.NewTags;
                UpdateTagsDisplay();
                ToolTip = Item.Content;
                _shelf.SaveItems();
            }
        }

        private void RevealInExplorer()
        {
            string filePath = Item.Content.Trim().TrimEnd('\0', '\r', '\n').Trim();

            // Virtual shell objects have no filesystem path to reveal.
            // Instead just open them (same as the open button).
            if (ShellHelper.IsVirtualPath(filePath))
            {
                System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo
                {
                    FileName        = filePath,
                    UseShellExecute = true
                });
                return;
            }

            if (Directory.Exists(filePath))
            {
                // For folders, open the folder itself (no /select trick needed)
                System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo
                {
                    FileName        = filePath,
                    UseShellExecute = true
                });
                return;
            }

            if (!File.Exists(filePath))
            {
                MessageBox.Show($"Item not found:\n{filePath}", "Not Found",
                    MessageBoxButton.OK, MessageBoxImage.Warning);
                return;
            }
            System.Diagnostics.Process.Start("explorer.exe", $"/select,\"{filePath}\"");
        }

        private void ShowQrCode()
        {
            try
            {
                using var gen = new QRCoder.QRCodeGenerator();
                var data  = gen.CreateQrCode(Item.Content, QRCoder.QRCodeGenerator.ECCLevel.Q);
                var code  = new QRCoder.PngByteQRCode(data);
                byte[] bytes = code.GetGraphic(6);

                var bmp = new BitmapImage();
                bmp.BeginInit();
                bmp.StreamSource = new MemoryStream(bytes);
                bmp.EndInit();

                var dlg = new Window
                {
                    Title           = "QR Code — " + GetDomain(Item.Content),
                    WindowStyle     = WindowStyle.SingleBorderWindow,
                    Background      = new SolidColorBrush(Color.FromRgb(43, 43, 43)),
                    SizeToContent   = SizeToContent.WidthAndHeight,
                    Owner           = _shelf,
                    ResizeMode      = ResizeMode.NoResize
                };
                var panel = new StackPanel { Margin = new Thickness(16) };
                panel.Children.Add(new Image { Source = bmp, Width = 200, Height = 200 });
                panel.Children.Add(new TextBlock
                {
                    Text         = Item.Content,
                    Foreground   = new SolidColorBrush(Color.FromRgb(224, 224, 224)),
                    FontSize     = 11,
                    TextWrapping = TextWrapping.Wrap,
                    MaxWidth     = 200,
                    Margin       = new Thickness(0, 8, 0, 8)
                });
                var closeBtn = new Button
                {
                    Content             = "Close",
                    Style               = (Style)Application.Current.Resources["DarkButton"],
                    Padding             = new Thickness(20, 8, 20, 8),
                    HorizontalAlignment = HorizontalAlignment.Center
                };
                closeBtn.Click += (_, _) => dlg.Close();
                panel.Children.Add(closeBtn);
                dlg.Content = panel;
                dlg.ShowDialog();
            }
            catch (Exception ex)
            {
                MessageBox.Show($"QR generation failed:\n{ex.Message}", "Error",
                    MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        // ── Drag & Drop ───────────────────────────────────────────────────────
        private Point _dragStart;
        private bool  _isDragging;

        private void SetupDragDrop()
        {
            MouseDown += OnMouseDown;
            MouseMove += OnMouseMove;
            MouseUp   += OnMouseUp;
        }

        private void OnMouseDown(object sender, MouseButtonEventArgs e)
        {
            if (e.LeftButton == MouseButtonState.Pressed && !_selectionMode)
            {
                _dragStart  = e.GetPosition(this);
                _isDragging = false;
                CaptureMouse();
            }
        }

        private void OnMouseMove(object sender, MouseEventArgs e)
        {
            if (!_isDragging && e.LeftButton == MouseButtonState.Pressed && IsMouseCaptured)
            {
                var pos = e.GetPosition(this);
                if (Math.Abs(pos.X - _dragStart.X) > 5 || Math.Abs(pos.Y - _dragStart.Y) > 5)
                {
                    _isDragging = true;
                    ReleaseMouseCapture();
                    DragDrop.DoDragDrop(this, new DataObject("DropShelfItem", this), DragDropEffects.Move);
                    _isDragging = false;
                }
            }
        }

        private void OnMouseUp(object sender, MouseButtonEventArgs e)
        {
            if (IsMouseCaptured) ReleaseMouseCapture();
            _isDragging = false;
        }
    }
}
