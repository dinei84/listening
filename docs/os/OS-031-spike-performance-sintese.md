# OS-031 — Spike: performance da síntese (batching / tamanho de chunk)

> **É um spike, não uma OS de implementação.** O objetivo é medir e recomendar, não otimizar. Nenhuma mudança de comportamento em produção deve sair desta OS — igual à OS-005 (spike da heurística de OCR), cuja decisão foi aprovada pelo dono do projeto **depois**, como decisão #9.

## 1. Objetivo

Medição feita em uso real (2026-08-05, livro "Security Engineering", RTX 3060 com CUDA ativo) estabeleceu a linha de base atual: **1,34 s/chunk**, ~14 s de áudio gerado por segundo de processamento, 3334 chunks (≈40h de áudio) em ~74 min. Não é patológico, mas nunca foi investigado se dá pra fazer melhor. Este spike mede se batching na GPU, chunks maiores, ou outra configuração do Kokoro trazem ganho real — com números, não com intuição.

## 2. Escopo

**Dentro do escopo:**
- Script de medição em `scripts/` (a pasta já existe), **fora** do caminho de produção — não alterar `core/`, `plugins/`, `worker/` ou `api/`.
- Estabelecer a linha de base de forma reproduzível: tempo por chunk e razão áudio-gerado/tempo-de-processamento, com o código atual, num texto fixo de tamanho conhecido.
- Medir pelo menos estas hipóteses (cada uma comparada contra a linha de base, mesmo texto, mesma GPU):
  1. **Batching**: `KPipeline.__call__` aceita `text: str | List[str]` — hoje `KokoroSpeaker.synthesize()` chama uma vez por chunk, com uma string. Passar uma lista de N chunks numa chamada só é mensuravelmente mais rápido? (Atenção: o retorno é um *generator* de `Result`, um por segmento — a associação resultado→chunk precisa ser preservada, senão o `sequence` do `AudioChunk` sai errado.)
  2. **Tamanho de chunk**: `DEFAULT_MAX_CHARS = 1000` hoje (`processing/chunker.py`). Chunks maiores reduzem o overhead por chamada, mas pioram a granularidade de playback e da retomada (OS-021/022), e aumentam o risco de bater no limite de 510 fonemas por segmento interno do Kokoro. Medir o trade-off, não só a velocidade.
  3. **Overhead fixo por chamada**: quanto do 1,34 s/chunk é G2P, quanto é inferência, quanto é escrita do `.wav` em disco (`soundfile.write`)? Se a escrita for significativa, isso muda o alvo da otimização.
- **Entregável: um relatório com números medidos e uma recomendação explícita**, incluindo a opção "não vale a pena mudar nada" se for esse o caso.

**Fora do escopo:**
- Implementar qualquer otimização — a implementação vira uma OS separada, **se** o dono do projeto aprovar a recomendação (mesmo fluxo da OS-005 → decisão #9).
- Mexer no `KokoroSpeaker` de produção.
- Paralelismo multi-worker / multi-GPU: com um worker só e a GPU já saturada durante a síntese, mais processos concorrentes tendem a competir pelo mesmo recurso escasso em vez de somar throughput. Fora do escopo deste spike; se os números sugerirem que a GPU **não** está saturada, registrar isso como achado.
- Trocar de engine TTS.

## 3. Contratos envolvidos

Nenhum. Spike não altera contratos nem código de produção.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] Linha de base medida e reproduzível (comando documentado no relatório, com o texto/tamanho usado)
- [ ] Cada hipótese acima medida com números concretos, comparada contra a linha de base
- [ ] Trade-offs não-performance explicitados (ex: chunk maior piora granularidade de playback/retomada; batching complica o mapeamento resultado→`sequence`)
- [ ] Recomendação explícita no relatório, com "não mudar nada" como resultado aceitável
- [ ] Nenhum arquivo de produção (`core/`, `plugins/`, `worker/`, `api/`, `processing/`) alterado
- [ ] Nenhuma chamada a API paga (Kokoro é local, `cost_per_char == 0.0`)

## 5. Testes exigidos (mínimo)

Spike não exige testes automatizados de produção (mesmo tratamento dado à OS-005). O que precisa existir é **evidência reproduzível**: o script de medição versionado em `scripts/`, e os números brutos no relatório — não só as conclusões.

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-031-report.md` (template em `docs/report/REPORT_TEMPLATE.md`). Este é o entregável principal desta OS.*
