$ErrorActionPreference = "Stop"

$toolsDir = Join-Path $env:GITHUB_WORKSPACE ".ci-tools"
$pythonDir = Join-Path $toolsDir "Python311"
$uvDir = Join-Path $toolsDir "uv"
$pythonExe = Join-Path $pythonDir "python.exe"
$uvExe = Join-Path $uvDir "uv.exe"

New-Item -ItemType Directory -Force -Path $toolsDir, $pythonDir, $uvDir | Out-Null

function Add-CiPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    $env:PATH = "$Path;$env:PATH"
    $Path >> $env:GITHUB_PATH
}

function Download-File {
    param(
        [Parameter(Mandatory = $true)][string]$Uri,
        [Parameter(Mandatory = $true)][string]$OutFile
    )

    for ($attempt = 1; $attempt -le 3; $attempt++) {
        Write-Host "Downloading $Uri (attempt $attempt/3)"
        Remove-Item -Force $OutFile -ErrorAction SilentlyContinue
        try {
            if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
                & curl.exe -L --fail --silent --show-error --retry 2 --connect-timeout 20 --max-time 300 -o $OutFile $Uri
                if ($LASTEXITCODE -ne 0) {
                    throw "curl.exe failed with exit code $LASTEXITCODE"
                }
            } else {
                Invoke-WebRequest -Uri $Uri -OutFile $OutFile -UseBasicParsing -TimeoutSec 300
            }
            return
        } catch {
            if ($attempt -eq 3) {
                throw
            }
            Start-Sleep -Seconds (5 * $attempt)
        }
    }
}

if (-not (Test-Path $pythonExe)) {
    $pythonPackage = Join-Path $env:RUNNER_TEMP "python-3.11.9-nuget.zip"
    $pythonExtract = Join-Path $env:RUNNER_TEMP "python-3.11.9-nuget"
    Remove-Item -Recurse -Force $pythonExtract -ErrorAction SilentlyContinue

    Write-Host "Installing portable Python 3.11.9"
    Download-File `
        -Uri "https://www.nuget.org/api/v2/package/python/3.11.9" `
        -OutFile $pythonPackage

    Write-Host "Extracting portable Python"
    Expand-Archive -LiteralPath $pythonPackage -DestinationPath $pythonExtract -Force
    $downloadedPython = Join-Path $pythonExtract "tools\python.exe"
    if (-not (Test-Path $downloadedPython)) {
        throw "python.exe was not found in downloaded Python package"
    }

    Remove-Item -Recurse -Force $pythonDir -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $pythonDir | Out-Null
    Copy-Item -Path (Join-Path $pythonExtract "tools\*") -Destination $pythonDir -Recurse -Force
} else {
    Write-Host "Using cached portable Python at $pythonDir"
}

if (-not (Test-Path $uvExe)) {
    $uvZip = Join-Path $env:RUNNER_TEMP "uv-0.11.14-windows.zip"
    $uvExtract = Join-Path $env:RUNNER_TEMP "uv-0.11.14-windows"
    Remove-Item -Recurse -Force $uvExtract -ErrorAction SilentlyContinue

    Write-Host "Installing portable uv 0.11.14"
    Download-File `
        -Uri "https://github.com/astral-sh/uv/releases/download/0.11.14/uv-x86_64-pc-windows-msvc.zip" `
        -OutFile $uvZip

    Write-Host "Extracting portable uv"
    Expand-Archive -LiteralPath $uvZip -DestinationPath $uvExtract -Force
    $downloadedUv = Get-ChildItem -Path $uvExtract -Filter "uv.exe" -Recurse | Select-Object -First 1
    if (-not $downloadedUv) {
        throw "uv.exe was not found in downloaded archive"
    }
    Copy-Item -Path $downloadedUv.FullName -Destination $uvExe -Force
} else {
    Write-Host "Using cached uv at $uvDir"
}

Add-CiPath $pythonDir
Add-CiPath (Join-Path $pythonDir "Scripts")
Add-CiPath $uvDir

python --version
uv --version
