# PROJECT_STATE.md

Fonte única de verdade sobre o estado atual do projeto. Deve ser atualizado a cada OS concluída — quem faz a atualização é o próprio agente que finalizou a OS, como último passo antes de abrir o PR.

Se um agente novo entra no projeto, este é o primeiro arquivo que ele lê, antes de `ARQUITETURA.md` e `AGENTS.md`.

---

## 1. Visão em uma linha

App pessoal que converte PDF em audiobook (estilo Audible), com pipeline plugável de extração de texto/OCR e TTS, otimizado para baixo custo.

## 2. Status atual

**Fase:** OS-006 concluída — `TesseractOCR` implementado com a fórmula de confidence aprovada (decisão #9) e 7 testes passando.

**Última OS concluída:** OS-006 — TesseractOCR.

**OS em andamento:** nenhuma.

**Próxima OS a abrir após OS-006:** a definir — candidato no backlog é `core/pipeline.py`.

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
| 8 | 2026-08-03 | Proposta (OS-005): considerar OCR "confiança baixa" quando `avg_confidence_words_normalized < 0.85` **ou** `words_counted == 0`; nesses casos, cair para o próximo extractor da cadeia (`TesseractOCR` → `PaddleOCR` → `CloudOCRFallback`) | Spike empírico com Tesseract 5.3.4 em 4 fixtures mostrou cenários de alta confiança (~0.90-0.96) e falha total (`words_counted == 0`, confiança 0.0) em imagem muito degradada. PaddleOCR confidence pesquisado em documentação oficial (`rec_score` / `rec_scores`) mas **não validado empiricamente** neste ambiente |
| 9 | 2026-08-03 | **Decisão #8 aprovada pelo dono do projeto, sem alterações.** A heurística `avg_confidence_words_normalized < 0.85` ou `words_counted == 0` é agora oficial e foi incorporada em `ARQUITETURA.md` seção 4.1. Isso resolve a decisão #5 | Aprovação explícita em conversa, após revisão que confirmou a reprodutibilidade dos números do spike. Ressalva conhecida (não invalida a aprovação): as fixtures usadas cobriram bem sucesso (~0.90-0.96) e falha total (0.0), mas não um caso de degradação intermediária — `0.85` é uma margem de segurança, não um ponto fino validado empiricamente |

> Toda OS que tomar uma decisão de arquitetura nova ou alterar uma decisão existente deve atualizar esta tabela.

## 4. Componentes e status individual

| Componente | Status | Última OS | Observações |
|---|---|---|---|
| `core/models.py` | concluído (testado) | OS-002 | 5 modelos Pydantic implementados com validações de status |
| `core/pipeline.py` | não iniciado | OS-001 | Stub vazio — implementação real é OS-003+ |
| `core/config.py` | não iniciado | OS-001 | Stub vazio — implementação real é OS-003+ |
| `plugins/extractors/base.py` | concluído (testado) | OS-003 | Classe abstrata `Extractor` com `supports()` e `extract()` |
| `plugins/extractors/pymupdf_extractor.py` | concluído (testado) | OS-003 | `PyMuPDFExtractor` com suporte a PDF nativo e image-only |
| `plugins/extractors/tesseract_ocr.py` | concluído (testado) | OS-006 | `TesseractOCR` com fórmula de confidence aprovada (decisão #9) |
| `plugins/speakers/base.py` | concluído (testado) | OS-004 | Classe abstrata `Speaker` com `synthesize()` e `cost_per_char` |
| `plugins/speakers/kokoro_speaker.py` | concluído (testado) | OS-004 | `KokoroSpeaker` com mock de inferência nos testes |
| `processing/cleaner.py` | não iniciado | OS-001 | Stub vazio — implementação real é OS-003+ |
| `processing/chunker.py` | não iniciado | OS-001 | Stub vazio — implementação real é OS-003+ |
| `api/` (FastAPI) | não iniciado | OS-001 | Stubs vazios — implementação real é OS-005+ |
| `worker/` (fila) | não iniciado | OS-001 | Stub vazio — implementação real é OS-005+ |
| `storage/` | não iniciado | OS-001 | Stubs vazios — implementação real é OS-005+ |
| `player/` (frontend) | não iniciado | OS-001 | Stub vazio — implementação real é OS-007+ |

Valores possíveis de status: `não iniciado` · `em andamento` · `implementado sem testes` · `concluído (testado)` · `bloqueado`.

## 5. Backlog priorizado (próximas OS candidatas)

1. **OS-001 — Bootstrap do repositório e instalação de dependências** — status: concluída
2. **OS-002 — `core/models.py`** — modelos de dados base — status: concluída
3. **OS-003 — `plugins/extractors/base.py` + `PyMuPDFExtractor`** — status: concluída
4. **OS-004 — `plugins/speakers/base.py` + `KokoroSpeaker`** — status: concluída
5. **OS-005 — Spike: heurística de confiança de OCR** (decisão #5) — status: concluída, heurística aprovada (decisão #9)
6. **OS-006 — `plugins/extractors/tesseract_ocr.py`** — `TesseractOCR` usando a heurística aprovada — status: concluída
7. `core/pipeline.py` — orquestração síncrona mínima ligando extractor → processor → speaker
8. `processing/cleaner.py` e `processing/chunker.py`
9. API mínima (`POST /books`, `GET /books/{id}/status`)
10. Player web básico

## 6. Riscos e bloqueios conhecidos

- Decisões #3 e #4 ainda em aberto (fila de jobs e banco de dados).
- Confidence do PaddleOCR foi levantado por documentação oficial (`rec_score` / `rec_scores`) sem validação empírica local no spike — validar quando `PaddleOCR` ganhar OS própria.
- Threshold `0.85` (decisão #9) é uma margem de segurança, não um ponto fino validado empiricamente — as fixtures do spike não cobriram degradação intermediária. Se `TesseractOCR` em produção mostrar falsos positivos/negativos de fallback, revisitar com mais dados.

## 7. Como este arquivo deve ser mantido

- Atualizar a seção 2 (status atual) e 4 (componentes) a cada OS concluída.
- Mover item do backlog (seção 5) para "implementado" só depois que o DoD da OS foi cumprido, não quando o código foi só escrito.
- Nunca editar o log de decisões (seção 3) retroativamente — só adicionar.
