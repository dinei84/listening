# OS-039 — Navegação por trecho no player (voltar e avançar)

## 1. Objetivo

Achado em uso real: depois de pular para um capítulo e ouvir um pouco, **não há como voltar ao trecho anterior**. O player só tem play/pause e velocidade; o avanço acontece sozinho no evento `ended`, o `<audio controls>` só permite arrastar **dentro** do trecho corrente (~60s), e clicar num capítulo pula sempre para o **início** dele. Na prática a navegação é um caminho de mão única. Esta OS dá controle de trecho ao ouvinte.

Sem IA e sem custo — é lacuna de UI. Faz parte do **nível simples** do produto (decisão #23).

## 2. Escopo

**Dentro do escopo:**

- **`player/index.html`**: botões "◀ Anterior" e "Próximo ▶" na seção `#controls`, ao lado do play/pause.
- **`player/app.js`**:
  - Anterior: volta um trecho. Comportamento a definir e documentar — a sugestão é o padrão de tocador de podcast: se já se passaram mais de ~3s do trecho corrente, o primeiro clique **reinicia o trecho atual**; abaixo disso (ou num segundo clique rápido), vai para o trecho anterior. Documentar a escolha no relatório.
  - Próximo: avança um trecho, sem esperar o `ended`.
  - Ambos precisam respeitar o que já existe: ancoragem por `sequence` e não por índice (OS-030), atualização do capítulo em foco e do indicador de posição (OS-029), e gravação de progresso no servidor (OS-028).
  - Desabilitar "Anterior" no primeiro trecho e "Próximo" quando não houver trecho seguinte **já sintetizado** — durante a síntese incremental (OS-021/030) o próximo pode ainda não existir; nesse caso o botão fica desabilitado em vez de falhar.
- **Atalhos de teclado**: seta esquerda/direita para trecho anterior/próximo, espaço para play/pause. Não capturar quando o foco estiver num campo de texto (`input`/`select`), senão quebra o campo "Abrir livro existente".

**Fora do escopo:**
- Barra de progresso arrastável do **livro inteiro** (seek para qualquer ponto). É desejável, mas exige mapear tempo→trecho para centenas de arquivos; fica para uma OS própria se o uso pedir.
- Marcadores/favoritos dentro do livro.
- Retroceder/avançar N segundos dentro do trecho — o `<audio controls>` nativo já cobre.
- Qualquer mudança de backend. Se algum ajuste parecer necessário, **parar e reportar** — os dados de que a UI precisa (`sequence`, `chapter_id`, `chunks_total`) já vêm das OS-027/029.

## 3. Contratos envolvidos

Nenhum. Esta OS só consome o que já existe.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] Botão "Anterior" volta um trecho e a reprodução continua a partir dele
- [ ] Botão "Próximo" avança um trecho sem esperar o fim do atual
- [ ] O comportamento de "Anterior" com o trecho já em andamento está definido e documentado (reiniciar vs. voltar)
- [ ] "Anterior" desabilitado no primeiro trecho; "Próximo" desabilitado quando o seguinte ainda não foi sintetizado
- [ ] Indicador de posição e destaque do capítulo (OS-029) acompanham a navegação manual
- [ ] O progresso continua sendo gravado no servidor (OS-028) ao navegar
- [ ] Setas do teclado navegam entre trechos, sem sequestrar a digitação em campos de texto
- [ ] Nenhum arquivo de backend alterado
- [ ] Verificação manual em navegador real registrada no relatório (padrão das OS-014/016/023/029/030)

## 5. Testes exigidos (mínimo)

UI em JS puro, sem suíte JS no projeto (decisão #12) — a verificação principal é manual, registrada no relatório. Cobertura automatizada onde couber, no padrão que `tests/integration/test_player.py` já usa:

- `test_player_has_prev_and_next_buttons` (o HTML servido contém os controles)

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-039-report.md`.*
