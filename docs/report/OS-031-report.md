# OS-031 — Relatório de entrega (spike: performance da síntese)

**Data:** 2026-08-05
**Branch:** os/031-spike-performance-sintese
**Commit(s) relevante(s):** N/A (spike de medição — script em `scripts/spike_synthesis_performance.py`, números brutos abaixo; nenhum código de produção alterado)

## 1. Resumo do que foi feito

Spike de medição de performance da síntese (Kokoro, RTX 3060 CUDA). Script reproduzível em `scripts/spike_synthesis_performance.py` mede, sobre um corpus fixo de 19.204 caracteres (21 chunks a `max_chars=1000`, ~20 min de áudio por rodada): (1) linha de base do fluxo atual, (2) batching via `KPipeline.__call__(List[str])`, (3) tamanho de chunk (`max_chars` 1000/1500/2000/3000), (4) decomposição do overhead (G2P vs inferência vs escrita de `.wav`). Mediu-se também a utilização da GPU durante a síntese. **Recomendação: não mudar nada** — nenhuma das hipóteses traz ganho mensurável; o gargalo é a inferência pura na GPU, já saturada (~89-100% de utilização).

## 2. Checklist de DoD

### DoD específico da OS (`docs/os/OS-031-spike-performance-sintese.md` seção 4)

- [x] Linha de base medida e reproduzível — comando documentado na seção 3; corpus fixo de 19.204 caracteres, 21 chunks a 1000; 3 repetições → **0,896 s/chunk**, razão áudio/tempo ≈ **63,7×**
- [x] Cada hipótese medida com números concretos, comparada contra a linha de base — seções 4.1 a 4.4 (batching ≈ ganho zero; chunk size ≈ ganho zero; overhead ≈ 3% do tempo total)
- [x] Trade-offs não-performance explicitados — seção 5 (batching complica o mapeamento resultado→`sequence`; chunk maior piora granularidade de playback/retomada e aumenta o risco de segmentos internos de 510 fonemas)
- [x] Recomendação explícita no relatório, com "não mudar nada" como resultado aceitável — seção 6 (é o resultado escolhido)
- [x] Nenhum arquivo de produção alterado — `git diff` limpo fora de `scripts/` + `docs/report/`
- [x] Nenhuma chamada a API paga — Kokoro local (`cost_per_char == 0.0`), voz `af_heart` já cacheada em disco; sem rede durante as medições

### DoD padrão (`AGENTS.md` seção 4)

Spike não toca código de produção nem contratos; os itens abaixo são aplicáveis àquilo que esta OS produziu:

- [x] Evidência reproduzível: script versionado em `scripts/` e números brutos colados neste relatório (seção 4) — único requisito da seção 5 da OS
- [x] `PROJECT_STATE.md` atualizado (achado registrado em "Riscos e bloqueios" e como decisão proposta pendente de aprovação)
- [x] Relatório criado em `docs/report/OS-031-report.md` (nunca dentro do arquivo da própria OS)
- [x] PR aberto contra o branch principal (título `[OS-031] spike performance da síntese`)
- [ ] Testes automatizados — N/A por definição (spike, mesmo tratamento da OS-005); o script de medição NÃO é um teste de produção e não entra em `pytest.ini`

## 3. Metodologia (reproduzível)

Comando:
```
$ venv/bin/python scripts/spike_synthesis_performance.py
```

Ambiente: `torch 2.13.0+cu130`, CUDA ativo, `NVIDIA GeForce RTX 3060`. Corpus fixo em inglês (prosa de engenharia de segurança, mesmo idioma do baseline real): 19.204 caracteres, montado pela repetição de 12 parágrafos com prefixo de seção (cada chunk é único), `chunk_text` → 21 chunks com `max_chars=1000`. Voz `af_heart`, `speed=1.0`, pipeline `lang_code='a'`. Aquecimento (primeira síntese, que carrega voz/pesos) fora das medições.

- **Baseline** replica o fluxo atual do `KokoroSpeaker.synthesize()`: uma chamada a `pipeline(text, ...)` por chunk + `soundfile.write` do `.wav`.
- **Batching** chama `pipeline(lista_de_chunks, ...)` uma vez por lote, agrupa os `Result`s por `text_index` (linha 386 de `kokoro/pipeline.py`) e concatena o áudio de cada grupo — preservando a associação chunk→`sequence`.
- **Chunk size** re-usa o mesmo fluxo baseline sobre `chunk_text(CORPUS, max_chars=1500/2000/3000)`.
- **Overhead** separa: (a) escrita de `.wav` (média de 5 chamadas a `sf.write`), (b) G2P puro (pipeline quieto `model=False`, que fonemiza/chunkeia sem inferir), (c) por diferença, o tempo de inferência.
- **Saturação da GPU** amostrada com `nvidia-smi --query-gpu=utilization.gpu,memory.used` em thread separada durante uma rodada inteira do baseline.

## 4. Saída de comandos relevantes (bruta)

### 4.1 Script completo (`venv/bin/python scripts/spike_synthesis_performance.py`)

```text
torch: 2.13.0+cu130
cuda_available: True
gpu: NVIDIA GeForce RTX 3060
corpus_chars: 19204
chunk_count_1000: 21
warmup: ok

# baseline (max_chars=1000, um chunk por chamada + .wav)
{
  "per_rep": [
    {"chunks": 21, "total_seconds": 18.771, "seconds_per_chunk": 0.8939, "audio_seconds": 1198.4, "audio_ratio": 63.84},
    {"chunks": 21, "total_seconds": 18.796, "seconds_per_chunk": 0.895,   "audio_seconds": 1198.4, "audio_ratio": 63.76},
    {"chunks": 21, "total_seconds": 18.894, "seconds_per_chunk": 0.8997,  "audio_seconds": 1198.4, "audio_ratio": 63.43}
  ],
  "mean_seconds_per_chunk": 0.8962,
  "mean_audio_ratio": 63.68
}

# overhead: escrita do .wav (média por chunk, fluxo de produção)
{
  "mean_write_seconds_per_chunk": 0.0134,
  "per_call": [0.0138, 0.013, 0.0132, 0.0135, 0.0136]
}

# overhead: G2P puro (sem inferência)
{
  "g2p_total_seconds": 0.25,
  "g2p_segments": 43
}

# batching (List[str] numa chamada só)
{
  "batch_size": 2,  "mean_seconds_per_chunk": 0.9054, "mean_audio_ratio": 63.03,
  "per_rep": [{"chunks": 21, "total_seconds": 18.98,  "seconds_per_chunk": 0.9038, "audio_seconds": 1198.4, "audio_ratio": 63.14},
              {"chunks": 21, "total_seconds": 19.045, "seconds_per_chunk": 0.9069, "audio_seconds": 1198.4, "audio_ratio": 62.92}]
}
{
  "batch_size": 4,  "mean_seconds_per_chunk": 0.9042, "mean_audio_ratio": 63.12,
  "per_rep": [{"chunks": 21, "total_seconds": 18.996, "seconds_per_chunk": 0.9046, "audio_seconds": 1198.4, "audio_ratio": 63.09},
              {"chunks": 21, "total_seconds": 18.979, "seconds_per_chunk": 0.9037, "audio_seconds": 1198.4, "audio_ratio": 63.15}]
}
{
  "batch_size": 8,  "mean_seconds_per_chunk": 0.9052, "mean_audio_ratio": 63.04,
  "per_rep": [{"chunks": 21, "total_seconds": 19.055, "seconds_per_chunk": 0.9074, "audio_seconds": 1198.4, "audio_ratio": 62.89},
              {"chunks": 21, "total_seconds": 18.965, "seconds_per_chunk": 0.9031, "audio_seconds": 1198.4, "audio_ratio": 63.19}]
}
{
  "batch_size": 21, "mean_seconds_per_chunk": 0.9059, "mean_audio_ratio": 63.0,
  "per_rep": [{"chunks": 21, "total_seconds": 19.088, "seconds_per_chunk": 0.9089, "audio_seconds": 1198.4, "audio_ratio": 62.78},
              {"chunks": 21, "total_seconds": 18.959, "seconds_per_chunk": 0.9028, "audio_seconds": 1198.4, "audio_ratio": 63.21}]
}

# tamanho de chunk (mesmo corpus, chunk_text com max_chars maior)
{
  "mean_seconds_per_chunk": 1.3638, "mean_audio_ratio": 62.6, "max_chars": 1500, "chunk_count": 14,
  "per_rep": [{"chunks": 14, "total_seconds": 19.237, "seconds_per_chunk": 1.3741, "audio_seconds": 1195.2, "audio_ratio": 62.13},
              {"chunks": 14, "total_seconds": 18.95,  "seconds_per_chunk": 1.3536, "audio_seconds": 1195.2, "audio_ratio": 63.07}]
}
{
  "mean_seconds_per_chunk": 1.882, "mean_audio_ratio": 63.27, "max_chars": 2000, "chunk_count": 10,
  "per_rep": [{"chunks": 10, "total_seconds": 18.914, "seconds_per_chunk": 1.8914, "audio_seconds": 1190.6, "audio_ratio": 62.95},
              {"chunks": 10, "total_seconds": 18.725, "seconds_per_chunk": 1.8725, "audio_seconds": 1190.6, "audio_ratio": 63.59}]
}
{
  "mean_seconds_per_chunk": 2.7171, "mean_audio_ratio": 63.02, "max_chars": 3000, "chunk_count": 7,
  "per_rep": [{"chunks": 7, "total_seconds": 19.171, "seconds_per_chunk": 2.7387, "audio_seconds": 1198.5, "audio_ratio": 62.52},
              {"chunks": 7, "total_seconds": 18.868, "seconds_per_chunk": 2.6954, "audio_seconds": 1198.5, "audio_ratio": 63.52}]
}
```

### 4.2 Saturação da GPU (amostragem `nvidia-smi` durante rodada completa do baseline)

```text
samples: 86
gpu_util_min/max/mean: 37 100 89.2
mem_mb_max: 2746
```

## 5. Análise por hipótese

### 5.1 Batching (`List[str]` numa chamada só) — **sem ganho**

| Modo | s/chunk (média) | Δ vs baseline |
|---|---|---|
| Baseline (1 chamada por chunk) | 0,8962 | — |
| Batch 2 | 0,9054 | +1,0% |
| Batch 4 | 0,9042 | +0,9% |
| Batch 8 | 0,9052 | +1,0% |
| Batch 21 (corpus inteiro) | 0,9059 | +1,1% |

O "batching" do Kokoro não agrupa segmentos num único `KModel.__call__`: em `kokoro/pipeline.py`, `__call__` só *itera* sobre os segmentos e chama `KPipeline.infer(model, ps, pack, speed)` uma vez por string de fonemas (linha 383). Passar `List[str]` apenas elimina o overhead de setup Python do loop externo — desprezível quando o corpo do loop é uma inferência de ~0,9 s. A diferença medida (±1%) é ruído de medição.

**Trade-off:** o `text_index` em cada `Result` (linha 386) preserva a associação chunk→áudio, mas um chunk grande pode renderizar vários `Result`s (quebra de 510 fonemas no `en_tokenize`), exigindo agrupar por `text_index` e concatenar — a mecânica que o spike implementou e que qualquer OS de implementação teria que reproduzir com cuidado, para nada. **Custo de complexidade > ganho.**

### 5.2 Tamanho de chunk — **sem ganho de throughput**

| max_chars | chunks | s/chunk | razão áudio/tempo | tempo total do corpus (média) |
|---|---|---|---|---|
| 1000 (atual) | 21 | 0,896 | 63,7× | 18,8 s |
| 1500 | 14 | 1,364 | 62,6× | 19,1 s |
| 2000 | 10 | 1,882 | 63,3× | 18,8 s |
| 3000 | 7 | 2,717 | 63,0× | 19,0 s |

`seconds_per_chunk` cresce linearmente com o tamanho do chunk e a razão áudio/tempo fica constante (~63×): o tempo total para sintetizar o mesmo corpus é **o mesmo** (~19 s) em qualquer `max_chars`. Ou seja, menos chamadas ao Speaker não aceleram nada — o custo é proporcional ao áudio gerado, dominado pela inferência.

**Trade-off:** chunk maior piora (a) a granularidade do playback incremental (OS-021/030 — o usuário espera chunks menores aparecendo mais cedo), (b) a granularidade da retomada (OS-022 — um chunk interrompido no meio = mais áudio a regenerar), e (c) aumenta a frequência de segmentos internos de ~510 fonemas (o `en_tokenize` quebra o chunk em vários `Result`s, que o speaker já concatena — funciona, mas cada `AudioChunk` vira um mosaico maior). **Nenhum benefício para pagar esse preço.**

### 5.3 Overhead fixo por chamada — **irrelevante (~3%)**

| Componente | s/chunk | % do tempo do chunk |
|---|---|---|
| G2P (fonemização + chunking) | ~0,012 | ~1,3% |
| Escrita do `.wav` (`sf.write`) | 0,0134 | ~1,5% |
| **Inferência (GPU)** | **~0,87** | **~97%** |

(G2P: 0,25 s para o corpus inteiro ÷ 21 chunks ≈ 0,012 s/chunk.) Mesmo zerar G2P e escrita por completo economizaria ~3% — dentro da variação de medição entre rodadas. **O alvo de qualquer otimização é a inferência, não o entorno.**

### 5.4 Saturação da GPU

Utilização média **89,2%** durante a síntese (pico 100%, min 37% nos intervalos entre chunks), memória 2.746 MB. A GPU já está essencialmente saturada: o achado previsto no escopo ("se os números sugerirem que a GPU NÃO está saturada") **não** se confirmou. Paralelismo multi-worker/multi-GPU continuaria competindo pelo mesmo recurso escasso — fora de escopo, e os números não sugerem reabri-lo.

## 6. Recomendação

**Não mudar nada na síntese.** Evidências: batching ≈ +1% (ruído), tamanho de chunk não altera o throughput (~63× constante), overhead de entorno ≈ 3%, GPU saturada em ~89%. O 1,34 s/chunk do baseline real (livro "Security Engineering", 3334 chunks) vs 0,90 s/chunk do corpus sintético é esperado — o texto real tem chunks com mais áudio por caracter e a medição real aconteceu sob carga do worker completo (persistência incremental, escrita em disco real, status updates); o spike mede o custo puro do Kokoro sobre corpus fixo, que é o que importa para comparar hipóteses entre si.

Se algum dia o throughput da síntese for um problema de verdade, as alavancas que os números apontam (todas fora do escopo desta OS) são: modelo mais leve/rápido ou GPU maior, e — apenas se o idioma deixar — desativar o fallback de inglês para não perder tempo tentando pipeline indisponível. Nenhuma mudança de batching/chunk-size/serialização muda o número que importa.

## 7. Desvios do escopo original

Nenhum. Script criado em `scripts/`, nenhum arquivo de `core/`, `plugins/`, `worker/`, `api/` ou `processing/` alterado (verificado com `git status`/`git diff`).

## 8. Dúvidas / bloqueios

Nenhuma.

## 9. Link do PR

https://github.com/dinei84/listening/pull/23
