#   Tidal-Rich-Presence, Discord rich presence for TIDAL.
#   Copyright (C) 2024  Arun Fletcher
#
#   Neither I nor this program are affiliated with TIDAL in any way.
#   The TIDAL wordmark and logo are registered trademarks of TIDAL Music AS.
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.

import time
import os
import sys
import json
import struct
import threading
import psutil
import win32gui
import win32process
import PySimpleGUI as sg
from psgtray import SystemTray
from pypresence import Presence, PipeClosed, InvalidID, DiscordNotFound


def get_config_path():
    """
    Returns the persistent directory path where config.json should be stored.
    When running as a PyInstaller frozen executable, sys.executable points to the .exe directory.
    """
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, 'config.json')


def load_config():
    """Loads saved Client ID from config.json if it exists."""
    config_file = get_config_path()
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('client_id', '')
        except Exception:
            pass
    return ''


def save_config(client_id):
    """Saves Client ID to config.json."""
    config_file = get_config_path()
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump({'client_id': client_id}, f, indent=4)
        return True
    except Exception as e:
        print(f"Failed to save config: {e}")
        return False


def get_valid_b64_icon(raw_b64):
    """
    Pads raw Base64 bytes to ensure length is a multiple of 4.
    Prevents binascii.Error (incorrect padding) in Python 3.13+ strict validation mode.
    """
    clean_bytes = raw_b64.strip()
    missing_padding = len(clean_bytes) % 4
    if missing_padding:
        clean_bytes += b'=' * (4 - missing_padding)
    return clean_bytes


class TidalRPCEngine:
    """
    Background worker engine managing IPC communication with Discord
    and window enumeration for TIDAL metadata.
    """
    def __init__(self, client_id, log_callback=None):
        self.client_id = client_id
        self.log_callback = log_callback
        self.rpc = None
        self.last_track = None
        self.start_time = None
        self.last_update_time = 0
        self.tidal_pids = set()
        self._stop_event = threading.Event()

    def log(self, message):
        """Thread-safe logging helper."""
        if self.log_callback:
            self.log_callback(message)

    def update_client_id(self, new_id):
        """Dynamically updates the Client ID and triggers a reconnect."""
        if new_id != self.client_id:
            self.client_id = new_id
            self.log("Client ID updated. Reconnecting to Discord...")
            self.disconnect_discord()

    def stop(self):
        """Signals the background thread to exit cleanly."""
        self._stop_event.set()

    def disconnect_discord(self):
        """Safely closes the IPC pipe handle and resets tracking state."""
        if self.rpc:
            try:
                self.rpc.close()
            except Exception:
                pass
        self.rpc = None
        self.last_track = None
        self.last_update_time = 0

    def connect_discord(self):
        """Attempts to establish an IPC pipe connection with Discord."""
        self.disconnect_discord()
        
        if not self.client_id or not self.client_id.strip() or self.client_id == "0000000000000000000":
            self.log("Please enter a valid Discord Client ID above and click Save.")
            return False

        try:
            client = Presence(self.client_id)
            client.connect()
            self.rpc = client
            self.log("Connected to Discord RPC.")
            return True
        except InvalidID:
            self.log("Invalid Client ID! Please verify your Discord App ID.")
            self.disconnect_discord()
            return False
        except (DiscordNotFound, ConnectionRefusedError, FileNotFoundError, OSError):
            self.log("Discord not found or not running.")
            self.disconnect_discord()
            return False
        except Exception as e:
            self.log(f"Error connecting to Discord: {e}")
            self.disconnect_discord()
            return False

    def refresh_tidal_pids(self):
        """Caches active PIDs associated with TIDAL processes."""
        try:
            pids = set()
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    name = proc.info.get('name')
                    if name and "tidal" in name.lower():
                        pids.add(proc.info['pid'])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            self.tidal_pids = pids
        except Exception as e:
            self.log(f"Error refreshing PIDs: {e}")
            self.tidal_pids = set()

    def get_current_track(self):
        """Extracts track metadata from active Win32 window titles."""
        if not self.tidal_pids or not any(psutil.pid_exists(pid) for pid in self.tidal_pids):
            self.refresh_tidal_pids()

        if not self.tidal_pids:
            return None, None

        found_titles = []

        def callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                try:
                    _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                    if found_pid in self.tidal_pids:
                        title = win32gui.GetWindowText(hwnd)
                        if title:
                            found_titles.append(title)
                except Exception:
                    pass
            return True

        try:
            win32gui.EnumWindows(callback, None)
        except Exception:
            pass

        for title in found_titles:
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                if len(parts) == 2:
                    return parts[0].strip(), parts[1].strip()

        if "TIDAL" in found_titles:
            return "PAUSED", None

        self.tidal_pids.clear()
        return None, None

    def sleep_interruptible(self, seconds):
        """Sleeps in short increments to allow immediate thread exit on application shutdown."""
        for _ in range(int(seconds * 10)):
            if self._stop_event.is_set():
                break
            time.sleep(0.1)

    def run(self):
        """Main execution loop using the zero-overhead IPC heartbeat mechanism."""
        self.log("TIDAL RPC Worker Started.")
        HEARTBEAT_INTERVAL = 12  # Seconds between forced IPC ping writes

        while not self._stop_event.is_set():
            if self.rpc is None:
                if not self.connect_discord():
                    self.sleep_interruptible(10)
                    continue

            track, artist = self.get_current_track()

            try:
                if track and artist:
                    if track == "PAUSED":
                        if self.last_track != "PAUSED":
                            self.log("Tidal is Paused.")
                            self.rpc.clear()
                            self.last_track = "PAUSED"
                    else:
                        sig = f"{track}-{artist}"
                        now = time.time()

                        if sig != self.last_track or (now - self.last_update_time) >= HEARTBEAT_INTERVAL:
                            if sig != self.last_track:
                                self.log(f"Now Playing: {track} by {artist}")
                                self.start_time = now
                                self.last_track = sig

                            self.rpc.update(
                                details=track,
                                state=f"by {artist}",
                                large_image="tidallogo",
                                large_text="TIDAL",
                                small_image="hra",
                                small_text="High Fidelity",
                                start=self.start_time
                            )
                            self.last_update_time = now
                else:
                    if self.last_track is not None:
                        self.log("Tidal closed or not found.")
                        try:
                            self.rpc.clear()
                        except Exception:
                            pass
                        self.last_track = None
                        self.tidal_pids.clear()

            except (PipeClosed, InvalidID, AssertionError, BrokenPipeError, 
                    ConnectionResetError, OSError, struct.error) as e:
                self.log(f"IPC Connection lost ({type(e).__name__}). Resetting...")
                self.disconnect_discord()
            except Exception as e:
                self.log(f"Unexpected RPC Error ({type(e).__name__}: {e}). Resetting...")
                self.disconnect_discord()

            self.sleep_interruptible(4)

        self.disconnect_discord()
        self.log("Worker thread stopped.")


def the_gui():
    menu = ['', ['Show Window', 'Hide Window', 'Exit']]
    tooltip = 'Tidal RPC'
    
    saved_client_id = load_config()

    layout = [
        [sg.Text("Discord Client ID:"), 
         sg.Input(default_text=saved_client_id, key='-CLIENT_ID-', size=(26, 1)), 
         sg.Button("Save", key='-SAVE_ID-')],
        [sg.Multiline(size=(58, 9), key='-ML-', write_only=True, autoscroll=True, auto_refresh=True, reroute_cprint=True)],
        [sg.T('Double click tray icon to restore, or right click and choose Show Window!')],
        [sg.Button("Hide Window"), sg.Button("Exit")]
    ]
    
    window = sg.Window("TIDAL RPC", layout, finalize=True)
    
    app_icon = b'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'
    
    # Initialize system tray with padding-validated base64 icon
    tray = SystemTray(
        menu, 
        single_click_events=False, 
        window=window, 
        tooltip=tooltip, 
        icon=get_valid_b64_icon(app_icon)
    )

    # Initialize RPC worker engine using thread-safe window event logging
    engine = TidalRPCEngine(
        saved_client_id, 
        log_callback=lambda msg: window.write_event_value('-LOG_MSG-', msg)
    )
    worker_thread = threading.Thread(target=engine.run, daemon=True)
    worker_thread.start()

    tray.show_icon()

    # --------------------- EVENT LOOP ---------------------
    while True:
        event, values = window.read(timeout=100)

        if event == sg.TIMEOUT_EVENT:
            continue

        if event == tray.key:
            event = values[event]

        if event in ('Exit', sg.WIN_CLOSED):
            break

        # Thread-safe logging event pushed from worker thread
        if event == '-LOG_MSG-':
            sg.cprint(values['-LOG_MSG-'])

        # Save Button clicked
        if event == '-SAVE_ID-':
            new_id = values['-CLIENT_ID-'].strip()
            if save_config(new_id):
                sg.cprint(f"Saved Client ID: {new_id}")
                engine.update_client_id(new_id)

        if event in ('Show Window', sg.EVENT_SYSTEM_TRAY_ICON_DOUBLE_CLICKED):
            window.un_hide()
            window.bring_to_front()
        elif event in ('Hide Window', sg.WIN_CLOSE_ATTEMPTED_EVENT):
            window.hide()
            tray.show_message('TIDAL RPC', 'TIDAL RPC hidden to system tray.')

    # Clean application termination sequence
    engine.stop()
    worker_thread.join(timeout=2.0)
    tray.close()
    window.close()
    sys.exit(0)


if __name__ == '__main__':
    the_gui()
