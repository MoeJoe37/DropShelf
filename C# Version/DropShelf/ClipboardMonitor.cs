using System;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;

namespace DropShelf
{
    public class ClipboardMonitor : IDisposable
    {
        [DllImport("user32.dll")]
        private static extern bool AddClipboardFormatListener(IntPtr hwnd);
        [DllImport("user32.dll")]
        private static extern bool RemoveClipboardFormatListener(IntPtr hwnd);

        private const int WM_CLIPBOARDUPDATE = 0x031D;

        private HwndSource? _source;
        public event Action? ClipboardChanged;

        public void Initialize(Window window)
        {
            if (window.IsLoaded)
                Attach(window);
            else
                window.Loaded += (_, _) => Attach(window);
        }

        private void Attach(Window window)
        {
            var handle = new WindowInteropHelper(window).Handle;
            _source = HwndSource.FromHwnd(handle);
            _source?.AddHook(WndProc);
            AddClipboardFormatListener(handle);
        }

        private IntPtr WndProc(IntPtr hwnd, int msg, IntPtr wParam, IntPtr lParam, ref bool handled)
        {
            if (msg == WM_CLIPBOARDUPDATE)
                ClipboardChanged?.Invoke();
            return IntPtr.Zero;
        }

        public void Dispose()
        {
            if (_source != null)
            {
                RemoveClipboardFormatListener(_source.Handle);
                _source.RemoveHook(WndProc);
            }
        }
    }
}
