"""OS-062 — exportar o livro como arquivo único, com capítulos.

O MVP é ouvir no celular longe de casa, e hoje o áudio só existe como ~645 `.wav`
servidos por `localhost:8000`. Este script produz o arquivo que vai para o
telefone.

A montagem dos capítulos e da linha de comando são funções puras: o `ffmpeg`
não é invocado em teste nenhum deste arquivo.
"""

import pytest

from core.models import AudioChunk, Chapter
from scripts import export_book


def _chunk(sequence, chapter_id, duracao):
    return AudioChunk(
        chapter_id=chapter_id,
        sequence=sequence,
        file_path=f"/audio/{sequence}.wav",
        duration_seconds=duracao,
        engine_used="kokoro",
    )


def _capitulo(id_, titulo, ordem):
    return Chapter(id=id_, title=titulo, order=ordem, text="", start_page=1, end_page=2)


# --------------------------------------------------------------------------
# Marcadores de capítulo
# --------------------------------------------------------------------------


def test_chapter_marks_start_at_cumulative_duration():
    """O início de um capítulo é a soma das durações de tudo que veio antes —
    mesma conta da linha de tempo da OS-057, agora para o arquivo."""
    chunks = [
        _chunk(0, "cap-a", 10.0),
        _chunk(1, "cap-a", 20.0),
        _chunk(2, "cap-b", 30.0),
        _chunk(3, "cap-c", 5.0),
    ]
    capitulos = [
        _capitulo("cap-a", "Primeiro", 0),
        _capitulo("cap-b", "Segundo", 1),
        _capitulo("cap-c", "Terceiro", 2),
    ]

    marcas = export_book.build_chapter_marks(capitulos, chunks)

    assert [m.start_seconds for m in marcas] == [0.0, 30.0, 60.0]
    assert [m.end_seconds for m in marcas] == [30.0, 60.0, 65.0]


def test_chapter_marks_use_chapter_titles():
    chunks = [_chunk(0, "cap-a", 10.0), _chunk(1, "cap-b", 10.0)]
    capitulos = [_capitulo("cap-a", "Prefácio", 0), _capitulo("cap-b", "Dicas", 1)]

    marcas = export_book.build_chapter_marks(capitulos, chunks)

    assert [m.title for m in marcas] == ["Prefácio", "Dicas"]


def test_chapter_marks_follow_chapter_order_not_list_order():
    """`list_chapters` já ordena, mas o marcador não pode depender disso: um
    capítulo fora de ordem produziria um M4B com a navegação embaralhada."""
    chunks = [_chunk(0, "cap-a", 10.0), _chunk(1, "cap-b", 10.0)]
    capitulos = [_capitulo("cap-b", "Segundo", 1), _capitulo("cap-a", "Primeiro", 0)]

    marcas = export_book.build_chapter_marks(capitulos, chunks)

    assert [m.title for m in marcas] == ["Primeiro", "Segundo"]


def test_chapter_without_chunks_is_skipped():
    """Capítulo detectado na extração mas sem áudio persistido (síntese
    interrompida) não pode virar marcador de duração zero no meio do arquivo."""
    chunks = [_chunk(0, "cap-a", 10.0), _chunk(1, "cap-c", 10.0)]
    capitulos = [
        _capitulo("cap-a", "Primeiro", 0),
        _capitulo("cap-b", "Sem áudio", 1),
        _capitulo("cap-c", "Terceiro", 2),
    ]

    marcas = export_book.build_chapter_marks(capitulos, chunks)

    assert [m.title for m in marcas] == ["Primeiro", "Terceiro"]
    assert [m.start_seconds for m in marcas] == [0.0, 10.0]


def test_no_chapters_produces_no_marks():
    chunks = [_chunk(0, "", 10.0)]
    assert export_book.build_chapter_marks([], chunks) == []


def test_no_chunks_produces_no_marks():
    capitulos = [_capitulo("cap-a", "Primeiro", 0)]
    assert export_book.build_chapter_marks(capitulos, []) == []


# --------------------------------------------------------------------------
# FFMETADATA
# --------------------------------------------------------------------------


def test_metadata_is_valid_ffmetadata():
    marcas = export_book.build_chapter_marks(
        [_capitulo("cap-a", "Prefácio", 0)], [_chunk(0, "cap-a", 10.0)]
    )
    texto = export_book.build_ffmetadata("Meu Livro", marcas)

    assert texto.startswith(";FFMETADATA1")
    assert "title=Meu Livro" in texto
    assert "[CHAPTER]" in texto
    assert "TIMEBASE=1/1000" in texto


def test_metadata_timestamps_are_in_milliseconds():
    """TIMEBASE=1/1000: START e END em milissegundos inteiros. Mandar segundos
    aqui colocaria todos os 348 capítulos nos primeiros 20 minutos."""
    marcas = export_book.build_chapter_marks(
        [_capitulo("cap-a", "Um", 0), _capitulo("cap-b", "Dois", 1)],
        [_chunk(0, "cap-a", 12.5), _chunk(1, "cap-b", 7.5)],
    )
    texto = export_book.build_ffmetadata("L", marcas)

    assert "START=0" in texto
    assert "END=12500" in texto
    assert "START=12500" in texto
    assert "END=20000" in texto


def test_metadata_escapes_special_characters_in_titles():
    """`=`, `;`, `#`, `\\` e quebra de linha são sintaxe no FFMETADATA: um título
    de capítulo com `=` truncaria o arquivo de metadados."""
    marcas = export_book.build_chapter_marks(
        [_capitulo("cap-a", "Custo = benefício; veja #3", 0)],
        [_chunk(0, "cap-a", 10.0)],
    )
    texto = export_book.build_ffmetadata("L", marcas)

    assert r"\=" in texto
    assert r"\;" in texto
    assert r"\#" in texto


def test_metadata_without_chapters_still_has_title():
    texto = export_book.build_ffmetadata("Só o Título", [])
    assert "title=Só o Título" in texto
    assert "[CHAPTER]" not in texto


# --------------------------------------------------------------------------
# Linha de comando do ffmpeg
# --------------------------------------------------------------------------


def test_build_command_uses_aac_mono_and_bitrate():
    comando = export_book.build_ffmpeg_command(
        concat_path="/tmp/lista.txt",
        metadata_path="/tmp/meta.txt",
        output_path="/tmp/livro.m4b",
        bitrate="64k",
    )
    assert "aac" in comando
    assert "64k" in comando
    # Fala é mono; estéreo dobraria o arquivo sem ganho nenhum.
    assert "1" in comando[comando.index("-ac") + 1 : comando.index("-ac") + 2]


def test_build_command_includes_inputs_and_output():
    comando = export_book.build_ffmpeg_command(
        concat_path="/tmp/lista.txt",
        metadata_path="/tmp/meta.txt",
        output_path="/tmp/livro.m4b",
    )
    assert "/tmp/lista.txt" in comando
    assert "/tmp/meta.txt" in comando
    assert comando[-1] == "/tmp/livro.m4b"


def test_build_command_maps_metadata_from_the_second_input():
    """Sem `-map_metadata 1`, o ffmpeg ignora o arquivo de capítulos em silêncio
    e produz um M4B sem navegação nenhuma."""
    comando = export_book.build_ffmpeg_command(
        concat_path="/tmp/l.txt", metadata_path="/tmp/m.txt", output_path="/tmp/o.m4b"
    )
    assert "-map_metadata" in comando
    assert comando[comando.index("-map_metadata") + 1] == "1"


def test_concat_list_makes_paths_absolute():
    """O demuxer `concat` resolve caminho relativo contra o diretório da LISTA, e
    a lista vive num temporário — não contra o CWD. Os `file_path` no banco são
    relativos (`storage/audio/<id>/0.wav`), então sem absolutizar o ffmpeg
    procura em `/tmp/tmpXXXX/storage/audio/...` e falha. Encontrado rodando de
    verdade, depois de os testes com caminho absoluto passarem."""
    relativo = _chunk(0, "c", 1.0).model_copy(
        update={"file_path": "storage/audio/livro/0.wav"}
    )
    conteudo = export_book.build_concat_list([relativo])
    caminho = conteudo.split("'")[1]
    assert caminho.startswith("/"), conteudo
    assert caminho.endswith("storage/audio/livro/0.wav")


def test_concat_list_keeps_absolute_paths_untouched():
    absoluto = _chunk(0, "c", 1.0).model_copy(update={"file_path": "/audio/x/0.wav"})
    assert "'/audio/x/0.wav'" in export_book.build_concat_list([absoluto])


def test_concat_list_quotes_paths_with_apostrophes():
    """O demuxer `concat` usa aspas simples; um caminho com apóstrofo quebraria a
    lista — e livro com apóstrofo no nome é comum."""
    conteudo = export_book.build_concat_list(
        [_chunk(0, "c", 1.0).model_copy(update={"file_path": "/a/O'Reilly/0.wav"})]
    )
    assert r"'\''" in conteudo or "O'\\''Reilly" in conteudo


# --------------------------------------------------------------------------
# Nome do arquivo
# --------------------------------------------------------------------------


def test_output_name_strips_pdf_extension():
    assert export_book.output_name("O Programador Pragmático.pdf").endswith(".m4b")
    assert "pdf" not in export_book.output_name("Meu Livro.pdf").lower()


def test_output_name_is_filesystem_safe():
    nome = export_book.output_name("Livro: parte 1/2 <final>.pdf")
    for proibido in '/<>:"\\|?*':
        assert proibido not in nome


def test_output_name_of_empty_title_still_produces_a_file():
    nome = export_book.output_name("")
    assert nome.endswith(".m4b")
    assert len(nome) > len(".m4b")


# --------------------------------------------------------------------------
# Falhas com mensagem clara
# --------------------------------------------------------------------------


def test_export_without_chunks_fails_with_clear_message():
    """Sem isto, o ffmpeg falharia com erro de lista vazia — mensagem que não
    ajuda ninguém a entender que o livro ainda não foi sintetizado."""
    with pytest.raises(export_book.ExportError, match="nenhum trecho"):
        export_book.build_concat_list([])
