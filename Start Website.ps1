param([switch]$NoBrowser, [switch]$NoDialog)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$url = 'http://127.0.0.1:5002/packages'
$python = Join-Path $root '.venv\Scripts\python.exe'
$logFolder = Join-Path $root 'instance\launcher'
$mutex = New-Object System.Threading.Mutex($false, 'Local\DirkRossWebsiteLauncher5002')
$locked = $false
$http = $null

function Test-Website {
    try {
        $html = $http.GetStringAsync($url).GetAwaiter().GetResult()
        return $html.Contains('/static/images/dirk-ross-logo.jpg') -and $html.Contains('Dirk Ross')
    } catch { return $false }
}

function Test-Port {
    $socket = New-Object System.Net.Sockets.TcpClient
    try {
        $connection = $socket.ConnectAsync('127.0.0.1', 5002)
        return $connection.Wait(500) -and $socket.Connected
    } catch { return $false }
    finally { $socket.Dispose() }
}

try {
    Add-Type -AssemblyName System.Net.Http
    $handler = New-Object System.Net.Http.HttpClientHandler
    $handler.UseProxy = $false
    $http = New-Object System.Net.Http.HttpClient($handler)
    $http.Timeout = [TimeSpan]::FromSeconds(2)
    try { $locked = $mutex.WaitOne(0) }
    catch [System.Threading.AbandonedMutexException] { $locked = $true }

    if ($locked -and -not (Test-Website)) {
        if (Test-Port) {
            throw 'Port 5002 is in use, but the website is not responding correctly. No other program was stopped. Check PostgreSQL and the website server before trying again.'
        }
        if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
            throw 'The website Python environment is missing. Restore .venv in the website folder before starting.'
        }
        New-Item -ItemType Directory -Path $logFolder -Force | Out-Null
        Start-Process -FilePath $python -ArgumentList '-m flask --app app run --host 127.0.0.1 --port 5002 --no-reload' -WorkingDirectory $root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logFolder 'server-output.log') -RedirectStandardError (Join-Path $logFolder 'server-error.log') | Out-Null
    }

    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    $ready = Test-Website
    while (-not $ready -and $timer.Elapsed.TotalSeconds -lt 90) {
        Start-Sleep -Milliseconds 700
        $ready = Test-Website
    }
    if (-not $ready) {
        throw "The website did not become ready. Check that PostgreSQL is running. Startup logs are in $logFolder. Your database was not reset."
    }
    if (-not $NoBrowser) { Start-Process $url }
    Write-Output "Website ready: $url"
} catch {
    $message = $_.Exception.Message
    if (-not $NoDialog) {
        Add-Type -AssemblyName System.Windows.Forms
        [System.Windows.Forms.MessageBox]::Show($message, 'Start Website', 'OK', 'Error') | Out-Null
    }
    Write-Error $message -ErrorAction Continue
    exit 1
} finally {
    if ($http) { $http.Dispose() }
    if ($locked) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
