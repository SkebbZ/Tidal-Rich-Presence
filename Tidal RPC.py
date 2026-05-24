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
    os.system('cls' if os.name == 'nt' else 'clear')

class TidalRPC:
    def __init__(self, client_id):
        self.client_id = client_id
        self.rpc = None
        self.last_track = None
        self.start_time = None
        self.tidal_pids = []

    def connect_discord(self):
        """
        Attempts to connect. Only assigns self.rpc if successful.
        """
        try:
            # Create a new instance
            client = Presence(self.client_id)
            client.connect()
            
            # Only if the line above succeeds, do we assign it
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
        """Finds ALL Process IDs associated with Tidal."""
        self.tidal_pids = []
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] and "tidal" in proc.info['name'].lower():
                    self.tidal_pids.append(proc.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    def get_current_track(self):
        # 1. If we don't have PIDs, find them.
        if not self.tidal_pids:
            self.refresh_tidal_pids()
        
        # If still no PIDs, Tidal isn't running.
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
                except:
                    pass
        
        try:
            win32gui.EnumWindows(callback, None)
        except Exception:
            pass

        # 2. Parse Titles
        # Look for "Song - Artist" format
        for title in found_titles:
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                if len(parts) == 2:
                    return parts[0], parts[1] # Track, Artist
        
        # 3. If we found "TIDAL" but no song info, it's paused.
        if "TIDAL" in found_titles:
            return "PAUSED", None
        
        # 4. If we found nothing, maybe PIDs changed (Tidal restarted). 
        # Clear PIDs so we scan for new ones next loop.
        self.tidal_pids = [] 
        return None, None

    def run(self):
        print("Tidal RPC Script Started (Robust Connection Support).")
        
        while True:
            # ---------------------------------------------------------
            # 1. CONNECTION CHECK
            # ---------------------------------------------------------
            if self.rpc is None:
                print("Attempting to connect to Discord...")
                if not self.connect_discord():
                    # If connect fails, wait 10s and try again. 
                    # Don't run the rest of the loop.
                    time.sleep(10)
                    continue

            # ---------------------------------------------------------
            # 2. GET TRACK INFO
            # ---------------------------------------------------------
            track, artist = self.get_current_track()

            # ---------------------------------------------------------
            # 3. UPDATE PRESENCE
            # ---------------------------------------------------------
            try:
                if track and artist:
                    if track == "PAUSED":
                        if self.last_track != "PAUSED":
                            print("Tidal is Paused.")
                            self.rpc.clear()
                            self.last_track = "PAUSED"
                    else:
                        # It's a real song
                        sig = f"{track}-{artist}"
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
                    # Tidal not found or closed
                    if self.last_track is not None:
                        print("Tidal closed or not found.")
                        self.rpc.clear()
                        self.last_track = None
                        self.tidal_pids = [] # Force refresh PIDs
            
            except (PipeClosed, InvalidID, AssertionError) as e:
                # This catches the specific Discord disconnect errors
                print(f"Connection lost ({e}). Resetting...")
                self.rpc = None
            except Exception as e:
                # This catches 'You must connect your client' or other generic errors
                print(f"RPC Error: {e}. Resetting connection...")
                self.rpc = None

            time.sleep(15)

if __name__ == "__main__":
    CLIENT_ID = ""
    bot = TidalRPC(CLIENT_ID)
    try:
        bot.run()
    except KeyboardInterrupt:
        print("Exiting...")
