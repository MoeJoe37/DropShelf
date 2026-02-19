using System;
using System.IO;
using System.IO.Pipes;
using System.Threading;
using System.Windows;
using System.Windows.Threading;

namespace DropShelf
{
    public partial class App : Application
    {
        // Use a unique global name so the mutex is truly per-user per-machine
        private const string MutexName  = "Global\\DropShelf_SingleInstance_7E4A2F3B";
        private const string PipeName   = "DropShelf_IPC_7E4A2F3B";

        private static Mutex?                  _mutex;
        private static NamedPipeServerStream?  _pipeServer;

        protected override void OnStartup(StartupEventArgs e)
        {
            // ── Unhandled-exception safety net ──────────────────────────────
            DispatcherUnhandledException += (_, ex) =>
            {
                MessageBox.Show($"Unhandled UI error:\n{ex.Exception}", "DropShelf Error",
                    MessageBoxButton.OK, MessageBoxImage.Error);
                ex.Handled = true;
            };
            AppDomain.CurrentDomain.UnhandledException += (_, ex) =>
            {
                MessageBox.Show($"Fatal error:\n{ex.ExceptionObject}", "DropShelf Fatal",
                    MessageBoxButton.OK, MessageBoxImage.Error);
            };

            // ── Single-instance check ────────────────────────────────────────
            try
            {
                _mutex = new Mutex(initiallyOwned: true, MutexName, out bool createdNew);
                if (!createdNew)
                {
                    // Another instance is running — tell it to show itself, then exit
                    SignalExistingInstance();
                    Shutdown(0);
                    return;
                }
            }
            catch (Exception ex)
            {
                // Mutex might fail on some restricted environments — just proceed
                DataManager.Log($"Mutex error (non-fatal): {ex.Message}");
            }

            base.OnStartup(e);

            // ── Start IPC server for "bring-to-front" from second instance ──
            TryStartPipeServer();

            // ── Create and show the main window ─────────────────────────────
            try
            {
                var window = new MainWindow();
                MainWindow = window;
                window.Show();
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Failed to create main window:\n{ex}", "DropShelf Startup Error",
                    MessageBoxButton.OK, MessageBoxImage.Error);
                Shutdown(1);
            }
        }

        // ── IPC helpers ─────────────────────────────────────────────────────

        private static void SignalExistingInstance()
        {
            try
            {
                using var client = new NamedPipeClientStream(".", PipeName, PipeDirection.Out);
                client.Connect(800);
                using var writer = new StreamWriter(client) { AutoFlush = true };
                writer.Write("SHOW");
            }
            catch { /* Existing instance may not have the pipe yet — ignore */ }
        }

        private void TryStartPipeServer()
        {
            try
            {
                _pipeServer = new NamedPipeServerStream(
                    PipeName,
                    PipeDirection.In,
                    maxNumberOfServerInstances: 1,
                    PipeTransmissionMode.Byte,
                    PipeOptions.Asynchronous);

                _pipeServer.BeginWaitForConnection(OnPipeConnectionReceived, null);
            }
            catch (Exception ex)
            {
                // Pipe server is optional — single-instance still works via mutex
                DataManager.Log($"Pipe server start error (non-fatal): {ex.Message}");
            }
        }

        private void OnPipeConnectionReceived(IAsyncResult ar)
        {
            try
            {
                _pipeServer?.EndWaitForConnection(ar);

                string msg = "";
                using (var reader = new StreamReader(_pipeServer!))
                    msg = reader.ReadToEnd().Trim();

                if (msg == "SHOW")
                    Dispatcher.Invoke(() => (MainWindow as MainWindow)?.ShowWindow());

                // Reset the server for the next connection
                _pipeServer.Dispose();
                _pipeServer = null;
                TryStartPipeServer();
            }
            catch { /* Pipe may have been closed during shutdown */ }
        }

        // ── Cleanup ─────────────────────────────────────────────────────────

        protected override void OnExit(ExitEventArgs e)
        {
            try { _mutex?.ReleaseMutex(); } catch { }
            try { _mutex?.Dispose(); }      catch { }
            try { _pipeServer?.Dispose(); } catch { }
            base.OnExit(e);
        }
    }
}
