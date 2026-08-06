# OS-041 — Spike: comparação de provedores de TTS cloud (voz em português)

> **Esta OS faz chamadas reais a APIs pagas — exceção deliberada, fora da suíte de testes.** O `AGENTS.md` seção 4 proíbe API paga **dentro dos testes**; um spike de comparação de provedores não tem como cumprir seu objetivo sem chamar os serviços de verdade. Requer do dono do projeto: **credenciais** dos provedores a comparar e **aprovação de um orçamento pequeno** (a amostra é de poucos milhares de caracteres, custo esperado na casa de centavos por provedor). Nenhuma chamada paga entra em `pytest`.

## 1. Objetivo

Escolher o motor de TTS do nível premium (decisão #23) com base em **evidência**, não em suposição: comparar qualidade de voz **em português brasileiro** e **preço atual real** de 2–3 provedores, sobre o mesmo trecho. Spike de medição e recomendação, sem código de produção — mesmo formato das OS-005 e OS-031.

## 2. Contexto

A decisão #23 estabeleceu que o salto de humanização do premium vem de trocar o `Speaker`, não de somar LLM ao Kokoro (que é um modelo pequeno, sem controle de emoção). A limitação atual está registrada em `PROJECT_STATE.md` seção 6: o Kokoro fonemiza português com **espeak-ng**, motor por regras, produzindo aproximações ("segurança" → `sˌeɡuɾˈɐ̃ŋsæ`, com um `æ` que não existe em português).

**Tamanho real do acervo, medido para dimensionar custo:**

| Livro | Caracteres | ~Áudio |
|---|---|---|
| Arquitetura Limpa | 533.371 | ~10h |
| O Programador Pragmático | 648.877 | ~11h |
| DDD Referência | 84.879 | ~1,5h |

Um livro técnico típico tem **500–650 mil caracteres**. Como TTS cloud cobra por caractere, essa é a unidade que define a viabilidade do plano.

## 3. Escopo

**Dentro do escopo:**

- **Escolher 2–3 provedores** para comparar. Candidatos naturais: Google Cloud TTS (vozes neurais/Chirp), Amazon Polly (neural), OpenAI TTS, ElevenLabs. O critério de entrada é ter **voz em pt-BR** — provedor sem português decente está fora antes de qualquer teste.
- **Levantar o preço atual de cada um**, por 1M de caracteres, **na documentação oficial no momento do spike** (não confiar em valor de memória — preço muda). Converter para "custo por livro" usando os números reais da seção 2.
- **Sintetizar a MESMA amostra** em todos: um trecho de ~1.500–3.000 caracteres de um livro real do acervo, em português, incluindo de propósito os casos difíceis já conhecidos — sigla (`UML`, `API`), estrangeirismo (`design`, `Docker`), número/moeda (`R$ 50`), e uma frase longa sem pontuação interna.
- **Comparar também com o Kokoro atual** — a linha de base. Sem isso não dá para saber se o ganho justifica o custo.
- **Salvar os áudios** para audição do dono do projeto (fora do repositório — são arquivos binários; indicar o caminho no relatório).
- **Medir latência por chamada** e verificar se há **limite de caracteres por requisição** em cada provedor (informação que a OS-043 precisa).
- **Recomendação explícita** ao final, com "nenhum vale o custo" como resultado aceitável.

**Fora do escopo:**
- Implementar o `Speaker` — é OS seguinte, depois desta decisão.
- Alterar qualquer arquivo de produção. O script do spike vai em `scripts/`, como o da OS-031.
- Contratar plano/assinatura — o spike usa crédito mínimo de teste.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] Preço por 1M de caracteres de cada provedor, **com data e link da fonte oficial**
- [ ] Custo estimado por livro real do acervo, provedor a provedor
- [ ] Mesma amostra sintetizada em todos os provedores **e** no Kokoro (linha de base)
- [ ] Os casos difíceis (sigla, estrangeirismo, moeda, frase longa) estão na amostra e comentados um a um
- [ ] Latência por chamada e limite de caracteres por requisição registrados
- [ ] Recomendação explícita, com "não vale o custo" aceito como resultado
- [ ] Nenhum arquivo de produção alterado; nenhuma chamada paga dentro de `pytest`
- [ ] Credenciais **não** commitadas — ler de variável de ambiente, e o relatório não pode conter chave

## 5. Testes exigidos

N/A por definição — spike, mesmo tratamento da OS-005 e da OS-031. O script de medição fica em `scripts/`, versionado e reproduzível, e **não** entra em `pytest.ini`.

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-041-report.md`.*
