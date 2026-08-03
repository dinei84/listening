# TDD.md

Metodologia de testes obrigatória para toda OS. O objetivo é falhar rápido: um teste errado ou uma suposição errada deve aparecer antes de qualquer linha de implementação ser escrita, não depois.

---

## 1. Ciclo obrigatório: Red → Green → Refactor

1. **Red** — escrever o teste primeiro, para o comportamento que a OS pede. Rodar e confirmar que falha (e falha pelo motivo certo — código ainda não existe, não por erro de sintaxe no teste).
2. **Green** — escrever o mínimo de código necessário para o teste passar. Nada além do que o teste exige.
3. **Refactor** — limpar o código mantendo os testes verdes. Só depois disso o PR é considerado pronto.

O commit do teste falhando (`Red`) deve existir no histórico do branch, separado do commit de implementação. Isso é auditável e faz parte do DoD.

## 2. Estrutura de testes

```
tests/
├── unit/
│   ├── extractors/
│   │   ├── test_pymupdf_extractor.py
│   │   └── test_tesseract_ocr.py
│   ├── speakers/
│   │   └── test_kokoro_speaker.py
│   └── processing/
│       ├── test_cleaner.py
│       └── test_chunker.py
├── integration/
│   └── test_pipeline_end_to_end.py
└── fixtures/
    ├── pdfs/
    │   ├── native_text_sample.pdf
    │   └── scanned_sample.pdf
    └── texts/
        └── messy_extracted_text.txt
```

- `unit/`: testa um plugin ou módulo isolado, com dependências externas mockadas.
- `integration/`: testa o pipeline completo com plugins "fake"/locais (nunca chamando API paga).
- `fixtures/`: arquivos de exemplo pequenos e versionados no repositório — nunca baixar arquivo externo durante o teste.

## 3. Regra inegociável: nenhuma chamada real a serviço pago em teste

- OCR cloud (Document AI, Textract) e TTS cloud (OpenAI, ElevenLabs) **nunca** são chamados de dentro de um teste automatizado.
- Todo plugin que fala com uma API externa paga precisa de uma versão fake/mock que implementa a mesma interface (`base.py`), usada exclusivamente em testes.
- Testes de engines locais (Kokoro, Piper, PyMuPDF, Tesseract) podem rodar de verdade, desde que sejam rápidos (< alguns segundos) — não precisam de mock, pois não têm custo variável.

## 4. O que testar em cada camada

**Extractors:**
- `supports()` retorna o valor correto para PDF nativo vs PDF escaneado (usar fixtures de ambos).
- `extract()` retorna texto não vazio, com `confidence` dentro do range esperado.
- Caso de erro: PDF corrompido não deve derrubar o processo, deve retornar erro tratado.

**Speakers:**
- `synthesize()` retorna um `AudioChunk` com `duration_seconds > 0`.
- `cost_per_char` está correto para o plugin (0.0 para local).
- Texto vazio não deve gerar chamada ao engine — deve ser validado antes.

**Processing (cleaner/chunker):**
- Cleaner remove headers/footers repetidos em um texto de fixture conhecido — assert no resultado exato.
- Chunker nunca corta uma sentença no meio — testar com texto de tamanho conhecido e verificar os limites dos chunks.

**Pipeline (integração):**
- Rodar um PDF pequeno de fixture do início ao fim usando plugins locais/fake, e verificar que um `Book` com status `ready` e pelo menos um `AudioChunk` é produzido.

## 5. Cobertura mínima esperada

- Todo plugin novo (`Extractor` ou `Speaker`) precisa de teste antes de ser aceito — sem exceção, faz parte do DoD.
- Módulos de `core/` e `processing/` precisam de cobertura de casos de borda (texto vazio, PDF de uma página só, capítulo sem título).
- Não é necessário perseguir 100% de cobertura — o critério é "todo comportamento descrito na OS tem um teste que falha se o comportamento quebrar".

## 6. Convenção de nomeação de testes

`test_<comportamento_esperado>_<condicao>`, por exemplo:
`test_extract_returns_empty_confidence_when_page_has_no_text`

Evitar nomes genéricos como `test_extractor_1`.

## 7. Relação com o relatório da OS

O relatório de cada OS (ver `docs/os/TEMPLATE.md`) deve listar os testes escritos e confirmar que o commit "Red" existe antes do commit "Green" no histórico do branch. Isso é parte do critério de aceite, não um detalhe opcional.
