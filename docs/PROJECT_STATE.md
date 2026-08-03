# PROJECT_STATE.md

Fonte única de verdade sobre o estado atual do projeto. Deve ser atualizado a cada OS concluída — quem faz a atualização é o próprio agente que finalizou a OS, como último passo antes de abrir o PR.

Se um agente novo entra no projeto, este é o primeiro arquivo que ele lê, antes de `ARQUITETURA.md` e `AGENTS.md`.

---

## 1. Visão em uma linha

App pessoal que converte PDF em audiobook (estilo Audible), com pipeline plugável de extração de texto/OCR e TTS, otimizado para baixo custo.

## 2. Status atual

**Fase:** Planejamento / arquitetura — nenhum código implementado ainda.

**Última OS concluída:** nenhuma.

**OS em andamento:** OS-001 — Bootstrap do repositório e instalação de dependências (ver `docs/os/OS-001-bootstrap-setup.md`).

**Próxima OS a abrir após OS-001:** OS-002 — `core/models.py` (ver `docs/os/OS-002-core-models.md`).

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
| `core/models.py` | não iniciado | — | |
| `core/pipeline.py` | não iniciado | — | |
| `core/config.py` | não iniciado | — | |
| `plugins/extractors/base.py` | não iniciado | — | |
| `plugins/extractors/pymupdf_extractor.py` | não iniciado | — | |
| `plugins/extractors/tesseract_ocr.py` | não iniciado | — | |
| `plugins/speakers/base.py` | não iniciado | — | |
| `plugins/speakers/kokoro_speaker.py` | não iniciado | — | |
| `processing/cleaner.py` | não iniciado | — | |
| `processing/chunker.py` | não iniciado | — | |
| `api/` (FastAPI) | não iniciado | — | |
| `worker/` (fila) | não iniciado | — | |
| `storage/` | não iniciado | — | |
| `player/` (frontend) | não iniciado | — | |

Valores possíveis de status: `não iniciado` · `em andamento` · `implementado sem testes` · `concluído (testado)` · `bloqueado`.

## 5. Backlog priorizado (próximas OS candidatas)

1. **OS-001 — Bootstrap do repositório e instalação de dependências** — status: aberta, aguardando execução
2. **OS-002 — `core/models.py`** — modelos de dados base — status: aberta, aguardando OS-001
3. Spike: definir heurística de confiança de OCR (decisão #5 pendente em `PROJECT_STATE.md` seção 3)
4. `plugins/extractors/base.py` + `PyMuPDFExtractor` (com testes)
5. `plugins/speakers/base.py` + `KokoroSpeaker` (com testes, sem chamar engine real em CI)
6. `core/pipeline.py` — orquestração síncrona mínima ligando extractor → processor → speaker
7. `processing/cleaner.py` e `processing/chunker.py`
8. API mínima (`POST /books`, `GET /books/{id}/status`)
9. Player web básico

## 6. Riscos e bloqueios conhecidos

- Nenhum ainda — projeto em fase zero.

## 7. Como este arquivo deve ser mantido

- Atualizar a seção 2 (status atual) e 4 (componentes) a cada OS concluída.
- Mover item do backlog (seção 5) para "implementado" só depois que o DoD da OS foi cumprido, não quando o código foi só escrito.
- Nunca editar o log de decisões (seção 3) retroativamente — só adicionar.
