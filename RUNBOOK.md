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

## 5. Testar o fluxo completo pelo navegador

1. Abrir `http://localhost:8000/` — é o player, servido como arquivo estático pela própria API.
2. Escolher um PDF e clicar em "Enviar". Um PDF com texto nativo processa mais rápido (vai direto pelo `PyMuPDFExtractor`); um PDF escaneado cai para o `TesseractOCR` (mais lento).
3. A página faz polling do status a cada 2s. Acompanhe também os logs do Terminal 2 (worker) — é lá que o processamento de fato acontece.
4. Quando o status virar `ready`, o áudio começa a tocar sozinho.
5. Testar play/pause, trocar a velocidade (dropdown), recarregar a página (deve oferecer "Retomar de onde parou?").
6. Pra reabrir um livro processado antes, usar o campo "Abrir livro existente" com o `id` devolvido no upload (aparece na tela e também em `GET /books/{id}/status`).

### Testar só a API, sem o navegador

```bash
# Enviar um PDF
curl -s -X POST http://127.0.0.1:8000/books \
  -F "file=@tests/fixtures/native_text_sample.pdf;type=application/pdf"
# => {"id": "...", "status": "uploaded"}

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
- **Livro fica travado em `status: "uploaded"`** — o worker não está rodando. Ver passo 4, Terminal 2.
- **Primeira síntese demora muito / aviso de "unauthenticated requests to the HF Hub"** — esperado na primeira vez que o Kokoro roda: ele baixa os pesos do modelo. Não é erro.
- **Porta 8000 já em uso** — trocar a porta no comando do `uvicorn` (`--port 8001`, por exemplo) e ajustar a URL usada no navegador/curl de acordo.

## Referências

- `docs/HANDOFF.md` — contexto e histórico do projeto
- `docs/PROJECT_STATE.md` — estado atual, decisões, backlog
- `docs/ARQUITETURA.md` — contratos técnicos, estrutura de pastas
- `docs/TDD.md` — metodologia de testes
- `docs/os/` — Ordens de Serviço já definidas
- `docs/report/` — relatórios de entrega de cada OS
