# OS-020 — Detecção automática de idioma pro Kokoro

## 1. Objetivo

O `KokoroSpeaker` está fixo em inglês (`lang_code="a"`, voz `"af_heart"`) — testado em uso real com um PDF em português, o áudio saiu incompreensível (fonemas de inglês aplicados a texto em português). O Kokoro **já suporta português** (`lang_code="p"`, via `espeak-ng`, já instalado — ver `venv/lib/python3.12/site-packages/kokoro/pipeline.py`, `ALIASES`/`LANG_CODES`), assim como espanhol, francês, hindi, italiano, japonês e mandarim. Esta OS liga a detecção automática de idioma do texto extraído à seleção do idioma/voz certos do Kokoro.

## 2. Escopo

**Dentro do escopo:**
- Adicionar `langdetect` a `requirements.txt` (biblioteca leve, pura Python, sem framework de deep learning novo — versão real conferida no PyPI, mesma prática desde a OS-001).
- `plugins/speakers/kokoro_speaker.py`:
  - Detectar o idioma do texto recebido em `synthesize()` (por chunk, não por livro inteiro — o contrato do `Speaker`, `ARQUITETURA.md` seção 4.2, não muda; a detecção fica interna ao `KokoroSpeaker`, mesmo princípio já usado na OS-019 pra manter peculiaridades do Kokoro fora do `core/pipeline.py`).
  - Mapear o idioma detectado pro `lang_code` do Kokoro (`ALIASES` do próprio pacote: `en`→`a`, `pt`→`p`, `es`→`e`, `fr`→`f`, `hi`→`h`, `it`→`i`, `ja`→`j`, `zh`→`z`). Idioma detectado sem mapeamento conhecido → cair para `lang_code="a"` (inglês, comportamento atual) como padrão seguro, não erro.
  - Escolher uma voz padrão por idioma — **pesquisar/testar os nomes reais das vozes disponíveis pro Kokoro em cada idioma** (não estão listadas estaticamente no pacote, são baixadas por nome do Hugging Face Hub; verificar empiricamente, não advinhar), documentar no relatório quais nomes foram usados e como foram descobertos.
  - Como o `KPipeline` do Kokoro é construído com um `lang_code` fixo (não dá pra trocar depois de criado), o `KokoroSpeaker` passa a gerenciar **um pipeline por idioma** (cache lazy por `lang_code`, mesmo princípio do `_get_pipeline()` atual, só que agora é um dicionário em vez de uma instância só).
  - **Texto curto demais pra detectar com confiança** (chunks pequenos, ex: só um cabeçalho ou uma palavra) — `langdetect` é conhecidamente pouco confiável em strings curtas. Definir um comportamento explícito: usar um tamanho mínimo de texto abaixo do qual não confia na detecção e cai pro idioma padrão (ou, se fizer sentido, reaproveita o último idioma detectado com sucesso na mesma síntese — decisão de implementação, documentar a escolha e o porquê no relatório).
- Testes usam dublês fake — nenhuma chamada real ao Kokoro nem ao `langdetect` precisa necessariamente ser mockada (`langdetect` é rápido e local, sem download nem chamada de rede — diferente do `_get_pipeline()`, que continua exigindo mock total nos testes automatizados, mesma regra desde a OS-004/017).

**Fora de escopo:**
- Detecção de idioma em `core/pipeline.py` ou em qualquer lugar fora do `KokoroSpeaker` — fica encapsulado no plugin, como já é o padrão.
- Seleção manual de idioma pelo usuário (via UI/API) — a decisão foi por detecção automática; um override manual pode virar OS futura se a detecção automática se mostrar insuficiente na prática.
- Extractors/OCR em outros idiomas (Tesseract/EasyOCR já lidam com o texto como está, independente de idioma, dentro do que os engines de OCR já suportam nativamente) — esta OS é só sobre o TTS.
- Qualquer mudança em `processing/chunker.py` ou `core/pipeline.py`.

## 3. Contratos envolvidos

Nenhuma mudança no contrato `Speaker` (`ARQUITETURA.md` seção 4.2) — `synthesize(text, voice=None)` continua com a mesma assinatura. A detecção de idioma é um detalhe de implementação interno ao `KokoroSpeaker`, não um parâmetro novo no contrato.

## 4. Critérios de aceite (DoD específico desta OS)

- [ ] `langdetect` em `requirements.txt`, versão real conferida no PyPI
- [ ] `KokoroSpeaker.synthesize()` detecta o idioma do texto recebido e usa o `lang_code`/voz correspondentes do Kokoro
- [ ] Idioma detectado sem mapeamento conhecido cai pro inglês (`lang_code="a"`) como padrão, não erro
- [ ] Texto curto demais pra detecção confiável tem comportamento explícito e documentado (não é simplesmente ignorado)
- [ ] `KokoroSpeaker` gerencia um pipeline por idioma (cache lazy), não recria a cada chamada
- [ ] Nomes de voz por idioma verificados empiricamente (não advinhados), documentados no relatório
- [ ] Testes automatizados continuam sem construir um `easyocr.Reader`/`kokoro.KPipeline` real — mock total, mesma regra desde a OS-004
- [ ] Validação empírica no relatório: sintetizar um texto em português de verdade (não mockado) e confirmar que o `lang_code`/voz escolhidos batem com o esperado (mesmo padrão de evidência das OS-005/006/017/019)
- [ ] Nenhuma chamada de rede ou API paga dentro da suíte de testes automatizada

## 5. Testes exigidos (mínimo)

- `test_kokoro_speaker_detects_portuguese_and_uses_correct_lang_code`
- `test_kokoro_speaker_detects_english_and_uses_correct_lang_code`
- `test_kokoro_speaker_falls_back_to_english_for_unmapped_language`
- `test_kokoro_speaker_caches_pipeline_per_language`
- `test_kokoro_speaker_handles_short_text_without_crashing`

Local sugerido: `tests/unit/speakers/test_kokoro_speaker.py` (adicionar casos).

## 6. Relatório

*A preencher pelo agente ao concluir a OS, em `docs/report/OS-020-report.md` (template em `docs/report/REPORT_TEMPLATE.md`). Incluir a validação empírica com texto em português real e os nomes de voz descobertos por idioma.*
