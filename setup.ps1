[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$ToolsRoot = Join-Path $ProjectRoot "tools"
$FfmpegRoot = Join-Path $ToolsRoot "ffmpeg"
$FfmpegBin = Join-Path $FfmpegRoot "bin"
$FfmpegLocationFile = Join-Path $ToolsRoot "ffmpeg-location.txt"
$DenoRoot = Join-Path $ToolsRoot "deno"
$DenoExe = Join-Path $DenoRoot "deno.exe"

function Test-PythonCandidate {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [string[]]$Arguments = @()
    )
    try {
        $Output = @(& $Executable @Arguments -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>&1)
        if ($LASTEXITCODE -ne 0) { return $null }
        $Version = [string]$Output[-1]
        if ($Version -notmatch '^(\d+)\.(\d+)\.(\d+)$') { return $null }
        if ([int]$Matches[1] -ne 3 -or [int]$Matches[2] -lt 10) { return $null }
        return [PSCustomObject]@{
            Executable = $Executable
            Arguments = @($Arguments)
            Version = $Version
        }
    } catch {
        return $null
    }
}

function Find-CompatiblePython {
    $Seen = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($CommandName in @("python.exe", "python3.exe")) {
        $Candidates = @(Get-Command $CommandName -CommandType Application -All -ErrorAction SilentlyContinue)
        foreach ($Candidate in $Candidates) {
            $Path = $Candidate.Source
            if (-not $Seen.Add($Path)) { continue }
            $Result = Test-PythonCandidate -Executable $Path
            if ($Result) { return $Result }
        }
    }
    $Launchers = @(Get-Command py.exe -CommandType Application -All -ErrorAction SilentlyContinue)
    foreach ($Launcher in $Launchers) {
        $Result = Test-PythonCandidate -Executable $Launcher.Source -Arguments @("-3")
        if ($Result) { return $Result }
    }
    throw "Python 3.10 ou superior nao foi encontrado. Instale uma versao atual em https://www.python.org/downloads/ e tente novamente."
}

function Test-Executable {
    param([Parameter(Mandatory = $true)][string]$Path)
    try {
        $null = & $Path -version 2>&1
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Find-WorkingCommand {
    param([Parameter(Mandatory = $true)][string]$Name)
    $Commands = @(Get-Command $Name -CommandType Application -All -ErrorAction SilentlyContinue)
    foreach ($Command in $Commands) {
        if (Test-Executable -Path $Command.Source) { return $Command.Source }
    }
    return $null
}

function Test-FfmpegDirectory {
    param([Parameter(Mandatory = $true)][string]$Directory)
    $Ffmpeg = Join-Path $Directory "ffmpeg.exe"
    $Ffprobe = Join-Path $Directory "ffprobe.exe"
    return ((Test-Path -LiteralPath $Ffmpeg -PathType Leaf) -and
            (Test-Path -LiteralPath $Ffprobe -PathType Leaf) -and
            (Test-Executable -Path $Ffmpeg) -and
            (Test-Executable -Path $Ffprobe))
}

function Find-Ffmpeg {
    $FfmpegOnPath = Find-WorkingCommand -Name "ffmpeg.exe"
    $FfprobeOnPath = Find-WorkingCommand -Name "ffprobe.exe"
    if ($FfmpegOnPath -and $FfprobeOnPath) {
        return [PSCustomObject]@{ Source = "PATH"; Directory = $null; Ffmpeg = $FfmpegOnPath; Ffprobe = $FfprobeOnPath }
    }
    if (Test-FfmpegDirectory -Directory $FfmpegBin) {
        return [PSCustomObject]@{
            Source = "local"; Directory = $FfmpegBin
            Ffmpeg = Join-Path $FfmpegBin "ffmpeg.exe"
            Ffprobe = Join-Path $FfmpegBin "ffprobe.exe"
        }
    }
    if ($env:LOCALAPPDATA) {
        $WinGetRoot = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages"
        if (Test-Path -LiteralPath $WinGetRoot -PathType Container) {
            $WinGetFfmpeg = Get-ChildItem -LiteralPath $WinGetRoot -Filter "ffmpeg.exe" -File -Recurse -ErrorAction SilentlyContinue |
                Where-Object { $_.FullName -like "*Gyan.FFmpeg*\bin\ffmpeg.exe" } |
                Select-Object -First 1
            if ($WinGetFfmpeg -and (Test-FfmpegDirectory -Directory $WinGetFfmpeg.DirectoryName)) {
                return [PSCustomObject]@{
                    Source = "WinGet"; Directory = $WinGetFfmpeg.DirectoryName
                    Ffmpeg = $WinGetFfmpeg.FullName
                    Ffprobe = Join-Path $WinGetFfmpeg.DirectoryName "ffprobe.exe"
                }
            }
        }
    }
    return $null
}

function Test-Deno {
    param([Parameter(Mandatory = $true)][string]$Path)
    try {
        $Output = @(& $Path --version 2>&1)
        if ($LASTEXITCODE -ne 0 -or [string]$Output[0] -notmatch '^deno (\d+)\.(\d+)\.') { return $false }
        return ([int]$Matches[1] -gt 2 -or ([int]$Matches[1] -eq 2 -and [int]$Matches[2] -ge 3))
    } catch {
        return $false
    }
}

function Find-Deno {
    $Commands = @(Get-Command deno.exe -CommandType Application -All -ErrorAction SilentlyContinue)
    foreach ($Command in $Commands) {
        if (Test-Deno -Path $Command.Source) { return $Command.Source }
    }
    if ((Test-Path -LiteralPath $DenoExe -PathType Leaf) -and (Test-Deno -Path $DenoExe)) { return $DenoExe }
    return $null
}

function Install-LocalFfmpeg {
    $Architecture = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
    if ($Architecture -notin @("X64", "Arm64")) {
        throw "Download automatico do FFmpeg nao disponivel para arquitetura $Architecture. Instale FFmpeg e FFprobe manualmente no PATH."
    }
    if ($Architecture -eq "Arm64") { Write-Host "Aviso: no Windows ARM64 sera usada a build x64 por emulacao." }

    $Answer = Read-Host "FFmpeg e FFprobe nao foram encontrados. Deseja baixar uma copia local? [S/N]"
    if ($Answer.Trim().ToLowerInvariant() -notin @("s", "sim", "y", "yes")) {
        throw "Instalacao cancelada: FFmpeg e FFprobe sao necessarios para mesclar e converter midia."
    }

    $Archive = Join-Path $ToolsRoot "ffmpeg-release-essentials.zip"
    $Extracted = Join-Path $ToolsRoot "ffmpeg-extracted"
    $DownloadUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
    New-Item -ItemType Directory -Force -Path $ToolsRoot, $FfmpegBin | Out-Null
    if (Test-Path -LiteralPath $Archive) { Remove-Item -LiteralPath $Archive -Force }
    if (Test-Path -LiteralPath $Extracted) { Remove-Item -LiteralPath $Extracted -Recurse -Force }

    try {
        $Downloaded = $false
        for ($Attempt = 1; $Attempt -le 3; $Attempt++) {
            try {
                Write-Host "Baixando FFmpeg (tentativa $Attempt de 3)..."
                Invoke-WebRequest -Uri $DownloadUrl -OutFile $Archive -UseBasicParsing -TimeoutSec 120
                $Downloaded = $true
                break
            } catch {
                if (Test-Path -LiteralPath $Archive) { Remove-Item -LiteralPath $Archive -Force }
                if ($Attempt -eq 3) {
                    throw "Falha ao baixar FFmpeg. Verifique a internet, proxy ou firewall. Detalhes: $($_.Exception.Message)"
                }
                Start-Sleep -Seconds 2
            }
        }
        if (-not $Downloaded) { throw "O download do FFmpeg nao foi concluido." }
        Expand-Archive -LiteralPath $Archive -DestinationPath $Extracted -Force
        $ExtractedBin = Get-ChildItem -LiteralPath $Extracted -Recurse -Directory |
            Where-Object { Test-FfmpegDirectory -Directory $_.FullName } |
            Select-Object -First 1
        if (-not $ExtractedBin) { throw "A build baixada nao contem FFmpeg e FFprobe validos." }
        Copy-Item -LiteralPath (Join-Path $ExtractedBin.FullName "ffmpeg.exe") -Destination $FfmpegBin -Force
        Copy-Item -LiteralPath (Join-Path $ExtractedBin.FullName "ffprobe.exe") -Destination $FfmpegBin -Force
        if (-not (Test-FfmpegDirectory -Directory $FfmpegBin)) { throw "FFmpeg foi extraido, mas nao passou na verificacao de execucao." }
        Write-Host "FFmpeg instalado localmente em: $FfmpegBin"
    } finally {
        if (Test-Path -LiteralPath $Archive) { Remove-Item -LiteralPath $Archive -Force }
        if (Test-Path -LiteralPath $Extracted) { Remove-Item -LiteralPath $Extracted -Recurse -Force }
    }
}

function Install-LocalDeno {
    $Architecture = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
    if ($Architecture -eq "X64") {
        $Asset = "deno-x86_64-pc-windows-msvc.zip"
    } elseif ($Architecture -eq "Arm64") {
        $Asset = "deno-aarch64-pc-windows-msvc.zip"
    } else {
        throw "Download automatico do Deno nao disponivel para arquitetura $Architecture."
    }

    $Answer = Read-Host "Deno 2.3+ nao foi encontrado. Deseja baixar uma copia local para o yt-dlp? [S/N]"
    if ($Answer.Trim().ToLowerInvariant() -notin @("s", "sim", "y", "yes")) {
        Write-Host "Deno nao sera instalado. Downloads do YouTube podem ficar limitados."
        return $false
    }

    $Archive = Join-Path $ToolsRoot "deno.zip"
    $DownloadUrl = "https://github.com/denoland/deno/releases/latest/download/$Asset"
    New-Item -ItemType Directory -Force -Path $ToolsRoot, $DenoRoot | Out-Null
    if (Test-Path -LiteralPath $Archive) { Remove-Item -LiteralPath $Archive -Force }

    try {
        for ($Attempt = 1; $Attempt -le 3; $Attempt++) {
            try {
                Write-Host "Baixando Deno (tentativa $Attempt de 3)..."
                Invoke-WebRequest -Uri $DownloadUrl -OutFile $Archive -UseBasicParsing -TimeoutSec 120
                break
            } catch {
                if (Test-Path -LiteralPath $Archive) { Remove-Item -LiteralPath $Archive -Force }
                if ($Attempt -eq 3) {
                    throw "Falha ao baixar Deno. Verifique a internet, proxy ou firewall. Detalhes: $($_.Exception.Message)"
                }
                Start-Sleep -Seconds 2
            }
        }
        Expand-Archive -LiteralPath $Archive -DestinationPath $DenoRoot -Force
        if (-not (Test-Deno -Path $DenoExe)) { throw "Deno foi extraido, mas nao passou na verificacao ou e anterior a 2.3." }
        Write-Host "Deno instalado localmente em: $DenoExe"
    } finally {
        if (Test-Path -LiteralPath $Archive) { Remove-Item -LiteralPath $Archive -Force }
    }
    return $true
}

Set-Location $ProjectRoot
if (Test-Path -LiteralPath $VenvPython -PathType Leaf) {
    $VenvInfo = Test-PythonCandidate -Executable $VenvPython
    if (-not $VenvInfo) { throw "A .venv existente usa um Python incompativel ou danificado. Remova a pasta .venv e execute run.bat novamente." }
    Write-Host "Usando ambiente virtual existente com Python $($VenvInfo.Version)."
} else {
    $PythonCommand = Find-CompatiblePython
    Write-Host "Python $($PythonCommand.Version) encontrado em: $($PythonCommand.Executable)"
    Write-Host "Criando ambiente virtual em .venv..."
    $PythonArgs = @($PythonCommand.Arguments)
    $PythonExe = $PythonCommand.Executable
    & $PythonExe @PythonArgs -m venv ".venv"
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $VenvPython)) { throw "Nao foi possivel criar o ambiente virtual. Verifique se o modulo venv esta instalado." }
}

Write-Host "Instalando o projeto e o yt-dlp..."
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Nao foi possivel atualizar o pip. Verifique a conexao, proxy ou firewall." }
& $VenvPython -m pip install .
if ($LASTEXITCODE -ne 0) { throw "Nao foi possivel instalar o projeto. Verifique as mensagens do pip acima." }

$FfmpegInfo = Find-Ffmpeg
if (-not $FfmpegInfo) {
    Install-LocalFfmpeg
    $FfmpegInfo = Find-Ffmpeg
}
if (-not $FfmpegInfo) { throw "FFmpeg e FFprobe continuam indisponiveis apos a instalacao." }

if ($FfmpegInfo.Source -eq "WinGet" -and $FfmpegInfo.Directory) {
    New-Item -ItemType Directory -Force -Path $ToolsRoot | Out-Null
    Set-Content -LiteralPath $FfmpegLocationFile -Value $FfmpegInfo.Directory -Encoding UTF8
} elseif (Test-Path -LiteralPath $FfmpegLocationFile) {
    Remove-Item -LiteralPath $FfmpegLocationFile -Force
}

Write-Host "FFmpeg validado ($($FfmpegInfo.Source)): $($FfmpegInfo.Ffmpeg)"
Write-Host "FFprobe validado ($($FfmpegInfo.Source)): $($FfmpegInfo.Ffprobe)"

$DenoPath = Find-Deno
if (-not $DenoPath) {
    $null = Install-LocalDeno
    $DenoPath = Find-Deno
}
if ($DenoPath) {
    Write-Host "Deno validado: $DenoPath"
} else {
    Write-Host "Aviso: Deno 2.3+ indisponivel; outras plataformas continuam utilizaveis."
}
Write-Host ""
Write-Host "Instalacao concluida. Execute .\run.bat"
