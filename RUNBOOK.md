# RUNBOOK.md — Como rodar e testar a aplicação localmente

Guia prático pra subir o app do zero numa máquina nova e testar o fluxo completo (PDF → texto → áudio → player). Para entender o *porquê* das decisões de arquitetura, ver `docs/HANDOFF.md` e `docs/ARQUITETURA.md` — este arquivo é só o "como rodar".

---

## 1. Pré-requisitos de sistema

```bash
# Tesseract OCR (necessário para pytesseract / TesseractOCR)
sudo apt-get install tesseract-ocr

# espeak-ng (necessário para o Kokoro fazer G2P/fonemização)
sudo apt-get install espeak-ng
```

Confirmar que instalou:

```bash
tesseract --version
```

## 2. Setup do ambiente Python

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

## 3. Rodar a suíte de testes

```bash
pytest
```

Deve passar 100% sem tocar em rede, Tesseract ou Kokoro de verdade — todos os testes usam dublês fake dos plugins (ver `docs/TDD.md`). Se algo falhar aqui, não prossiga para os passos seguintes sem investigar.

## 4. Subir a aplicação de verdade

A aplicação tem **dois processos** que precisam rodar ao mesmo tempo, em janelas de terminal separadas (com o venv ativado nas duas):

### Terminal 1 — API

```bash
source venv/bin/activate
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

### Terminal 2 — Worker

```bash
source venv/bin/activate
python -m worker.tasks
```

**Se você só subir a API sem o worker, os livros enviados ficam parados em `status: "uploaded"` para sempre** — é o worker que efetivamente processa (extrai, sintetiza) e persiste o áudio. Isso é esperado, não é bug (decisão #11 em `docs/PROJECT_STATE.md`).

Na primeira vez que o worker processar um livro, o Kokoro baixa os pesos do modelo do Hugging Face Hub — espere alguns segundos a mais nessa primeira execução (chamadas seguintes são mais rápidas, o modelo fica em cache).

**Interromper o worker (Ctrl+C) no meio de um livro não perde o trabalho já feito** (desde a OS-022): ao subir de novo, ele devolve para a fila todo `Job` que ficou preso em `running` e continua a síntese a partir do primeiro chunk que ainda não foi persistido. Isso assume **um único worker rodando por vez** — se você subir dois, o segundo vai devolver para a fila o `Job` que o primeiro está processando de verdade.

## 5. Testar o fluxo completo pelo navegador

1. Abrir `http://localhost:8000/` — é o player, servido como arquivo estático pela própria API.
2. Escolher um PDF e clicar em "Enviar". Um PDF com texto nativo processa mais rápido (vai direto pelo `PyMuPDFExtractor`); um PDF escaneado cai para o `TesseractOCR` (mais lento). O seletor "Idioma" (padrão: "Automático") deixa forçar o idioma do livro no upload — útil quando a detecção automática erra (texto curto, PDF misto). Obs.: japonês e mandarim aparecem na lista mas degradam pro inglês neste ambiente (limitação já conhecida da OS-020, ver `docs/PROJECT_STATE.md` seção 6).
3. A página faz polling do status a cada 2s. Acompanhe também os logs do Terminal 2 (worker) — é lá que o processamento de fato acontece.
4. O áudio começa a tocar assim que o **primeiro trecho** fica pronto, sem esperar o livro inteiro (desde a OS-030) — a barra de progresso continua mostrando quanto falta sintetizar. Se a reprodução alcançar a síntese, o player mostra "Aguardando próximo trecho..." e retoma sozinho quando o trecho seguinte fica pronto.
5. Testar play/pause, trocar a velocidade (dropdown), recarregar a página (deve oferecer "Retomar de onde parou?").
6. Pra reabrir um livro processado antes, usar o campo "Abrir livro existente" com o `id` devolvido no upload (aparece na tela e também em `GET /books/{id}/status`).
7. **"Processar agora"** (desde a OS-032): cada livro da lista que está apenas enfileirado (`uploaded`) ou pausado (`paused`) tem esse botão. Clicar nele pausa a síntese em andamento no fim do chunk corrente (~1s) e coloca o livro escolhido no topo da fila — o livro pausado fica `paused`, com o áudio já gerado tocável, e retoma de onde parou quando for re-priorizado.
8. **UX da lista (desde a OS-033):** o cabeçalho do player mostra o **título** do livro (não mais o UUID cru); clicar num livro da lista preenche o campo "Abrir livro existente"; um livro apenas enfileirado aparece como **"Na fila — aguardando processamento"** (o status cru `uploaded` fica só na API); e um livro `uploaded` pode ser **deletado** — só `extracting`/`processing`/`synthesizing` continuam bloqueados (409) enquanto o worker escreve.

### Testar só a API, sem o navegador

```bash
# Enviar um PDF
curl -s -X POST http://127.0.0.1:8000/books \
  -F "file=@tests/fixtures/native_text_sample.pdf;type=application/pdf"
# => {"id": "...", "status": "uploaded"}

# Enviar um PDF forçando o idioma (opcional; valores válidos são os mesmos
# do langdetect: en/es/fr/hi/it/pt/ja/zh-cn/zh-tw; inválido cai pra automático)
curl -s -X POST http://127.0.0.1:8000/books \
  -F "file=@tests/fixtures/native_text_sample.pdf;type=application/pdf" \
  -F "language=pt"

# Checar status (repetir até "ready" ou "error")
curl -s http://127.0.0.1:8000/books/<id>/status

# Listar os chunks de áudio de um livro pronto
curl -s http://127.0.0.1:8000/books/<id>/audio

# Baixar um chunk específico
curl -s http://127.0.0.1:8000/books/<id>/audio/0 -o chunk0.wav
```

Fixtures de PDF já existentes no repo pra testar sem precisar de um PDF próprio: `tests/fixtures/native_text_sample.pdf` (texto nativo), `tests/fixtures/image_only_sample.pdf` e `tests/fixtures/ocr/*.pdf` (caminho de OCR).

## 6. Onde ficam os dados

Tudo abaixo é gerado em runtime, **não é versionado** (está no `.gitignore`) — pode apagar a qualquer momento pra resetar o estado local:

| Caminho | O que é |
|---|---|
| `books.db` | SQLite com metadados de livros (`books`), jobs da fila (`jobs`) e metadados de áudio (`audio_chunks`) — tudo no mesmo arquivo |
| `uploads/` | PDFs enviados via `POST /books` |
| `storage/audio/{book_id}/` | Arquivos `.wav` gerados pelo Speaker, um por chunk |

Resetar tudo:

```bash
rm -rf books.db uploads storage/audio
```

(a API recria o schema do zero automaticamente na próxima subida, via `lifespan` em `api/main.py`)

## 6.1 Dicionário fonético (pronúncia de termos específicos)

O Kokoro fonemiza português com **espeak-ng**, um motor baseado em regras — por isso alguns termos (siglas, estrangeirismos, nomes próprios) saem com pronúncia errada. O arquivo `plugins/speakers/phonetic_map.yaml` corrige termo a termo:

```yaml
JSON: djêizon         # chave = como aparece no texto; valor = grafia que o G2P acerta
```

A troca acontece antes da fonemização, respeita fronteira de palavra (não casa dentro de outra palavra) e ignora maiúsculas/minúsculas na busca.

**Para adicionar uma entrada, verifique antes se ela realmente melhora** — comparando o G2P **dentro de uma frase**, não com o termo isolado (o espeak lê o mesmo termo de formas diferentes conforme o contexto):

```bash
python -c "
import kokoro
from plugins.speakers.kokoro_speaker import _apply_phonetic_map
pt = kokoro.KPipeline(lang_code='p', repo_id='hexgrad/Kokoro-82M', model=False)
frase = 'O arquivo JSON foi salvo.'
print('antes :', pt.g2p(frase)[0])
print('depois:', pt.g2p(_apply_phonetic_map(frase))[0])
"
```

Se a fonemização não melhorar, **não adicione** — uma "correção" pior que o erro original só piora o áudio. Na OS-037 o termo `cache` foi testado e rejeitado por isso (`kˈaʃy` ficou melhor que `kˈɛksi`).

O mapa é lido uma vez por processo. Arquivo ausente ou malformado degrada para "sem substituição" — nunca derruba a síntese; reinicie o worker depois de editar.

## 7. Configuração

`config.yaml` na raiz define qual plugin usar em cada categoria:

```yaml
extractor: pymupdf   # extractor primário; cai para tesseract se supports() for False
speaker: kokoro
queue: sqlite
```

Trocar qualquer um desses nomes exige que a classe correspondente já esteja registrada em `plugins/registry.py` — ver `docs/ARQUITETURA.md` seção 4.4.

## 8. Problemas comuns

- **`tesseract: comando não encontrado`** — instalar via `sudo apt-get install tesseract-ocr` (passo 1). Precisa de senha interativa; não dá pra automatizar num agente sem acesso a terminal do usuário.
- **Livro fica travado em `status: "uploaded"`** — o worker não está rodando. Ver passo 4, Terminal 2. Na UI o livro aparece como "Na fila — aguardando processamento" (OS-033) e, como o worker nunca tocou nele, pode ser deletado sem risco.
- **Primeira síntese demora muito / aviso de "unauthenticated requests to the HF Hub"** — esperado na primeira vez que o Kokoro roda: ele baixa os pesos do modelo. Não é erro.
- **Porta 8000 já em uso** — trocar a porta no comando do `uvicorn` (`--port 8001`, por exemplo) e ajustar a URL usada no navegador/curl de acordo.
- **`retomada inconsistente: existem AudioChunks persistidos até a sequence N...`** — o livro tinha chunks de uma tentativa anterior que não batem com o texto re-extraído agora (o PDF mudou, ou a lógica de limpeza/chunking mudou entre as duas tentativas). O worker **não** apaga nada nesse caso: marca o livro como `error` com essa mensagem e pede reenvio. Reenviar o PDF gera um `book_id` novo e processa do zero.
- **`sqlite3.OperationalError: table books has no column named chunk_total`** — coluna nova adicionada na OS-024 pra barra de progresso da síntese. Igual ao que já aconteceu com `error_message` na OS-018, não existe migração de schema: um `books.db` local criado antes desta OS precisa ser apagado (ver seção 6, "Resetar tudo") pra recriar o schema com a coluna nova.
- **`sqlite3.OperationalError: table books has no column named language`** — coluna nova adicionada na OS-025 pra seleção manual de idioma. Mesmo padrão do `chunk_total` (OS-024): sem migração de schema, apagar `books.db` (ver seção 6, "Resetar tudo") pra recriar o schema com a coluna nova.
- **`sqlite3.OperationalError: table jobs has no column named priority`** — coluna nova adicionada na OS-032 pra preempção de fila ("Processar agora"). Mesmo padrão do `language` (OS-025): sem migração de schema, apagar `books.db` (ver seção 6, "Resetar tudo") pra recriar o schema com a coluna nova.
- **Livros processados antes da OS-019 têm pronúncia incorreta** — até a OS-019, `KokoroSpeaker` chamava a API errada do Kokoro (`generate_from_tokens` com texto bruto, sem rodar o G2P de verdade), gerando áudio com pronúncia errada em todo livro processado desde a OS-004 (decisão #14 em `docs/PROJECT_STATE.md`). Não há reprocessamento automático — reenviar manualmente qualquer livro que já estava `ready` antes dessa correção pra gerar o áudio de novo com a pronúncia certa.

## Referências

- `docs/HANDOFF.md` — contexto e histórico do projeto
- `docs/PROJECT_STATE.md` — estado atual, decisões, backlog
- `docs/ARQUITETURA.md` — contratos técnicos, estrutura de pastas
- `docs/TDD.md` — metodologia de testes
- `docs/os/` — Ordens de Serviço já definidas
- `docs/report/` — relatórios de entrega de cada OS
