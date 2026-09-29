# Simple Parallel yt-dlp

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

