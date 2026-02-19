using System;
using System.Collections.Generic;

namespace DropShelf
{
    public enum ItemType { Text, Url, File }

    public class ShelfItem
    {
        public ItemType Type { get; set; }
        public string Content { get; set; } = "";
        /// <summary>
        /// Human-readable display name captured at add-time for virtual shell
        /// objects (This PC, Recycle Bin, …).  Empty for normal paths.
        /// </summary>
        public string ShellDisplayName { get; set; } = "";
        public bool IsFavorite { get; set; }
        public bool HiddenFromMain { get; set; }
        public List<string> Tags { get; set; } = new();
        public DateTime DateAdded { get; set; } = DateTime.Now;
        public int UseCount { get; set; }

        public string TypeString => Type switch
        {
            ItemType.Url => "url",
            ItemType.File => "file",
            _ => "text"
        };

        public static ItemType ParseType(string s) => s?.ToLower() switch
        {
            "url" => ItemType.Url,
            "file" => ItemType.File,
            _ => ItemType.Text
        };
    }

    public class AppSettings
    {
        public bool MonitorClipboard { get; set; } = true;
        public string Hotkey { get; set; } = "Ctrl+Shift+X";
        public bool CloseToTray { get; set; } = true;
        public int MaxHistory { get; set; } = 200;
        public double WindowX { get; set; } = -1;
        public double WindowY { get; set; } = -1;
        public double WindowHeight { get; set; } = 600;
    }

    public class HistoryEntry
    {
        public string Type { get; set; } = "text";
        public string Content { get; set; } = "";
        public DateTime Time { get; set; } = DateTime.Now;
    }
}
