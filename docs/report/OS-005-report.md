# OS-005 — Relatorio de entrega

**Data:** 2026-08-03
**Branch:** `main`
**Commit(s) relevante(s):** N/A (OS bloqueada antes de qualquer implementacao)

## 1. Resumo do que foi feito

A OS foi iniciada seguindo a secao 2 (instalar/verificar Tesseract). O binario `tesseract` nao existe no ambiente e a instalacao via `sudo apt install -y tesseract-ocr` falhou por falta de permissao de `sudo` interativo. Pela regra explicita da OS-005 (secao 2), a execucao foi interrompida nesse ponto e nenhum numero foi estimado/inventado.

## 2. Checklist de DoD

### Checklist especifica da OS-005

- [ ] Relatorio explica, com fonte (doc oficial ou codigo-fonte lido), como o confidence score do Tesseract funciona
- [ ] Relatorio explica, com fonte, como funcionaria o confidence score do PaddleOCR (empirico se viavel, documental se nao)
- [ ] Ao menos 3 execucoes reais do Tesseract sobre fixtures de qualidade diferente, com numeros reais colados no relatorio (nao estimados)
- [ ] Recomendacao final tem um numero concreto de threshold, nao uma faixa vaga
- [ ] Recomendacao e registrada em `PROJECT_STATE.md` como proposta pendente de aprovacao
- [x] Nenhuma chamada a API paga (Cloud OCR) durante o spike
- [x] Se o binario do Tesseract nao puder ser instalado no ambiente, isso esta claramente registrado como bloqueio — nenhum numero foi inventado para compensar

## 3. Experimentos rodados

Nao foi possivel rodar experimentos de OCR real por bloqueio de infraestrutura (ausencia de `tesseract` + sem permissao de `sudo` interativo).

## 4. Saida de comandos relevantes (bruta)

### Comando: `tesseract --version 2>&1`

```text
/bin/bash: linha 1: tesseract: comando nao encontrado
```

### Comando: `sudo apt install -y tesseract-ocr 2>&1`

```text
sudo: a terminal is required to read the password; either use the -S option to read from standard input or configure an askpass helper
sudo: uma senha e necessaria
```

## 5. Desvios do escopo original

Nenhum desvio funcional. A interrupcao ocorreu exatamente conforme regra da OS-005 secao 2: sem permissao de `sudo`, parar e reportar bloqueio.

## 6. Duvidas / bloqueios

Bloqueio unico: sem `sudo` interativo no ambiente para instalar `tesseract-ocr`, impossibilitando gerar evidencia empirica real de confidence com Tesseract.

## 7. Link do PR

N/A nesta execucao (OS bloqueada antes de resultados tecnicos).
