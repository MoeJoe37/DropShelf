using System;
using System.Diagnostics;
using Microsoft.Win32;

namespace DropShelf
{
    public static class RegistryHelper
    {
        private const string RunKey  = @"Software\Microsoft\Windows\CurrentVersion\Run";
        private const string AppName = "DropShelf";

        public static bool IsStartupEnabled()
        {
            try
            {
                using var key = Registry.CurrentUser.OpenSubKey(RunKey, false);
                return key?.GetValue(AppName) != null;
            }
            catch { return false; }
        }

        public static void SetStartup(bool enable)
        {
            try
            {
                using var key = Registry.CurrentUser.OpenSubKey(RunKey, true)!;
                if (enable)
                {
                    // Process.GetCurrentProcess().MainModule.FileName always returns the
                    // actual .exe on disk — even in single-file .NET publish builds.
                    // Environment.ProcessPath and Assembly.Location can return the DLL
                    // or a temp-extracted path in those scenarios, which breaks startup.
                    string? exe = Process.GetCurrentProcess().MainModule?.FileName;
                    if (string.IsNullOrEmpty(exe))
                    {
                        DataManager.Log("SetStartup: could not determine exe path.");
                        return;
                    }
                    // Wrap in quotes so paths with spaces survive the registry launch
                    key.SetValue(AppName, $"\"{exe}\"");
                    DataManager.Log($"SetStartup: registered \"{exe}\"");
                }
                else
                {
                    key.DeleteValue(AppName, false);
                    DataManager.Log("SetStartup: removed startup entry.");
                }
            }
            catch (Exception ex)
            {
                DataManager.Log($"SetStartup error: {ex.Message}");
            }
        }
    }
}
