# OS-038 — "Ajudante LLM" para normalizar texto antes do TTS (opt-in)

> **DESBLOQUEADA em 2026-08-06.** A decisão de arquitetura pendente foi tomada pelo dono do projeto: **usar uma LLM barata via endpoint compatível com OpenAI**, com a chave que ele já possui. Custo medido por livro real do acervo (Programador Pragmático, 649k caracteres ≈ 216 mil tokens de entrada): **~US$ 0,16–0,87 por livro** — duas ordens de grandeza abaixo do TTS cloud do premium (US$ 8–107). Isso é o que torna o **nível médio** viável.
>
> **Provedor não é lock-in:** `TextNormalizer` é contrato de plugin, e a implementação mira o formato **compatível com OpenAI** (DeepSeek, Groq, Together, OpenRouter, OpenAI e outros expõem o mesmo shape) — trocar de provedor é mudar `base_url`, modelo e chave em `config.yaml`, sem código novo.

## 1. Objetivo

Normalizar o texto antes de mandá-lo ao TTS usando uma LLM barata: expandir números e abreviações por extenso (`R$ 50` → "cinquenta reais", `pág. 42` → "página quarenta e dois", `séc. XIX` → "século dezenove") e ajustar pontuação para pausas naturais. Proposta originada de sugestão externa (Etapa 3 do documento trazido pelo dono do projeto).

## 2. O que esta OS NÃO resolve, e o que ela custa (ler antes de aprovar)

**Não corrige o sotaque do português.** Isso foi medido: o problema é a **fonemização** (espeak-ng por regras, mapeando para um inventário de fonemas que não tem as vogais do português — "segurança" → `sˌeɡuɾˈɐ̃ŋsæ`), não o texto. Um texto perfeitamente pontuado produz exatamente o mesmo `æ`. Qualquer expectativa de que a LLM melhore o sotaque está errada.

**Custos e riscos a aceitar conscientemente:**

1. **Custo variável de API por livro.** Um livro grande (o "Arquitetura Limpa" tem 559 chunks; o "Security Engineering" teve 3334) significa uma chamada por chunk. Estimar e registrar o custo real medido num livro antes de liberar para uso geral. Isso contraria o padrão da decisão #2 ("TTS local como padrão, cloud sob demanda") — daí ser **opt-in**, nunca o caminho default.
2. **Latência.** Milhares de chamadas sequenciais somam tempo real à síntese, que já é o gargalo (OS-031: GPU saturada em ~89%).
3. **Risco de alteração de conteúdo — o mais sério.** Uma LLM reescrevendo o texto de um livro pode omitir, resumir ou inventar. Num audiobook isso é problema de **correção**, não de estilo: o ouvinte não tem como saber que ouviu algo diferente do que o autor escreveu. "Sem alterar o significado" é uma instrução no prompt, não uma garantia do modelo.

## 3. Escopo

**Dentro do escopo:**

- **Novo contrato de plugin `TextNormalizer`** (`plugins/normalizers/base.py`), seguindo a regra de ouro da `ARQUITETURA.md` seção 1 — "se envolve custo variável (API paga), é plugin". Registrar em `plugins/registry.py` (`NORMALIZERS`) e documentar em `ARQUITETURA.md` seção 4.
  - Implementação `NoOpNormalizer` (padrão, não faz nada, custo zero) e uma implementação com LLM.
  - Propriedade de custo estimado por caractere, no mesmo espírito de `Speaker.cost_per_char`.
- **Opt-in por livro**, não global: campo novo no upload (mesmo padrão do `language` da OS-025), persistido no `Book`. Sem escolha explícita, o caminho é o `NoOpNormalizer` e **nada muda**.
- **Guarda-corpo obrigatório contra alteração de conteúdo** — o ponto que torna esta OS aceitável:
  - comparar o texto original com o normalizado por uma métrica simples (ex: razão de tamanho, ou contagem de palavras);
  - se a diferença passar de um limiar (a definir e documentar), **descartar a saída da LLM e usar o texto original**, registrando em log;
  - nunca deixar a LLM "sumir" com um trecho silenciosamente.
- **Falha de rede/API não pode derrubar o livro**: degradar para o texto original, mesmo espírito do fallback de idioma do `KokoroSpeaker` (OS-020) e da leitura de TOC (OS-027).
- **Cache**: um mesmo chunk não deve ser reenviado à LLM numa retomada (OS-022) ou re-priorização (OS-032) — senão o custo se multiplica a cada interrupção. Onde guardar (tabela nova, ou junto do chunk) é decisão de implementação.
- **Provedor configurável por `config.yaml`**, não fixo no código: `base_url`, `model`, e a chave lida de **variável de ambiente** (nunca em arquivo versionado). Mirar o formato compatível com OpenAI (`POST {base_url}/chat/completions`), que a maioria dos provedores baratos expõe — isso é o que torna a troca de provedor gratuita.
- **Validação inicial obrigatória com o provedor real** (fora da suíte, como a OS-041 fez com TTS): rodar o normalizador em trechos reais de um livro do acervo e conferir três coisas no relatório — (a) `R$ 50` vira "cinquenta reais" e não "cinquenta dólares"; (b) nenhum conteúdo sumiu; (c) a saída **não** vem com comentário do modelo junto ("Aqui está o texto formatado:"), que é o modo de falha mais comum e passaria direto pelo guarda-corpo de tamanho.
- **Nenhuma chamada real à LLM na suíte de testes** — dublê sempre, conforme `AGENTS.md` seção 4 e `TDD.md`.

**Fora do escopo:**
- Escolher o provedor/modelo específico — decisão do dono, junto da aprovação de custo.
- Usar LLM para qualquer outra coisa (resumir, traduzir, gerar conteúdo).
- Corrigir sotaque/fonemas (ver seção 2).

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] Contrato `TextNormalizer` documentado em `ARQUITETURA.md` **antes** de implementar
- [ ] Livro enviado sem opt-in tem comportamento **byte a byte** idêntico ao de hoje (`NoOpNormalizer`), sem nenhuma chamada de rede
- [ ] Livro com opt-in tem o texto normalizado antes da síntese
- [ ] Saída da LLM que diverge demais do original é descartada em favor do texto original, com log
- [ ] Falha de rede/API degrada para o texto original, sem marcar o livro como `error`
- [ ] Um mesmo chunk não é reenviado à LLM ao retomar/re-priorizar
- [ ] Nenhuma chamada real a API paga na suíte de testes
- [ ] Custo real medido em um livro de verdade, registrado no relatório

## 5. Testes exigidos (mínimo)

- `test_noop_normalizer_returns_text_unchanged`
- `test_book_without_optin_never_calls_normalizer`
- `test_llm_normalizer_output_used_when_within_threshold`
- `test_llm_normalizer_output_discarded_when_diverges_too_much`
- `test_llm_normalizer_network_failure_falls_back_to_original_text`
- `test_normalized_chunk_is_not_resent_on_resume`

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-038-report.md`.*
