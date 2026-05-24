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
        # Utilizing a set instead of a list for O(1) membership testing 
        # during high-frequency window enumeration loops.
        self.tidal_pids = set()

    def connect_discord(self):
        """Attempts to establish an IPC connection with the local Discord client."""
        try:
            client = Presence(self.client_id)
            client.connect()
            self.rpc = client
            print("Connected to Discord RPC.")
            return True
        except (DiscordNotFound, ConnectionRefusedError, FileNotFoundError):
            print("Discord not found or not running.")
            self.rpc = None
            return False
        except Exception as e:
            print(f"Error connecting to Discord: {e}")
            self.rpc = None
            return False

    def refresh_tidal_pids(self):
        """Scans the active system process tree to cache all unique PIDs associated with Tidal."""
        try:
            # Set comprehension filters active processes, minimizing overhead.
            # Tidal runs on Electron, which spawns multiple architecture-specific processes.
            self.tidal_pids = {
                proc.info['pid']
                for proc in psutil.process_iter(['pid', 'name'])
                if proc.info['name'] and "tidal" in proc.info['name'].lower()
            }
        except Exception as e:
            print(f"Error refreshing PIDs: {e}")
            self.tidal_pids = set()

    def get_current_track(self):
        """Iterates through top-level windows to extract metadata from window titles."""
        if not self.tidal_pids:
            self.refresh_tidal_pids()
        
        if not self.tidal_pids:
            return None, None

        found_titles = []

        def callback(hwnd, _):
            """Win32 callback processing handles for all visible top-level windows."""
            if win32gui.IsWindowVisible(hwnd):
                try:
                    _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                    # O(1) hash lookup prevents performance degradation during iteration.
                    if found_pid in self.tidal_pids:
                        title = win32gui.GetWindowText(hwnd)
                        if title:
                            found_titles.append(title)
                except Exception:
                    pass
            return True  # Must return True to instruct EnumWindows to continue enumeration.
        
        try:
            win32gui.EnumWindows(callback, None)
        except Exception:
            pass

        # Parse collected window titles to isolate track and artist details.
        for title in found_titles:
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                if len(parts) == 2:
                    # Strip trailing/leading whitespaces inherited from window title formatting.
                    return parts[0].strip(), parts[1].strip()
        
        if "TIDAL" in found_titles:
            return "PAUSED", None
        
        # If active PIDs exist but no matching windows are discovered, the process tree 
        # may have mutated (e.g., application restart). Clear cache to force a rescan.
        self.tidal_pids.clear() 
        return None, None

    def run(self):
        """Main execution loop managing state machine synchronization and IPC payload delivery."""
        print("Tidal RPC Script Started (Robust Connection Support).")
        
        while True:
            # 1. Connection state verification
            if self.rpc is None:
                clear()
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
                        # Optimization: Enforce delta-updates. Payloads are only transmitted 
                        # over the local pipe when a track transition occurs, saving network/CPU cycles.
                        if sig != self.last_track:
                            print(f"Now Playing: {track} by {artist}")
                            self.start_time = time.time()
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
                else:
                    # Clean up presence state if the player application is terminated.
                    if self.last_track is not None:
                        print("Tidal closed or not found.")
                        self.rpc.clear()
                        self.last_track = None
                        self.tidal_pids.clear()
            
            except (PipeClosed, InvalidID, AssertionError) as e:
                print(f"Connection lost ({e}). Resetting...")
                self.rpc = None
            except Exception as e:
                print(f"RPC Error: {e}. Resetting connection...")
                self.rpc = None

            # Rate-limiting execution frequency to prevent system resource saturation.
            time.sleep(15)

if __name__ == "__main__":
    CLIENT_ID = "" #Enter your Client ID from your Discord App here, or nothing happens
    bot = TidalRPC(CLIENT_ID)
    try:
        bot.run()
    except KeyboardInterrupt:
        print("Exiting...")
