# OS-062 — Relatório de entrega

**Data:** 29/09/2026
**Branch:** `os/062-exportar-livro`
**Commit(s) relevante(s):** `60dbbde` (OS), `90223eb` (Red), `8db68bc` (Green)

## 1. Resumo do que foi feito

`scripts/export_book.py` junta os trechos de um livro num **arquivo único M4B**
com marcadores de capítulo, comprimido, para ser copiado ao celular e ouvido fora
de casa. É o item que faltava para o MVP definido pelo dono em 29/09/2026.

## 2. Checklist de DoD

### Padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação — commit Red precede o Green
- [x] Todos os testes da OS passam localmente
- [x] Nenhum teste existente quebrou — 502 → **508 passando**
- [x] Código segue os contratos de `ARQUITETURA.md` — nenhum contrato tocado; o script só lê pelo `storage`
- [x] Nenhuma chamada real a API paga nos testes — o script não toca rede
- [x] Type hints e docstring de uma linha em toda função pública
- [x] `PROJECT_STATE.md` atualizado
- [x] Relatório criado em `docs/report/OS-062-report.md`
- [x] PR aberto com título `[OS-062] ...`

### Específico (seção 4 da OS)

- [x] Gera arquivo único a partir dos chunks, na ordem de `sequence`
- [x] Capítulos entram como marcadores, com título e instante corretos
- [x] O início de um capítulo é a soma das durações dos trechos anteriores
- [x] Capítulo sem trecho persistido não vira marcador quebrado
- [x] Livro sem capítulos gera arquivo válido, sem marcadores
- [x] Livro sem trechos falha com mensagem clara, não com erro do `ffmpeg`
- [x] `ffmpeg` chamado com AAC mono e a taxa configurada
- [x] Nome do arquivo sai do título, sem `.pdf` e sem caractere proibido
- [x] O script diz quantos trechos entraram e o tamanho final
- [x] Livro inexistente falha com mensagem clara
- [x] Nenhum teste existente quebra

## 3. Testes escritos

20 novos, **nenhum invoca o `ffmpeg`**.

| Grupo | Casos | Passou? |
|---|---|---|
| marcadores de capítulo | início acumulado, títulos, ordem por `chapter_order`, capítulo sem áudio ignorado, sem capítulos, sem trechos | ✅ |
| FFMETADATA | cabeçalho válido, timestamps em milissegundos, escape de `=` `;` `#`, título sem capítulos | ✅ |
| linha de comando | AAC mono + bitrate, entradas e saída, `-map_metadata 1` | ✅ |
| lista do `concat` | **caminhos absolutos**, absolutos preservados, apóstrofo escapado | ✅ |
| nome do arquivo | tira `.pdf`, seguro para sistema de arquivos, título vazio | ✅ |
| falhas | sem trechos, livro inexistente | ✅ |

Commit "Red" antes do "Green"? **[x] Sim** — o Red falhava na coleta
(`scripts/export_book.py` não existia).

## 4. Saída de comandos relevantes

### Suíte completa e lint

```
508 passed, 2 warnings in 20.36s
All checks passed!     (scripts/export_book.py, tests/unit/test_export_book_os062.py)
```

### Exportação real, com `ffmpeg`

```
Livro: "teste-expressividade2.pdf"
  2 trecho(s), 0.0 h de áudio, 1 capítulo(s)
  codificando AAC 64k mono...
  pronto: .../teste-expressividade2.m4b (1 MB)
```

Conferido com `ffprobe` no arquivo gerado — não na intenção do comando:

```
codec_name=aac      channels=1      sample_rate=24000
format_name=mov,mp4,m4a,3gp,3g2,mj2
duration=105.637000     bit_rate=60090

capítulos:
  'Parte 1'  0.0s -> 105.6s
  total: 1 capitulo(s)
```

A duração bate exatamente com a do livro no player (105,64 s), e o capítulo cobre
o arquivo inteiro, como esperado num livro de um capítulo só.

### Compressão medida

```
4,9M   storage/audio/2cfe9a63-.../     (WAV)
776K   teste-expressividade2.m4b       (AAC 64k mono)
```

**6,5× menor.** Extrapolando para "O Programador Pragmático" (~10,9 h, medido em
29/09: 1.001 caracteres → 61,0 s de fala): ~1,8 GB de WAV viram **~280 MB**.

## 5. Desvios do escopo original

Nenhum desvio de escopo. **Mas dois defeitos apareceram só ao rodar de verdade,
depois de os 18 testes passarem** — é o padrão recorrente deste projeto, e os dois
merecem registro:

1. **Caminho relativo na lista do `concat`.** O demuxer resolve caminho relativo
   contra o diretório **da lista**, que vive num temporário — não contra o CWD. Os
   `file_path` no banco são relativos (`storage/audio/<id>/0.wav`), então o
   `ffmpeg` procurava em `/tmp/tmpXXXX/storage/audio/...` e falhava. **Os testes
   passavam porque todos usavam caminho absoluto.** Corrigido com
   `os.path.abspath`, e com dois testes novos: um com caminho relativo (que
   falhava antes da correção) e um garantindo que absoluto não é mexido.

2. **`python scripts/export_book.py` falhava com `ModuleNotFoundError`.** O Python
   põe `scripts/` no caminho de import, não a raiz do projeto, então só a forma
   com `-m` funcionava. Como é o erro que qualquer pessoa cometeria primeiro,
   corrigi no script em vez de só documentar a forma certa.

Um detalhe de processo, sem efeito no código: a primeira mensagem de commit do
Green tinha crase, que o shell interpretou como substituição de comando e comeu
um trecho do texto. Corrigido com `--amend` passando a mensagem por `stdin`.

## 6. Dúvidas / bloqueios

Nenhum bloqueio. Três observações:

1. **Não há rota nem botão — é script, e está declarado na OS.** Codificar ~11 h
   de áudio leva minutos, o que não cabe numa requisição HTTP; fazer direito
   exigiria um `stage` novo na fila e mudanças no worker. Se o botão fizer falta
   **ao usar**, vira OS própria, informada por uso real — que é o critério que o
   dono definiu para o MVP.

2. **O arquivo de verdade ainda não foi ouvido num celular.** Esta verificação
   provou que o M4B é válido, que os capítulos estão nos instantes certos e que o
   tamanho cai 6,5× — mas quem decide se serve é o ouvido do dono, com o telefone
   na mão. Vale para o teste de escuta longa que continua aberto desde a OS-056.

3. **Só foi exportado um livro de 2 trechos e 1 capítulo.** O caso de 645 trechos
   e 348 capítulos é a mesma lógica, mas não foi exercitado — depende da rodada
   completa, que está bloqueada pelo driver da GPU (ver seção 7 do relatório da
   sessão). O risco concreto ali é o tempo de codificação e o tamanho do
   FFMETADATA com 348 capítulos, nenhum dos dois medido.

## 7. Link do PR

Ver o PR aberto contra `main` com título `[OS-062] Exportar o livro como arquivo único`.
