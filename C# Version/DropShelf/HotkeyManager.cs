using System;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Input;
using System.Windows.Interop;

namespace DropShelf
{
    public class HotkeyManager : IDisposable
    {
        [DllImport("user32.dll")]
        private static extern bool RegisterHotKey(IntPtr hWnd, int id, uint fsModifiers, uint vk);

        [DllImport("user32.dll")]
        private static extern bool UnregisterHotKey(IntPtr hWnd, int id);

        private const int WM_HOTKEY = 0x0312;
        private const uint MOD_ALT = 0x0001;
        private const uint MOD_CTRL = 0x0002;
        private const uint MOD_SHIFT = 0x0004;
        private const uint MOD_WIN = 0x0008;

        private readonly Window _window;
        private HwndSource? _source;
        private int _id = 9001;
        public event Action? HotkeyPressed;

        public HotkeyManager(Window window)
        {
            _window = window;
        }

        public void Initialize()
        {
            if (_window.IsLoaded)
                AttachHook();
            else
                _window.Loaded += (_, _) => AttachHook();
        }

        private void AttachHook()
        {
            var handle = new WindowInteropHelper(_window).Handle;
            _source = HwndSource.FromHwnd(handle);
            _source?.AddHook(WndProc);
        }

        public bool Register(string hotkey)
        {
            Unregister();
            var (mods, vk) = ParseHotkey(hotkey);
            if (vk == 0) return false;
            var handle = new WindowInteropHelper(_window).Handle;
            bool ok = RegisterHotKey(handle, _id, mods, vk);
            DataManager.Log($"RegisterHotKey({hotkey}): {ok}");
            return ok;
        }

        public void Unregister()
        {
            try
            {
                var handle = new WindowInteropHelper(_window).Handle;
                UnregisterHotKey(handle, _id);
            }
            catch { }
        }

        private static (uint mods, uint vk) ParseHotkey(string hotkey)
        {
            uint mods = 0;
            uint vk = 0;
            var parts = hotkey.ToLower().Split('+');
            foreach (var part in parts)
            {
                switch (part.Trim())
                {
                    case "ctrl":  mods |= MOD_CTRL; break;
                    case "alt":   mods |= MOD_ALT; break;
                    case "shift": mods |= MOD_SHIFT; break;
                    case "win":   mods |= MOD_WIN; break;
                    default:
                        var key = ParseKey(part.Trim());
                        if (key != Key.None)
                            vk = (uint)KeyInterop.VirtualKeyFromKey(key);
                        break;
                }
            }
            return (mods, vk);
        }

        private static Key ParseKey(string s) => s switch
        {
            "a" => Key.A, "b" => Key.B, "c" => Key.C, "d" => Key.D, "e" => Key.E,
            "f" => Key.F, "g" => Key.G, "h" => Key.H, "i" => Key.I, "j" => Key.J,
            "k" => Key.K, "l" => Key.L, "m" => Key.M, "n" => Key.N, "o" => Key.O,
            "p" => Key.P, "q" => Key.Q, "r" => Key.R, "s" => Key.S, "t" => Key.T,
            "u" => Key.U, "v" => Key.V, "w" => Key.W, "x" => Key.X, "y" => Key.Y,
            "z" => Key.Z,
            "f1" => Key.F1, "f2" => Key.F2, "f3" => Key.F3, "f4" => Key.F4,
            "f5" => Key.F5, "f6" => Key.F6, "f7" => Key.F7, "f8" => Key.F8,
            "f9" => Key.F9, "f10" => Key.F10, "f11" => Key.F11, "f12" => Key.F12,
            "space" => Key.Space, "tab" => Key.Tab, "enter" => Key.Enter,
            "0" => Key.D0, "1" => Key.D1, "2" => Key.D2, "3" => Key.D3, "4" => Key.D4,
            "5" => Key.D5, "6" => Key.D6, "7" => Key.D7, "8" => Key.D8, "9" => Key.D9,
            _ => Key.None
        };

        private IntPtr WndProc(IntPtr hwnd, int msg, IntPtr wParam, IntPtr lParam, ref bool handled)
        {
            if (msg == WM_HOTKEY && wParam.ToInt32() == _id)
            {
                HotkeyPressed?.Invoke();
                handled = true;
            }
            return IntPtr.Zero;
        }

        public void Dispose()
        {
            Unregister();
            _source?.RemoveHook(WndProc);
        }
    }
}
