import sys, os
import requests
import webbrowser
import subprocess
import tempfile
import time
import queue
import threading
from panda3d.core import loadPrcFileData, Filename

from loading_screen import LoadingScreen
from sign_language_app import SignLanguageApp

APP_VERSION = "v1.1.0"
GITHUB_REPO = "Suja2004/ASR"

if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS

    model_path = Filename.fromOsSpecific(base_path).toOsSpecific()
    loadPrcFileData("", f"model-path {model_path}")

    loadPrcFileData("", "load-display pandagl")
    loadPrcFileData("", "aux-display tinydisplay")
    loadPrcFileData("", "window-title SignSynth")
    loadPrcFileData('', 'background-color 0.1 0.1 0.1 1')
    loadPrcFileData('', 'win-size 1280 720')
else:
    base_path = os.path.abspath(os.path.dirname(__file__))

    model_path = Filename.fromOsSpecific(base_path).toOsSpecific()
    loadPrcFileData("", f"model-path {model_path}")

if getattr(sys, 'frozen', False):
    dll_path = os.path.join(sys._MEIPASS, "vosk")
    if os.path.exists(dll_path):
        os.add_dll_directory(dll_path)

if getattr(sys, 'frozen', False) and sys.platform == 'win32':
    try:
        os.add_dll_directory(sys._MEIPASS)
        dll_path = os.path.join(sys._MEIPASS, "vosk")
        if os.path.exists(dll_path):
            os.add_dll_directory(dll_path)
    except Exception:
        pass

def check_for_updates(loader):
    """
    Checks GitHub for the latest release and prompts user to update.
    Returns True to continue loading, False to quit.
    """
    loader.update_progress("Checking for updates...", "Connecting to GitHub...")
    loader.update()
    try:
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        latest_release = response.json()
        latest_version = latest_release.get("tag_name", "")

        def version_tuple(v):
            try:
                return tuple(map(int, v.lstrip('v').split('.')))
            except:
                return (0, 0, 0)

        current_ver = version_tuple(APP_VERSION)
        latest_ver = version_tuple(latest_version)
        update_available = latest_ver > current_ver

        if update_available:
            print(f"Update found: {latest_version} (current: {APP_VERSION})")
            installer_url = None
            for asset in latest_release.get("assets", []):
                if asset.get("name", "").endswith(".exe"):
                    installer_url = asset.get("browser_download_url")
                    break

            if not installer_url:
                print("Update found, but no .exe installer available.")
                loader.update_progress("Update available", "No installer found, continuing...")
                loader.update()
                time.sleep(1)
                return True

            download_queue = queue.Queue()
            continue_loading = {'value': True}

            def do_download(url, path):
                """Runs in a separate thread to download the file"""
                try:
                    with requests.get(url, stream=True, timeout=30) as r:
                        r.raise_for_status()
                        total_size = int(r.headers.get('content-length', 0))
                        downloaded_size = 0

                        with open(path, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                                    downloaded_size += len(chunk)
                                    download_queue.put(
                                        ("progress", downloaded_size, total_size)
                                    )
                    download_queue.put(("done", path))
                except Exception as e:
                    download_queue.put(("error", e, url))

            def check_download_progress():
                """
                Runs in the main thread to update the UI.
                This is now optimized to only process the *last* progress message.
                """
                try:
                    last_progress_msg = None
                    final_msg = None

                    while not download_queue.empty():
                        msg = download_queue.get_nowait()
                        msg_type = msg[0]

                        if msg_type == "progress":
                            last_progress_msg = msg
                        elif msg_type == "done" or msg_type == "error":
                            final_msg = msg
                            break

                    if last_progress_msg:
                        msg_type, *data = last_progress_msg
                        downloaded_size, total_size = data
                        progress_mb = f"{(downloaded_size / (1024 * 1024)):.1f} MB"
                        if total_size > 0:
                            progress_mb += f" / {(total_size / (1024 * 1024)):.1f} MB"
                            progress_pct = int((downloaded_size / total_size) * 100)
                            loader.set_progress(progress_pct)

                        loader.update_status_text("Downloading update...", progress_mb)

                    if final_msg:
                        msg_type, *data = final_msg

                        if msg_type == "done":
                            installer_path = data[0]

                            loader.update_status_text("Update downloaded", "Launching installer...")
                            loader.update()
                            time.sleep(1)

                            if sys.platform == 'win32':
                                import ctypes
                                try:
                                    ctypes.windll.shell32.ShellExecuteW(None, "runas",
                                                                        installer_path, '/SILENT',
                                                                        None,
                                                                        1)
                                except Exception as e:
                                    print(f"Failed to launch installer as admin: {e}")
                                    webbrowser.open(installer_url)
                            else:
                                subprocess.Popen([installer_path])

                            continue_loading['value'] = False
                            loader.root.quit()
                            return

                        elif msg_type == "error":
                            e, url = data
                            print(f"Failed to download or run updater: {e}")
                            loader.hide_update_prompt()

                            loader.update_status_text("Download failed",
                                                      "Opening browser instead...")
                            loader.update()
                            import tkinter.messagebox as messagebox
                            messagebox.showwarning("Update Failed",
                                                   f"Could not download update.\n\nError: {str(e)}\n\nOpening browser instead.")
                            webbrowser.open(url)

                            continue_loading['value'] = False
                            loader.root.quit()
                            return

                except queue.Empty:
                    pass

                if not loader.is_destroyed:
                    loader.root.after(100, check_download_progress)

            def on_yes():

                loader.set_progress(0)

                loader.update_progress("Downloading update...", "Starting download...")

                temp_dir = tempfile.gettempdir()
                installer_name = os.path.basename(installer_url)
                installer_path = os.path.join(temp_dir, installer_name)

                threading.Thread(
                    target=do_download,
                    args=(installer_url, installer_path),
                    daemon=True
                ).start()

                loader.root.after(100, check_download_progress)

            def on_no():
                continue_loading['value'] = True
                loader.root.quit()

            loader.show_update_prompt(
                f"A new version ({latest_version}) is available!",
                on_yes,
                on_no
            )
            loader.mainloop()

            if continue_loading['value'] == True:

                loader.hide_update_prompt()
                loader.update_progress("Continuing with current version...", "")
                loader.update()
                time.sleep(0.5)
                return True
            else:

                return False

        else:
            print(f"App is up-to-date (version {APP_VERSION})")
            loader.update_progress("Application is up-to-date", "")
            loader.update()
            time.sleep(0.5)
            return True

    except requests.exceptions.Timeout:
        print("Update check timed out")
        loader.update_progress("Update check timed out", "Continuing offline...")
        loader.update()
        time.sleep(1)
        return True

    except requests.exceptions.RequestException as e:
        print(f"Could not check for updates: {e}")
        loader.update_progress("Could not check for updates", "Continuing offline...")
        loader.update()
        time.sleep(1)
        return True

    except Exception as e:
        print(f"Unexpected error during update check: {e}")
        import traceback
        traceback.print_exc()
        loader.update_progress("Update check failed", "Continuing...")
        loader.update()
        time.sleep(1)
        return True


if __name__ == "__main__":
    loading = LoadingScreen(version=APP_VERSION)

    loading.set_steps([
        "Checking for updates",
        "Initializing 3D engine",
        "Loading 3D models",
        "Initializing audio",
        "Finalizing UI"
    ])

    loading.center()
    loading.show()
    loading.update()

    should_continue = check_for_updates(loading)

    if not should_continue:
        loading.close()
        sys.exit()

    loadPrcFileData("", "window-type none")

    loading.update_progress("Initializing 3D engine...", "Starting Panda3D...")
    loading.update()

    try:
        panda_app = SignLanguageApp()
    except Exception as e:
        loading.close()
        import tkinter.messagebox as messagebox

        messagebox.showerror("Fatal Error", f"Failed to initialize Panda3D: {e}")
        sys.exit(1)

    loading.update_progress("Loading 3D models...", "Character, arms, and skybox")
    loading.update()

    loading.update_progress("Initializing audio...", "Starting Vosk speech engine")
    loading.update()

    loading.update_progress("Finalizing UI...", "Preparing user interface")
    loading.update()


    def on_loading_finished():
        print("Loading complete. Starting Panda3D event loop.")
        panda_app.open_app_window()
        panda_app.run()


    loading.finished_connect(on_loading_finished)
    loading.complete()

    loading.mainloop()
