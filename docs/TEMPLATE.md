# OS-NNN — [título curto]

> Copiar este template para `docs/os/OS-NNN-slug-curto.md` ao abrir uma nova OS. Preencher as seções 1 a 5 antes de entregar ao agente. O agente preenche a seção 6 (Relatório) ao final.

## 1. Objetivo

Uma frase: o que esta OS entrega, e por quê.

## 2. Escopo

- Arquivos/módulos que devem ser criados ou alterados (listar explicitamente).
- O que está **fora** de escopo (declarar mesmo que pareça óbvio — evita PR inchado).

## 3. Contratos envolvidos

Referenciar a seção exata de `ARQUITETURA.md` que esta OS implementa ou depende (ex: "seção 4.1 — Extractor"). Se esta OS **cria** um contrato novo, ele deve ser proposto aqui e aprovado antes da execução — não durante.

## 4. Critérios de aceite (DoD específico desta OS)

Além da checklist padrão em `AGENTS.md` seção 4, esta OS precisa especificamente de:

- [ ] Critério específico 1 (ex: "PyMuPDFExtractor.supports() retorna False para PDF sem camada de texto")
- [ ] Critério específico 2
- [ ] Critério específico 3

## 5. Testes exigidos (mínimo)

Listar os casos de teste esperados, mesmo que em alto nível — o agente detalha na implementação:

- `test_...`
- `test_...`

## 6. Relatório

O relatório desta OS **não é escrito neste arquivo**. Ao concluir, criar `docs/report/OS-NNN-report.md` a partir de `docs/report/REPORT_TEMPLATE.md`. Este arquivo (a definição da OS) permanece estático como registro do que foi pedido; o relatório é o registro separado do que foi de fato entregue.
