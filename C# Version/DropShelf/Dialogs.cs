using System;
using System.Collections.Generic;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace DropShelf
{
    // ─── Base Dialog Helper ───────────────────────────────────────────────────
    internal static class DialogHelper
    {
        public static Style MakeBtnStyle(Color bg, Color hover)
        {
            var style = new Style(typeof(Button));
            style.Setters.Add(new Setter(Control.BackgroundProperty, new SolidColorBrush(bg)));
            style.Setters.Add(new Setter(Control.ForegroundProperty, Brushes.White));
            style.Setters.Add(new Setter(Control.BorderThicknessProperty, new Thickness(0)));
            style.Setters.Add(new Setter(FrameworkElement.CursorProperty, System.Windows.Input.Cursors.Hand));
            style.Setters.Add(new Setter(Control.PaddingProperty, new Thickness(16, 8, 16, 8)));
            style.Setters.Add(new Setter(Control.FontWeightProperty, FontWeights.Bold));
            style.Setters.Add(new Setter(Control.FontSizeProperty, 13.0));
            var trigger = new Trigger { Property = UIElement.IsMouseOverProperty, Value = true };
            trigger.Setters.Add(new Setter(Control.BackgroundProperty, new SolidColorBrush(hover)));
            style.Triggers.Add(trigger);
            return style;
        }

        public static Border MakeGroupBox(string title)
        {
            var outer = new Border
            {
                BorderBrush = new SolidColorBrush(Color.FromRgb(68, 68, 68)),
                BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(8),
                Margin = new Thickness(0, 10, 0, 0),
                Padding = new Thickness(12, 16, 12, 12)
            };
            var stack = new StackPanel();
            var header = new TextBlock
            {
                Text = title,
                Foreground = Brushes.White,
                FontWeight = FontWeights.Bold,
                FontSize = 12,
                Margin = new Thickness(0, 0, 0, 8)
            };
            stack.Children.Add(header);
            outer.Child = stack;
            outer.Tag = stack;  // Tag points to inner StackPanel
            return outer;
        }

        public static StackPanel GetPanel(Border groupBox) => (StackPanel)groupBox.Tag;

        public static TextBox MakeDarkTextBox(string? placeholder = null, bool multiline = false)
        {
            var tb = new TextBox
            {
                Background = new SolidColorBrush(Color.FromRgb(58, 58, 58)),
                Foreground = new SolidColorBrush(Color.FromRgb(224, 224, 224)),
                BorderBrush = new SolidColorBrush(Color.FromRgb(68, 68, 68)),
                BorderThickness = new Thickness(1),
                Padding = new Thickness(8),
                FontFamily = new FontFamily("Segoe UI"),
                FontSize = 12,
                CaretBrush = Brushes.White,
                SelectionBrush = new SolidColorBrush(Color.FromRgb(76, 175, 80))
            };
            if (multiline)
            {
                tb.TextWrapping = TextWrapping.Wrap;
                tb.AcceptsReturn = true;
                tb.MinHeight = 100;
                tb.VerticalScrollBarVisibility = ScrollBarVisibility.Auto;
            }
            return tb;
        }
    }

    // ─── Edit Dialog ──────────────────────────────────────────────────────────
    public class EditDialog : Window
    {
        public string? NewContent { get; private set; }
        public List<string> NewTags { get; private set; } = new();

        private TextBox? _contentBox;
        private TextBox _tagsBox = null!;

        public EditDialog(ShelfItem item, Window owner)
        {
            Owner = owner;
            Title = "Edit Item";
            WindowStyle = WindowStyle.None;
            AllowsTransparency = true;
            Background = new SolidColorBrush(Color.FromArgb(245, 30, 30, 30));
            ShowInTaskbar = false;
            ResizeMode = ResizeMode.NoResize;
            SizeToContent = SizeToContent.Height;
            Width = 520;

            var outer = new Border
            {
                Background = new SolidColorBrush(Color.FromArgb(245, 30, 30, 30)),
                BorderBrush = new SolidColorBrush(Color.FromRgb(68, 68, 68)),
                BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(12)
            };

            var panel = new StackPanel { Margin = new Thickness(20) };
            outer.Child = panel;
            Content = outer;

            // Title
            panel.Children.Add(new TextBlock
            {
                Text = "Edit Item",
                Foreground = Brushes.White,
                FontSize = 18,
                FontWeight = FontWeights.Bold,
                Margin = new Thickness(0, 0, 0, 16)
            });

            // Content group
            var contentGroup = DialogHelper.MakeGroupBox("Content");
            var contentPanel = DialogHelper.GetPanel(contentGroup);

            if (item.Type == ItemType.Text)
            {
                _contentBox = DialogHelper.MakeDarkTextBox(multiline: true);
                _contentBox.Text = item.Content;
                contentPanel.Children.Add(_contentBox);
            }
            else
            {
                var typeRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 0, 0, 4) };
                typeRow.Children.Add(new TextBlock { Text = "Type:", Foreground = new SolidColorBrush(Color.FromRgb(224, 224, 224)), FontSize = 12, Margin = new Thickness(0, 0, 8, 0) });
                typeRow.Children.Add(new TextBlock { Text = item.Type.ToString().ToUpper(), Foreground = Brushes.White, FontWeight = FontWeights.Bold, FontSize = 13 });
                contentPanel.Children.Add(typeRow);

                string display = item.Content.Length > 120 ? item.Content[..117] + "..." : item.Content;
                contentPanel.Children.Add(new TextBlock
                {
                    Text = display,
                    Foreground = new SolidColorBrush(Color.FromRgb(224, 224, 224)),
                    FontSize = 12,
                    TextWrapping = TextWrapping.Wrap
                });
            }
            panel.Children.Add(contentGroup);

            // Tags group
            var tagsGroup = DialogHelper.MakeGroupBox("Tags");
            var tagsPanel = DialogHelper.GetPanel(tagsGroup);
            tagsPanel.Children.Add(new TextBlock
            {
                Text = "Separate multiple tags with commas (e.g. work, important, todo)",
                Foreground = new SolidColorBrush(Color.FromRgb(136, 136, 136)),
                FontSize = 11,
                FontStyle = FontStyles.Italic,
                TextWrapping = TextWrapping.Wrap,
                Margin = new Thickness(0, 0, 0, 6)
            });
            _tagsBox = DialogHelper.MakeDarkTextBox("work, important, project...");
            _tagsBox.Text = string.Join(", ", item.Tags);
            _tagsBox.Height = 32;
            tagsPanel.Children.Add(_tagsBox);
            panel.Children.Add(tagsGroup);

            // Buttons
            var btnRow = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right, Margin = new Thickness(0, 16, 0, 0) };
            var cancelBtn = new Button
            {
                Content = "Cancel",
                Width = 100,
                Height = 36,
                Style = DialogHelper.MakeBtnStyle(Color.FromRgb(58, 58, 58), Color.FromRgb(74, 74, 74)),
                Margin = new Thickness(0, 0, 8, 0)
            };
            cancelBtn.Click += (_, _) => Close();
            btnRow.Children.Add(cancelBtn);

            var saveBtn = new Button
            {
                Content = "Save",
                Width = 100,
                Height = 36,
                Style = DialogHelper.MakeBtnStyle(Color.FromRgb(76, 175, 80), Color.FromRgb(56, 142, 60))
            };
            saveBtn.Click += (_, _) =>
            {
                NewContent = _contentBox?.Text;
                NewTags = _tagsBox.Text.Split(',', StringSplitOptions.RemoveEmptyEntries)
                    .Select(t => t.Trim()).Where(t => !string.IsNullOrEmpty(t)).ToList();
                DialogResult = true;
                Close();
            };
            btnRow.Children.Add(saveBtn);
            panel.Children.Add(btnRow);

            // Handle window dragging
            panel.MouseDown += (s, e) =>
            {
                if (e.LeftButton == System.Windows.Input.MouseButtonState.Pressed)
                    DragMove();
            };
        }
    }

    // ─── Settings Dialog ──────────────────────────────────────────────────────
    public class SettingsDialog : Window
    {
        private TextBox _hotkeyBox = null!;
        private CheckBox _clipboardCb = null!;
        private CheckBox _trayCloseCb = null!;
        private CheckBox _startupCb = null!;
        private TextBox _historyBox = null!;
        private MainWindow _parent;

        public SettingsDialog(MainWindow parent)
        {
            _parent = parent;
            Owner = parent;
            Title = "DropShelf Settings";
            WindowStyle = WindowStyle.None;
            AllowsTransparency = true;
            Background = Brushes.Transparent;
            ShowInTaskbar = false;
            ResizeMode = ResizeMode.NoResize;
            SizeToContent = SizeToContent.Height;
            Width = 380;

            var outer = new Border
            {
                Background = new SolidColorBrush(Color.FromArgb(245, 30, 30, 30)),
                BorderBrush = new SolidColorBrush(Color.FromRgb(68, 68, 68)),
                BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(12)
            };

            var panel = new StackPanel { Margin = new Thickness(20) };
            outer.Child = panel;
            Content = outer;

            panel.Children.Add(new TextBlock
            {
                Text = "Settings",
                Foreground = Brushes.White,
                FontSize = 18,
                FontWeight = FontWeights.Bold,
                Margin = new Thickness(0, 0, 0, 8)
            });

            // Hotkey group
            var hotkeyGroup = DialogHelper.MakeGroupBox("Hotkey");
            var hotkeyPanel = DialogHelper.GetPanel(hotkeyGroup);
            hotkeyPanel.Children.Add(new TextBlock { Text = "Toggle hotkey:", Foreground = Brushes.White, FontSize = 12, Margin = new Thickness(0, 0, 0, 4) });
            _hotkeyBox = DialogHelper.MakeDarkTextBox();
            _hotkeyBox.Text = parent.Settings.Hotkey;
            _hotkeyBox.Height = 32;
            _hotkeyBox.PreviewKeyDown += HotkeyBox_PreviewKeyDown;
            _hotkeyBox.IsReadOnly = false;
            hotkeyPanel.Children.Add(_hotkeyBox);
            panel.Children.Add(hotkeyGroup);

            // General group
            var generalGroup = DialogHelper.MakeGroupBox("General");
            var generalPanel = DialogHelper.GetPanel(generalGroup);

            _clipboardCb = new CheckBox { Content = "Monitor clipboard", Style = (Style)Application.Current.Resources["DarkCheckBox"], Margin = new Thickness(0, 0, 0, 8) };
            _clipboardCb.IsChecked = parent.Settings.MonitorClipboard;
            generalPanel.Children.Add(_clipboardCb);

            _trayCloseCb = new CheckBox { Content = "Close to system tray", Style = (Style)Application.Current.Resources["DarkCheckBox"], Margin = new Thickness(0, 0, 0, 8) };
            _trayCloseCb.IsChecked = parent.Settings.CloseToTray;
            generalPanel.Children.Add(_trayCloseCb);

            _startupCb = new CheckBox { Content = "Run on startup", Style = (Style)Application.Current.Resources["DarkCheckBox"], Margin = new Thickness(0, 0, 0, 8) };
            _startupCb.IsChecked = RegistryHelper.IsStartupEnabled();
            generalPanel.Children.Add(_startupCb);

            var histRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 0, 0, 0) };
            histRow.Children.Add(new TextBlock { Text = "History size:", Foreground = Brushes.White, FontSize = 12, VerticalAlignment = VerticalAlignment.Center, Margin = new Thickness(0, 0, 8, 0) });
            _historyBox = new TextBox
            {
                Background = new SolidColorBrush(Color.FromRgb(58, 58, 58)),
                Foreground = Brushes.White,
                BorderBrush = new SolidColorBrush(Color.FromRgb(68, 68, 68)),
                BorderThickness = new Thickness(1),
                Padding = new Thickness(6, 4, 6, 4),
                FontFamily = new FontFamily("Segoe UI"),
                FontSize = 13,
                CaretBrush = Brushes.White,
                Width = 70,
                Height = 28,
                Text = parent.Settings.MaxHistory.ToString(),
                TextAlignment = TextAlignment.Center
            };
            histRow.Children.Add(_historyBox);
            generalPanel.Children.Add(histRow);
            panel.Children.Add(generalGroup);

            // Quick actions
            var actGroup = DialogHelper.MakeGroupBox("Quick Actions");
            var actPanel = DialogHelper.GetPanel(actGroup);
            var actRow = new StackPanel { Orientation = Orientation.Horizontal };
            foreach (var (label, action) in new[] {
                ("Stats",   (Action)parent.OpenStats),
                ("Export",  parent.ExportItems),
                ("Import",  parent.ImportItems)
            })
            {
                var btn = new Button
                {
                    Content = label,
                    Height = 32,
                    Padding = new Thickness(12, 0, 12, 0),
                    Style = DialogHelper.MakeBtnStyle(Color.FromRgb(58, 58, 58), Color.FromRgb(74, 74, 74)),
                    Margin = new Thickness(0, 0, 8, 0)
                };
                var a = action;
                btn.Click += (_, _) => { a(); };
                actRow.Children.Add(btn);
            }
            actPanel.Children.Add(actRow);
            panel.Children.Add(actGroup);

            // Save/Cancel
            var btnRow = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 16, 0, 0) };
            var cancelBtn = new Button
            {
                Content = "Cancel",
                Height = 36,
                Padding = new Thickness(16, 0, 16, 0),
                Style = DialogHelper.MakeBtnStyle(Color.FromRgb(58, 58, 58), Color.FromRgb(74, 74, 74)),
                Margin = new Thickness(0, 0, 8, 0)
            };
            cancelBtn.Click += (_, _) => Close();
            btnRow.Children.Add(cancelBtn);

            var saveBtn = new Button
            {
                Content = "Save",
                Height = 36,
                Padding = new Thickness(16, 0, 16, 0),
                Style = DialogHelper.MakeBtnStyle(Color.FromRgb(76, 175, 80), Color.FromRgb(56, 142, 60))
            };
            saveBtn.Click += (_, _) => SaveAndClose();
            btnRow.Children.Add(saveBtn);
            panel.Children.Add(btnRow);

            panel.MouseDown += (_, e) => { if (e.LeftButton == System.Windows.Input.MouseButtonState.Pressed) DragMove(); };
        }

        private void HotkeyBox_PreviewKeyDown(object sender, System.Windows.Input.KeyEventArgs e)
        {
            e.Handled = true;
            var key = e.Key == System.Windows.Input.Key.System ? e.SystemKey : e.Key;
            if (key == System.Windows.Input.Key.LeftCtrl || key == System.Windows.Input.Key.RightCtrl ||
                key == System.Windows.Input.Key.LeftShift || key == System.Windows.Input.Key.RightShift ||
                key == System.Windows.Input.Key.LeftAlt || key == System.Windows.Input.Key.RightAlt ||
                key == System.Windows.Input.Key.LWin || key == System.Windows.Input.Key.RWin)
                return;

            var parts = new List<string>();
            if ((System.Windows.Input.Keyboard.Modifiers & System.Windows.Input.ModifierKeys.Control) != 0)
                parts.Add("Ctrl");
            if ((System.Windows.Input.Keyboard.Modifiers & System.Windows.Input.ModifierKeys.Alt) != 0)
                parts.Add("Alt");
            if ((System.Windows.Input.Keyboard.Modifiers & System.Windows.Input.ModifierKeys.Shift) != 0)
                parts.Add("Shift");

            string keyName = key.ToString();
            if (!string.IsNullOrEmpty(keyName))
                parts.Add(keyName);

            if (parts.Count >= 2)
                _hotkeyBox.Text = string.Join("+", parts);
        }

        private void SaveAndClose()
        {
            string oldHotkey = _parent.Settings.Hotkey;
            _parent.Settings.MonitorClipboard = _clipboardCb.IsChecked == true;
            _parent.Settings.CloseToTray = _trayCloseCb.IsChecked == true;
            if (int.TryParse(_historyBox.Text, out int hist))
                _parent.Settings.MaxHistory = Math.Max(0, Math.Min(1000, hist));
            _parent.Settings.Hotkey = _hotkeyBox.Text;

            RegistryHelper.SetStartup(_startupCb.IsChecked == true);

            if (_parent.Settings.Hotkey != oldHotkey)
                _parent.ReRegisterHotkey();

            _parent.SaveSettings();
            _parent.UpdateHistoryTabVisibility();
            Close();
        }
    }

    // ─── Stats Dialog ─────────────────────────────────────────────────────────
    public class StatsDialog : Window
    {
        public StatsDialog(List<ShelfItem> items, Window owner)
        {
            Owner = owner;
            Title = "DropShelf Statistics";
            WindowStyle = WindowStyle.None;
            AllowsTransparency = true;
            Background = Brushes.Transparent;
            ShowInTaskbar = false;
            ResizeMode = ResizeMode.NoResize;
            Width = 520;
            SizeToContent = SizeToContent.Height;

            var outer = new Border
            {
                Background = new SolidColorBrush(Color.FromArgb(245, 30, 30, 30)),
                BorderBrush = new SolidColorBrush(Color.FromRgb(68, 68, 68)),
                BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(12)
            };

            var panel = new StackPanel { Margin = new Thickness(20) };
            outer.Child = panel;
            Content = outer;

            panel.Children.Add(new TextBlock
            {
                Text = "Usage Statistics",
                Foreground = Brushes.White,
                FontSize = 18,
                FontWeight = FontWeights.Bold,
                Margin = new Thickness(0, 0, 0, 8)
            });

            // Overview
            int total = items.Count;
            int totalUses = items.Sum(x => x.UseCount);
            int favCount = items.Count(x => x.IsFavorite);
            var typeCounts = items.GroupBy(x => x.Type).ToDictionary(g => g.Key, g => g.Count());

            var overviewGroup = DialogHelper.MakeGroupBox("Overview");
            var overviewPanel = DialogHelper.GetPanel(overviewGroup);

            AddStatRow(overviewPanel, "Total Items:", total.ToString());
            AddStatRow(overviewPanel, "Total Uses:", totalUses.ToString());
            AddStatRow(overviewPanel, "Favorites:", favCount.ToString());

            string typeBreakdown = string.Join("  •  ", typeCounts.Select(kv => $"{kv.Key}: {kv.Value}"));
            overviewPanel.Children.Add(new TextBlock
            {
                Text = typeBreakdown,
                Foreground = new SolidColorBrush(Color.FromRgb(224, 224, 224)),
                FontSize = 11,
                Margin = new Thickness(0, 4, 0, 0)
            });
            panel.Children.Add(overviewGroup);

            // Most used
            var mostUsedGroup = DialogHelper.MakeGroupBox("Most Used Items (Top 15)");
            var mostUsedPanel = DialogHelper.GetPanel(mostUsedGroup);

            var sortedItems = items.OrderByDescending(x => x.UseCount).Take(15).Where(x => x.UseCount > 0).ToList();
            if (sortedItems.Count == 0)
            {
                mostUsedPanel.Children.Add(new TextBlock
                {
                    Text = "No items have been used yet",
                    Foreground = new SolidColorBrush(Color.FromRgb(136, 136, 136)),
                    FontSize = 12,
                    Margin = new Thickness(0, 4, 0, 0)
                });
            }
            else
            {
                var listBox = new Border
                {
                    Background = new SolidColorBrush(Color.FromRgb(43, 43, 43)),
                    BorderBrush = new SolidColorBrush(Color.FromRgb(68, 68, 68)),
                    BorderThickness = new Thickness(1),
                    CornerRadius = new CornerRadius(6),
                    Padding = new Thickness(8),
                    MinHeight = 150,
                    MaxHeight = 200
                };
                var scrollv = new ScrollViewer { VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
                var itemsStack = new StackPanel();
                foreach (var item in sortedItems)
                {
                    string content = item.Content.Length > 45 ? item.Content[..42] + "..." : item.Content;
                    var row = new TextBlock
                    {
                        Text = $"[{item.UseCount}×]  {item.Type.ToString().ToUpper()}  •  {content}",
                        Foreground = new SolidColorBrush(Color.FromRgb(224, 224, 224)),
                        FontSize = 12,
                        Padding = new Thickness(0, 4, 0, 4)
                    };
                    itemsStack.Children.Add(row);
                }
                scrollv.Content = itemsStack;
                listBox.Child = scrollv;
                mostUsedPanel.Children.Add(listBox);
            }
            panel.Children.Add(mostUsedGroup);

            // Close button
            var closeBtn = new Button
            {
                Content = "Close",
                Height = 40,
                Padding = new Thickness(24, 0, 24, 0),
                Style = DialogHelper.MakeBtnStyle(Color.FromRgb(58, 58, 58), Color.FromRgb(74, 74, 74)),
                HorizontalAlignment = HorizontalAlignment.Center,
                Margin = new Thickness(0, 16, 0, 0)
            };
            closeBtn.Click += (_, _) => Close();
            panel.Children.Add(closeBtn);

            panel.MouseDown += (_, e) => { if (e.LeftButton == System.Windows.Input.MouseButtonState.Pressed) DragMove(); };
        }

        private static void AddStatRow(StackPanel panel, string label, string value)
        {
            var row = new Grid { Margin = new Thickness(0, 0, 0, 4) };
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            row.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });

            var lbl = new TextBlock { Text = label, Foreground = new SolidColorBrush(Color.FromRgb(224, 224, 224)), FontSize = 12 };
            Grid.SetColumn(lbl, 0);
            var val = new TextBlock { Text = value, Foreground = new SolidColorBrush(Color.FromRgb(76, 175, 80)), FontWeight = FontWeights.Bold, FontSize = 13 };
            Grid.SetColumn(val, 2);

            row.Children.Add(lbl);
            row.Children.Add(val);
            panel.Children.Add(row);
        }
    }
}
