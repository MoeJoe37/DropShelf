using System;
using System.Collections.Generic;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows;
using System.Windows.Media.Imaging;

namespace DropShelf
{
    internal static class ShellHelper
    {
        // ─── PInvoke ──────────────────────────────────────────────────────────

        [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
        private static extern int SHParseDisplayName(
            [MarshalAs(UnmanagedType.LPWStr)] string pszName,
            IntPtr pbc, out IntPtr ppidl, uint sfgaoIn, out uint psfgaoOut);

        // String overload
        [DllImport("shell32.dll", CharSet = CharSet.Auto)]
        private static extern IntPtr SHGetFileInfo(
            string pszPath, uint dwFileAttrib,
            ref SHFILEINFO psfi, uint cbFileInfo, uint uFlags);

        // PIDL overload — EntryPoint maps to the real "SHGetFileInfoW" export.
        // Without EntryPoint the runtime looks for a non-existent "SHGetFileInfoPidl"
        // export and the call silently fails, returning a generic icon/name.
        [DllImport("shell32.dll", EntryPoint = "SHGetFileInfoW", CharSet = CharSet.Unicode)]
        private static extern IntPtr SHGetFileInfoPidl(
            IntPtr pidl, uint dwFileAttrib,
            ref SHFILEINFO psfi, uint cbFileInfo, uint uFlags);

        [DllImport("shell32.dll")]
        private static extern IntPtr ILCombine(IntPtr pidl1, IntPtr pidl2);

        [DllImport("shell32.dll")]
        private static extern void ILFree(IntPtr pidl);

        [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
        private static extern bool SHGetPathFromIDListW(IntPtr pidl, StringBuilder pszPath);

        [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
        private static extern int SHGetNameFromIDList(IntPtr pidl, SIGDN sigdn, out IntPtr ppszName);

        [DllImport("ole32.dll")]
        private static extern void CoTaskMemFree(IntPtr pv);

        [DllImport("user32.dll")]
        private static extern bool DestroyIcon(IntPtr hIcon);

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Auto)]
        private struct SHFILEINFO
        {
            public IntPtr hIcon;
            public int    iIcon;
            public uint   dwAttributes;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)]
            public string szDisplayName;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 80)]
            public string szTypeName;
        }

        private enum SIGDN : uint
        {
            NORMALDISPLAY          = 0x00000000,
            DESKTOPABSOLUTEPARSING = 0x80028000,
        }

        private const uint SHGFI_ICON              = 0x0100;
        private const uint SHGFI_DISPLAYNAME       = 0x0200;
        private const uint SHGFI_LARGEICON         = 0x0000;
        private const uint SHGFI_PIDL              = 0x0008;
        private const uint SHGFI_USEFILEATTRIBUTES = 0x0010;
        private const uint FILE_ATTRIBUTE_NORMAL   = 0x0080;

        // ─── Public helpers ───────────────────────────────────────────────────

        public static bool IsVirtualPath(string? path) =>
            !string.IsNullOrEmpty(path) &&
            path.TrimStart().StartsWith("::{", StringComparison.Ordinal);

        /// <summary>
        /// Returns the shell icon and display name for ANY path — real or virtual.
        /// Uses SHParseDisplayName → PIDL → SHGetFileInfo(SHGFI_PIDL) which is the
        /// only documented API path guaranteed to work for virtual shell objects.
        /// </summary>
        public static (BitmapSource? icon, string displayName) GetShellInfo(string path)
        {
            // ── Route 1: parse to PIDL and query from the PIDL ──────────────
            // This works for everything: real files, real folders, ::{GUID} virtual
            // objects, UNC paths, drive roots, etc.
            if (SHParseDisplayName(path, IntPtr.Zero, out IntPtr pidl, 0, out _) == 0
                && pidl != IntPtr.Zero)
            {
                try { return QueryPidl(pidl); }
                finally { ILFree(pidl); }
            }

            // ── Route 2: string + USEFILEATTRIBUTES (for deleted real files) ──
            try
            {
                var info = new SHFILEINFO();
                IntPtr r = SHGetFileInfo(path, FILE_ATTRIBUTE_NORMAL, ref info,
                    (uint)Marshal.SizeOf(info),
                    SHGFI_ICON | SHGFI_LARGEICON | SHGFI_DISPLAYNAME | SHGFI_USEFILEATTRIBUTES);

                BitmapSource? bmp = MakeBitmap(r, ref info);
                string name = !string.IsNullOrWhiteSpace(info.szDisplayName)
                    ? info.szDisplayName : FallbackName(path);
                return (bmp, name);
            }
            catch { return (null, FallbackName(path)); }
        }

        public static string GetDisplayName(string path) => GetShellInfo(path).displayName;
        public static BitmapSource? GetIcon(string path)  => GetShellInfo(path).icon;

        public static string GetFolderInfo(string path)
        {
            try
            {
                int count = 0; bool overflow = false;
                foreach (var _ in Directory.EnumerateFileSystemEntries(path))
                    if (++count > 999) { overflow = true; break; }
                string s = overflow ? "1000+ items" : $"{count} item{(count == 1 ? "" : "s")}";
                return $"Folder • {s}";
            }
            catch { return "Folder"; }
        }

        public static List<(string parseName, string displayName)> TryGetShellItems(
            IDataObject dataObject)
        {
            var result = new List<(string, string)>();
            try
            {
                if (!dataObject.GetDataPresent("Shell IDList Array")) return result;
                var raw = dataObject.GetData("Shell IDList Array");
                byte[]? data = raw switch
                {
                    byte[]       b  => b,
                    MemoryStream ms => ms.ToArray(),
                    _               => null
                };
                if (data == null || data.Length < 8) return result;

                var gh = GCHandle.Alloc(data, GCHandleType.Pinned);
                try
                {
                    IntPtr pBase    = gh.AddrOfPinnedObject();
                    int    cidl     = Marshal.ReadInt32(pBase, 0);
                    if (cidl <= 0) return result;

                    IntPtr parent = IntPtr.Add(pBase, Marshal.ReadInt32(pBase, 4));
                    for (int i = 0; i < cidl; i++)
                    {
                        IntPtr child  = IntPtr.Add(pBase, Marshal.ReadInt32(pBase, 8 + i * 4));
                        IntPtr abs    = ILCombine(parent, child);
                        if (abs == IntPtr.Zero) continue;
                        try
                        {
                            ExtractFromPidl(abs, out string parse, out string display);
                            if (!string.IsNullOrEmpty(parse))
                                result.Add((parse, display));
                        }
                        finally { ILFree(abs); }
                    }
                }
                finally { gh.Free(); }
            }
            catch (Exception ex) { DataManager.Log($"ShellHelper.TryGetShellItems: {ex.Message}"); }
            return result;
        }

        // ─── Private helpers ──────────────────────────────────────────────────

        private static (BitmapSource? icon, string displayName) QueryPidl(IntPtr pidl)
        {
            try
            {
                var info = new SHFILEINFO();
                // SHGetFileInfoPidl is the DllImport alias for SHGetFileInfo called with a PIDL.
                // We use the IntPtr overload (SHGetFileInfoPidl) + SHGFI_PIDL flag together.
                IntPtr r = SHGetFileInfoPidl(pidl, 0, ref info,
                    (uint)Marshal.SizeOf(info),
                    SHGFI_PIDL | SHGFI_ICON | SHGFI_LARGEICON | SHGFI_DISPLAYNAME);

                BitmapSource? bmp  = MakeBitmap(r, ref info);
                string        name = !string.IsNullOrWhiteSpace(info.szDisplayName)
                                         ? info.szDisplayName : "";
                return (bmp, name);
            }
            catch { return (null, ""); }
        }

        private static void ExtractFromPidl(IntPtr abs, out string parse, out string display)
        {
            parse   = "";
            display = "";

            // Try real filesystem path first
            var sb = new StringBuilder(32768);
            if (SHGetPathFromIDListW(abs, sb) && sb.Length > 0)
            {
                parse = sb.ToString();
                var (_, dn) = QueryPidl(abs);
                display = !string.IsNullOrEmpty(dn)
                    ? dn
                    : Path.GetFileName(parse.TrimEnd(
                          Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar));
                if (string.IsNullOrEmpty(display)) display = parse;
                return;
            }

            // Virtual object — get ::{GUID} parsing name
            IntPtr pParse = IntPtr.Zero;
            try
            {
                if (SHGetNameFromIDList(abs, SIGDN.DESKTOPABSOLUTEPARSING, out pParse) == 0
                    && pParse != IntPtr.Zero)
                    parse = Marshal.PtrToStringUni(pParse) ?? "";
            }
            finally { if (pParse != IntPtr.Zero) CoTaskMemFree(pParse); }

            // Display name from live PIDL — guaranteed correct
            var (_, dname) = QueryPidl(abs);
            display = !string.IsNullOrEmpty(dname) ? dname : parse;
        }

        private static BitmapSource? MakeBitmap(IntPtr shellResult, ref SHFILEINFO info)
        {
            if (shellResult == IntPtr.Zero || info.hIcon == IntPtr.Zero) return null;
            try
            {
                var bmp = System.Windows.Interop.Imaging.CreateBitmapSourceFromHIcon(
                    info.hIcon, Int32Rect.Empty, BitmapSizeOptions.FromEmptyOptions());
                bmp.Freeze();
                return bmp;
            }
            catch { return null; }
            finally { DestroyIcon(info.hIcon); info.hIcon = IntPtr.Zero; }
        }

        private static string FallbackName(string path) =>
            Path.GetFileName(path.TrimEnd(
                Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar));
    }
}
