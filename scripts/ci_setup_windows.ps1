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
        try {
            Invoke-WebRequest -Uri $Uri -OutFile $OutFile -UseBasicParsing
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
    $pythonInstaller = Join-Path $env:RUNNER_TEMP "python-3.11.9-amd64.exe"
    Download-File `
        -Uri "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe" `
        -OutFile $pythonInstaller

    $args = @(
        "/quiet",
        "InstallAllUsers=0",
        "TargetDir=$pythonDir",
        "Include_launcher=0",
        "PrependPath=0",
        "Include_test=0",
        "Shortcuts=0"
    )

    $process = Start-Process -FilePath $pythonInstaller -ArgumentList $args -Wait -PassThru
    if ($process.ExitCode -ne 0) {
        throw "Python installer failed with exit code $($process.ExitCode)"
    }
}

if (-not (Test-Path $uvExe)) {
    $uvZip = Join-Path $env:RUNNER_TEMP "uv-0.11.14-windows.zip"
    $uvExtract = Join-Path $env:RUNNER_TEMP "uv-0.11.14-windows"
    Remove-Item -Recurse -Force $uvExtract -ErrorAction SilentlyContinue

    Download-File `
        -Uri "https://github.com/astral-sh/uv/releases/download/0.11.14/uv-x86_64-pc-windows-msvc.zip" `
        -OutFile $uvZip

    Expand-Archive -LiteralPath $uvZip -DestinationPath $uvExtract -Force
    $downloadedUv = Get-ChildItem -Path $uvExtract -Filter "uv.exe" -Recurse | Select-Object -First 1
    if (-not $downloadedUv) {
        throw "uv.exe was not found in downloaded archive"
    }
    Copy-Item -Path $downloadedUv.FullName -Destination $uvExe -Force
}

Add-CiPath $pythonDir
Add-CiPath (Join-Path $pythonDir "Scripts")
Add-CiPath $uvDir

python --version
uv --version
