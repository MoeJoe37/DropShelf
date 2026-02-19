using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace DropShelf
{
    public static class DataManager
    {
        private static readonly string DataDir = GetDataDir();
        public static readonly string SettingsFile = Path.Combine(DataDir, "settings.json");
        public static readonly string FavoritesFile = Path.Combine(DataDir, "favorites.json");
        public static readonly string HistoryFile = Path.Combine(DataDir, "history.json");
        public static readonly string LogFile = Path.Combine(DataDir, "dropshelf.log");

        private static readonly JsonSerializerOptions JsonOptions = new()
        {
            WriteIndented = true,
            PropertyNameCaseInsensitive = true
        };

        private static string GetDataDir()
        {
            try
            {
                string appData = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
                string dir = Path.Combine(appData, "DropShelf");
                Directory.CreateDirectory(dir);
                return dir;
            }
            catch
            {
                string fallback = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".dropshelf");
                Directory.CreateDirectory(fallback);
                return fallback;
            }
        }

        private static void AtomicWrite(string path, string content)
        {
            string tmp = path + ".tmp";
            File.WriteAllText(tmp, content);
            if (File.Exists(path))
            {
                string bak = path + ".bak";
                if (File.Exists(bak)) File.Delete(bak);
                File.Move(path, bak);
            }
            File.Move(tmp, path);
        }

        public static void SaveSettings(AppSettings settings)
        {
            try
            {
                AtomicWrite(SettingsFile, JsonSerializer.Serialize(settings, JsonOptions));
            }
            catch (Exception ex) { Log($"SaveSettings error: {ex.Message}"); }
        }

        public static AppSettings LoadSettings()
        {
            try
            {
                if (!File.Exists(SettingsFile)) return new AppSettings();
                var json = File.ReadAllText(SettingsFile);
                return JsonSerializer.Deserialize<AppSettings>(json, JsonOptions) ?? new AppSettings();
            }
            catch (Exception ex)
            {
                Log($"LoadSettings error: {ex.Message}");
                return new AppSettings();
            }
        }

        public static void SaveItems(IEnumerable<ShelfItem> items)
        {
            try
            {
                var data = new List<object>();
                foreach (var item in items)
                    data.Add(new
                    {
                        type = item.TypeString,
                        content = item.Content,
                        shell_display_name = item.ShellDisplayName,
                        is_favorite = item.IsFavorite,
                        hidden_from_main = item.HiddenFromMain,
                        tags = item.Tags,
                        date_added = item.DateAdded.ToString("o"),
                        use_count = item.UseCount
                    });
                AtomicWrite(FavoritesFile, JsonSerializer.Serialize(data, JsonOptions));
            }
            catch (Exception ex) { Log($"SaveItems error: {ex.Message}"); }
        }

        public static List<ShelfItem> LoadItems()
        {
            var result = new List<ShelfItem>();
            if (!File.Exists(FavoritesFile)) return result;
            try
            {
                var json = File.ReadAllText(FavoritesFile);
                using var doc = JsonDocument.Parse(json);
                foreach (var el in doc.RootElement.EnumerateArray())
                {
                    var item = new ShelfItem
                    {
                        Type = ShelfItem.ParseType(el.TryGetProperty("type", out var t) ? t.GetString() ?? "" : ""),
                        Content = el.TryGetProperty("content", out var c) ? c.GetString() ?? "" : "",
                        ShellDisplayName = el.TryGetProperty("shell_display_name", out var sdn) ? sdn.GetString() ?? "" : "",
                        IsFavorite = el.TryGetProperty("is_favorite", out var fav) && fav.GetBoolean(),
                        HiddenFromMain = el.TryGetProperty("hidden_from_main", out var h) && h.GetBoolean(),
                        UseCount = el.TryGetProperty("use_count", out var u) ? u.GetInt32() : 0
                    };
                    if (el.TryGetProperty("date_added", out var da) && DateTime.TryParse(da.GetString(), out var dt))
                        item.DateAdded = dt;
                    if (el.TryGetProperty("tags", out var tags) && tags.ValueKind == JsonValueKind.Array)
                        foreach (var tag in tags.EnumerateArray())
                            if (tag.GetString() is string s && !string.IsNullOrEmpty(s))
                                item.Tags.Add(s);
                    result.Add(item);
                }
            }
            catch (Exception ex) { Log($"LoadItems error: {ex.Message}"); }
            return result;
        }

        public static void SaveHistory(IEnumerable<HistoryEntry> entries)
        {
            try
            {
                var data = new List<object>();
                foreach (var e in entries)
                    data.Add(new { type = e.Type, content = e.Content, time = e.Time.ToString("o") });
                AtomicWrite(HistoryFile, JsonSerializer.Serialize(data, JsonOptions));
            }
            catch (Exception ex) { Log($"SaveHistory error: {ex.Message}"); }
        }

        public static List<HistoryEntry> LoadHistory()
        {
            var result = new List<HistoryEntry>();
            if (!File.Exists(HistoryFile)) return result;
            try
            {
                var json = File.ReadAllText(HistoryFile);
                using var doc = JsonDocument.Parse(json);
                foreach (var el in doc.RootElement.EnumerateArray())
                {
                    var entry = new HistoryEntry
                    {
                        Type = el.TryGetProperty("type", out var t) ? t.GetString() ?? "text" : "text",
                        Content = el.TryGetProperty("content", out var c) ? c.GetString() ?? "" : ""
                    };
                    if (el.TryGetProperty("time", out var ti) && DateTime.TryParse(ti.GetString(), out var dt))
                        entry.Time = dt;
                    result.Add(entry);
                }
            }
            catch (Exception ex) { Log($"LoadHistory error: {ex.Message}"); }
            return result;
        }

        public static void Log(string message)
        {
            try
            {
                File.AppendAllText(LogFile, $"{DateTime.Now:yyyy-MM-dd HH:mm:ss} {message}\n");
            }
            catch { }
        }
    }
}
