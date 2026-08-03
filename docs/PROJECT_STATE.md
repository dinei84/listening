# PROJECT_STATE.md

Fonte única de verdade sobre o estado atual do projeto. Deve ser atualizado a cada OS concluída — quem faz a atualização é o próprio agente que finalizou a OS, como último passo antes de abrir o PR.

Se um agente novo entra no projeto, este é o primeiro arquivo que ele lê, antes de `ARQUITETURA.md` e `AGENTS.md`.

---

## 1. Visão em uma linha

App pessoal que converte PDF em audiobook (estilo Audible), com pipeline plugável de extração de texto/OCR e TTS, otimizado para baixo custo.

## 2. Status atual

**Fase:** OS-001 concluída — estrutura do repositório montada, dependências instaladas, smoke test passando.

**Última OS concluída:** OS-001 — Bootstrap do repositório e instalação de dependências.

**OS em andamento:** OS-002 — `core/models.py` (ver `docs/OS/OS-002-core-models.md`).

**Próxima OS a abrir após OS-002:** OS-003 — `plugins/extractors/base.py` + `PyMuPDFExtractor`.

## 3. Decisões já tomadas (Architecture Decision Log)

Registrar aqui toda decisão relevante, na ordem em que foram tomadas. Nunca apagar uma entrada — se uma decisão for revertida, adicionar uma nova entrada explicando o motivo, mantendo o histórico.

| # | Data | Decisão | Motivo |
|---|------|---------|--------|
| 1 | definir na 1ª OS | Arquitetura plugável para Extractor e Speaker via interface + registry | Permite trocar OCR/TTS sem reescrever pipeline; ver `ARQUITETURA.md` seção 1 |
| 2 | definir na 1ª OS | TTS local (Kokoro) como padrão, cloud como opção sob demanda | Controle de custo — ver brainstorm original |
| 3 | em aberto | Fila de jobs: Celery+Redis vs solução mais simples (SQLite como fila) | Pendente — depende do volume de uso real (projeto pessoal, não precisa de infra pesada) |
| 4 | em aberto | Banco de dados: SQLite (MVP) com migração futura para Postgres | Pendente confirmação |
| 5 | em aberto | Heurística de fallback de OCR (quando cair de Tesseract → PaddleOCR → cloud) | Precisa de uma OS dedicada de spike/pesquisa |

> Toda OS que tomar uma decisão de arquitetura nova ou alterar uma decisão existente deve atualizar esta tabela.

## 4. Componentes e status individual

| Componente | Status | Última OS | Observações |
|---|---|---|---|
| `core/models.py` | concluído (testado) | OS-001 | Stub vazio — implementação real é OS-002 |
| `core/pipeline.py` | concluído (testado) | OS-001 | Stub vazio — implementação real é OS-003+ |
| `core/config.py` | concluído (testado) | OS-001 | Stub vazio — implementação real é OS-003+ |
| `plugins/extractors/base.py` | concluído (testado) | OS-001 | Contém `class Extractor(ABC): pass` |
| `plugins/extractors/pymupdf_extractor.py` | concluído (testado) | OS-001 | Stub vazio — implementação real é OS-003 |
| `plugins/extractors/tesseract_ocr.py` | concluído (testado) | OS-001 | Stub vazio — implementação real é OS-004 |
| `plugins/speakers/base.py` | concluído (testado) | OS-001 | Contém `class Speaker(ABC): pass` |
| `plugins/speakers/kokoro_speaker.py` | concluído (testado) | OS-001 | Stub vazio — implementação real é OS-003 |
| `processing/cleaner.py` | concluído (testado) | OS-001 | Stub vazio — implementação real é OS-003+ |
| `processing/chunker.py` | concluído (testado) | OS-001 | Stub vazio — implementação real é OS-003+ |
| `api/` (FastAPI) | concluído (testado) | OS-001 | Stubs vazios — implementação real é OS-005 |
| `worker/` (fila) | concluído (testado) | OS-001 | Stub vazio — implementação real é OS-005+ |
| `storage/` | concluído (testado) | OS-001 | Stubs vazios — implementação real é OS-005+ |
| `player/` (frontend) | concluído (testado) | OS-001 | Stub vazio — implementação real é OS-006 |

Valores possíveis de status: `não iniciado` · `em andamento` · `implementado sem testes` · `concluído (testado)` · `bloqueado`.

## 5. Backlog priorizado (próximas OS candidatas)

1. **OS-001 — Bootstrap do repositório e instalação de dependências** — status: concluída
2. **OS-002 — `core/models.py`** — modelos de dados base — status: aberta, aguardando OS-001
3. Spike: definir heurística de confiança de OCR (decisão #5 pendente em `PROJECT_STATE.md` seção 3)
4. `plugins/extractors/base.py` + `PyMuPDFExtractor` (com testes)
5. `plugins/speakers/base.py` + `KokoroSpeaker` (com testes, sem chamar engine real em CI)
6. `core/pipeline.py` — orquestração síncrona mínima ligando extractor → processor → speaker
7. `processing/cleaner.py` e `processing/chunker.py`
8. API mínima (`POST /books`, `GET /books/{id}/status`)
9. Player web básico

## 6. Riscos e bloqueios conhecidos

- `tesseract` binary não instalado no sistema — `pytesseract` importa mas não executa sem o binário. Documentado no README.md do código.
- Decisões #3, #4, #5 ainda em aberto (fila de jobs, banco de dados, heurística de fallback de OCR).

## 7. Como este arquivo deve ser mantido

- Atualizar a seção 2 (status atual) e 4 (componentes) a cada OS concluída.
- Mover item do backlog (seção 5) para "implementado" só depois que o DoD da OS foi cumprido, não quando o código foi só escrito.
- Nunca editar o log de decisões (seção 3) retroativamente — só adicionar.
