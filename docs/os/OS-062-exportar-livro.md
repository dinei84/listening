# OS-062 — Exportar o livro como arquivo único

## 1. Objetivo

Produzir **um arquivo de áudio por livro**, comprimido e com capítulos, para ser
copiado ao celular e ouvido fora de casa — sem depender do notebook ligado.

Decisão do dono em 29/09/2026, ao definir o MVP: *"ouvir no celular, longe de
casa"*. É o item que falta para o MVP acontecer.

## 2. Escopo

### Por que isto, e não PWA offline

Hoje o áudio só existe como ~645 arquivos `.wav` servidos por `localhost:8000`.
Ouvir fora de casa exigiria o notebook ligado e na mesma rede.

A alternativa seria service worker cacheando o livro no celular. **Foi
descartado:** 1,8 GB de WAV por livro, gestão de cota, sincronização — caro e
frágil, para entregar o mesmo resultado que um arquivo entrega. E player nativo
(Apple Books, apps de podcast) é melhor do que o nosso jamais será, com retomada
de posição e navegação por capítulo de graça.

### Números medidos em 29/09/2026, sobre "O Programador Pragmático"

| | |
|---|---|
| caracteres extraídos | 604.872 |
| chunks | 645 |
| áudio estimado | ~10,9 h (medido: 1.001 caracteres → 61,0 s de fala) |
| WAV em disco | ~1,8 GB |
| **AAC 64 kbps mono** | **~300 MB** (~6× menor) |
| capítulos detectados | 348 |

### Alterados

- `scripts/export_book.py` — **novo**. Gera o arquivo a partir do que já está
  persistido em `audio_chunks`.
- `RUNBOOK.md` — como exportar.
- Testes correspondentes.

### Formato: M4B (AAC em contêiner MP4)

É o formato de audiolivro: aceita **marcadores de capítulo**, e temos `chapters`
com título e ordem desde a OS-027 — então os 348 capítulos entram de verdade, e
o app do telefone devolve navegação e retomada sem nós escrevermos nada.

`ffmpeg 7.0.2` já está instalado na máquina; nenhuma dependência Python nova.

### Decisão: script, não rota HTTP

Codificar ~11 h de áudio leva minutos, o que não cabe numa requisição HTTP. Fazer
direito exigiria um `stage` novo na fila e mudanças no worker — desproporcional
para um usuário que já roda `pytest` e `run_app.py` na mão.

**Se, ao usar, o botão fizer falta, vira OS própria** — informada por uso real, que
é justamente o critério que o dono definiu para o MVP.

### Fora de escopo

- **Rota HTTP e botão no player**, pelo motivo acima.
- **Comprimir o áudio na persistência (item 61).** O `_merge_wav_files` do
  pipeline precisa de PCM; comprimir na exportação entrega o resultado do MVP sem
  tocar o caminho de síntese. Com 81 GB livres, o disco não é o gargalo ainda.
- **Enviar o arquivo ao celular.** Transferência é USB, nuvem ou o que o dono
  preferir; automatizar isso não é problema deste projeto.
- **Exportar livro incompleto** como caso especial — exporta o que existe, e
  avisa quantos trechos entraram.

## 3. Contratos envolvidos

Nenhum contrato muda e **nenhum arquivo de produção é alterado**: o script só lê
`audio_chunks` e `chapters` pelo `storage`, e chama o `ffmpeg`.

A montagem dos capítulos e da linha de comando são funções puras, testadas sem
invocar o `ffmpeg`; a codificação de verdade é exercitada uma vez, com áudio real.

## 4. Critérios de aceite

- [ ] O script gera um arquivo único a partir dos chunks persistidos, na ordem de `sequence`
- [ ] Os capítulos entram como marcadores, com título e instante de início corretos
- [ ] O instante de início de um capítulo é a soma das durações dos trechos anteriores
- [ ] Capítulo sem nenhum trecho persistido não vira marcador quebrado
- [ ] Livro sem capítulos detectados gera arquivo válido, sem marcadores
- [ ] Livro sem nenhum trecho falha com mensagem clara, não com erro do `ffmpeg`
- [ ] O `ffmpeg` é chamado com AAC mono e a taxa configurada
- [ ] Título e nome do arquivo saem do título do livro, sem a extensão `.pdf`
- [ ] O script diz quantos trechos entraram e o tamanho final
- [ ] Livro inexistente falha com mensagem clara
- [ ] Nenhum teste existente quebra (502 hoje)

## 5. Testes exigidos (mínimo)

- `test_chapter_marks_start_at_cumulative_duration`
- `test_chapter_marks_use_chapter_titles`
- `test_chapter_without_chunks_is_skipped`
- `test_no_chapters_produces_no_marks`
- `test_metadata_is_valid_ffmetadata`
- `test_metadata_timestamps_are_in_milliseconds`
- `test_build_command_uses_aac_mono_and_bitrate`
- `test_build_command_includes_the_output_path`
- `test_output_name_strips_pdf_extension`
- `test_output_name_is_filesystem_safe`
- `test_export_without_chunks_fails_with_clear_message`
- `test_export_of_unknown_book_fails_with_clear_message`

## 6. Relatório

Ver `docs/report/OS-062-report.md`.
