# OS-059 — Relatório de entrega

**Data:** 29/09/2026
**Branch:** `os/059-transparencia-de-motor-e-custo`
**Commit(s) relevante(s):** `4dd8be0` (OS), `c6ffdf6` (Red), `b5bf8b3` (Green)

## 1. Resumo do que foi feito

`engine_used` saiu do banco e chegou à tela: o trecho corrente diz qual motor o
narrou e o livro mostra o balanço entre eles. E o banner de confirmação, que
dizia só "este livro deve custar US$ 0,85", passou a mostrar quantos trechos vão
para a voz paga, a que preço, e que o resto não custa nada.

## 2. Checklist de DoD

### Padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação — commit Red `c6ffdf6` precede o Green `b5bf8b3`
- [x] Todos os testes da OS passam localmente
- [x] Nenhum teste existente quebrou — 452 → **478 passando** (um teste da OS-057 foi ajustado; ver seção 5)
- [x] Código segue os contratos de `ARQUITETURA.md` — nenhum `base.py` de plugin foi tocado
- [x] Nenhuma chamada real a API paga nos testes — os Speakers são `FakeSpeaker`
- [x] Type hints e docstring de uma linha em toda função pública; JSDoc no `engines.js`
- [x] `PROJECT_STATE.md` atualizado
- [x] Relatório criado em `docs/report/OS-059-report.md`
- [x] PR aberto com título `[OS-059] ...`

### Específico (seção 4 da OS)

- [x] `estimate_breakdown` devolve custo total, do pago, do local, trechos pagos e totais
- [x] `estimate_breakdown().total` é **exatamente** o que `estimate_cost` devolvia — travado em 5 textos diferentes
- [x] Roteamento desligado → tudo no motor configurado, zero no pago
- [x] Roteamento ligado → só chunks acima do limiar contam como pagos
- [x] Custo do normalizador entra no total e **não** é atribuído a nenhum motor
- [x] A divisão é persistida antes de `pending_confirmation`
- [x] `GET /status` expõe a divisão
- [x] `GET /audio` expõe `engine_used` por trecho
- [x] `Engines.label` dá nome humano a `kokoro` e `openai`
- [x] `Engines.label` não imprime "undefined" para motor desconhecido
- [x] `Engines.summarize` conta por motor e ignora lista vazia
- [x] O trecho corrente mostra o motor — verificado no navegador
- [x] O banner mostra a divisão e diz que o local não custa nada
- [x] Livro sem roteamento não ganha ruído — o resumo some com menos de dois motores
- [x] Nenhum teste existente quebra

## 3. Testes escritos

26 novos (9 em Node, 16 em pytest unit, 11 em integration — a tabela agrupa por caso).

| Teste | Arquivo | Passou? |
|---|---|---|
| `label` conhecidos / desconhecido / vazio | `tests/player/engines.test.js` | ✅ |
| `isPaid` separa pago de grátis, e desconhecido conta como pago | `tests/player/engines.test.js` | ✅ |
| `summarize` vazio / conta / ordena / ignora sem `engine_used` / um motor só | `tests/player/engines.test.js` | ✅ |
| `total` idêntico a `estimate_cost` em 5 textos + com normalizador | `tests/unit/test_breakdown_os059.py` | ✅ |
| divisão sem roteamento / com roteamento / limiar inalcançável | `tests/unit/test_breakdown_os059.py` | ✅ |
| parcelas fecham o total / contagens fecham / texto vazio / soma entre capítulos | `tests/unit/test_breakdown_os059.py` | ✅ |
| normalizador não atribuído a motor | `tests/unit/test_breakdown_os059.py` | ✅ |
| migração das colunas em banco antigo / gravar e ler a divisão | `tests/unit/test_breakdown_os059.py` | ✅ |
| `engine_used` no payload e no delta `?since=` | `tests/integration/test_transparency_os059.py` | ✅ |
| divisão no `/status` / null quando nunca estimado | `tests/integration/test_transparency_os059.py` | ✅ |
| player: módulo servido, ordem dos scripts, indicador, resumo, banner | `tests/integration/test_transparency_os059.py` | ✅ |

Commit "Red" antes do "Green"? **[x] Sim** — `c6ffdf6` (16 falhas em unit, 10 em integration, 1 em Node) precede `b5bf8b3`.

## 4. Saída de comandos relevantes

### Suíte completa e lint

```
478 passed, 2 warnings in 13.57s
All checks passed!     (tests/ storage/ api/ core/ worker/)
```

### Verificação em navegador, com dois motores no mesmo livro

O banco local foi temporariamente marcado com um chunk `openai` e um `kokoro`
para exercitar o caminho de dois motores, e **restaurado ao estado original ao
fim** (ambos `kokoro`, `status: ready`, colunas da divisão de volta a `NULL`).

```
payload: [ {seq:0, engine:"kokoro"}, {seq:1, engine:"openai"} ]
trecho0: "Narrado com voz local"
trecho1: "Narrado com voz premium"
classeDaMarca: "marca-motor pago"
resumoDoLivro: "Neste livro: 1 de 2 trechos com voz local · 1 de 2 trechos com voz premium"
```

Banner de confirmação, nos três casos:

```
com divisão:
  "Custo estimado: US$ 0,85. 57 de 624 trechos (9,1%) vão para a voz premium,
   a US$ 0,85. Os outros 567 ficam na voz local, que não custa nada."

livro antigo, sem divisão no banco (colunas NULL):
  "Custo estimado: US$ 0,85."

roteamento que não mandou nada para o pago:
  "Custo estimado: US$ 0,00. Nenhum trecho vai para a voz premium neste livro."
```

Os números 57/624/US$ 0,85 são os do item 59 do backlog (limiar 3 sobre o
"Programador Pragmático"), usados como dado de verificação.

## 5. Desvios do escopo original

**Um teste da OS-057 foi ajustado, e não é o mesmo que quebrá-lo.**
`test_audio_endpoint_since_keeps_full_payload_shape` fixava o conjunto exato dos
quatro campos de então, e quebrou quando `engine_used` entrou. Mas o que ele diz
verificar, na própria docstring, é que *"o delta precisa ter os mesmos campos do
payload cheio"* — e `engine_used` entrou nos **dois**. Reescrito para comparar
delta contra payload cheio, que é a intenção declarada dele e sobrevive ao
próximo campo. A asserção sobre o conjunto concreto (agora com cinco campos)
existe em `test_audio_endpoint_engine_used_survives_since`, desta OS.

**Dois testes meus passavam vazios, e foram corrigidos durante o Green.**
`test_breakdown_total_matches_with_normalizer` e o de atribuição usavam
`FakeConfig` com `normalizer="noop"`, em que `_build_normalizer` devolve `None`:
o custo do normalizador ficava 0 dos **dois** lados e a asserção passava sem
exercitar nada. Passaram a usar `normalizer="llm"` e a afirmar
`normalizer_cost > 0`.

**Dois acertos de texto feitos após ver a tela:**

1. A porcentagem saía como `"9.1%"`, com ponto, ao lado de `"US$ 0,85"`, com
   vírgula. Trocado `toFixed` por `toLocaleString("pt-BR")`.
2. A linha de status dizia "Aguardando confirmação de custo — este livro deve
   custar US$ 0,85" e o banner logo abaixo repetia o valor. A linha passou a ser
   só "Aguardando confirmação de custo."; o número e a divisão ficam no banner.

**Escopo:** `core/models.py` e `worker/tasks.py` estavam declarados na seção 2 da
OS. Nenhum arquivo fora da lista foi tocado.

## 6. Dúvidas / bloqueios

Nenhum bloqueio. Três observações:

1. **O custo real após a síntese continua fora, e por um motivo concreto.** O
   número de caracteres por chunk não é persistido, então o custo real só sairia
   de estimativa sobre duração — número inventado com cara de medido. O que é
   **exato** depois da síntese é a contagem de trechos por motor, e é o que a
   tela mostra. Persistir os caracteres por chunk tornaria o custo real
   calculável, e é candidato a item de backlog se o dono quiser.

2. **A divisão é gravada uma vez, na estimativa, e não é reconciliada com o que
   de fato aconteceu.** Se um chunk cair para o motor local por
   `TransientSpeakerError` (OS-056), o banner terá previsto um trecho pago a
   mais. O resumo por motor — que vem dos chunks reais — mostra a verdade; o
   banner mostra a previsão. São coisas diferentes e a tela as apresenta em
   momentos diferentes, então não se contradizem na mesma visão.

3. **Esta é a superfície que o item 59 vai precisar.** Com a divisão exposta em
   `/status` e o motor por trecho no payload, transformar o limiar em
   diferenciador de plano passa a ter onde mostrar o que cada plano entrega. O
   bloqueio do item 59 continua sendo o conceito de usuário, que não existe.

## 7. Link do PR

Ver o PR aberto contra `main` com título `[OS-059] Transparência de motor e de custo`.
