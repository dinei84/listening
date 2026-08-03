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

## 6. Relatório (preenchido pelo agente ao final)

### 6.1 Resumo do que foi feito

[1-3 frases]

### 6.2 Checklist de DoD

Colar aqui a checklist da seção 4 acima e da checklist padrão de `AGENTS.md`, marcada.

### 6.3 Testes escritos

| Teste | Arquivo | Passou? |
|---|---|---|
| | | |

Confirmar: commit "Red" (testes falhando) existe antes do commit "Green"? [ ] Sim [ ] Não

### 6.4 Desvios do escopo original

[Se houve qualquer desvio do que foi definido na seção 2, explicar aqui. Se não houve, escrever "Nenhum".]

### 6.5 Dúvidas / bloqueios

[Qualquer decisão de arquitetura que não estava coberta pela OS e que o agente não tomou sozinho. Se nenhuma, escrever "Nenhuma".]

### 6.6 Link do PR

[URL do PR aberto]
