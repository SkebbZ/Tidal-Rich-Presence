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

from pypresence import Presence, InvalidID
from os import system, name
from time import sleep
import sys
import psutil
import win32gui
import win32process

# Application ID (Enter yours here).
client_id = "0000000000000000000"
discord_alive = False
discord_connected = False
RPC = Presence(client_id)
tidal_paused = True
tidal_alive = False

# Returns a list of windows related to the passed process ID.
def get_windows_by_pid(pid):
    pid_windows = []

    def callback(hwnd, hwnds):
        _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
        if win32gui.IsWindowVisible(hwnd) and pid == found_pid:
            hwnds.append(hwnd)
        return True

    win32gui.EnumWindows(callback, pid_windows)
    return pid_windows


def get_tidal_info():
    tidal_processes = []
    all_titles = []

    # Finds all processes related to TIDAL.
    for process in psutil.process_iter(attrs=['pid', 'name']):
        try:
            if "tidal" in process.info['name'].lower():
                tidal_processes.append(process.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    # Finds GUI windows related to each PID, if they exist.
    for tidal_process_id in tidal_processes:
        windows = get_windows_by_pid(tidal_process_id)
        # If a PID has a GUI window, add its title to the titles list.
        for w in windows:
            window_text = win32gui.GetWindowText(w)
            if window_text:
                all_titles.append(window_text)

    # Process titles to extract song information.
    if all_titles:
        song_info = all_titles[0].split(" - ")
        if len(song_info) >= 2:
            return song_info[0], song_info[1]

    return None, None
    
# If Discord was closed, safety check to see if it's running again before attempting to reconnect. Otherwise it crashes with PipeClosed exception.
def processRunning(processName):
    #print("Debug: looking for process " + processName, end='\n')
    # Iterate over the all the running process
    for p in psutil.process_iter(['name']):
        try:
            # Check if process name contains the given name string.
            if processName.lower() in p.info['name'].lower():
                #print("Debug: " + processName + " found!", end='\n')
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    #print("Debug: " + processName + " NOT found!", end='\n')
    return False;

# OS independent clear screen function.
def clear():
 
    # for windows
    if name == 'nt':
        _ = system('cls')
 
    # for mac and linux(here, os.name is 'posix')
    else:
        _ = system('clear')

# Checks if Discord is running and connects to the rich presence application, otherwise goes to sleep for 60 seconds and retries.
def connectDiscord():
    global discord_connected
    global RPC
    while not discord_connected:
        try:
            RPC.connect()
        # Notify the user if their entered client ID is invalid.
        except InvalidID:
            print("Invalid client ID. Please check the entered value in the code.")
            sleep(5)
            quit(1)
        except Exception:
            print("Discord not running, going to sleep for one minute.", end='\n')
            try:
                print("Hit CTRL-C if you want to terminate the script.", end='\n')
                sleep(60)
                clear()
            except KeyboardInterrupt:
                quit(0)
        else: discord_connected = True
        
def waitForTidal():
    global tidal_alive
    while not tidal_alive:
        clear()
        print("Tidal not running, going to sleep for one minute.", end='\n')
        try:
            print("Hit CTRL-C if you want to terminate the script.", end='\n')
            sleep(60)
            tidal_alive = processRunning("tidal")
        except KeyboardInterrupt:
            quit(0)
    clear()
    print("TIDAL is now running!", end='\n')

# Handles the updating of rich presence information while both TIDAL and Discord are found
def updateRPC():
    global RPC
    global details
    global tidal_alive
    tidal_alive = processRunning("tidal")
    if tidal_alive:
        RPC.update(
            state=f"by {details[1]}",
            details=details[0],
            large_image="tidallogo",
            large_text="TIDAL",
            small_image="hra",
            small_text="Streaming lossless in up to 24-bit 192kHz."
        )
        print("Rich presence successfully updated!", end='\n')
    else: print("Tidal process not found.", end='\n')
    
# Function to set the rich presence status to Paused when TIDAL is no longer playing or info can't be found
def pauseRPC():
    global RPC
    global tidal_alive
    global tidal_paused
    tidal_alive = processRunning("tidal")
    if tidal_alive:
        RPC.update(
            details="Paused",
            large_image="tidallogo",
            large_text="TIDAL"
        )
        print("Streaming paused or window closed...", end='\n')
        print("Rich presence set to Paused.", end='\n')
        tidal_paused = True
    else: print("Tidal process not found.", end='\n')
    
# Function to terminate the script, usually called from KeyboardInterrupt exception
def quit(code):
    print("Script terminated by user. Exiting.", end='\n')
    sleep(1)
    try:
        RPC.close()
        print("Successfully closed socket.", end='\n')
        sleep(1)
        sys.exit(code)
    except Exception:
        sys.exit(code)

# Call the function to attempt to connect to Discord
connectDiscord()
# Update your status every 15 seconds (to stay within rate limits).
while True:
    discord_alive = processRunning("discord")
    if not discord_alive:
        print("Discord process not found, closing socket and reconnecting in 15 seconds...", end='\n')
        RPC.close()
        discord_connected = False
        sleep(15)
        connectDiscord()
    tidal_alive = processRunning("tidal")
    if tidal_alive:
        try:
            #print("Debug: TIDAL is running!", end='\n')
            # Attempt to get info from TIDAL
            details = get_tidal_info()
            if details[0] and details[1]:
                #print("Debug: TIDAL is playing, successfully retrieved track info...", end='\n')
                tidal_paused = False
            else:
                #print("Debug: Unable to get song information.", end='\n')
                discord_alive = processRunning("discord")
                if discord_alive and discord_connected:
                    pauseRPC()
                elif discord_alive and not discord_connected:
                    discord_connected = False
                    clear()
                    print("Discord connection lost, attempting to reconnect.", end='\n')
                    connectDiscord()
                    print("Discord connection restored! Updating on the next cycle.", end='\n')
                else:
                    print("Discord process not found or not connected.", end='\n')
                    tidal_paused = True
        # A catch all exception. The program should continue attempting to find the TIDAL window
        # and maintain its Discord connection under all circumstances.
        except Exception:
            print("Unable to get song information.", end='\n')
            discord_alive = processRunning("discord")
            if discord_alive and discord_connected:
                pauseRPC()
            else:
                print("Discord process not found or not connected.", end='\n')
                tidal_paused = True
    else:
        #print("Debug: Tidal process not found.", end='\n')
        RPC.close()
        discord_connected = False
        tidal_paused = True
        waitForTidal()
        connectDiscord()
        print("Discord connection restored! Updating on the next cycle.", end='\n')
    if not tidal_paused:
        try:
            discord_alive = processRunning("discord")
            if discord_alive and discord_connected:
                #print("Debug: Attempting to update Rich presence...", end='\n')
                updateRPC()
            else:
                discord_connected = False
                clear()
                print("Discord connection lost, attempting to reconnect.", end='\n')
                connectDiscord()
                print("Discord process now found! Updating on the next cycle.", end='\n')
        except Exception:
            discord_connected = False
            clear()
            print("Discord connection lost or Discord closed, attempting to reconnect.", end='\n')
            connectDiscord()
            print("Discord process now found! Updating on the next cycle.", end='\n')
    try:
        # MUST be no less than 15 seconds to remain within Discord rate limits.
        print("Sleeping for 15 seconds. Hit CTRL-C if you want to terminate the script.", end='\n')
        sleep(15)
        clear()
    # Terminate properly on user CTRL-C
    except KeyboardInterrupt:
        quit(0)
