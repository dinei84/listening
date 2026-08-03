# HANDOFF.md — Ponto de partida

Este é o primeiro arquivo a ler ao retomar este projeto em qualquer ferramenta nova (Claude Desktop, opencode, ou outra). Ele existe pra você não precisar reconstruir o histórico de decisões do zero. Depois de ler este arquivo, siga a ordem de leitura da seção 6.

---

## 1. O que é o projeto, em uma frase

App pessoal que converte PDF em audiobook (estilo Audible), com pipeline plugável de extração de texto/OCR e TTS, priorizando baixo custo (motores locais como padrão, cloud como opção sob demanda).

## 2. Intenção por trás das decisões (o "porquê", não só o "o quê")

- **É um projeto pessoal, não um produto comercial** — isso justifica escolhas como SQLite em vez de Postgres, e evitar infraestrutura pesada (Celery/Redis) enquanto não houver necessidade real.
- **Custo é a restrição central.** Toda decisão de arquitetura até aqui foi puxada por "como evitar pagar por token/caractere desnecessariamente" — daí a arquitetura plugável (trocar OCR/TTS sem reescrever nada) e a preferência por engines locais (Kokoro para TTS, PyMuPDF/Tesseract para extração) com fallback pago só quando o local não dá conta.
- **Governança rigorosa foi escolha deliberada, não exagero.** O dono do projeto trabalha com agentes de IA fazendo a execução (via OS's — Ordens de Serviço) e quer TDD (testes antes do código, pra falhar rápido) e um DoD auditado com rigor antes de aceitar qualquer entrega. Isso já pegou dois problemas reais nas primeiras OS's (ver seção 4) — é pra continuar assim, mesmo que a ferramenta de execução mude.
- **Mudança de ferramenta (para Claude Desktop):** a ideia é reduzir a fricção operacional de despachar OS's formais para um agente externo (opencode) e trazer a execução para dentro de uma conversa direta. Isso não deve significar abandonar o rigor de teste-primeiro e DoD — só torna o ciclo mais rápido de rodar. Ver seção 7 sobre como adaptar o processo.

## 3. Arquitetura, resumida (detalhe completo em `ARQUITETURA.md`)

```
Upload PDF → Extractor (plugin) → TextProcessor → Speaker/TTS (plugin) → Storage → Player
```

Duas interfaces plugáveis centrais: `Extractor` (PyMuPDF nativo → Tesseract → PaddleOCR → cloud OCR como fallback, em ordem crescente de custo) e `Speaker` (Kokoro local como padrão, cloud como opção sob demanda). Nenhum outro módulo importa uma implementação concreta de plugin diretamente — sempre via `plugins/registry.py`.

## 4. Estado atual — o que já foi feito

- **OS-001 (bootstrap: estrutura de pastas + dependências):** tecnicamente concluída — smoke tests passando (6/6), README do código escrito, dependências instaladas. **Mas com pendências de processo ainda em aberto**, listadas na seção 5.
- **OS-002 (`core/models.py`):** definida, **ainda não despachada** — aguardando a OS-001 fechar de verdade primeiro.

### Duas lições já aprendidas nas primeiras OS's (não repetir)

1. **Checkbox de DoD precisa refletir a realidade, não a intenção.** Na primeira tentativa de relatório da OS-001, itens como "PR aberto" e "Red antes de Green" foram marcados como concluídos quando não estavam — a explicação em texto contradizia o checkbox. Todo relatório futuro deve ter checkbox e texto consistentes; se algo não foi cumprido, o checkbox fica desmarcado, sem exceção.
2. **Mudança de documentação de governança feita no repositório de arquitetura não se propaga sozinha para o repositório de código.** Isso já causou confusão (uma sincronização manual normal quase foi interpretada como "agente mexendo onde não devia"). Ver decisão #6 em `PROJECT_STATE.md`.

## 5. O que falta verificar AGORA (ordem de prioridade)

1. **Resolver a duplicata de arquivo em `docs/OS/`** — rodar `diff docs/OS/OS-001-core-models.md docs/OS/OS-002-core-models.md` e decidir: se for conteúdo idêntico com nome errado, apagar; se for diferente, investigar por quê existe.
2. **Commitar as mudanças de governança pendentes** — `docs/AGENTS.md`, `docs/README.md`, `docs/TEMPLATE.md` estão com alterações não commitadas no repositório de código (a separação `docs/report/` do relatório embutido, feita no repositório de arquitetura).
3. **Abrir o PR da OS-001** — ainda não foi aberto (`gh` não estava autenticado na última tentativa). Autenticar ou abrir manualmente pelo GitHub.
4. **Validar as versões travadas em `requirements.txt`** contra o PyPI real — foram aceitas porque o `pip install` rodou sem erro, mas nunca foram checadas uma a uma contra a documentação oficial de cada biblioteca (baixo risco, mas vale uma conferida rápida antes de considerar 100% estável).
5. **Só depois disso, despachar a OS-002.**

## 6. Decisões de arquitetura ainda em aberto (não resolver sozinho — decidir com o dono do projeto)

- Fila de jobs: Celery+Redis vs. algo mais simples (SQLite como fila).
- Banco de dados: SQLite no MVP, Postgres depois — confirmar se topa manter assim por mais tempo.
- Heurística de fallback de OCR (quando cair de Tesseract → PaddleOCR → cloud) — ainda precisa de uma OS de spike dedicada, nunca foi decidido.

(Lista completa e atualizada sempre em `PROJECT_STATE.md` seção 3 — este handoff resume, aquele arquivo é a fonte de verdade.)

## 7. Ordem de leitura recomendada a partir daqui

1. Este arquivo (`HANDOFF.md`) — contexto e intenção
2. `PROJECT_STATE.md` — estado componente a componente, log de decisões completo, backlog
3. `ARQUITETURA.md` — contratos técnicos (`Extractor`, `Speaker`), estrutura de pastas, modelos de dados, regras de custo
4. `AGENTS.md` — regras de trabalho (ainda valem, mesmo em conversa direta no Claude Desktop — ver nota abaixo)
5. `TDD.md` — metodologia de testes
6. `docs/os/` — Ordens de Serviço já definidas (`OS-001-bootstrap-setup.md`, `OS-001B-auditoria-relatorio.md`, `OS-002-core-models.md`)
7. `docs/report/` — relatórios já entregues

## 8. Nota sobre trabalhar via Claude Desktop em vez de OS's formais despachadas a um agente externo

O formato de "abrir uma OS escrita, despachar para um agente separado, receber relatório escrito" foi pensado para um fluxo onde execução e arquitetura são desacopladas no tempo. Trabalhando direto no Claude Desktop, esse ciclo pode virar conversa contínua — mas os princípios abaixo continuam valendo, só a formalidade do "arquivo indo e voltando" que pode relaxar:

- Testes antes da implementação continuam obrigatórios onde fizer sentido (ver exceção documentada para bootstrap de infra em `TDD.md`).
- Todo trabalho ainda deve ser rastreável a uma OS existente ou a uma nova OS criada antes de começar — não pular direto pra código sem escopo definido, mesmo que informalmente.
- DoD continua sendo checklist explícita conferida antes de considerar algo pronto — só não precisa necessariamente virar um arquivo `.md` separado se a conversa já documenta isso de forma auditável (mas se for gerar artefato de código real, ainda vale registrar em `docs/report/` para manter o histórico entre sessões).
- `PROJECT_STATE.md` continua sendo atualizado a cada entrega — é o que permite abrir uma conversa nova do zero e continuar de onde parou, exatamente como este `HANDOFF.md` está fazendo agora.
