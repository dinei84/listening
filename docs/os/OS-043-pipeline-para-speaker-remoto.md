# OS-043 — Preparar o pipeline para um `Speaker` remoto (limite por engine + resiliência de rede)

## 1. Objetivo

Duas suposições estão hoje embutidas no pipeline porque o único `Speaker` é local, e as duas quebram com um `Speaker` cloud. Esta OS as remove **antes** de o `Speaker` pago existir, para que a OS de implementação dele seja pequena. Pode ser feita sem depender da OS-041.

## 2. Contexto: as duas suposições

**(a) O limite de tamanho é medido em fonemas, com o G2P do Kokoro.** A OS-034 criou `_split_by_phoneme_budget()` dentro do `KokoroSpeaker`, que usa `pipeline.g2p` para medir e corta em 510 fonemas. Um `Speaker` cloud **não tem G2P** e tem limite em **caracteres por requisição** (tipicamente alguns milhares — número real a levantar na OS-041). Hoje essa lógica está corretamente encapsulada no `KokoroSpeaker`, então o problema não é vazamento — é que **não existe forma de um `Speaker` novo declarar o próprio limite** sem reimplementar tudo.

**(b) Qualquer falha vira livro com erro.** `worker/tasks.py::process_job()` captura `Exception` e marca o `Book` como `error` (captura ampla intencional desde a OS-010). Com síntese local isso é razoável — falha é bug, não intermitência. Com cloud, **683 chamadas de rede** num livro significam que mesmo 1% de intermitência derruba ~7 vezes. E cada queda, num livro pago, é dinheiro já gasto virando status de erro exigindo intervenção manual.

## 3. Escopo

**Dentro do escopo:**

- **Limite declarado pelo `Speaker`** — extensão aditiva do contrato (`ARQUITETURA.md` seção 4.2), mesmo padrão das OS-021/022/025. Cada `Speaker` passa a poder informar seu limite de tamanho por chamada e como medi-lo; quem não informar mantém o comportamento atual. O `KokoroSpeaker` continua medindo em fonemas com o G2P dele — **nada muda no áudio produzido hoje**, e isso precisa ser provado por regressão.
- **Retry com backoff para falha transitória**, aplicado à síntese de um chunk. Distinguir **transitório** (rede, timeout, 429/5xx) de **permanente** (credencial inválida, texto rejeitado, 4xx não-429): transitório tenta de novo com espera crescente; permanente falha na hora, sem queimar tentativas.
  - Onde aplicar é decisão de implementação; o candidato natural é em volta da chamada ao `Speaker`, em `core/pipeline.py::synthesize_text()`.
  - **Número de tentativas e espera precisam ser configuráveis**, não fixos no código.
- **Esgotar as tentativas não pode perder o trabalho já feito.** Hoje a retomada da OS-022 já salva os chunks persistidos, mas o `Book` vai para `error` e exige re-priorização manual. Avaliar e documentar: manter `error` (o usuário reprocessa e a OS-022 pula o que existe) ou tratar como pausa. Recomendação: **manter `error` com mensagem clara**, porque falha persistente de rede merece atenção humana — mas dizendo explicitamente que o áudio já gerado está preservado.

**Fora do escopo:**
- Implementar o `Speaker` cloud (depende da OS-041) e a trava de custo (OS-042).
- Paralelizar chamadas — a OS-031 mostrou GPU saturada localmente; para cloud a questão é limite de taxa do provedor, e isso se decide com o provedor escolhido.
- Cache de áudio entre livros diferentes.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] Um `Speaker` pode declarar limite próprio de tamanho por chamada; quem não declara mantém o comportamento atual
- [ ] O `KokoroSpeaker` produz **exatamente o mesmo resultado de hoje** — regressão explícita das OS-034/037
- [ ] Falha transitória na síntese de um chunk é repetida com backoff, sem derrubar o livro
- [ ] Falha permanente falha de imediato, sem gastar tentativas
- [ ] Tentativas e espera são configuráveis
- [ ] Esgotadas as tentativas, os chunks já persistidos continuam no banco e a mensagem diz isso
- [ ] Nenhuma chamada de rede real na suíte — dublê de `Speaker` que falha de forma controlada
- [ ] Nenhum teste das OS-021/022/024/032/034/037 quebra

## 5. Testes exigidos (mínimo)

- `test_speaker_can_declare_own_size_limit`
- `test_kokoro_speaker_output_unchanged` (regressão OS-034/037)
- `test_transient_failure_is_retried_with_backoff`
- `test_permanent_failure_fails_immediately`
- `test_retry_exhausted_keeps_persisted_chunks`
- `test_retry_count_is_configurable`

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-043-report.md`.*
