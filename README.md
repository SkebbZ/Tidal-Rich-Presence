# Python-based Rich Presence for TIDAL

Neither I nor this program are affiliated with TIDAL or Discord in any way.  
TIDAL, the wordmark, and logo are registered trademarks of TIDAL Music AS.

A lightweight Discord Rich Presence integration for TIDAL on Windows. Displays your current track, artist, high-fidelity badges, and album artwork on your Discord profile.

---

## 1. Discord Application Setup (Required for All Methods)

Before running the application (either as an `.exe` or from source code), you must create a Discord Application to host your Rich Presence artwork assets:

1. Head to the [Discord Developer Portal](https://discord.com/developers/applications) and sign in.
2. Click **New Application**.
3. Under **General Information**, set the Application Name to `TIDAL` *(this name will display on your Discord profile as "Playing TIDAL")*.
4. Copy your **Application ID / Client ID** shown under General Information.
5. In the left menu, navigate to **Rich Presence** > **Art Assets**.
6. Upload the two image assets (`hra` and `tidallogo`) included in the repository assets or release `.zip`:
   > ⚠️ **Important:** Do **NOT** rename these image files! The script explicitly calls `hra` and `tidallogo`.
7. Click **Save Changes**.

---

## 2. Installation & Usage Options

Choose **Option A** if you want a ready-to-use standalone executable, or **Option B** if you want to run or modify the Python source code directly.

### Option A: Pre-Built Executable (Easiest — No Python Required)

1. Download the latest version from the [Releases Page](https://github.com/SkebbZ/Tidal-Rich-Presence/releases):
   * **`TidalRPC_Setup.exe`** *(Installer — Recommended)*: Installs to `Program Files`, creates Start Menu/Desktop shortcuts, and includes an uninstaller.
   * **`TidalRPC.exe`** *(Portable)*: Single executable file that can be placed and run from any folder.
2. Launch **TIDAL RPC**.
3. Paste your copied **Discord Client ID** into the top text box and click **Save**.
4. Play music on the TIDAL desktop application!

---

### Option B: Running from Python Source Code (.py)

#### 1. Install Dependencies
Open your terminal or command prompt and install the required Python packages:

```bash
# Core requirements (CLI version)
python -m pip install pypresence psutil pywin32

# Additional requirements (GUI version)
python -m pip install PySimpleGUI psgtray
```

#### 2. Running the CLI Script
1. Clone or download this repository.
2. Open `Tidal RPC.py` in a text editor and paste your Application ID into the `CLIENT_ID` variable:
   ```python
   CLIENT_ID = "YOUR_DISCORD_CLIENT_ID_HERE"
   ```
3. Run the script:
   ```cmd
   python "Tidal RPC.py"
   ```

#### 3. Running the GUI Script
1. Run the GUI script:
   ```cmd
   python "Tidal RPC GUI.py"
   ```
2. Paste your **Discord Client ID** into the top text box and click **Save** *(this automatically saves to `config.json` for future launches)*.

---

> ℹ️ **Important Window Note:**  
> TIDAL must remain open on your system for metadata enumeration. It can sit in the background behind other windows, but it **cannot** be minimized to the system tray or completely closed.

---

## Running Source Scripts in the Background via AutoHotkey (Optional)

If running raw Python scripts directly, you can launch them silently in the background using a batch script and the included AutoHotkey v2 wrapper script (`TIDAL RPC.ahk`).

1. Create a batch file (e.g., `run_tidal_rpc.bat`) to launch your script:
   ```bat
   @echo off
   python "C:\path\to\Tidal RPC GUI.py"
   ```

2. Download [`TIDAL RPC.ahk`](https://github.com/SkebbZ/Tidal-Rich-Presence/blob/main/TIDAL%20RPC.ahk) from this repository.

3. Open `TIDAL RPC.ahk` in a text editor and update the paths to match your local setup:
   ```autohotkey
   ; Update the icon path
   TraySetIcon("C:\path\to\your\RPCapp.ico")

   ; Update the path to your batch file
   Run('"C:\path\to\your\run_tidal_rpc.bat"', , "Hide", &pid)
   ```

4. Compile the script using **Ahk2Exe** *(Set `Compression: NONE` to prevent false-positive security flags)*.

![AHK Compiler Settings](https://i.ibb.co/wNtdVRCR/image.png)

5. Run the compiled executable, or place a shortcut to it in your Windows Startup folder (`Win + R` -> type `shell:startup`).

---

## Media & Previews

**Rich Presence Preview:**

![Project in Action](https://aejae.github.io/img/tidal-rp-media.png)

**GUI Preview:**

![GUI version](https://i.ibb.co/yh4zM01/bilde.png)

**System Tray & Notifications Preview:**

![Notification and hide in system tray](https://i.ibb.co/WtX0zFP/bilde.png)

---

## Credits
Project maintained by AJSF ([@AeJae](https://github.com/AeJae))  
[![Logo](https://aejae.github.io/img/logo.png)](https://aejae.github.io/)