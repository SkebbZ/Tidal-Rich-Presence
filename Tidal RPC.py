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
import struct
import psutil
import win32gui
import win32process
from pypresence import Presence, PipeClosed, InvalidID, DiscordNotFound

def clear():
    """Clears the terminal environment based on the underlying host operating system."""
    os.system('cls' if os.name == 'nt' else 'clear')

class TidalRPC:
    def __init__(self, client_id):
        self.client_id = client_id
        self.rpc = None
        self.last_track = None
        self.start_time = None
        self.last_update_time = 0
        self.tidal_pids = set()

    def disconnect_discord(self):
        """
        Safely closes the active IPC handle and resets track state.
        Resetting self.last_track to None guarantees that upon reconnection,
        the presence payload is immediately re-sent to Discord even if the song hasn't changed.
        """
        if self.rpc:
            try:
                self.rpc.close()
            except Exception:
                pass
        self.rpc = None
        self.last_track = None
        self.last_update_time = 0

    def connect_discord(self):
        """Attempts to establish an IPC connection with the local Discord client."""
        self.disconnect_discord()
        try:
            client = Presence(self.client_id)
            client.connect()
            self.rpc = client
            print("Connected to Discord RPC.")
            return True
        except (DiscordNotFound, ConnectionRefusedError, FileNotFoundError, OSError):
            print("Discord not found or not running.")
            self.disconnect_discord()
            return False
        except Exception as e:
            print(f"Error connecting to Discord: {e}")
            self.disconnect_discord()
            return False

    def refresh_tidal_pids(self):
        """
        Scans the active process tree to cache all PIDs associated with Tidal.
        Guarded against NoSuchProcess exceptions if processes exit during iteration.
        """
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
            print(f"Error refreshing PIDs: {e}")
            self.tidal_pids = set()

    def get_current_track(self):
        """
        Iterates through top-level Win32 windows to extract track metadata from titles.
        Verifies cached PID liveness before enumerating handles.
        """
        # If cache is empty or all cached processes have died, perform a process tree rescan
        if not self.tidal_pids or not any(psutil.pid_exists(pid) for pid in self.tidal_pids):
            self.refresh_tidal_pids()

        if not self.tidal_pids:
            return None, None

        found_titles = []

        def callback(hwnd, _):
            """Win32 callback processing handles for visible top-level windows."""
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

        # Parse titles for "Track - Artist" format
        for title in found_titles:
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                if len(parts) == 2:
                    return parts[0].strip(), parts[1].strip()

        if "TIDAL" in found_titles:
            return "PAUSED", None

        # PIDs exist but no main window discovered (e.g., playback stopped/closed to tray)
        self.tidal_pids.clear()
        return None, None

    def run(self):
        """
        Main loop managing state synchronization and IPC payload delivery.
        
        Uses an IPC Heartbeat strategy:
        By forcing an rpc.update() write at least every 12 seconds, Windows Named Pipe
        breakages (e.g., when Discord closes) are detected immediately via OS write exceptions,
        eliminating the need to poll the system process table.
        """
        print("Tidal RPC Script Started (Optimized Heartbeat Support).")
        HEARTBEAT_INTERVAL = 12  # Seconds before forcing a pipe write ping

        while True:
            # 1. Connection state verification
            if self.rpc is None:
                print("Attempting to connect to Discord...")
                if not self.connect_discord():
                    time.sleep(10)
                    continue

            # 2. Metadata acquisition
            track, artist = self.get_current_track()

            # 3. Rich presence state evaluation and transmission
            try:
                if track and artist:
                    if track == "PAUSED":
                        if self.last_track != "PAUSED":
                            print("Tidal is Paused.")
                            self.rpc.clear()
                            self.last_track = "PAUSED"
                    else:
                        sig = f"{track}-{artist}"
                        now = time.time()

                        # Write to pipe if track changed OR if heartbeat interval elapsed
                        if sig != self.last_track or (now - self.last_update_time) >= HEARTBEAT_INTERVAL:
                            # Only reset the track start timer when a new track actually begins
                            if sig != self.last_track:
                                print(f"Now Playing: {track} by {artist}")
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
                    # Clear presence state if TIDAL is closed
                    if self.last_track is not None:
                        print("Tidal closed or not found.")
                        try:
                            self.rpc.clear()
                        except Exception:
                            pass
                        self.last_track = None
                        self.tidal_pids.clear()

            # Catch IPC pipe closures, socket resets, and protocol unpacking errors
            except (PipeClosed, InvalidID, AssertionError, BrokenPipeError, 
                    ConnectionResetError, OSError, struct.error) as e:
                print(f"IPC Connection lost ({type(e).__name__}). Resetting...")
                self.disconnect_discord()
            except Exception as e:
                print(f"Unexpected RPC Error ({type(e).__name__}: {e}). Resetting...")
                self.disconnect_discord()

            # Short polling interval allows fast response to manual track changes
            time.sleep(4)

if __name__ == "__main__":
    CLIENT_ID = ""  # Enter your Client ID from your Discord App here
    bot = TidalRPC(CLIENT_ID)
    try:
        bot.run()
    except KeyboardInterrupt:
        print("Exiting...")