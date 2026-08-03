# REPORT_TEMPLATE.md

Molde para o relatório de entrega de uma OS. Ao concluir a OS-NNN, copiar este template para `docs/report/OS-NNN-report.md` (usar o mesmo sufixo de letra da OS quando houver, ex: `OS-001B-report.md`) e preencher.

Regra de nomenclatura: `docs/report/OS-NNN[letra]-report.md`, sempre com hífen antes de "report", nunca underscore — mantém consistência com o padrão já usado em `docs/os/`.

Uma OS pode gerar mais de um relatório ao longo do tempo (ex: uma tentativa que falhou e foi retomada). Nesse caso, não sobrescrever — versionar como `OS-NNN-report-v2.md`, mantendo o anterior como histórico. O relatório mais recente é sempre o que vale para a decisão de merge, mas o histórico de tentativas é auditável.

---

# OS-NNN — Relatório de entrega

**Data:**
**Branch:**
**Commit(s) relevante(s):**

## 1. Resumo do que foi feito

[1-3 frases]

## 2. Checklist de DoD

Colar aqui a checklist de `AGENTS.md` seção 4 (padrão) e a checklist específica da seção 4/5 da OS correspondente em `docs/os/`, cada item marcado `[x]` ou `[ ]`. Todo item não aplicável deve dizer explicitamente por quê — nunca deixar em branco.

## 3. Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| | | |

Confirmar: commit "Red" (testes falhando) existe antes do commit "Green" no histórico do branch? [ ] Sim [ ] Não — se "Não", explicar o motivo aqui.

## 4. Saída de comandos relevantes (quando a OS exigir)

[Colar saída bruta de comandos de verificação pedidos pela OS — instalação de dependências, execução de testes, etc. Sem resumir ou editar a saída.]

## 5. Desvios do escopo original

[Se houve qualquer desvio do que foi definido na seção 2 da OS, explicar aqui, incluindo o motivo. Se não houve, escrever "Nenhum".]

## 6. Dúvidas / bloqueios

[Qualquer decisão de arquitetura que não estava coberta pela OS e que o agente não tomou sozinho. Se nenhuma, escrever "Nenhuma".]

## 7. Link do PR

[URL do PR aberto. Se a OS for só de auditoria/leitura e não gerar PR, escrever "N/A — OS de leitura apenas".]
