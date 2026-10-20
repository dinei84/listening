# OS-063 — Relatório de entrega

**Data:** 20/10/2026
**Branch:** `os/063-timeout-de-leitura`
**Commit(s) relevante(s):** `cc07bad` (OS), `63540b6` (Red), `cefa644` (Green)

## 1. Resumo do que foi feito

O timeout de leitura da OpenAI passou a ser classificado como
`TransientSpeakerError`, para o retry da OS-043 agir. Antes ele escapava das duas
categorias e derrubava o livro inteiro.

## 2. Checklist de DoD

### Padrão (`AGENTS.md` seção 4)

- [x] Testes escritos antes da implementação — commit Red precede o Green
- [x] Todos os testes da OS passam localmente
- [x] Nenhum teste existente quebrou — 522 → **530 passando**
- [x] Código segue os contratos de `ARQUITETURA.md` — nenhum contrato alterado
- [x] Nenhuma chamada real a API paga nos testes — o ponto de rede é mockado
- [x] Type hints e docstring de uma linha em toda função pública
- [x] `PROJECT_STATE.md` atualizado — item 67 registrado
- [x] Relatório criado em `docs/report/OS-063-report.md`
- [x] PR aberto com título `[OS-063] ...`

### Específico (seção 4 da OS)

- [x] `TimeoutError` de leitura vira `TransientSpeakerError`
- [x] `socket.timeout` também
- [x] Falha de conexão (`URLError`) continua transitória
- [x] `HTTPError` continua classificado antes, por status
- [x] 401 continua `PermanentSpeakerError`
- [x] 429 por falta de crédito continua `PermanentSpeakerError`
- [x] Qualquer `OSError` de rede é transitório
- [x] A mensagem diz que vale retentar
- [x] Nenhum teste existente quebra

## 3. Testes escritos

8 novos, em `tests/unit/speakers/test_openai_speaker.py`.

| Teste | Passou? |
|---|---|
| `read_timeout_is_transient` | ✅ |
| `socket_timeout_is_transient` | ✅ |
| `network_oserror_is_transient` (reset, aborted, broken pipe, OSError) | ✅ |
| `http_error_is_classified_before_generic_oserror` | ✅ |
| `insufficient_quota_is_still_permanent_after_the_fix` | ✅ |

Commit "Red" antes do "Green"? **[x] Sim** — 6 falhas antes da correção.

## 4. Saída de comandos relevantes

### O defeito, reproduzido antes da correção

```
TimeoutError e subclasse de URLError? False
socket.timeout e TimeoutError?        True

RESULTADO: ESCAPOU sem classificacao -> TimeoutError: The read operation timed out
```

### Depois

```
AGORA: Transient -> falha de rede ao chamar a OpenAI
(TimeoutError: The read operation timed out); tentativa pode ser repetida
```

### Suíte e lint

```
530 passed, 1 warning in 13.86s
All checks passed!     (plugins/ tests/)
```

### A rodada que expôs o defeito

Primeira tentativa de sintetizar um livro inteiro ("O Programador Pragmático"),
em 20/10/2026:

```
[11:08:18] synthesizing  9 / 641
[11:09:18] synthesizing  10 / 641
[11:10:18] synthesizing  10 / 641
[11:11:18] error  10 / 641
error_message: "The read operation timed out"

por motor: [('kokoro', 10)]      <- nenhuma chamada paga completou
gasto em TTS: US$ 0,00
```

O primeiro chunk roteado para a OpenAI foi o primeiro a falhar, e levou o livro
junto. A estimativa que o app calculou antes de gastar (US$ 0,8647; 59 de 641
trechos no pago) bateu com a estimativa a seco de 29/09 (US$ 0,8483; 56 de 645).

## 5. Desvios do escopo original

Nenhum desvio de escopo. Três registros:

1. **Uma suposição minha na abertura da OS estava errada, e foi corrigida em vez
   de virar item de backlog.** Declarei que o `LLMNormalizer` "provavelmente tem o
   mesmo buraco". **Tem não:** ele envolve a chamada em `except Exception` e
   degrada para o texto original com aviso (`llm_normalizer.py:88`), então um
   timeout ali custa a normalização daquele trecho, não o livro. O documento da OS
   foi corrigido.

2. **O autofix do `ruff` apagou o sentido de um teste, e eu quase deixei passar.**
   A regra UP041 reescreveu `socket.timeout` para `TimeoutError`, o que
   transformava `test_openai_socket_timeout_is_transient` numa cópia idêntica do
   teste anterior. Restaurado com `# noqa: UP041` explícito e o motivo no
   comentário, mais uma asserção de que os dois nomes ainda são o mesmo objeto —
   se um dia deixarem de ser, o teste avisa em vez de abrir um buraco em silêncio.

3. **Item 67 registrado no backlog:** não existe caminho para retomar um livro em
   `error`. A máquinaria existe (`skip_sequences`, OS-022); falta a porta de
   entrada. Custou pouco aqui (10 trechos gratuitos), mas um livro que morresse no
   trecho 500 jogaria fora ~45 min de GPU e os dólares já gastos.

## 6. Dúvidas / bloqueios

Nenhum bloqueio. Duas observações:

1. **É a quinta vez nesta sequência que algo passa em teste mockado e falha em uso
   real.** O padrão é sempre o mesmo: o mock levanta a exceção que eu *imaginei*
   (`URLError`, falha de conexão), não a que a biblioteca de fato levanta naquele
   ponto (`TimeoutError`, depois da conexão aberta). Nenhuma quantidade de teste
   com mock teria encontrado isto — só a rodada real.

2. **Não sei se a OpenAI cobrou pela requisição que estourou o timeout.** O áudio
   pode ter sido gerado do lado deles e perdido do nosso. O valor é desprezível
   (um chunk), mas vale olhar o painel para a conta fechar com o que medirmos na
   rodada completa.

## 7. Link do PR

Ver o PR aberto contra `main` com título `[OS-063] Timeout de leitura mata o livro`.
