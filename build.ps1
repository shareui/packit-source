$ErrorActionPreference = "Stop"

if (-not (Get-Command zip -ErrorAction SilentlyContinue)) {
    Write-Host "zip не найден."

    if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
        Write-Host "Chocolatey не найден. Установить Chocolatey? (y/n)" -NoNewline
        $answer = Read-Host
        if ($answer -eq 'y') {
            Set-ExecutionPolicy Bypass -Scope Process -Force
            [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
            Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
        } else {
            Write-Error "Chocolatey не установлен. Установите zip вручную и повторите запуск."
            exit 1
        }
    }

    Write-Host "Установить zip через Chocolatey? (y/n)" -NoNewline
    $answer = Read-Host
    if ($answer -eq 'y') {
        choco install zip -y
    } else {
        Write-Error "zip не установлен. Установите zip и повторите запуск."
        exit 1
    }
}

$ADD_VERSION = $true
$ADD_PASSWORD = $true

$META = "packit/mf/meta.yml"
$PASSWORD = "oxf"

if (-not (Test-Path "packit")) {
    Write-Error "error: packit/ not found"
    exit 1
}

if (-not (Test-Path "refmap.yml")) {
    Write-Error "error: refmap.yml not found"
    exit 1
}

if (-not (Test-Path $META)) {
    Write-Error "error: $META not found"
    exit 1
}

$VERSION = (Get-Content $META | Where-Object { $_ -match '^version:' }) -replace 'version:\s*"', '' -replace '"', ''

if ($ADD_VERSION) {
    $BASE = $VERSION -replace '\.\d+$', ''
    $NUM = [int]($VERSION -replace '^.*\.', '')
    $NEW_VERSION = "$BASE.$($NUM + 1)"
    (Get-Content $META) -replace "^version: `"$VERSION`"", "version: `"$NEW_VERSION`"" | Set-Content $META
    $VERSION = $NEW_VERSION
    Write-Host "version bumped: $NEW_VERSION"
}

$OUTPUT_FILE = "packit-${VERSION}.eaf"

New-Item -ItemType Directory -Force -Path "builds" | Out-Null

if ($ADD_PASSWORD) {
    zip -P $PASSWORD -r "builds/$OUTPUT_FILE" packit refmap.yml
} else {
    zip -r "builds/$OUTPUT_FILE" packit refmap.yml
}

Write-Host "created: builds/$OUTPUT_FILE"
