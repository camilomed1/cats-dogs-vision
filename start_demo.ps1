<#
Starts the whole demo, each part in its own window:
  1 Backend (Flask + model + MongoDB + MQTT)   2 Web client   3 Camera station   4 Virtual ESP32   5 Mobile (Expo)

Usage (double-click start_demo.bat, or from PowerShell):
  .\start_demo.bat                      lab camera from camera_station\.env
  .\start_demo.bat -Camera webcam       laptop webcam instead
  .\start_demo.bat -Camera video        test video (no camera needed)
  .\start_demo.bat -WebSockets          MQTT over WebSockets (if the network blocks port 1883)
  .\start_demo.bat -Hotspot             phone connected to the laptop's Mobile Hotspot (Expo uses 192.168.137.1)
  .\start_demo.bat -Desktop             also open the desktop app
  .\start_demo.bat -NoMobile            do not start Expo
Close a window (or press Ctrl+C in it) to stop that part.
#>
param(
    [ValidateSet("lab", "webcam", "video")] [string]$Camera = "lab",
    [switch]$WebSockets,
    [switch]$Hotspot,
    [switch]$Desktop,
    [switch]$NoMobile,
    [switch]$DryRun
)

$root = $PSScriptRoot

function Start-Part($title, $folder, $command) {
    $full = "`$Host.UI.RawUI.WindowTitle = '$title'; Set-Location '$(Join-Path $root $folder)'; $command"
    if ($DryRun) { Write-Host "[$title] $full"; return }
    # -EncodedCommand avoids quoting problems with spaces and quotes inside the command
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($full))
    Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-EncodedCommand", $encoded
}

# --- checks
$mongo = Get-Service -Name MongoDB -ErrorAction SilentlyContinue
if (-not $mongo -or $mongo.Status -ne "Running") {
    Write-Host "WARNING: the MongoDB service is not running. Start it (services.msc > MongoDB > Start) or predictions will not be saved." -ForegroundColor Yellow
}
$ips = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" }).IPAddress
Write-Host "This PC's IP addresses: $($ips -join ', ')"

# --- shared settings
$mqtt = ""
if ($WebSockets) { $mqtt = "`$env:MQTT_TRANSPORT = 'websockets'; `$env:MQTT_PORT = '8083'; " }

$cameraEnv = switch ($Camera) {
    "webcam" { "`$env:CAMERA_URL = '0'; `$env:CAMERA_NAME = 'Laptop webcam'; " }
    "video"  { "`$env:CAMERA_URL = 'test_video.mp4'; `$env:CAMERA_NAME = 'Test video'; " }
    default  { "" }  # lab camera: CAMERA_URL from camera_station\.env
}

# --- start everything
Start-Part "1 Backend" "backend" "$mqtt.venv\Scripts\python app.py"
Start-Part "2 Web" "web" "npm run dev"
if ($Camera -eq "lab") {
    # Check the camera first, so a network problem is explained clearly before the station starts
    Start-Part "3 Camera station" "camera_station" "$mqtt.venv\Scripts\python check_camera.py; .venv\Scripts\python station.py"
} else {
    Start-Part "3 Camera station" "camera_station" "$mqtt$cameraEnv.venv\Scripts\python station.py"
}
Start-Part "4 Virtual ESP32" "iot" "$mqtt.venv\Scripts\python virtual_esp32.py"
if ($Desktop) { Start-Part "6 Desktop app" "desktop" ".venv\Scripts\python main.py" }
if (-not $NoMobile) {
    $expoHost = ""
    if ($Hotspot) { $expoHost = "`$env:REACT_NATIVE_PACKAGER_HOSTNAME = '192.168.137.1'; " }
    Start-Part "5 Mobile (Expo)" "mobile" "${expoHost}npx expo start"
}

if (-not $DryRun) {
    Write-Host "Started. The model takes about 10 seconds to load; then open http://localhost:5173" -ForegroundColor Green
    Start-Sleep -Seconds 12
    Start-Process "http://localhost:5173"
}
