$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    throw 'Create the environment first: py -m venv .venv'
}
& '.\.venv\Scripts\python.exe' -m flask --app app init-db
if ($LASTEXITCODE -ne 0) { throw 'Database setup failed. Run configure.py and check PostgreSQL.' }
& '.\.venv\Scripts\python.exe' -m flask --app app run --host 127.0.0.1 --port 5000
