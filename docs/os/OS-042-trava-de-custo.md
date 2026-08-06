# OS-042 — Trava de custo: estimativa com confirmação + teto de segurança

## 1. Objetivo

Antes de existir qualquer `Speaker` pago, o sistema precisa de proteção contra gasto acidental. Hoje **nada** impede enviar um livro de 650 mil caracteres e queimar o valor sem saber — e num produto vendido isso é inaceitável. Esta OS liga o gancho que já existe no contrato e adiciona **duas** proteções, conforme decisão do dono: **estimativa com confirmação explícita** no upload **e** **teto de segurança** que corta mesmo o que foi confirmado.

**Pode ser feita antes de escolher o provedor (OS-041)** — com o Kokoro (`cost_per_char == 0.0`) como único `Speaker`, a estimativa dá zero e o fluxo é exercitável de ponta a ponta.

## 2. Contexto

`Speaker.cost_per_char` existe desde a OS-004 e está documentado em `ARQUITETURA.md` seção 4.2 como *"0.0 para engines locais. Usado para estimar custo antes de rodar"* — mas **nunca foi lido por nada** (verificado: nenhuma referência em `core/`, `worker/` ou `api/`). É um gancho dormante projetado exatamente para este momento.

Tamanho real do acervo, para dimensionar: livro técnico típico tem **500–650 mil caracteres** (medido na OS-041 seção 2).

## 3. Escopo

**Dentro do escopo:**

- **Estimativa de custo**: função que, dado o texto extraído de um livro e o `Speaker` configurado, devolve o custo estimado (`total_de_caracteres × cost_per_char`). Onde mora é decisão de implementação — `core/pipeline.py` é o lugar natural, junto de `count_text_chunks()`.
- **Persistir a estimativa** no `Book`, para poder mostrar e auditar depois.
- **Confirmação explícita antes de processar**: um livro cuja estimativa seja **maior que zero** não entra na fila direto — fica num estado aguardando confirmação, e a UI mostra "este livro deve custar ~X; confirmar?". Endpoint para confirmar. Custo zero (Kokoro) segue direto, **sem** perguntar nada — o nível simples não pode ganhar fricção.
- **Teto de segurança** em `config.yaml`: limite por livro. Estimativa acima do teto **não processa nem com confirmação** — e o motivo aparece para o usuário. Decisão de implementação a documentar: recusar de vez ou degradar para o `Speaker` local. Recomendação: **degradar**, com aviso claro — entregar o livro com voz local é melhor que não entregar.
- **UI**: mostrar a estimativa e o botão de confirmar; mostrar o motivo quando o teto barrar.

**Fora do escopo:**
- Implementar `Speaker` cloud (depende da OS-041).
- Cobrança, billing, controle de assinatura ou de saldo — isto é só **proteção contra gasto**, não financeiro.
- Custo de LLM (OS-038) — quando existir, deve reaproveitar este mesmo mecanismo; registrar isso no relatório.

**Cuidado obrigatório:** a estimativa **precisa vir antes da síntese começar**, não durante. Descobrir o custo no meio do processamento já significa dinheiro gasto. Como a extração já roda antes da síntese em `process_job()`, a contagem de caracteres está disponível no momento certo.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] A estimativa é calculada a partir do texto real extraído e do `cost_per_char` do `Speaker` configurado
- [ ] Livro com estimativa **zero** (Kokoro) processa direto, sem confirmação e sem mudança de comportamento — regressão de todo o fluxo atual
- [ ] Livro com estimativa **maior que zero** não é sintetizado antes de confirmação explícita
- [ ] Estimativa acima do teto de `config.yaml` não processa mesmo confirmada; o comportamento escolhido está documentado
- [ ] O usuário vê o valor estimado antes de confirmar, e vê o motivo quando o teto barra
- [ ] A estimativa acontece **antes** de qualquer chamada ao `Speaker`
- [ ] Nenhuma chamada de rede ou API paga na suíte — dublê de `Speaker` com `cost_per_char` fictício
- [ ] Nenhum teste das OS-021/022/024/032 quebra

## 5. Testes exigidos (mínimo)

- `test_estimate_cost_uses_speaker_cost_per_char`
- `test_zero_cost_book_processes_without_confirmation` (regressão do fluxo atual)
- `test_paid_book_is_not_synthesized_before_confirmation`
- `test_confirmed_book_proceeds_to_synthesis`
- `test_estimate_above_cap_does_not_process_even_when_confirmed`
- `test_estimate_happens_before_any_speaker_call`

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-042-report.md`.*
