# OS-051 — Sinal de worker ativo

## 1. Objetivo

Tornar visível a diferença entre "na fila, worker trabalhando" e "na fila, ninguém escutando" — hoje os dois estados são idênticos na tela, e a espera é indefinida.

## 2. Motivação, com o episódio real

Em 11/08/2026 o dono esperou vários minutos por um livro que nunca ia processar. O `uvicorn` estava de pé, o job estava `queued`, e o worker simplesmente não estava rodando. A tela dizia **"Na fila — aguardando processamento"**, que é exatamente o que ela diria se estivesse tudo certo.

Clicar em "Processar agora" agravou a confusão: a prioridade subiu de 0 para 2 — o botão **funcionou** —, mas priorizar uma fila que ninguém consome não produz efeito visível. O log do worker, legível desde a correção de `basicConfig`, também não ajuda quando o worker não existe para logar.

## 3. Escopo

Alterados:

- `storage/db.py` — tabela e funções de heartbeat.
- `worker/tasks.py` — registrar o batimento.
- `api/routes_books.py` — expor o estado do worker.
- `player/app.js` e `player/index.html` — avisar quando não há worker.
- Testes correspondentes.

Fora de escopo (declarado):

- **Detecção de `Job` órfão por heartbeat.** A decisão #15 registra que a retomada assume um único worker por vez, justamente por não existir heartbeat. Esta OS **cria** o heartbeat, mas **não** muda `requeue_orphaned()` — usar o novo sinal para distinguir "worker morreu" de "outro worker está processando" é ganho real, porém é outra responsabilidade e mexe no contrato `JobQueue`.
- **Múltiplos workers.** Continua valendo a decisão #11: um worker ativo por vez. A tabela guarda uma linha só.
- **Reiniciar o worker automaticamente.** Esta OS informa; não age.

## 4. Contratos envolvidos

Nenhum contrato de plugin é alterado. O heartbeat vive em `storage/db.py`, que é a camada de armazenamento da aplicação — não em `JobQueue`, senão toda implementação de fila futura teria de suportá-lo.

**Decisão de schema que evita dívida conhecida:** o heartbeat entra como **tabela nova**, nunca como coluna nova em tabela existente. O `PROJECT_STATE.md` registra que o projeto não tem migração de schema — só `CREATE TABLE IF NOT EXISTS`, que cria tabela ausente mas **nunca adiciona coluna** a uma tabela que já existe. Isso já quebrou o `books.db` local nas OS-018, OS-032 e OS-042, sempre com erro obscuro. Tabela nova é criada normalmente pelo `init_db()` e **não** exige apagar o banco.

## 5. O problema difícil: worker ocupado não é worker morto

O batimento não pode ser escrito só no laço de polling do `run_worker`. Durante `process_job`, o worker fica minutos sem voltar ao laço — sintetizando um capítulo inteiro. Escrito só no polling, **um worker trabalhando pareceria morto**, que é o oposto do que esta OS quer.

Solução exigida: registrar o batimento **também durante a síntese**, no mesmo ponto onde a preempção da OS-032 já é consultada — o callback por chunk. Assim os dois estados ficam cobertos:

| Estado do worker | Onde o batimento é escrito |
|---|---|
| ocioso, aguardando job | laço de `run_worker` |
| sintetizando | callback por chunk |

O limiar de "parado" precisa acomodar o chunk mais lento. Com Kokoro um chunk sai em segundos; com um motor remoto, mais. Proposto: **120 segundos**, com o valor em constante para calibração.

## 6. Critérios de aceite

- [ ] O worker registra batimento ao iniciar, antes do primeiro job
- [ ] O worker registra batimento a cada ciclo do laço de polling
- [ ] O worker registra batimento **durante a síntese**, a cada chunk persistido
- [ ] `db` expõe o instante do último batimento e se ele está dentro do limiar
- [ ] Um batimento mais antigo que o limiar é reportado como worker parado
- [ ] Banco sem nenhum batimento é reportado como worker parado, não como erro
- [ ] A API expõe o estado do worker
- [ ] O player avisa quando há livro aguardando **e** nenhum worker ativo
- [ ] O aviso não aparece quando o worker está ativo
- [ ] `init_db()` cria a tabela nova sem exigir apagar `books.db`
- [ ] Nenhum teste existente quebra (321 hoje)

## 7. Testes exigidos (mínimo)

- `test_heartbeat_absent_reports_worker_stopped`
- `test_heartbeat_recent_reports_worker_alive`
- `test_heartbeat_older_than_threshold_reports_worker_stopped`
- `test_init_db_creates_heartbeat_table_on_existing_database`
- `test_worker_records_heartbeat_on_startup`
- `test_worker_records_heartbeat_while_synthesizing`
- `test_api_exposes_worker_status`
- `test_player_warns_when_no_worker_and_book_waiting`

## 8. Relatório

Ver `docs/report/OS-051-report.md`.
