#SingleInstance Force
Persistent()

global hBatFile := 0
global pid := 0

; Setup Tray icon and menu items - replace path to icon with your own
TraySetIcon("C:\Users\USERNAME\Tidal RPC\RPCapp.ico")
A_TrayMenu.Add("Show / Hide TIDAL_RPC", TrayClick)
A_TrayMenu.Add("Close TIDAL_RPC", CloseItem)
A_TrayMenu.Default := "Show / Hide TIDAL_RPC"

; Run program or batch file hidden
DetectHiddenWindows(true)

; Output var uses reference (&pid) in v2 - replace path with your own
Run('"C:\Users\USERNAME\Tidal RPC\pingu.bat"', , "Hide", &pid)

if WinWait("ahk_pid " pid, , 5) {
    hBatFile := WinExist()
}
DetectHiddenWindows(false)


; --- Callbacks & Functions ---

TrayClick(ItemName, ItemPos, MyMenu) {
    OnTrayClick()
}

OnTrayClick() {
    if !hBatFile
        return

    if DllCall("IsWindowVisible", "Ptr", hBatFile) {
        WinHide(hBatFile)
    } else {
        WinShow(hBatFile)
        WinActivate(hBatFile)
    }
}

CloseItem(ItemName, ItemPos, MyMenu) {
    DetectHiddenWindows(true)
    
    ; Target specific PID rather than any generic cmd.exe
    if pid && ProcessExist(pid) {
        ProcessClose(pid)
    } else {
        ProcessClose("cmd.exe")
    }
    
    ExitApp()
}