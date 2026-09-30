import os
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp


MAX_DOWNLOADS = 4
FRAGMENTOS = 4
PLATAFORMAS_CONSERVADORAS = {
    "facebook",
    "instagram",
    "tiktok",
    "twitter",
    "x/twitter",
}
PASTA_DOWNLOAD = "downloads"

print_lock = threading.Lock()


def _executavel_funciona(caminho):
    try:
        subprocess.run(
            [str(caminho), "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=10,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def _diretorio_ffmpeg_valido(bin_dir):
    bin_dir = Path(bin_dir)
    ffmpeg = bin_dir / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    ffprobe = bin_dir / ("ffprobe.exe" if os.name == "nt" else "ffprobe")
    return _executavel_funciona(ffmpeg) and _executavel_funciona(ffprobe)


def encontrar_ffmpeg():
    """Retorna a localização do FFmpeg; string vazia significa usar o PATH."""
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg and ffprobe and _executavel_funciona(ffmpeg) and _executavel_funciona(ffprobe):
        ffmpeg_dir = Path(ffmpeg).resolve().parent
        ffprobe_dir = Path(ffprobe).resolve().parent
        return str(ffmpeg_dir) if ffmpeg_dir == ffprobe_dir else ""

    raizes = [Path.cwd(), Path(__file__).resolve().parents[2]]
    candidatos = [raiz / "tools" / "ffmpeg" / "bin" for raiz in raizes]

    for raiz in raizes:
        arquivo_localizacao = raiz / "tools" / "ffmpeg-location.txt"
        if arquivo_localizacao.is_file():
            try:
                candidatos.append(Path(arquivo_localizacao.read_text(encoding="utf-8-sig").strip()))
            except OSError:
                pass

    for bin_dir in candidatos:
        if _diretorio_ffmpeg_valido(bin_dir):
            return str(bin_dir)

    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        winget = Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "WinGet" / "Packages"
        try:
            for executavel in winget.glob("Gyan.FFmpeg*/**/bin/ffmpeg.exe"):
                if _diretorio_ffmpeg_valido(executavel.parent):
                    return str(executavel.parent)
        except OSError:
            pass

    return None


def _deno_valido(caminho):
    try:
        resultado = subprocess.run(
            [str(caminho), "--version"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        primeira_linha = resultado.stdout.splitlines()[0]
        versao = primeira_linha.removeprefix("deno ").split(".")
        return len(versao) >= 2 and (int(versao[0]), int(versao[1])) >= (2, 3)
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return False


def encontrar_deno():
    deno_path = shutil.which("deno")
    if deno_path and _deno_valido(deno_path):
        return str(Path(deno_path).resolve())

    candidatos = [
        Path.cwd() / "tools" / "deno" / "deno.exe",
        Path(__file__).resolve().parents[2] / "tools" / "deno" / "deno.exe",
    ]
    for candidato in candidatos:
        if _deno_valido(candidato):
            return str(candidato)
    return None


def classificar_erro(erro):
    mensagem = str(erro).lower()
    categorias = {
        "autenticacao": (
            "sign in to confirm you’re not a bot",
            "sign in to confirm you're not a bot",
            "use --cookies-from-browser",
            "login required",
            "log in to",
            "sign in to",
            "authentication required",
            "account is required",
            "cookies are required",
            "age-restricted",
        ),
        "limite": (
            "http error 429",
            "too many requests",
            "rate limit",
            "temporarily blocked",
        ),
        "privado": (
            "private video",
            "private account",
            "private content",
            "members-only",
        ),
        "regiao": (
            "geo-restricted",
            "not available in your country",
            "not available in your region",
        ),
        "indisponivel": (
            "video unavailable",
            "content is not available",
            "has been removed",
            "deleted video",
        ),
        "rede": (
            "timed out",
            "timeout",
            "connection reset",
            "temporary failure",
            "network is unreachable",
        ),
        "formato": (
            "requested format is not available",
            "no video formats found",
        ),
        "ffmpeg": (
            "ffmpeg not found",
            "ffprobe not found",
            "postprocessing",
        ),
    }
    for categoria, trechos in categorias.items():
        if any(trecho in mensagem for trecho in trechos):
            return categoria
    return "desconhecido"


def erro_exige_cookies(erro):
    return classificar_erro(erro) == "autenticacao"


def plataforma_da_url(url):
    try:
        host = urlparse(url).hostname or "plataforma"
    except ValueError:
        return "plataforma"
    return host.removeprefix("www.")


def nome_plataforma(info, padrao="Plataforma"):
    extrator = str(info.get("extractor_key") or info.get("extractor") or padrao)
    normalizado = extrator.lower()
    nomes = (
        ("youtube", "YouTube"),
        ("soundcloud", "SoundCloud"),
        ("tiktok", "TikTok"),
        ("instagram", "Instagram"),
        ("twitter", "X/Twitter"),
        ("facebook", "Facebook"),
        ("vimeo", "Vimeo"),
        ("twitch", "Twitch"),
        ("reddit", "Reddit"),
        ("bandcamp", "Bandcamp"),
    )
    for trecho, nome in nomes:
        if trecho in normalizado:
            return nome
    return extrator


def obter_url_item(video):
    for campo in ("webpage_url", "original_url", "url"):
        valor = video.get(campo)
        if isinstance(valor, str) and valor.startswith(("http://", "https://")):
            return valor

    extrator = str(video.get("ie_key") or video.get("extractor_key") or "").lower()
    identificador = video.get("id") or video.get("url")
    if "youtube" in extrator and identificador:
        return f"https://www.youtube.com/watch?v={identificador}"
    return None


def configuracao_adaptativa(items, autenticado=False):
    quantidade = len(items)
    if quantidade <= 1:
        return 1, FRAGMENTOS, "item individual"

    plataformas = {str(item.get("plataforma", "")).lower() for item in items}
    conservadora = any(
        nome in plataforma
        for plataforma in plataformas
        for nome in PLATAFORMAS_CONSERVADORAS
    )
    if autenticado:
        return min(2, quantidade), 2, "coleção autenticada"
    if conservadora:
        return min(2, quantidade), 2, "plataforma com limites mais sensíveis"
    return min(MAX_DOWNLOADS, quantidade), 2, "coleção sem autenticação"


def configurar_cookies_com_consentimento(plataformas=None):
    plataformas = sorted({str(item) for item in (plataformas or []) if item})
    alvo = ", ".join(plataformas) if plataformas else "a plataforma"
    print("\n" + "=" * 60)
    print("AUTENTICAÇÃO SOLICITADA")
    print("=" * 60)
    print(
        f"\n{alvo} exigiu autenticação. Para continuar, "
        "o programa precisa ler temporariamente os cookies de uma sessão "
        "já conectada no seu navegador."
    )
    print("\nRiscos importantes:")
    print("- A plataforma pode limitar, suspender ou banir temporária ou permanentemente a conta.")
    print("- Coleções e downloads paralelos geram muitas requisições e aumentam esse risco.")
    print("- Prefira baixar vídeos individuais e evite executar muitos downloads seguidos.")
    print("- Use cookies apenas quando necessário e somente para conteúdo que você pode baixar.")
    print("- O programa não exportará os cookies para um arquivo, mas terá acesso à sessão durante a execução.")

    resposta = input("\nVocê entende e aceita esses riscos para continuar? [s/n]: ").strip().lower()
    if resposta not in ("s", "sim"):
        print("\nOperação cancelada. Os cookies do navegador não foram acessados.")
        return None

    print("\nNavegador com uma sessão conectada à plataforma:")
    print("1 - Chrome")
    print("2 - Edge")
    print("3 - Firefox")
    print("4 - Brave")
    escolha = input("\nEscolha: ").strip()
    navegador = {"1": "chrome", "2": "edge", "3": "firefox", "4": "brave"}.get(escolha)
    if not navegador:
        print("\nOpção inválida. Operação cancelada.")
        return None
    return {"cookiesfrombrowser": (navegador,)}


def configurar_download():
    print("\nTipo de download:")
    print("1 - Vídeo + Áudio")
    print("2 - Somente Vídeo")
    print("3 - Somente Áudio")
    tipo = input("\nEscolha: ").strip()

    if tipo == "1":
        print("\nFormato:")
        print("1 - MP4")
        print("2 - MKV")
        print("3 - WEBM")
        formato = {"1": "mp4", "2": "mkv", "3": "webm"}.get(input("\nEscolha: ").strip(), "mp4")

        print("\nQualidade:")
        print("1 - Melhor disponível")
        print("2 - 2160p")
        print("3 - 1440p")
        print("4 - 1080p")
        print("5 - 720p")
        print("6 - 480p")
        escolha = input("\nEscolha: ").strip()
        if escolha == "1":
            formato_yt = "bestvideo+bestaudio/best"
        else:
            altura = {"2": 2160, "3": 1440, "4": 1080, "5": 720, "6": 480}.get(escolha, 1080)
            formato_yt = f"bestvideo[height<={altura}]+bestaudio/best[height<={altura}]"
        return {"format": formato_yt, "merge_output_format": formato}

    if tipo == "2":
        print("\nQualidade:")
        print("1 - Melhor disponível")
        print("2 - 2160p")
        print("3 - 1440p")
        print("4 - 1080p")
        print("5 - 720p")
        print("6 - 480p")
        escolha = input("\nEscolha: ").strip()
        if escolha == "1":
            formato_yt = "bestvideo"
        else:
            altura = {"2": 2160, "3": 1440, "4": 1080, "5": 720, "6": 480}.get(escolha, 1080)
            formato_yt = f"bestvideo[height<={altura}]"
        return {"format": formato_yt}

    if tipo == "3":
        print("\nFormato:")
        print("1 - MP3")
        print("2 - M4A")
        print("3 - OPUS")
        print("4 - FLAC")
        print("5 - WAV")
        codec = {"1": "mp3", "2": "m4a", "3": "opus", "4": "flac", "5": "wav"}.get(
            input("\nEscolha: ").strip(), "mp3"
        )
        qualidade = "0"
        if codec in ["mp3", "m4a", "opus"]:
            print("\nQualidade:")
            print("1 - Melhor")
            print("2 - 320 kbps")
            print("3 - 256 kbps")
            print("4 - 192 kbps")
            print("5 - 128 kbps")
            qualidade = {"1": "0", "2": "320", "3": "256", "4": "192", "5": "128"}.get(
                input("\nEscolha: ").strip(), "0"
            )
        return {
            "format": "bestaudio/best",
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": codec, "preferredquality": qualidade}
            ],
        }

    print("\nOpção inválida. Usando vídeo + áudio em MP4.")
    return {"format": "bestvideo+bestaudio/best", "merge_output_format": "mp4"}


def progresso(indice, titulo):
    def hook(d):
        if d["status"] == "finished":
            with print_lock:
                print(f"[{indice:03d}] Download concluído: {titulo}")

    return hook


def baixar_item(item, configuracao, ffmpeg_location, fragmentos):
    indice, titulo, url = item["indice"], item["titulo"], item["url"]
    opcoes = {
        "outtmpl": os.path.join(PASTA_DOWNLOAD, f"{indice:03d} - %(title)s.%(ext)s"),
        "concurrent_fragment_downloads": fragmentos,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [progresso(indice, titulo)],
    }
    if ffmpeg_location:
        opcoes["ffmpeg_location"] = ffmpeg_location
    opcoes.update(configuracao)

    try:
        with print_lock:
            print(f"[{indice:03d}] Iniciando: {titulo}")
        with yt_dlp.YoutubeDL(opcoes) as ydl:
            ydl.download([url])
        return indice, titulo, True, item, None, None
    except Exception as erro:
        with print_lock:
            print(f"\nERRO [{indice:03d}] {titulo}\n{erro}\n")
        return indice, titulo, False, item, str(erro), classificar_erro(erro)


def analisar_url(url, opcoes_comuns=None):
    print("\nAnalisando URL...\n")
    opcoes = {"quiet": True, "extract_flat": True, "skip_download": True}
    opcoes.update(opcoes_comuns or {})
    with yt_dlp.YoutubeDL(opcoes) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info:
        raise RuntimeError("Não foi possível obter informações da URL.")

    plataforma = nome_plataforma(info, plataforma_da_url(url))

    if info.get("entries"):
        items = []
        ignorados = 0
        for indice, video in enumerate(info["entries"], start=1):
            if not video:
                continue
            titulo = video.get("title", f"Vídeo {indice}")
            video_url = obter_url_item(video)
            if not video_url:
                ignorados += 1
                continue
            items.append(
                {
                    "indice": indice,
                    "titulo": titulo,
                    "url": video_url,
                    "plataforma": nome_plataforma(video, plataforma),
                }
            )
        if ignorados:
            print(f"Aviso: {ignorados} item(ns) sem URL utilizável foram ignorados.")
        if not items:
            raise RuntimeError("A coleção não contém itens com URLs utilizáveis.")
        return "colecao", info.get("title", "Coleção"), items, plataforma

    titulo = info.get("title", "Vídeo")
    item = {
        "indice": 1,
        "titulo": titulo,
        "url": info.get("webpage_url") or info.get("original_url") or url,
        "plataforma": plataforma,
    }
    return "video", titulo, [item], plataforma


def baixar_items(items, configuracao, ffmpeg_location):
    autenticado = bool(configuracao.get("cookiesfrombrowser") or configuracao.get("cookiefile"))
    max_downloads, fragmentos, motivo = configuracao_adaptativa(items, autenticado)
    print(
        f"Paralelismo adaptativo: {max_downloads} download(s), "
        f"{fragmentos} fragmento(s) por download ({motivo})."
    )
    if len(items) == 1:
        return [baixar_item(items[0], configuracao, ffmpeg_location, fragmentos)]

    resultados = []
    with ThreadPoolExecutor(max_workers=max_downloads) as executor:
        futuros = [
            executor.submit(baixar_item, item, configuracao, ffmpeg_location, fragmentos)
            for item in items
        ]
        for futuro in as_completed(futuros):
            try:
                resultados.append(futuro.result())
            except Exception as erro:
                print("Erro inesperado:", erro)
    return resultados


def mostrar_falhas(falhas):
    print(f"\nFalharam {len(falhas)} download(s):")
    for indice, titulo, _, _, _, categoria in falhas:
        print(f"{indice:03d} - {titulo} [{categoria or 'desconhecido'}]")


def tratar_falhas_de_autenticacao(resultados, configuracao, ffmpeg_location):
    falhas_login = [
        resultado
        for resultado in resultados
        if not resultado[2] and resultado[5] == "autenticacao"
    ]
    if not falhas_login:
        return resultados

    plataformas = {resultado[3].get("plataforma") for resultado in falhas_login}
    print(f"\nAutenticação exigida em {len(falhas_login)} download(s).")
    opcoes_cookies = configurar_cookies_com_consentimento(plataformas)
    if not opcoes_cookies:
        return resultados

    configuracao.update(opcoes_cookies)
    print("\n" + "=" * 60)
    print("REPETINDO SOMENTE AS FALHAS DE AUTENTICAÇÃO")
    print("=" * 60 + "\n")
    resultados_login = baixar_items(
        [resultado[3] for resultado in falhas_login],
        configuracao,
        ffmpeg_location,
    )
    ids_login = {id(resultado) for resultado in falhas_login}
    resultados_preservados = [
        resultado for resultado in resultados if id(resultado) not in ids_login
    ]
    return resultados_preservados + resultados_login


def tentar_novamente(falhas, configuracao, ffmpeg_location):
    while falhas:
        mostrar_falhas(falhas)

        falhas_repetiveis = [
            resultado
            for resultado in falhas
            if resultado[5] in ("rede", "desconhecido")
        ]
        if not falhas_repetiveis:
            print(
                "\nAs falhas restantes não são adequadas para repetição imediata "
                "(autenticação, limite, conteúdo privado/indisponível, região, formato ou FFmpeg)."
            )
            break

        resposta = input("\nDeseja tentar baixar novamente apenas os que falharam? [s/n]: ").strip().lower()
        if resposta not in ["s", "sim"]:
            break
        print("\n" + "=" * 60 + "\nTENTANDO NOVAMENTE\n" + "=" * 60 + "\n")
        resultados = baixar_items(
            [resultado[3] for resultado in falhas_repetiveis],
            configuracao,
            ffmpeg_location,
        )
        resultados = tratar_falhas_de_autenticacao(
            resultados,
            configuracao,
            ffmpeg_location,
        )
        falhas_bloqueadas = [
            resultado
            for resultado in falhas
            if resultado not in falhas_repetiveis
        ]
        falhas = falhas_bloqueadas + [resultado for resultado in resultados if not resultado[2]]
        sucessos = [resultado for resultado in resultados if resultado[2]]
        print(f"\nNesta tentativa:\nSucessos: {len(sucessos)}\nFalhas: {len(falhas)}")
        if not falhas:
            print("\nTodos os downloads foram concluídos com sucesso.")
    return falhas


def main():
    print("=" * 60 + "\n      YT-DLP DOWNLOADER\n" + "=" * 60)
    ffmpeg_location = encontrar_ffmpeg()
    if ffmpeg_location is None:
        print("\nAviso: FFmpeg/FFprobe não foram encontrados. Execute setup.ps1.")
    elif ffmpeg_location:
        print(f"\nFFmpeg: {ffmpeg_location}")
    else:
        print("\nFFmpeg e FFprobe encontrados no PATH.")

    deno_path = encontrar_deno()
    opcoes_comuns = {}
    if deno_path:
        print(f"Deno: {deno_path}")
        opcoes_comuns["js_runtimes"] = {"deno": {"path": deno_path}}
    else:
        print("Aviso: Deno 2.3+ não foi encontrado; a extração do YouTube pode ficar limitada.")

    url = input("\nURL do vídeo ou playlist: ").strip()
    configuracao = configurar_download()
    os.makedirs(PASTA_DOWNLOAD, exist_ok=True)

    try:
        tipo, titulo, items, plataforma = analisar_url(url, opcoes_comuns)
    except Exception as erro:
        if not erro_exige_cookies(erro):
            print(f"\nErro ao analisar URL ({classificar_erro(erro)}):\n{erro}")
            return

        opcoes_cookies = configurar_cookies_com_consentimento([plataforma_da_url(url)])
        if not opcoes_cookies:
            return
        opcoes_comuns.update(opcoes_cookies)
        try:
            tipo, titulo, items, plataforma = analisar_url(url, opcoes_comuns)
        except Exception as erro_autenticado:
            print(f"\nErro ao analisar URL mesmo com autenticação:\n{erro_autenticado}")
            return

    configuracao.update(opcoes_comuns)

    print(f"\nPlataforma: {plataforma}")
    if tipo == "colecao":
        print(f"Coleção detectada.\nNome: {titulo}\nItens: {len(items)}")
    else:
        print(f"Item individual detectado.\nTítulo: {titulo}")
    print("\n" + "=" * 60 + "\nIniciando download...\n" + "=" * 60 + "\n")

    resultados = baixar_items(items, configuracao, ffmpeg_location)
    resultados = tratar_falhas_de_autenticacao(
        resultados,
        configuracao,
        ffmpeg_location,
    )
    sucessos = [resultado for resultado in resultados if resultado[2]]
    falhas = [resultado for resultado in resultados if not resultado[2]]
    print("\n" + "=" * 60 + "\nPRIMEIRA TENTATIVA FINALIZADA\n" + "=" * 60)
    print(f"\nSucessos: {len(sucessos)}\nFalhas: {len(falhas)}")
    if falhas:
        falhas = tentar_novamente(falhas, configuracao, ffmpeg_location)

    print("\n" + "=" * 60 + "\nDOWNLOAD FINALIZADO\n" + "=" * 60)
    if falhas:
        print(f"\nAinda restaram {len(falhas)} falha(s).")
        mostrar_falhas(falhas)
    else:
        print("\nTodos os downloads foram concluídos.")
    print(f"\nArquivos salvos em:\n{os.path.abspath(PASTA_DOWNLOAD)}")


if __name__ == "__main__":
    main()
