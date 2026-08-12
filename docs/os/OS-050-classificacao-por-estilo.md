# OS-050 — Classificação de blocos por estilo

## 1. Objetivo

Parar de narrar o que não é texto do autor — cabeçalho corrente, número de página e nota de rodapé — usando o estilo e a posição que o PDF já carrega e que a OS-049 passou a ler.

## 2. Escopo

Alterados:

- `plugins/extractors/pymupdf_extractor.py` — classificação de bloco e descarte do que não se narra.
- `tests/unit/extractors/test_pymupdf_extractor.py` e fixture nova.

Fora de escopo (declarado):

- **O contrato `Extractor` NÃO muda** — decisão do dono, 11/08/2026. A classificação age **na extração**: o bloco descartado não chega ao pipeline, e o que sobra continua sendo `text: str`. `TesseractOCR` e `EasyOCRExtractor` seguem intactos.
- **Entrega diferenciada para título e citação.** Dar pausa maior ao título ou registro diferente à citação exigiria carregar o *tipo* do bloco até o Speaker, ou seja, estender o contrato. Ficou para uma OS futura, **condicionada a evidência de escuta** de que ainda incomoda depois desta.
- **Reordenar nota de rodapé para o fim do capítulo.** Decisão do dono: descartar, como a OS-040 já faz com URL e e-mail.
- `processing/cleaner.py` — não é tocado. Ele continua removendo linha repetida em duas ou mais páginas; esta OS cobre o que escapa dessa regra.

## 3. Contratos envolvidos

Nenhum contrato de interface alterado — decisão explícita do dono. `ARQUITETURA.md`, seção do `Extractor`: assinatura e retorno preservados, como na OS-049.

## 4. Regras, e a medição que as sustenta

Medido em 70 páginas do miolo do "Programador Pragmático". Corpo = **9,7pt** (moda por caractere, 79.030 chars).

| Regra | Blocos | Exemplo real | Ação |
|---|---|---|---|
| Primeiro bloco com topo no terço superior da margem | 1 por página | `"CAPÍTULO 1  UMA FILOSOFIA PRAGMÁTICA  25"` | **descartar** |
| Tamanho ≤ 0,85× do corpo | 52 | `"1  Ao fazer isso, console-se com a frase..."` | **descartar** |
| Tamanho ≥ 1,35× do corpo | 56 | `"Uma Filosofia Pragmática"` | manter |
| ≥ 80% dos chars em itálico | 58 | `"A maior de todas as fraquezas é o medo..."` | manter |
| resto | 593 | — | manter |

**O cabeçalho corrente exige posição, não tamanho.** Ele está a 9,3pt — 0,96× do corpo — e escaparia de qualquer limiar de tamanho. O sinal confiável é a posição: medido em 10 páginas consecutivas, sempre o primeiro bloco, sempre em `y=53,9` numa página de altura 708,7 (**7,6% do topo**), alternando entre páginas pares e ímpares. É justamente essa alternância que o faz escapar do `clean_text`, que exige repetição idêntica.

**Risco conhecido, a tratar na implementação:** descartar o primeiro bloco por posição pode comer conteúdo numa página que comece com texto legítimo muito acima. Mitigação proposta: exigir **duas** condições — posição na faixa de topo **e** bloco curto (limiar a calibrar sobre os 31–50 chars medidos). O teste precisa cobrir uma página cujo primeiro bloco seja conteúdo real.

**Risco do limiar de 0,85×:** a classe "miúdo" também pegou URLs a 7,5pt. Como a OS-040 já troca URL por "link" antes, o descarte aqui é redundante e inofensivo — mas o teste deve garantir que texto pequeno **legítimo** não some.

## 5. Critérios de aceite

- [ ] Cabeçalho corrente não é narrado
- [ ] Número de página isolado não é narrado
- [ ] Nota de rodapé (bloco ≤ 0,85× do corpo) não é narrada
- [ ] Título (≥ 1,35×) continua sendo narrado, separado como na OS-049
- [ ] Citação (≥ 80% itálico) continua sendo narrada
- [ ] Página cujo primeiro bloco é conteúdo real **não** perde esse bloco
- [ ] O tamanho do corpo é medido **do documento**, não fixo em 9,7 — outro PDF terá outro corpo
- [ ] Contrato `Extractor` inalterado
- [ ] Nenhum teste existente quebra (313 hoje)

## 6. Testes exigidos (mínimo)

- `test_pymupdf_drops_running_header`
- `test_pymupdf_drops_footnote_block`
- `test_pymupdf_keeps_heading_block`
- `test_pymupdf_keeps_italic_quote_block`
- `test_pymupdf_keeps_first_block_when_it_is_real_content`
- `test_pymupdf_body_size_is_measured_per_document`
- `test_pymupdf_extract_contract_unchanged` (já existe — não pode quebrar)

## 7. Relatório

Ver `docs/report/OS-050-report.md`.
