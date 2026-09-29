import os
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yt_dlp


MAX_DOWNLOADS = 4
FRAGMENTOS = 4
PASTA_DOWNLOAD = "downloads"

print_lock = threading.Lock()


def encontrar_ffmpeg():
    """Retorna o diretório do FFmpeg, priorizando o PATH."""
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg and ffprobe:
        return str(Path(ffmpeg).resolve().parent)

    candidatos = [
        Path.cwd() / "tools" / "ffmpeg" / "bin",
        Path(__file__).resolve().parents[2] / "tools" / "ffmpeg" / "bin",
    ]
    for bin_dir in candidatos:
        if (bin_dir / "ffmpeg.exe").is_file() and (bin_dir / "ffprobe.exe").is_file():
            return str(bin_dir)

    return None


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


def baixar_item(item, configuracao, ffmpeg_location):
    indice, titulo, url = item["indice"], item["titulo"], item["url"]
    opcoes = {
        "outtmpl": os.path.join(PASTA_DOWNLOAD, f"{indice:03d} - %(title)s.%(ext)s"),
        "concurrent_fragment_downloads": FRAGMENTOS,
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
        return indice, titulo, True, item
    except Exception as erro:
        with print_lock:
            print(f"\nERRO [{indice:03d}] {titulo}\n{erro}\n")
        return indice, titulo, False, item


def analisar_url(url):
    print("\nAnalisando URL...\n")
    with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True, "skip_download": True}) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info:
        raise RuntimeError("Não foi possível obter informações da URL.")

    if info.get("entries"):
        items = []
        for indice, video in enumerate(info["entries"], start=1):
            if not video:
                continue
            titulo = video.get("title", f"Vídeo {indice}")
            video_url = video.get("webpage_url") or video.get("url")
            if not video_url:
                continue
            if not video_url.startswith("http"):
                video_url = "https://www.youtube.com/watch?v=" + video_url
            items.append({"indice": indice, "titulo": titulo, "url": video_url})
        return "playlist", info.get("title", "Playlist"), items

    titulo = info.get("title", "Vídeo")
    return "video", titulo, [{"indice": 1, "titulo": titulo, "url": info.get("webpage_url") or url}]


def baixar_items(items, configuracao, ffmpeg_location):
    if len(items) == 1:
        return [baixar_item(items[0], configuracao, ffmpeg_location)]

    resultados = []
    with ThreadPoolExecutor(max_workers=MAX_DOWNLOADS) as executor:
        futuros = [executor.submit(baixar_item, item, configuracao, ffmpeg_location) for item in items]
        for futuro in as_completed(futuros):
            try:
                resultados.append(futuro.result())
            except Exception as erro:
                print("Erro inesperado:", erro)
    return resultados


def mostrar_falhas(falhas):
    print(f"\nFalharam {len(falhas)} download(s):")
    for indice, titulo, *_ in falhas:
        print(f"{indice:03d} - {titulo}")


def tentar_novamente(falhas, configuracao, ffmpeg_location):
    while falhas:
        mostrar_falhas(falhas)
        resposta = input("\nDeseja tentar baixar novamente apenas os que falharam? [s/n]: ").strip().lower()
        if resposta not in ["s", "sim"]:
            break
        print("\n" + "=" * 60 + "\nTENTANDO NOVAMENTE\n" + "=" * 60 + "\n")
        resultados = baixar_items([resultado[3] for resultado in falhas], configuracao, ffmpeg_location)
        falhas = [resultado for resultado in resultados if not resultado[2]]
        sucessos = [resultado for resultado in resultados if resultado[2]]
        print(f"\nNesta tentativa:\nSucessos: {len(sucessos)}\nFalhas: {len(falhas)}")
        if not falhas:
            print("\nTodos os downloads foram concluídos com sucesso.")
    return falhas


def main():
    print("=" * 60 + "\n      YT-DLP DOWNLOADER\n" + "=" * 60)
    ffmpeg_location = encontrar_ffmpeg()
    if ffmpeg_location:
        print(f"\nFFmpeg: {ffmpeg_location}")
    else:
        print("\nAviso: FFmpeg/FFprobe não foram encontrados. Execute setup.ps1.")

    url = input("\nURL do vídeo ou playlist: ").strip()
    configuracao = configurar_download()
    os.makedirs(PASTA_DOWNLOAD, exist_ok=True)

    try:
        tipo, titulo, items = analisar_url(url)
    except Exception as erro:
        print(f"\nErro ao analisar URL:\n{erro}")
        return

    if tipo == "playlist":
        print(f"\nPlaylist detectada.\nNome: {titulo}\nVídeos: {len(items)}")
    else:
        print(f"\nVídeo individual detectado.\nTítulo: {titulo}")
    print(f"\nDownloads simultâneos: {MAX_DOWNLOADS}\nFragmentos por download: {FRAGMENTOS}")
    print("\n" + "=" * 60 + "\nIniciando download...\n" + "=" * 60 + "\n")

    resultados = baixar_items(items, configuracao, ffmpeg_location)
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
