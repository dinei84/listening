# AGENTS.md

Regras de trabalho para qualquer agente de IA que for executar uma Ordem de Serviço (OS) neste projeto. Leitura obrigatória antes de tocar em código.

> Estas regras valem independente da ferramenta de execução — opencode, Claude Desktop, ou qualquer outra. Ao trocar de ferramenta, ler `HANDOFF.md` primeiro para contexto de continuidade, depois este arquivo.

---

## 1. Papéis

- **Aqui (repositório de arquitetura/estratégia):** decisões de design, contratos de interface, backlog, OS's. Nenhum código de produção vive aqui.
- **Agente de execução:** recebe uma OS, implementa em um branch próprio, escreve testes primeiro (ver `TDD.md`), abre um PR pequeno, entrega um relatório de DoD.
- **Humano (dono do projeto):** aprova decisões de arquitetura, revisa e faz merge dos PRs, prioriza o backlog.

O agente de execução **não decide arquitetura**. Se a OS não cobrir um caso que aparece durante a implementação, o agente pausa, registra a dúvida no relatório da OS e não improvisa uma decisão de design nova.

## 2. Ciclo de vida de uma OS

1. OS é aberta a partir do backlog em `PROJECT_STATE.md`, usando o template em `docs/os/TEMPLATE.md`.
2. Agente cria um branch: `os/<numero>-<slug-curto>` (ex: `os/003-pymupdf-extractor`).
3. Agente escreve os testes primeiro (ver `TDD.md`) — comita os testes falhando antes de qualquer implementação.
4. Agente implementa o mínimo necessário para os testes passarem.
5. Agente roda a checklist de DoD (seção 4 deste arquivo, e a checklist específica da OS).
6. Agente cria o relatório de entrega em `docs/report/OS-NNN-report.md` (template em `docs/report/REPORT_TEMPLATE.md`). **O relatório nunca é escrito dentro do arquivo da OS** (`docs/os/OS-NNN-*.md`) — a definição da OS é instrução estável, o relatório é o resultado da execução, e os dois vivem em pastas separadas.
7. Agente abre PR curto, referenciando o número da OS.
8. Agente atualiza `PROJECT_STATE.md` (status do componente, decisões novas se houver).

## 3. Regras de escopo — o que faz um PR ficar "curto"

- Uma OS = uma responsabilidade. Não misturar "implementar extractor" com "ajustar pipeline" na mesma OS.
- Se durante a execução o agente perceber que a OS precisa tocar em mais de ~3 arquivos fora do escopo declarado, ele **para** e reporta isso no relatório em vez de expandir o PR.
- Nenhuma OS deve alterar um contrato de interface (`base.py` de um plugin) sem que isso esteja explicitamente no escopo da OS.
- PRs sem teste correspondente não cumprem DoD — não devem ser abertos como prontos para revisão.

## 4. Definition of Done (DoD) — checklist padrão

Toda OS herda esta checklist, além dos critérios específicos definidos na própria OS:

- [ ] Testes escritos antes da implementação (commit dos testes falhando existe no histórico do branch)
- [ ] Todos os testes da OS passam localmente
- [ ] Nenhum teste existente quebrou
- [ ] Código segue os contratos definidos em `ARQUITETURA.md` (interfaces, nomes, estrutura de pastas)
- [ ] Nenhuma chamada real a API paga (OCR cloud, TTS cloud) dentro dos testes — tudo mockado
- [ ] Type hints e docstring de uma linha em toda função pública
- [ ] `PROJECT_STATE.md` atualizado (status do componente + decisões novas, se houver)
- [ ] Relatório criado em `docs/report/OS-NNN-report.md` (nunca dentro do arquivo da própria OS)
- [ ] PR aberto contra o branch principal, com título no formato `[OS-NNN] descrição curta`

Uma OS só está "concluída" quando todos os itens acima estão marcados. Se algum item não se aplica, o relatório deve dizer explicitamente por quê — não deixar em branco.

## 5. Convenções de código

- Python: type hints obrigatórios, `black` para formatação, `ruff` para lint.
- Nomes de arquivos e classes seguem exatamente o que está em `ARQUITETURA.md` seção 3 e 4 — não inventar nomes alternativos.
- Commits pequenos e descritivos: `test: adiciona testes para PyMuPDFExtractor`, `feat: implementa PyMuPDFExtractor`.
- Nenhum plugin importa outro plugin diretamente — comunicação sempre via `core/pipeline.py` e `plugins/registry.py`. **Um plugin pode importar `core.models` e `processing`** (camadas puras, sem I/O nem estado); **não pode** importar `api` nem `worker`. `plugins` → `storage` é permitido **com ressalva** — ver decisão #24 em `PROJECT_STATE.md` antes de criar uma aresta nova dessas.

## 6. O que reportar quando algo trava

Se o agente encontrar ambiguidade, contrato faltando, ou dependência não resolvida:
1. Não decidir sozinho um novo padrão de arquitetura.
2. Registrar o impasse na seção "Dúvidas/Bloqueios" do relatório da OS.
3. Deixar o PR em rascunho (draft) até a decisão ser tomada no repositório de arquitetura.

## 7. Documentos de referência (ordem de leitura)

1. `PROJECT_STATE.md` — o que já existe, o que está pendente
2. `ARQUITETURA.md` — contratos, estrutura, regras de custo
3. `AGENTS.md` — este arquivo
4. `TDD.md` — como escrever os testes antes do código
5. `docs/os/TEMPLATE.md` — template da OS específica que o agente recebeu
6. `docs/report/REPORT_TEMPLATE.md` — template do relatório de entrega, preenchido ao final
