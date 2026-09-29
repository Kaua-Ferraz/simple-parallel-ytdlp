# Parallel yt-dlp

Downloader interativo de vídeos e playlists que executa vários downloads em paralelo.

## Uso no Windows

Execute `run.bat`. Na primeira execução, ele pergunta se você deseja instalar o projeto. Se você confirmar, o script cria `.venv`, instala as dependências e, quando necessário, baixa FFmpeg e FFprobe para `tools/ffmpeg/`. Ele aguarda o término da instalação e permite tentar novamente se ocorrer algum erro.

Também é possível executar a instalação manualmente pelo PowerShell:

```powershell
.\setup.ps1
```

Depois, execute normalmente:

```bat
run.bat
```

Nenhum dos scripts altera permanentemente o `PATH` do Windows.

Os arquivos são salvos em `downloads/`.

## Compatibilidade

- Windows 10 ou 11.
- Python 3.10 ou superior. O instalador testa as versões disponíveis e escolhe uma compatível.
- Windows x64; no Windows ARM64, a build x64 do FFmpeg é usada por emulação.

O instalador valida Python, FFmpeg e FFprobe executando-os, reconhece instalações do FFmpeg feitas pelo WinGet e pede confirmação antes de baixar uma cópia local. Em caso de falha de rede, tenta o download novamente e apresenta uma mensagem específica.

