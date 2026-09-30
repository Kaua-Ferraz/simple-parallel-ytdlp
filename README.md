# Simple Parallel yt-dlp

Downloader interativo de vídeos e coleções que usa os extratores do yt-dlp e executa vários downloads em paralelo.

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

Para downloads do YouTube, o instalador também valida Deno 2.3+ e oferece uma cópia portátil opcional em `tools/deno/`. Recusar o Deno não impede o uso das outras plataformas.

O programa deixa o yt-dlp identificar a plataforma e pode trabalhar com vídeos, áudios, playlists, álbuns, perfis e outras coleções aceitas pelos extratores instalados. Exemplos incluem YouTube, TikTok, X/Twitter, Instagram, SoundCloud, Vimeo, Twitch, Reddit, Facebook e Bandcamp; o funcionamento efetivo depende do suporte atual do yt-dlp e das regras de acesso de cada serviço.

O paralelismo é adaptativo:

- item individual: 1 download com até 4 fragmentos;
- coleção comum sem autenticação: até 4 downloads, com 2 fragmentos cada;
- Instagram, TikTok, X/Twitter ou Facebook: até 2 downloads, com 2 fragmentos cada;
- coleção autenticada: até 2 downloads, com 2 fragmentos cada.

O programa primeiro tenta os downloads sem autenticação. Se uma plataforma exigir login, explica os riscos, solicita consentimento uma única vez e repete somente as falhas de autenticação usando cookies de Chrome, Edge, Firefox ou Brave. Os cookies não são exportados para arquivo. Falhas de limite, conteúdo privado ou removido, bloqueio regional, formato e FFmpeg não são repetidas imediatamente como se fossem erros temporários.

