# OS-005 — Spike: heurística de fallback de OCR (decisão #5)

> Esta OS é diferente das anteriores: é uma OS de **pesquisa/decisão**, não de implementação. O entregável é uma recomendação fundamentada em evidência, documentada em `PROJECT_STATE.md`, não código de produção. Ver seção 5 (adaptação das regras de teste) antes de começar.

## 1. Objetivo

Decidir, com números reais e não achismo, a heurística concreta que o pipeline vai usar para cair de um extractor para o próximo mais caro na cadeia já definida em `ARQUITETURA.md` seção 4.1: `PyMuPDFExtractor` → `TesseractOCR` → `PaddleOCR` → `CloudOCRFallback`. Isso resolve a decisão #5, hoje "em aberto" em `PROJECT_STATE.md` seção 3.

## 2. Escopo

**Dentro do escopo:**
- Pesquisar como `pytesseract`/Tesseract expõe confidence score (por palavra, por linha, por página — `image_to_data()` é o caminho usual).
- Se `tesseract` (binário do sistema) não estiver instalado neste ambiente, instalar via `sudo apt install -y tesseract-ocr` antes de rodar o experimento. Se não houver permissão de `sudo` no ambiente do agente, parar aqui e reportar isso como bloqueio na seção de dúvidas do relatório — não simular ou estimar números sem rodar de verdade.
- Rodar Tesseract de verdade sobre pelo menos 3 fixtures de qualidade diferente (ex: PDF/imagem nítida, imagem de baixa qualidade/desfocada, PDF nativo forçado como imagem) e registrar o confidence real reportado para cada uma. Fixtures podem ser geradas no próprio spike (não precisam ser bonitas, só precisam ter uma diferença real de legibilidade) e commitadas em `tests/fixtures/` se forem pequenas.
- Pesquisar (documentação oficial, sem precisar instalar) como o PaddleOCR expõe confidence, para comparação — só instalar a lib se isso for rápido e leve; se for pesado/lento, documentar com base na documentação oficial e marcar explicitamente como "não validado empiricamente aqui".
- Propor um valor de threshold **concreto** (ex.: "confidence médio de página < 0.75 cai para o próximo extractor da cadeia"), com a justificativa baseada nos números do experimento.
- Propor como o campo `ExtractedPage.confidence` deve ser preenchido por `TesseractOCR` e `PaddleOCR` quando forem implementados (hoje só `PyMuPDFExtractor` existe, com `confidence` fixo em `1.0`).

**Fora do escopo:**
- Implementar `TesseractOCR`, `PaddleOCR` ou `CloudOCRFallback` de verdade — isso é OS futura, só depois que esta heurística for aprovada.
- Qualquer chamada a Cloud OCR (API paga) — fica só citado por completude, nunca executado.
- Editar `ARQUITETURA.md` para tornar a heurística definitiva. O agente entrega a **recomendação**; a mudança de contrato (se houver) só é commitada depois de aprovação explícita do dono do projeto (`AGENTS.md` seção 2: agente não decide arquitetura sozinho).

## 3. Contratos envolvidos

`ARQUITETURA.md` seção 4.1 (regra de decisão do pipeline, hoje só descrita em prosa: "se `supports()` retornar `False` ou a confiança vier baixa...") e o campo `ExtractedPage.confidence` (seção 5). Esta OS propõe uma especificação concreta para "confiança vier baixa" — hoje isso não tem número nenhum definido.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] Relatório explica, com fonte (doc oficial ou código-fonte lido), como o confidence score do Tesseract funciona
- [ ] Relatório explica, com fonte, como funcionaria o confidence score do PaddleOCR (empírico se viável, documental se não)
- [ ] Ao menos 3 execuções reais do Tesseract sobre fixtures de qualidade diferente, com números reais colados no relatório (não estimados)
- [ ] Recomendação final tem um número concreto de threshold, não uma faixa vaga
- [ ] Recomendação é registrada em `PROJECT_STATE.md` como proposta pendente de aprovação (nova linha na tabela de decisões, seção 3 — a linha #5 original nunca é apagada, só uma nova entrada é adicionada conforme a regra da seção 7)
- [ ] Nenhuma chamada a API paga (Cloud OCR) durante o spike
- [ ] Se o binário do Tesseract não puder ser instalado no ambiente, isso está claramente registrado como bloqueio — nenhum número é inventado para compensar

## 5. Testes exigidos (adaptado — isto não é uma OS de implementação)

Não há código de produção nem testes automatizados permanentes obrigatórios aqui. Em vez disso:
- Um script descartável (pode viver só em `docs/report/OS-005-report.md` colado como bloco de código, ou em `scripts/spike_ocr_confidence.py` se for mais prático) que roda Tesseract sobre as fixtures e imprime o confidence por página/palavra.
- A saída bruta e completa desse script colada no relatório, sem resumir.

Isso segue a mesma lógica já usada na OS-001B (auditoria): quando a OS não produz código de produção, o "teste" vira "evidência reproduzível colada no relatório".

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-005-report.md` (adaptar o template em `docs/report/REPORT_TEMPLATE.md` — a seção "Testes escritos" vira "Experimentos rodados").*
