# OS-041 — Relatório de entrega (spike: comparação de provedores de TTS cloud)

**Data:** 2026-08-06
**Branch:** `os/041-spike-tts-cloud`
**Commit(s) relevante(s):** N/A (spike de medição — script em `scripts/spike_tts_cloud.py`, números brutos abaixo; nenhum código de produção alterado)

## 1. Resumo do que foi feito

Spike de comparação de provedores de TTS cloud para o nível premium (decisão #23), sobre a **mesma amostra** em português brasileiro (1.858 caracteres, texto real do "Arquitetura Limpa", com os casos difíceis embutidos). Script reproduzível em `scripts/spike_tts_cloud.py` com um adaptador por provedor (Google Cloud TTS / Chirp, Amazon Polly, OpenAI, ElevenLabs), cada um **gated por variável de ambiente** — só chama API paga se a credencial existir. Preços oficiais levantados na documentação de cada provedor em 2026-08-06 e convertidos em custo por livro real do acervo.

**Decisão do dono do projeto (registrada em conversa antes da execução):** executar o spike **sem chamadas pagas** — pesquisa de preços oficiais + script + baseline Kokoro real; a parte empírica dos provedores cloud fica **bloqueada por falta de credenciais** e é o desbloqueio necessário para concluir o spike. Nenhuma das chamadas cloud foi feita; o script já está pronto para rodá-las assim que as credenciais existirem.

**Recomendação preliminar (parcial, ver seção 6):** nenhum provedor pode ser recomendado ainda — a qualidade de voz em pt-BR **não foi ouvida** (sem credenciais), e qualidade é o critério decisivo do nível premium. O que o spike já consegue dizer com segurança: custo por livro (tabela da seção 5), limites por requisição (seção 4) e a linha de base Kokoro (seção 4.1). A recomendação de motor fica **pendente do dono fornecer credenciais e aprovar o orçamento pequeno** para as ~12 chamadas de teste (3 por provedor × 4 provedores).

## 2. Checklist de DoD

### DoD específico da OS (`docs/os/OS-041-spike-tts-cloud.md` seção 4)

- [x] Preço por 1M de caracteres de cada provedor, com data e link da fonte oficial — seção 4, todos com `date` e `source`
- [x] Custo estimado por livro real do acervo, provedor a provedor — seção 5 (3 livros × 6 patamares de preço, com os números reais da OS seção 2)
- [ ] Mesma amostra sintetizada em todos os provedores **e** no Kokoro — **parcial**: Kokoro **feito** (áudio real em `/tmp/os041-audio/kokoro_pt-BR_af_heart.wav`, 125,17 s); provedores cloud **não** (bloqueado por credenciais, decisão do dono pela opção 2). Adaptadores prontos e testados estruturalmente no script
- [x] Os casos difíceis (sigla, estrangeirismo, moeda, frase longa) estão na amostra e comentados um a um — seção 3 e no próprio script
- [x] Latência por chamada e limite de caracteres por requisição registrados — latência real do Kokoro (seção 4.1); limites por requisição de cada provedor com fonte (seção 4.2), informação que a OS-043 pede
- [ ] Recomendação explícita, com "não vale o custo" aceito como resultado — seção 6: **recomendação suspensa** (qualidade não ouvida); nenhum provedor recomendado, sem bloquear a opção "nenhum vale o custo"
- [x] Nenhum arquivo de produção alterado; nenhuma chamada paga dentro de `pytest` — `git status` mostra só `scripts/spike_tts_cloud.py` novo; nada entra em `pytest.ini`
- [x] Credenciais **não** commitadas — lidas de variável de ambiente, nenhuma chave neste relatório nem no script

### DoD padrão (`AGENTS.md` seção 4)

Spike não toca código de produção nem contratos; os itens abaixo são aplicáveis àquilo que esta OS produziu:

- [x] Evidência reproduzível: script versionado em `scripts/` e números brutos colados neste relatório (seção 4) — único requisito da seção 5 da OS
- [x] `PROJECT_STATE.md` atualizado (achado registrado em "Riscos e bloqueios" e como pendência do nível premium)
- [x] Relatório criado em `docs/report/OS-041-report.md` (nunca dentro do arquivo da própria OS)
- [ ] PR aberto contra o branch principal (título `[OS-041] spike comparação de TTS cloud`) — **em rascunho (draft)**, ver seção 7 (Dúvidas/bloqueios): a OS exige credenciais do dono que ainda não foram fornecidas, e o relatório deve refletir isso antes de merge
- [ ] Testes automatizados — N/A por definição (spike, mesmo tratamento da OS-005/OS-031); o script de medição NÃO é um teste de produção e não entra em `pytest.ini`

## 3. Amostra fixa e casos difíceis

Texto real extraído do "Arquitetura Limpa" (livro do acervo, via `PyMuPDFExtractor` + `clean_text`), com os casos difíceis embutidos de propósito. **1.858 caracteres** — dentro da faixa de 1.500–3.000 da OS. Texto integral no script (`SAMPLE_TEXT`), comentado caso a caso:

| Caso difícil | Ocorrência na amostra | Por que importa |
|---|---|---|
| Sigla `UML` | "desenham diagramas de classes em UML" | G2P por regras (espeak) tende a ler letra a letra ou com vogal indevida |
| Sigla `API` | "usando a API interna do sistema" (aparece 2×) | Idem; onipresente em texto técnico |
| Estrangeirismo `design` | "usamos o design orientado a objetos" | espeak-ng tende a ler "designe" (vogais do português) |
| Estrangeirismo `Docker` | "vou subir o Docker" | Idem, pronúncia inglesa vs. aportuguesada |
| Número/moeda `R$ 50` | "custe apenas R$ 50 por mês" | Como cada TTS lê símbolo + número (o sanitizador da OS-040 expande símbolos, mas a comparação mede o engine em si) |
| Frase longa sem pontuação interna | 4º parágrafo inteiro (uma frase de ~370 caracteres sem vírgula) | Estressa o respiro/segmentação de cada engine; é o caso real que a OS-034/035 já endereçou no Kokoro |

## 4. Saída de comandos relevantes (bruta)

### 4.1 Script completo (`venv/bin/python scripts/spike_tts_cloud.py`)

```text
# spike_tts_cloud (OS-041)
sample_chars: 1858
audio_output_dir: /tmp/os041-audio
latency_calls_per_provider: 3
credenciais detectadas:
{
  "kokoro": {
    "label": "Kokoro (baseline local)",
    "credential_status": "local, sem custo",
    "audio_file": "/tmp/os041-audio/kokoro_pt-BR_af_heart.wav",
    "latency_seconds": [
      8.204140773000063,
      3.164318028000025,
      2.961343708999948
    ],
    "statuses": [
      "ok",
      "ok",
      "ok"
    ],
    "char_limit_per_request": null
  }
}
{
  "google": {
    "label": "Google Cloud TTS (Chirp 3: HD)",
    "credential_status": "skip — variável de ambiente GOOGLE_APPLICATION_CREDENTIALS ausente",
    "pricing_source": "https://cloud.google.com/text-to-speech/pricing"
  }
}
{
  "polly": {
    "label": "Amazon Polly (neural)",
    "credential_status": "skip — variável de ambiente AWS_ACCESS_KEY_ID ausente",
    "pricing_source": "https://aws.amazon.com/polly/pricing/"
  }
}
{
  "openai": {
    "label": "OpenAI TTS",
    "credential_status": "skip — variável de ambiente OPENAI_API_KEY ausente",
    "pricing_source": "https://platform.openai.com/docs/pricing"
  }
}
{
  "elevenlabs": {
    "label": "ElevenLabs (eleven_multilingual_v2)",
    "credential_status": "skip — variável de ambiente ELEVENLABS_API_KEY ausente",
    "pricing_source": "https://elevenlabs.io/pricing/"
  }
}

# custo estimado por livro (USD — preço oficial das fontes, levantado em 2026-08-06)

Google Chirp 3: HD: US$ 30.00 por 1M chars (fonte: https://cloud.google.com/text-to-speech/pricing, 2026-08-06)
  Arquitetura Limpa: US$ 16.00
  O Programador Pragmático: US$ 19.47
  DDD Referência: US$ 2.55

Google Neural2: US$ 16.00 por 1M chars (fonte: https://cloud.google.com/text-to-speech/pricing, 2026-08-06)
  Arquitetura Limpa: US$ 8.53
  O Programador Pragmático: US$ 10.38
  DDD Referência: US$ 1.36

Amazon Polly neural: US$ 16.00 por 1M chars (fonte: https://aws.amazon.com/polly/pricing/, 2026-08-06)
  Arquitetura Limpa: US$ 8.53
  O Programador Pragmático: US$ 10.38
  DDD Referência: US$ 1.36

Amazon Polly generative: US$ 30.00 por 1M chars (fonte: https://aws.amazon.com/polly/pricing/, 2026-08-06)
  Arquitetura Limpa: US$ 16.00
  O Programador Pragmático: US$ 19.47
  DDD Referência: US$ 2.55

OpenAI tts-1: US$ 15.00 por 1M chars (fonte: https://platform.openai.com/docs/pricing, 2026-08-06)
  Arquitetura Limpa: US$ 8.00
  O Programador Pragmático: US$ 9.73
  DDD Referência: US$ 1.27

OpenAI tts-1-hd: US$ 30.00 por 1M chars (fonte: https://platform.openai.com/docs/pricing, 2026-08-06)
  Arquitetura Limpa: US$ 16.00
  O Programador Pragmático: US$ 19.47
  DDD Referência: US$ 2.55
```

Áudio do baseline: `/tmp/os041-audio/kokoro_pt-BR_af_heart.wav` — 24.000 Hz, **125,17 s** de áudio para os 1.858 caracteres (proporção típica de narração técnica). Latência Kokoro: primeira chamada 8,2 s (carrega pipeline/voz), depois ~3,1 s e ~3,0 s (consistente com o ~1,34 s/chunk em chunks reais de ~1000 chars da linha de base real, OS-031; aqui a amostra é maior que um chunk e o Kokoro divide internamente).

## 5. Preços oficiais e custo por livro

### 5.1 Preço por 1M de caracteres (levantado 2026-08-06, moeda oficial USD)

| Provedor / voz | US$ / 1M chars | Fonte oficial | Observações |
|---|---|---|---|
| Google Chirp 3: HD | US$ 30,00 | https://cloud.google.com/text-to-speech/pricing | 1M chars grátis/mês antes de cobrar |
| Google Neural2 | US$ 16,00 | https://cloud.google.com/text-to-speech/pricing | sem o salto de qualidade do Chirp |
| Amazon Polly neural | US$ 16,00 | https://aws.amazon.com/polly/pricing/ | free tier 1M chars/mês por 12 meses |
| Amazon Polly generative | US$ 30,00 | https://aws.amazon.com/polly/pricing/ | patamar mais alto da Polly em pt-BR |
| OpenAI tts-1 | US$ 15,00 | https://platform.openai.com/docs/pricing | preço por caractere |
| OpenAI tts-1-hd | US$ 30,00 | https://platform.openai.com/docs/pricing | preço por caractere |
| OpenAI gpt-4o-mini-tts | n/d | https://platform.openai.com/docs/pricing | cobrada por token (US$0,60/1M tokens texto + US$12/1M tokens áudio) — não comparável por caractere |
| ElevenLabs (multilingual v2) | n/d | https://elevenlabs.io/pricing/ | modelo de créditos: 1 char = 1 crédito; planos Starter $6/30k, Creator $22/121k, Pro $99/600k (~US$165/1M no Pro) |

### 5.2 Custo estimado por livro real (caracteres da OS-041 seção 2)

| Provedor (US$/1M) | Arquitetura Limpa (533.371) | Pragmático (648.877) | DDD (84.879) |
|---|---|---|---|
| OpenAI tts-1 (15) | US$ 8,00 | US$ 9,73 | US$ 1,27 |
| Google Neural2 / Polly neural (16) | US$ 8,53 | US$ 10,38 | US$ 1,36 |
| Google Chirp 3 HD / Polly generative / tts-1-hd (30) | US$ 16,00 | US$ 19,47 | US$ 2,55 |
| ElevenLabs multilingual v2 (~165, plano Pro) | ~US$ 88,00 | ~US$ 107,00 | ~US$ 14,00 |

**Leitura:** um livro técnico típico (500–650k chars) sai entre **US$ 8 e US$ 20** nos patamares mais baratos (tts-1, Neural2/Polly neural) e é **~10× mais caro na ElevenLabs** (~US$ 88–107). Conversão para BRL é deixada ao dono — câmbio muda e o objetivo é comparar provedores, não fixar um câmbio no código.

## 6. Recomendação

**Suspensa — aguardando a medição real da qualidade.** Os três requisitos para recomendar um motor do nível premium são: (1) voz boa em pt-BR, (2) custo aceitável, (3) latência/limites viáveis para o pipeline. Este spike confirma (2) e (3) com dados oficiais, mas **não mediu (1)** porque a parte empírica foi bloqueada por decisão do dono (opção 2, sem credenciais). Qualidade de voz é o critério decisivo do premium (decisão #23: "o salto de humanização vem de trocar o Speaker") — recomendar por preço sem ouvir seria repetir o erro que a OS-041 existe para evitar.

O que já dá para afirmar:

- **Custo não é impeditivo** nas opções baratas: ~US$ 8–16 por livro (Neural2/Polly neural/tts-1). Dentro de um plano pago do produto, é viável — e a trava de custo (OS-042) se encaixa bem nesses patamares.
- **ElevenLabs é uma ordem de magnitude mais cara** (~US$ 88–107 por livro) e provavelmente sai do páreo **antes** da audição, salvo se a qualidade em pt-BR justificar de forma inequívoca.
- **OpenAI merece atenção especial:** é o único em que o preço por caractere está claramente documentado (US$15/1M) e a voz é considerada entre as melhores de TTS API; e o `gpt-4o-mini-tts` aceita instruções de emoção/ritmo (o "controle" que o Kokoro não tem, decisão #23) — mas a cobrança por token exige uma medição de tokens/caractere na amostra para fechar o custo real.
- **Limites por requisição (info da OS-043):** Polly 3.000 chars cobráveis/chamada (6.000 totais; 100.000 via `StartSpeechSynthesisTask`), Google 5.000/chamada, OpenAI 4.096, ElevenLabs 5.000. Todos acomodam o `max_chars=1000` atual com folga — nenhum provoca mudança no tamanho de chunk do pipeline.

**Para fechar o spike** (decisão do dono pendente): fornecer credenciais (as 5 variáveis listadas no cabeçalho do script) e aprovar o orçamento pequeno; rodar `venv/bin/python scripts/spike_tts_cloud.py` com as credenciais exportadas, ouvir os áudios em `/tmp/os041-audio/`, e então a recomendação sai. Sem isso, o resultado honesto é **"nenhum provedor recomendado ainda — faltam os dados de qualidade"**, que é um subconjunto do resultado aceitável da OS ("nenhum vale o custo" também é aceito, mas é uma conclusão diferente que só a audição pode dar).

## 7. Desvios do escopo original

Nenhum desvio de escopo. A execução seguiu o formato do spike (script em `scripts/`, relatório em `docs/report/`), e a limitação empírica é a **condição de entrada da própria OS** (credenciais + aprovação de orçamento), não uma mudança de escopo. Nenhum arquivo de produção alterado (verificado com `git status`: só `scripts/spike_tts_cloud.py` novo).

## 8. Dúvidas / bloqueios

**Bloqueio ativo: credenciais de TTS cloud e aprovação de orçamento.** A OS-041 declara explicitamente exigir ambos do dono, e o dono optou (em conversa, antes desta execução) por rodar **sem chamadas pagas** — pesquisa + script + baseline Kokoro. O que permanece bloqueado e precisa do dono para concluir o spike:

1. Credenciais (qualquer subconjunto dos 4 provedores) — exportar as variáveis do cabeçalho do script.
2. Aprovação do orçamento pequeno para as ~12 chamadas de teste (3 por provedor × 4), custo esperado na casa de centavos por provedor.
3. Decisão de quais 2–3 provedores levar à audição — os 4 foram preparados; se o dono quiser enxugar, o script aceita desligar qualquer um removendo a env var.

Decisões de arquitetura **não** foram tomadas pelo agente (AGENTS.md seção 1): nenhuma recomendação de provedor, nenhum contrato novo, nenhuma mudança de pipeline. Isso está registrado nesta seção e o PR fica **em rascunho** até o dono decidir.

## 9. Link do PR

Em rascunho (draft), aguardando a decisão do dono sobre credenciais. O PR foi aberto com título `[OS-041] spike comparação de TTS cloud` — deve ser mergeado como está (pesquisa + script + baseline são entregas válidas do spike) e a conclusão empírica pode vir como atualização do mesmo relatório (`OS-041-report-v2.md`), conforme a regra de versionamento do `REPORT_TEMPLATE.md`.
