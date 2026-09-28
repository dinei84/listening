# OS-055 — Relatório de entrega

**Data:** 28/09/2026 (implementação em 13/08/2026; validação com crédito real em 28/09/2026)
**Branch:** `os/055-openai-speaker`
**Commit(s) relevante(s):** `b6065db` (Red), `2949e39` (Green), `defee2a` e `fe44fae` (classificação de erro), `52336a8` (duração real)

## 1. Resumo do que foi feito

O app deixou de ter um único motor de voz. `OpenAISpeaker` implementa o contrato `Speaker` e está registrado, então `speaker: openai` no `config.yaml` narra o livro inteiro pela API da OpenAI. As chaves passaram a vir de `.env`.

## 2. Checklist de DoD

Padrão (`AGENTS.md` seção 4):

- [x] Testes antes da implementação — `b6065db` (Red) antes de `2949e39` (Green)
- [x] Todos os testes da OS passam
- [x] Nenhum teste existente quebrou (365 → 401 no branch, somando OS-055 e OS-056)
- [x] Contratos de `ARQUITETURA.md` respeitados — o contrato `Speaker` **não muda**; esta OS o implementa
- [x] **Nenhuma chamada paga nos testes** — `_call_api` e `_post` são os únicos pontos de rede, ambos mockados
- [x] Type hints e docstring de uma linha em toda função pública
- [x] `PROJECT_STATE.md` atualizado
- [x] Relatório em `docs/report/OS-055-report.md`
- [x] PR aberto — ver seção 7

Específico (seção 8 da OS):

- [x] Implementa `cost_per_char`, `max_request_chars` e `synthesize`
- [x] `cost_per_char` = 1,608e-05, derivado de medição real (US$ 0,015 por 933 chars no painel da OpenAI)
- [x] `max_request_chars` = 4096; o pipeline divide antes de chamar (OS-043)
- [x] Texto acima de 4096 é dividido e concatenado sem cabeçalho no meio
- [x] 429 e 5xx → `TransientSpeakerError`; 401/403/400 → `PermanentSpeakerError`
- [x] `instructions` configurável e enviado quando presente
- [x] Sem chave, falha com mensagem clara em vez de degradar
- [x] `cloud_speaker.py` (0 bytes) apagado, com teste travando a remoção

## 3. Testes escritos

20 testes em `tests/unit/speakers/test_openai_speaker.py`, cobrindo contrato, preço, limite por requisição, formato do áudio, `instructions`, sobrescrita de voz, ausência de chave e as seis classes de erro HTTP. Mais 2 em `tests/unit/test_registry.py` (registro e remoção do placeholder vazio).

Commit "Red" antes do "Green"? [x] Sim.

## 4. Saída de comandos relevantes

Verificação com credencial e crédito reais (28/09/2026):

```
SPEAKERS registrados: ['kokoro', 'openai']
openai -> cost_per_char: 1.608e-05 | max_request_chars: 4096
livro de 533.371 chars: US$ 8,58

sem chave configurada:
  PermanentSpeakerError: OPENAI_API_KEY não configurada — defina a chave no
  .env ou no ambiente para usar o Speaker da OpenAI.

chamada real:
  duração: 4,7 s | motor: openai | cabeçalho: 111.600 frames a 24.000 Hz
```

Suíte: `401 passed`.

## 5. Desvios do escopo original

**Três, todos por defeito encontrado em uso real — e nenhum teria aparecido em teste mockado.**

**a) Configuração por variável de ambiente, não por bloco no `config.yaml`.** A OS previa um bloco próprio. O pipeline instancia o Speaker sem argumentos (`SPEAKERS[nome]()`), então não há por onde passar config sem mexer no registry. Modelo, voz e `instructions` passaram a vir do ambiente, o que também atende ao pedido do dono de manter tudo num `.env`.

**b) `.env` carregado na importação de `core.config`.** Não estava na OS. Foi pedido do dono, e `python-dotenv` já estava no `requirements.txt` **desde o início do projeto, declarado e nunca instalado nem usado**. Carregado com `override=False`: variável exportada no shell vence o arquivo, senão um `.env` esquecido sobrescreveria calado a chave recém-definida.

**c) Classificação de erro corrigida duas vezes, ambas por falha observada:**

- Degradar **qualquer** erro do motor pago para o local fez o livro sair inteiro em Kokoro com um WARNING que ninguém leu. Agora só `TransientSpeakerError` degrada; falha permanente vira `Book: error` com mensagem — coerente com a decisão do dono de 13/08 por falha rápida com aviso.
- **429 é ambíguo**: limite de taxa passa sozinho, saldo esgotado nunca passa. Tratar os dois como transitório fez o sistema degradar em silêncio durante várias rodadas de teste, enquanto o dono acreditava estar ouvindo a IA. O corpo da resposta (`insufficient_quota`) passou a decidir.

**d) Duração do áudio, achada na primeira chamada com crédito.** A API devolve WAV de *streaming*, com RIFF e data size em `0xFFFFFFFF`. O `wave` clampa em 2³¹-1 frames e a duração saía **89.478 s para 4,9 s reais**. Como a duração alimenta barra de progresso, retomada (OS-028) e navegação por trecho (OS-039), os três seriam envenenados. `_normalize_wav` regrava o arquivo com tamanhos reais e mede pela contagem de bytes.

## 6. Dúvidas / bloqueios

**O `instructions` nunca foi exercido com áudio real até 28/09.** Ele é a alavanca de estilo da `gpt-4o-mini-tts` — e, portanto, da entonação de pergunta e exclamação, que é o objetivo do produto. Enquanto a conta esteve sem crédito, nenhuma chamada completou. Fica registrado que o valor dele para o caso de uso **ainda não foi avaliado de ouvido**.

**Escolha de voz da OpenAI pelo usuário continua fora.** A OS-053 fez isso para o Kokoro; estender ao motor novo exige catálogo próprio e é outra responsabilidade.

**Custo por token, não por caractere.** A `gpt-4o-mini-tts` é cobrada por token de áudio; não existe preço por caractere publicado. O `cost_per_char` é uma conversão do custo observado numa amostra de 933 caracteres e deve ser recalibrado se o preço ou o modelo mudarem.

## 7. Link do PR

Ver PR do branch `os/055-openai-speaker`, que entrega OS-055 e OS-056 juntas (ver seção 5 do relatório da OS-056).
