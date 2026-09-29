[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$FfmpegRoot = Join-Path $ProjectRoot "tools\ffmpeg"
$FfmpegBin = Join-Path $FfmpegRoot "bin"

function Find-Python {
    $Python = Get-Command python -ErrorAction SilentlyContinue
    if ($Python) {
        & $Python.Source --version 2>$null
        if ($LASTEXITCODE -eq 0) { return @($Python.Source) }
    }

    $Launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($Launcher) {
        & $Launcher.Source -3 --version 2>$null
        if ($LASTEXITCODE -eq 0) { return @($Launcher.Source, "-3") }
    }

    throw "Python 3 nao foi encontrado. Instale-o em https://www.python.org/downloads/ e tente novamente."
}

function Install-LocalFfmpeg {
    Write-Host "FFmpeg/FFprobe nao encontrados no PATH. Baixando uma build local..."
    $ToolsRoot = Split-Path $FfmpegRoot -Parent
    $Archive = Join-Path $ToolsRoot "ffmpeg-release-essentials.zip"
    $Extracted = Join-Path $ToolsRoot "ffmpeg-extracted"
    $DownloadUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

    New-Item -ItemType Directory -Force -Path $ToolsRoot, $FfmpegBin | Out-Null
    Invoke-WebRequest -Uri $DownloadUrl -OutFile $Archive -UseBasicParsing
    Expand-Archive -LiteralPath $Archive -DestinationPath $Extracted -Force

    $ExtractedBin = Get-ChildItem -LiteralPath $Extracted -Recurse -Directory |
        Where-Object { $_.Name -eq "bin" -and (Test-Path (Join-Path $_.FullName "ffmpeg.exe")) } |
        Select-Object -First 1

    if (-not $ExtractedBin) {
        throw "A build baixada nao contem ffmpeg.exe na estrutura esperada."
    }

    Copy-Item -LiteralPath (Join-Path $ExtractedBin.FullName "ffmpeg.exe") -Destination $FfmpegBin -Force
    Copy-Item -LiteralPath (Join-Path $ExtractedBin.FullName "ffprobe.exe") -Destination $FfmpegBin -Force

    Remove-Item -LiteralPath $Archive -Force
    Remove-Item -LiteralPath $Extracted -Recurse -Force
    Write-Host "FFmpeg instalado localmente em: $FfmpegBin"
}

Set-Location $ProjectRoot
$PythonCommand = @(Find-Python)

if (-not (Test-Path $VenvPython)) {
    Write-Host "Criando ambiente virtual em .venv..."
    $PythonArgs = @($PythonCommand | Select-Object -Skip 1)
    $PythonExe = $PythonCommand[0]
    & $PythonExe @PythonArgs -m venv ".venv"
    if ($LASTEXITCODE -ne 0) { throw "Nao foi possivel criar o ambiente virtual." }
}

Write-Host "Instalando o projeto..."
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Nao foi possivel atualizar o pip." }
& $VenvPython -m pip install .
if ($LASTEXITCODE -ne 0) { throw "Nao foi possivel instalar o projeto." }

$FfmpegOnPath = Get-Command ffmpeg -ErrorAction SilentlyContinue
$FfprobeOnPath = Get-Command ffprobe -ErrorAction SilentlyContinue
if (-not ($FfmpegOnPath -and $FfprobeOnPath)) {
    if (-not ((Test-Path (Join-Path $FfmpegBin "ffmpeg.exe")) -and (Test-Path (Join-Path $FfmpegBin "ffprobe.exe")))) {
        Install-LocalFfmpeg
    } else {
        Write-Host "Usando FFmpeg local existente em: $FfmpegBin"
    }
} else {
    Write-Host "FFmpeg e FFprobe encontrados no PATH."
}

Write-Host ""
Write-Host "Instalacao concluida. Execute .\run.bat"

