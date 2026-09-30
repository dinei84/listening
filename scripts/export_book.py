"""Exporta um livro sintetizado como arquivo único M4B, com capítulos (OS-062).

O MVP é ouvir no celular longe de casa. Hoje o áudio só existe como centenas de
`.wav` servidos por `localhost:8000`, o que exige o notebook ligado e na mesma
rede. Este script produz o arquivo que vai para o telefone.

M4B (AAC em contêiner MP4) porque aceita **marcadores de capítulo**, e o projeto
tem `chapters` com título e ordem desde a OS-027 — então a navegação e a retomada
de posição vêm de graça do player nativo, sem nós escrevermos nada.

Uso:

    venv/bin/python scripts/export_book.py <book_id>
    venv/bin/python scripts/export_book.py <book_id> --out ~/livros --bitrate 96k
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass

# Permite tanto `python -m scripts.export_book` quanto
# `python scripts/export_book.py`: na segunda forma o Python põe `scripts/` no
# caminho, e não a raiz do projeto, e o import de `core` falharia.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import AudioChunk, Chapter
from storage import audio_store, db

DEFAULT_BITRATE = "64k"

# Fala mono a 64 kbps: ~300 MB para as ~10,9 h de um livro técnico, contra ~1,8 GB
# dos WAV. Estéreo dobraria o arquivo sem ganho nenhum numa voz sintetizada.
AUDIO_CHANNELS = "1"

# O FFMETADATA declara a base de tempo dos capítulos. Com 1/1000, START e END são
# milissegundos inteiros.
TIMEBASE = "1/1000"

# Caracteres que são sintaxe no FFMETADATA e precisam de escape no valor.
_ESCAPAR_METADATA = re.compile(r"([=;#\\\n])")

# Proibidos (ou arriscados) em nome de arquivo nos sistemas que interessam.
_PROIBIDOS_NO_NOME = re.compile(r'[/<>:"\\|?*\x00-\x1f]')


class ExportError(Exception):
    """Falha de exportação com mensagem destinada a quem rodou o comando."""


@dataclass(frozen=True)
class ChapterMark:
    """Um marcador de capítulo no arquivo final."""

    title: str
    start_seconds: float
    end_seconds: float


def build_chapter_marks(
    chapters: list[Chapter], chunks: list[AudioChunk]
) -> list[ChapterMark]:
    """Monta os marcadores de capítulo a partir das durações acumuladas dos trechos."""
    if not chapters or not chunks:
        return []

    # Instante em que cada capítulo começa e termina, varrendo os trechos na ordem
    # de `sequence` — é a mesma conta de deslocamento acumulado da linha de tempo
    # da OS-057, agora para o arquivo.
    faixas: dict[str, list[float]] = {}
    decorrido = 0.0
    for chunk in sorted(chunks, key=lambda c: c.sequence):
        duracao = float(chunk.duration_seconds or 0.0)
        faixa = faixas.get(chunk.chapter_id)
        if faixa is None:
            faixas[chunk.chapter_id] = [decorrido, decorrido + duracao]
        else:
            faixa[1] = decorrido + duracao
        decorrido += duracao

    marcas = []
    # Ordena por `chapter_order`: depender da ordem da lista recebida produziria um
    # M4B com a navegação embaralhada se ela vier de outra fonte.
    for capitulo in sorted(chapters, key=lambda c: c.order):
        faixa = faixas.get(capitulo.id)
        # Capítulo detectado na extração mas sem áudio persistido (síntese
        # interrompida) viraria um marcador de duração zero no meio do arquivo.
        if faixa is None:
            continue
        marcas.append(
            ChapterMark(
                title=capitulo.title, start_seconds=faixa[0], end_seconds=faixa[1]
            )
        )
    return marcas


def _escapar(valor: str) -> str:
    """Escapa os caracteres que são sintaxe no FFMETADATA."""
    return _ESCAPAR_METADATA.sub(r"\\\1", valor)


def build_ffmetadata(title: str, marks: list[ChapterMark]) -> str:
    """Monta o arquivo de metadados do ffmpeg com o título e os capítulos."""
    linhas = [";FFMETADATA1", f"title={_escapar(title)}"]
    for marca in marks:
        linhas += [
            "",
            "[CHAPTER]",
            f"TIMEBASE={TIMEBASE}",
            # Milissegundos inteiros: mandar segundos aqui colocaria todos os
            # capítulos nos primeiros minutos do arquivo.
            f"START={round(marca.start_seconds * 1000)}",
            f"END={round(marca.end_seconds * 1000)}",
            f"title={_escapar(marca.title)}",
        ]
    return "\n".join(linhas) + "\n"


def build_concat_list(chunks: list[AudioChunk]) -> str:
    """Monta a lista do demuxer `concat` do ffmpeg, na ordem de sequence."""
    if not chunks:
        raise ExportError(
            "nenhum trecho de áudio persistido para este livro — ele ainda não foi "
            "sintetizado, ou a síntese não chegou a gravar nada."
        )
    linhas = []
    for chunk in sorted(chunks, key=lambda c: c.sequence):
        # ABSOLUTO: o demuxer `concat` resolve caminho relativo contra o diretório
        # da LISTA, que vive num temporário — não contra o CWD. Os `file_path` no
        # banco são relativos, então sem isto o ffmpeg procura em
        # `/tmp/tmpXXXX/storage/audio/...` e falha.
        caminho = os.path.abspath(chunk.file_path)
        # O demuxer usa aspas simples; caminho com apóstrofo (comum em título de
        # livro) quebraria a lista sem o escape.
        caminho = caminho.replace("'", r"'\''")
        linhas.append(f"file '{caminho}'")
    return "\n".join(linhas) + "\n"


def build_ffmpeg_command(
    concat_path: str,
    metadata_path: str,
    output_path: str,
    bitrate: str = DEFAULT_BITRATE,
) -> list[str]:
    """Monta a linha de comando do ffmpeg que junta, codifica e carimba os capítulos."""
    return [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        concat_path,
        "-i",
        metadata_path,
        # Sem isto o ffmpeg ignora o arquivo de capítulos em silêncio e produz um
        # M4B sem navegação nenhuma.
        "-map_metadata",
        "1",
        "-c:a",
        "aac",
        "-b:a",
        bitrate,
        "-ac",
        AUDIO_CHANNELS,
        output_path,
    ]


def output_name(book_title: str) -> str:
    """Nome de arquivo seguro para o livro, sem a extensão `.pdf` do upload."""
    base = re.sub(r"\.pdf$", "", (book_title or "").strip(), flags=re.IGNORECASE)
    base = _PROIBIDOS_NO_NOME.sub("-", base).strip(" .") or "audiobook"
    return f"{base}.m4b"


def export(
    book_id: str, out_dir: str, bitrate: str = DEFAULT_BITRATE, log=print
) -> str:
    """Exporta o livro para `out_dir` e devolve o caminho do arquivo gerado."""
    book = db.get_book(book_id)
    if book is None:
        raise ExportError(f"livro {book_id} não existe no banco.")

    chunks = audio_store.list_chunks(book_id)
    lista = build_concat_list(chunks)
    marcas = build_chapter_marks(db.list_chapters(book_id), chunks)
    total = sum(float(c.duration_seconds or 0.0) for c in chunks)

    log(f'Livro: "{book.title}"')
    log(
        f"  {len(chunks)} trecho(s), {total / 3600:.1f} h de áudio, {len(marcas)} capítulo(s)"
    )
    if book.status != "ready":
        # Exportar livro incompleto é permitido de propósito; calar sobre isso não.
        log(f"  AVISO: status do livro é '{book.status}' — exportando só o que existe.")

    os.makedirs(out_dir, exist_ok=True)
    destino = os.path.join(out_dir, output_name(book.title))

    with tempfile.TemporaryDirectory() as temporario:
        caminho_lista = os.path.join(temporario, "concat.txt")
        caminho_meta = os.path.join(temporario, "metadata.txt")
        with open(caminho_lista, "w", encoding="utf-8") as arquivo:
            arquivo.write(lista)
        with open(caminho_meta, "w", encoding="utf-8") as arquivo:
            arquivo.write(build_ffmetadata(book.title, marcas))

        log(f"  codificando AAC {bitrate} mono...")
        resultado = subprocess.run(
            build_ffmpeg_command(caminho_lista, caminho_meta, destino, bitrate),
            capture_output=True,
            text=True,
            check=False,
        )
    if resultado.returncode != 0:
        # As últimas linhas do ffmpeg são onde está o motivo real.
        raise ExportError(
            "ffmpeg falhou:\n" + "\n".join(resultado.stderr.strip().splitlines()[-8:])
        )

    tamanho = os.path.getsize(destino) / 1024 / 1024
    log(f"  pronto: {destino} ({tamanho:.0f} MB)")
    return destino


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada da linha de comando."""
    parser = argparse.ArgumentParser(
        description="Exporta um livro sintetizado como M4B com capítulos."
    )
    parser.add_argument("book_id")
    parser.add_argument("--out", default="exports", help="diretório de saída")
    parser.add_argument("--bitrate", default=DEFAULT_BITRATE)
    args = parser.parse_args(argv)

    try:
        export(args.book_id, args.out, args.bitrate)
    except ExportError as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
