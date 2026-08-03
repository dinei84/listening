# PROJECT_STATE.md

Fonte única de verdade sobre o estado atual do projeto. Deve ser atualizado a cada OS concluída — quem faz a atualização é o próprio agente que finalizou a OS, como último passo antes de abrir o PR.

Se um agente novo entra no projeto, este é o primeiro arquivo que ele lê, antes de `ARQUITETURA.md` e `AGENTS.md`.

---

## 1. Visão em uma linha

App pessoal que converte PDF em audiobook (estilo Audible), com pipeline plugável de extração de texto/OCR e TTS, otimizado para baixo custo.

## 2. Status atual

**Fase:** OS-002 concluída — `core/models.py` implementado com modelos Pydantic e 4 testes passando.

**Última OS concluída:** OS-002 — Modelos de dados base (`core/models.py`).

**OS em andamento:** OS-003 — Extractor base + `PyMuPDFExtractor` (ver `docs/os/OS-003-pymupdf-extractor.md`).

**Próxima OS a abrir após OS-003:** a definir — candidatos no backlog (seção 5) são o spike de heurística de OCR ou `KokoroSpeaker`.

## 3. Decisões já tomadas (Architecture Decision Log)

Registrar aqui toda decisão relevante, na ordem em que foram tomadas. Nunca apagar uma entrada — se uma decisão for revertida, adicionar uma nova entrada explicando o motivo, mantendo o histórico.

| # | Data | Decisão | Motivo |
|---|------|---------|--------|
| 1 | definir na 1ª OS | Arquitetura plugável para Extractor e Speaker via interface + registry | Permite trocar OCR/TTS sem reescrever pipeline; ver `ARQUITETURA.md` seção 1 |
| 2 | definir na 1ª OS | TTS local (Kokoro) como padrão, cloud como opção sob demanda | Controle de custo — ver brainstorm original |
| 3 | em aberto | Fila de jobs: Celery+Redis vs solução mais simples (SQLite como fila) | Pendente — depende do volume de uso real (projeto pessoal, não precisa de infra pesada) |
| 4 | em aberto | Banco de dados: SQLite (MVP) com migração futura para Postgres | Pendente confirmação |
| 5 | em aberto | Heurística de fallback de OCR (quando cair de Tesseract → PaddleOCR → cloud) | Precisa de uma OS dedicada de spike/pesquisa |
| 6 | 2026-08-03 | Atualizações de governança (`AGENTS.md`, `README.md`, `TEMPLATE.md` etc.) feitas aqui no repositório de arquitetura precisam ser baixadas e commitadas manualmente no repositório de código — não há sincronização automática | Descoberto durante a OS-001: mudanças ficaram como "não commitadas" no repo de código e quase foram atribuídas erroneamente a um agente de execução. Toda vez que a documentação de governança for atualizada aqui, o próximo agente deve confirmar via `git diff` contra o último commit se os docs já estão sincronizados antes de assumir que uma mudança veio de execução indevida |
| 7 | 2026-08-03 | Estrutura de documentação do repositório de código usa `docs/os/` e `docs/report/` em minúsculo (não `docs/OS/`/`docs/REPORT/`) | Encontrada divergência de caixa entre o que a governança definia e o que existia no repo de código; corrigido por renomeação para bater com a convenção documentada em `README.md` |

> Toda OS que tomar uma decisão de arquitetura nova ou alterar uma decisão existente deve atualizar esta tabela.

## 4. Componentes e status individual

| Componente | Status | Última OS | Observações |
|---|---|---|---|
| `core/models.py` | concluído (testado) | OS-002 | 5 modelos Pydantic implementados com validações de status |
| `core/pipeline.py` | não iniciado | OS-001 | Stub vazio — implementação real é OS-003+ |
| `core/config.py` | não iniciado | OS-001 | Stub vazio — implementação real é OS-003+ |
| `plugins/extractors/base.py` | não iniciado | OS-001 | Contém só `class Extractor(ABC): pass` |
| `plugins/extractors/pymupdf_extractor.py` | não iniciado | OS-001 | Stub vazio — implementação real é OS-003 |
| `plugins/extractors/tesseract_ocr.py` | não iniciado | OS-001 | Stub vazio — implementação real é OS-004 |
| `plugins/speakers/base.py` | não iniciado | OS-001 | Contém só `class Speaker(ABC): pass` |
| `plugins/speakers/kokoro_speaker.py` | não iniciado | OS-001 | Stub vazio — implementação real é OS-003 |
| `processing/cleaner.py` | não iniciado | OS-001 | Stub vazio — implementação real é OS-003+ |
| `processing/chunker.py` | não iniciado | OS-001 | Stub vazio — implementação real é OS-003+ |
| `api/` (FastAPI) | não iniciado | OS-001 | Stubs vazios — implementação real é OS-005+ |
| `worker/` (fila) | não iniciado | OS-001 | Stub vazio — implementação real é OS-005+ |
| `storage/` | não iniciado | OS-001 | Stubs vazios — implementação real é OS-005+ |
| `player/` (frontend) | não iniciado | OS-001 | Stub vazio — implementação real é OS-006 |

Valores possíveis de status: `não iniciado` · `em andamento` · `implementado sem testes` · `concluído (testado)` · `bloqueado`.

## 5. Backlog priorizado (próximas OS candidatas)

1. **OS-001 — Bootstrap do repositório e instalação de dependências** — status: concluída
2. **OS-002 — `core/models.py`** — modelos de dados base — status: concluída
3. **OS-003 — `plugins/extractors/base.py` + `PyMuPDFExtractor`** — status: aberta, aguardando execução (ver `docs/os/OS-003-pymupdf-extractor.md`)
4. Spike: definir heurística de confiança de OCR (decisão #5 pendente em `PROJECT_STATE.md` seção 3)
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
