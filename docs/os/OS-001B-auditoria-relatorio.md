# OS-001B — Auditoria emergencial do estado atual (sem escrever código)

## 1. Objetivo

A execução anterior (OS-001) foi interrompida por uma falha de terminal e, ao ser retomada, avançou além do escopo definido (implementou lógica de plugins e modelos que pertencem a OS's futuras, sem testes, sem commits). Antes de continuar qualquer implementação, precisamos de um raio-x completo e fiel do estado atual do repositório para decidir, do lado da arquitetura, o que manter, revisar ou descartar.

Esta OS é **somente leitura**. Nenhuma decisão de manter/descartar deve ser tomada pelo agente — ele só coleta e relata.

## 2. Escopo

**Dentro do escopo:**
- Rodar exatamente os comandos listados na seção 4, na ordem.
- Colar a saída **bruta e completa** de cada comando no relatório (seção 6), sem resumir, sem truncar, sem editorializar o conteúdo.
- Classificar cada arquivo listado pelo `find` final como: `(a) dentro do escopo original da OS-001` (estrutura vazia/stub), `(b) fora do escopo — implementação adiantada`, ou `(c) documentação duplicada/possível lixo`. Essa classificação é factual (ex: "arquivo contém lógica além de `pass`/`NotImplementedError`" → categoria b), não uma opinião sobre o que fazer com o arquivo.

**Estritamente fora do escopo — proibido:**
- Criar, editar, apagar, mover ou renomear qualquer arquivo.
- Rodar `git add`, `git commit`, `git stash`, `git reset`, `git checkout` ou qualquer comando que altere o estado do repositório.
- Instalar ou desinstalar dependências.
- "Corrigir" ou "completar" qualquer coisa que pareça incompleta — isso será decidido depois, com base neste relatório.

Se o agente identificar algo que "parece precisar de correção urgente", ele deve apenas anotar isso na seção 6.5 do relatório (dúvidas/observações), nunca agir.

## 3. Contratos envolvidos

Nenhum. Esta OS não implementa nem altera nenhum contrato — é puramente diagnóstica.

## 4. Comandos a executar (nesta ordem, dentro da raiz do projeto)

```bash
# Estado do git
git status
git diff
git diff --staged
git log --oneline --all

# Ambiente
python --version
ls -la venv/ .venv/ 2>&1 | head -5

# Dependências declaradas
cat requirements.txt
cat requirements-dev.txt

# Interfaces (verificar se estão vazias como deveriam nesta fase)
cat plugins/extractors/base.py
cat plugins/speakers/base.py

# Conteúdo completo dos arquivos implementados além do escopo da OS-001
cat core/models.py
cat core/pipeline.py
cat core/config.py
cat plugins/extractors/pymupdf_extractor.py
cat plugins/extractors/tesseract_ocr.py
cat plugins/extractors/paddle_ocr.py
cat plugins/extractors/cloud_ocr_fallback.py
cat plugins/speakers/kokoro_speaker.py
cat plugins/speakers/piper_speaker.py
cat plugins/speakers/cloud_speaker.py
cat plugins/registry.py

# Config e infra esperados da OS-001
cat config.yaml
cat .gitignore
cat pytest.ini

# Testes existentes (a OS-001 exigia smoke test — checar se existe de fato)
find tests -type f -name "test_*.py"
find tests -type f

# Estado da documentação copiada para o repo de código
ls -la docs/ docs/OS/ 2>&1
diff docs/OS-001-core-models.md docs/OS/OS-002-core-models.md 2>&1

# Árvore completa do projeto
find . -not -path './.git/*' -not -path './venv/*' -not -path './.venv/*' -type f
```

## 5. Critérios de aceite (DoD específico desta OS)

- [ ] Nenhum arquivo do repositório foi criado, alterado ou removido durante esta OS (`git status` no início e no fim do relatório devem ser idênticos)
- [ ] Saída de todos os comandos da seção 4 está colada integralmente no relatório
- [ ] Cada arquivo do `find` final está classificado em (a), (b) ou (c), conforme seção 2
- [ ] Nenhuma opinião ou recomendação de ação foi incluída fora da seção 6.5 (observações)

## 6. Relatório

### 6.1 Resumo

[1-3 frases sobre o estado geral encontrado]

### 6.2 Saída bruta dos comandos

[Colar aqui, na ordem, a saída completa de cada comando da seção 4, identificando qual comando gerou qual bloco]

### 6.3 Classificação dos arquivos

| Arquivo | Classificação (a/b/c) | Observação factual |
|---|---|---|
| | | |

### 6.4 Checklist de DoD desta OS

[Marcar os itens da seção 5]

### 6.5 Observações / algo que pareceu precisar de correção (sem agir sobre isso)

[Listar aqui, sem tomar nenhuma ação]

### 6.6 Confirmação de não-alteração

`git status` no início:
```
[colar]
```

`git status` no final:
```
[colar]
```
