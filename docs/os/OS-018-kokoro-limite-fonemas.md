# OS-018 — Corrige falha de síntese em texto denso ("Phoneme string too long")

## 1. Objetivo

Corrigir um bug real encontrado em uso: enviar um livro técnico longo (Security Engineering, Ross Anderson) resultou em `Book.status == "error"`. A causa raiz, confirmada consultando `jobs.error_message` direto no SQLite (não havia endpoint nem log pra isso — ver seção 2, item extra): `Phoneme string too long: 863 > 510`. O Kokoro tem um limite de ~510 fonemas por chamada de síntese; `processing/chunker.py` divide por **caracteres** (`DEFAULT_MAX_CHARS = 1000`), sem saber quantos fonemas um pedaço vai gerar — texto denso/técnico gera mais fonemas por caractere que texto comum, e um chunk dentro do limite de caracteres pode estourar o limite de fonemas do Kokoro. Como a síntese hoje é sequencial e sem tolerância a falha parcial (`worker/tasks.py`), **um único chunk problemático derruba o livro inteiro**, mesmo que o resto processasse bem.

## 2. Escopo

**Dentro do escopo:**
- `plugins/speakers/kokoro_speaker.py` — tornar `KokoroSpeaker.synthesize()` resiliente a esse erro específico do Kokoro:
  - Extrair a chamada real ao pipeline (`generate_from_tokens` + concatenação do áudio) para um método interno que devolve o áudio bruto (não grava arquivo ainda), pra permitir recursão limpa.
  - Se o Kokoro rejeitar o texto por causa do limite de fonemas, **dividir o texto ao meio por palavra** (não por sentença — o texto pode ser uma única sentença longa sem pontuação, e o `chunk_text()` da OS-008 nunca corta sentença, o que não ajudaria aqui; esta é uma divisão interna só pra caber no limite do engine, diferente da divisão em chunks pra playback) e sintetizar cada metade recursivamente, concatenando o áudio resultante.
  - Ter um limite de tentativas/profundidade de recursão razoável — se dividir repetidamente não resolver (caso patológico, ex: uma "palavra" isolada gigante), desistir com um erro claro em vez de recursão infinita.
  - `synthesize()` continua devolvendo um único `AudioChunk` — o contrato do `Speaker` (`ARQUITETURA.md` seção 4.2) não muda. A divisão/retry é um detalhe de implementação interno ao Kokoro, invisível pra quem chama.
- `processing/chunker.py` — recalibrar `DEFAULT_MAX_CHARS` empiricamente: rodar o Kokoro de verdade (sem mock) contra uma amostra de texto denso/técnico real (pode reaproveitar um trecho do próprio PDF que causou o bug, ou texto técnico similar), medir a relação real caractere→fonema observada, e escolher um novo valor com margem de segurança. Documentar o processo e os números no relatório — mesmo padrão de validação empírica já usado nas OS-005/006/017, não um número escolhido de cabeça.
- Adicionar um jeito simples de consultar o erro de um `Job` que falhou — hoje só existe direto no SQLite (`jobs.error_message`), o que forçou uma investigação manual pra achar esse bug. Não precisa ser um endpoint novo sofisticado: pode ser `GET /books/{id}/status` passando a incluir `error_message` quando `status == "error"` (mudança pequena, mesmo endpoint já existente).

**Fora de escopo:**
- Recuperação parcial no `worker/tasks.py` (ex: continuar processando os chunks que sintetizam bem e só marcar como falho o(s) chunk(s) problemático(s), em vez de o livro inteiro) — depois da correção no Kokoro, esse cenário deve ficar raro; se voltar a acontecer com frequência, tratar em OS futura.
- Qualquer mudança em `processing/chunker.py` além do valor de `DEFAULT_MAX_CHARS` — a lógica de divisão por sentença continua igual.
- Retry automático de `Job`s que já falharam antes desta correção (o livro do achado original precisa ser reenviado depois que a OS for concluída).
- Qualquer chamada de rede ou API paga além do já existente (download de modelo do Kokoro na primeira execução, comportamento já conhecido).

## 3. Contratos envolvidos

Nenhuma mudança no contrato `Speaker` (`ARQUITETURA.md` seção 4.2) — `synthesize()` continua com a mesma assinatura e devolve um `AudioChunk` só. A mudança em `GET /books/{id}/status` é uma extensão aditiva da resposta (campo novo opcional), não quebra o contrato existente da OS-010/012.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] `KokoroSpeaker.synthesize()` não lança mais `Phoneme string too long` pra cima — quando o Kokoro rejeita um texto por esse motivo, divide e tenta de novo automaticamente
- [ ] A divisão é por palavra (não por sentença), com limite de tentativas — não trava em recursão infinita num caso patológico
- [ ] `synthesize()` continua devolvendo um único `AudioChunk`, mesmo quando internamente precisou dividir e sintetizar em partes — contrato do `Speaker` inalterado
- [ ] `processing/chunker.py`: `DEFAULT_MAX_CHARS` recalibrado com base em teste real contra o Kokoro (não mockado), documentado no relatório com os números observados
- [ ] `GET /books/{id}/status` inclui `error_message` na resposta quando `status == "error"` (omitido ou `null` nos demais casos)
- [ ] Testes automatizados da resiliência do `KokoroSpeaker` usam um dublê de pipeline que simula a rejeição por fonemas (mesmo padrão de mock total da construção do engine já usado desde a OS-004) — nenhum teste chama o Kokoro real
- [ ] Nenhuma chamada de rede ou API paga dentro da suíte de testes automatizada

## 5. Testes exigidos (mínimo)

- `test_kokoro_speaker_splits_and_retries_on_phoneme_limit_error`
- `test_kokoro_speaker_returns_single_audio_chunk_after_split_retry`
- `test_kokoro_speaker_gives_up_with_clear_error_if_split_does_not_help`
- `test_get_books_status_includes_error_message_when_status_is_error`
- `test_get_books_status_omits_error_message_when_status_is_not_error`

Local sugerido: `tests/unit/speakers/test_kokoro_speaker.py` (adicionar casos) e `tests/integration/test_api_books.py` (adicionar casos).

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-018-report.md` (template em `docs/report/REPORT_TEMPLATE.md`). Incluir a seção de recalibração empírica de `DEFAULT_MAX_CHARS` com números reais, mesmo padrão da OS-006/017.*
