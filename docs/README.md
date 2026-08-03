# Audiobook Pessoal — repositório de arquitetura

Este repositório é o "cérebro" do projeto: decisões de arquitetura, contratos, backlog e Ordens de Serviço (OS). A execução (código) acontece em PRs curtos abertos por agentes de IA a partir de cada OS.

## Ordem de leitura recomendada

0. **`HANDOFF.md`** — ponto de partida: intenção do projeto, estado atual, pendências imediatas. Leia isso primeiro sempre que retomar o projeto em uma ferramenta/conversa nova.
1. **`PROJECT_STATE.md`** — o que já existe, o que está pendente, decisões já tomadas.
2. **`ARQUITETURA.md`** — a arquitetura plugável: contratos de `Extractor` e `Speaker`, estrutura de pastas, modelos de dados, regras de custo.
3. **`AGENTS.md`** — como um agente de IA deve trabalhar: ciclo de uma OS, escopo, Definition of Done, convenções.
4. **`TDD.md`** — metodologia de testes: testes antes do código, o que nunca chamar de verdade em teste (APIs pagas), estrutura de `tests/`.
5. **`docs/os/`** — as Ordens de Serviço (definição/instrução, estática). `TEMPLATE.md` é o molde; `OS-001-bootstrap-setup.md` é a primeira OS real; `OS-002-core-models.md` é a segunda.
6. **`docs/report/`** — os relatórios de entrega (resultado da execução, um por OS). `REPORT_TEMPLATE.md` é o molde; nunca é escrito dentro do arquivo da OS.

## Fluxo de trabalho resumido

```
PROJECT_STATE.md (backlog) → nova OS criada a partir do TEMPLATE.md
    → agente cria branch → escreve testes (Red) → implementa (Green) → refatora
    → preenche relatório da OS com checklist de DoD
    → abre PR curto referenciando a OS
    → humano revisa e faz merge
    → PROJECT_STATE.md é atualizado
```

## Estrutura deste repositório

```
.
├── README.md                  # este arquivo
├── HANDOFF.md                 # ponto de partida — leia primeiro
├── PROJECT_STATE.md           # estado atual, decisões, backlog
├── ARQUITETURA.md             # contratos e estrutura técnica
├── AGENTS.md                  # regras de trabalho dos agentes
├── TDD.md                     # metodologia de testes
└── docs/
    └── os/
        ├── TEMPLATE.md                  # molde de nova OS
        ├── OS-001-bootstrap-setup.md    # estrutura de pastas + dependências
        ├── OS-001B-auditoria-relatorio.md   # OS de auditoria (leitura apenas)
        └── OS-002-core-models.md        # modelos de dados base
    └── report/
        ├── REPORT_TEMPLATE.md           # molde de relatório de entrega
        └── OS-001B-report.md            # relatório já entregue, arquivado
```

O código do produto em si (pipeline, plugins, API, player) vive em um repositório separado, criado a partir das OS's executadas aqui. Nesse repositório de código, a pasta de documentação deve seguir a mesma convenção em minúsculo: `docs/os/` e `docs/report/` — não `docs/OS/`.
