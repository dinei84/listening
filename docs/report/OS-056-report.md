# OS-056 — Relatório de entrega

**Data:** 28/09/2026 (implementação em 13/08/2026)
**Branch:** `os/055-openai-speaker` (mesmo branch da OS-055 — ver seção 5)
**Commit(s) relevante(s):** `ce3663e` (Red), `5a8b25e` (Green), `defee2a` (falha permanente)

## 1. Resumo do que foi feito

O pipeline passou a decidir, por chunk, qual motor usa: conta as frases com `!` ou `?` e, a partir de um limiar, manda o chunk **inteiro** para o motor pago. O resto do livro continua no motor local, sem custo.

## 2. Checklist de DoD

Padrão (`AGENTS.md` seção 4):

- [x] Testes antes da implementação — `ce3663e` (Red) antes de `5a8b25e` (Green)
- [x] Todos os testes da OS passam
- [x] Nenhum teste existente quebrou
- [x] Nenhum contrato de plugin alterado
- [x] Nenhuma chamada paga nos testes — os dois motores são dublês
- [x] Type hints e docstring de uma linha em toda função pública
- [x] `PROJECT_STATE.md` atualizado
- [x] Relatório em `docs/report/OS-056-report.md`
- [x] PR aberto — ver seção 7

Específico (seção 6 da OS):

- [x] Chunk com ≥ limiar vai inteiro para o Speaker pago
- [x] Chunk abaixo do limiar vai inteiro para o local
- [x] Limiar configurável, padrão 3
- [x] Nenhum `AudioChunk` mistura motores
- [x] `engine_used` reflete o motor realmente usado
- [x] Roteamento desligado (padrão) não muda nada
- [x] A estimativa da OS-042 conta só a fração roteada
- [x] Falha **transitória** do pago degrada aquele chunk; **permanente** para o livro (ver seção 5)
- [x] Pausas da OS-045 seguem valendo dentro de cada chunk
- [x] **Amostra de áudio de parágrafo real anexada** — cumprido em 28/09/2026, ver `docs/report/OS-056-teste-troca-de-vozes.md`

## 3. Testes escritos

12 testes em `tests/unit/test_routing.py`: roteamento acima e abaixo do limiar, limiar configurável, `engine_used`, ausência de mistura de motores, roteamento desligado, degradação transitória, parada em falha permanente, `speaker_name` desligando o roteamento, e as duas variantes de estimativa de custo.

Commit "Red" antes do "Green"? [x] Sim.

## 4. Saída de comandos relevantes

Calibração do limiar, medida em 230 chunks reais (páginas 24–140 do "Programador Pragmático", 216.365 caracteres):

```
LIMIAR       CHUNKS      % CHARS         TROCAS    US$/livro
1                85        37.1%             86        3.19
2                44        19.2%             56        1.65
3                21         9.2%             32        0.79
4                14         6.1%             25        0.53
5                10         4.3%             17        0.37

roteando por FRASE:  9,0% dos chars, ~374 trocas, US$ 0,78
```

Decisão do roteamento em dois textos de perfil oposto:

```
teste-expressividade2        2 chunks |  1 roteado (72% dos chars)
Pragmático (pgs 24-140)    230 chunks | 21 roteados (9% dos chars)
```

Suíte: `401 passed`.

## 5. Desvios do escopo original

**a) O desenho mudou antes da execução, por proposta do dono.** A OS foi aberta com roteamento **frase a frase**. Depois de ouvir o efeito num texto de frases curtas, o dono propôs contar as expressivas do chunk e mandar o chunk inteiro. A medição mostrou que a proposta dele é estritamente melhor: mesma cobertura (9,2% contra 9,0%), mesmo custo (US$ 0,79 contra 0,78) e **12× menos trocas de voz** (32 contra 374). A OS foi reescrita antes da implementação.

Isso também simplificou o código: como o chunk inteiro vai para um motor só, **nenhum `AudioChunk` mistura fontes**, e sumiram os requisitos de casar volume e taxa de amostragem que o desenho anterior exigia.

**b) Falha permanente deixou de degradar.** A OS pedia que falha do motor pago degradasse o chunk. Na prática, degradar **qualquer** falha fez o livro sair inteiro no motor local durante várias rodadas de teste, sem o dono saber. Só falha transitória degrada agora.

**c) Entregue no mesmo branch da OS-055.** As duas são inseparáveis na prática — roteamento sem um segundo motor registrado não tem para onde rotear —, e separar os branches significaria abrir um PR que não pode ser testado sozinho.

## 6. Dúvidas / bloqueios

**A amostra de áudio foi produzida em 28/09/2026 e o item está fechado.** Na entrega original ela não existiu porque a conta da OpenAI ficou sem crédito durante toda a fase de testes: cada chamada voltava 429 e o sistema degradava para o local. Com crédito, o teste foi feito com limiar 5 sobre um texto de perfil misto, produzindo `OpenAI → Kokoro → OpenAI` em 2m27s, e **aprovado na escuta**. Registro completo em `docs/report/OS-056-teste-troca-de-vozes.md`.

**A hipótese central segue não verificada.** Estimei ~506 trocas de timbre por livro no roteamento frase a frase e usei isso para argumentar contra ele. A estimativa nunca foi validada de ouvido — está registrada como suposição. O desenho por limiar reduz o problema a 32 trocas, mas **se a troca de voz na fronteira de chunk incomoda ou passa despercebida é pergunta em aberto**.

**Correção de premissa registrada.** Foi afirmado, com base em 42 frases de duas amostras pequenas, que prosa técnica tem ~0% de frases com `!` ou `?`, e isso foi usado para argumentar que o roteamento raramente dispararia. A medição em 2.076 frases reais deu **9,0%** — uma em cada onze. A amostra anterior era pequena demais para a conclusão.

## 7. Link do PR

Ver PR do branch `os/055-openai-speaker`.
