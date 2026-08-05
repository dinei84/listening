# Arquitetura — Audiobook Pessoal (PDF → Áudio)

Documento de referência para desenvolvimento assistido por agentes de IA. Define contratos, estrutura de pastas e regras de decisão. Qualquer agente que for implementar uma feature deve ler este documento antes de escrever código.

---

## 1. Princípio central: arquitetura plugável

Nenhuma etapa cara ou sujeita a troca (extração de texto, OCR, TTS) deve ser chamada diretamente. Toda etapa desse tipo é acessada através de uma **interface abstrata**, com implementações concretas registradas por nome em um **registry**, selecionadas por configuração (arquivo `config.yaml` ou variável de ambiente).

Regra de ouro: **se envolve custo variável (API paga) ou pode ser substituído por algo melhor no futuro, é plugin.** Se é lógica de negócio fixa (ex: montar nome de arquivo, calcular progresso do player), não é plugin — fica direto no core.

---

## 2. Visão geral do pipeline

```
Upload PDF → Extractor (plugin) → TextProcessor → Speaker/TTS (plugin) → Storage → Player
```

Orquestrado por uma fila de jobs assíncrona (etapas de extração e TTS podem demorar).

---

## 3. Estrutura de pastas proposta

```
audiobook/
├── core/
│   ├── models.py          # Book, Chapter, AudioSegment, Job (dataclasses/pydantic)
│   ├── pipeline.py        # orquestra as etapas, chama os plugins via registry
│   └── config.py          # carrega config.yaml, decide qual plugin usar
├── plugins/
│   ├── extractors/
│   │   ├── base.py        # classe abstrata Extractor
│   │   ├── pymupdf_extractor.py
│   │   ├── tesseract_ocr.py
│   │   ├── easyocr_extractor.py  # decisão #13 — substitui paddle_ocr.py do roadmap original
│   │   └── cloud_ocr_fallback.py
│   ├── speakers/
│   │   ├── base.py        # classe abstrata Speaker
│   │   ├── kokoro_speaker.py
│   │   ├── piper_speaker.py
│   │   └── cloud_speaker.py   # OpenAI TTS / ElevenLabs / etc
│   ├── queues/
│   │   ├── base.py        # classe abstrata JobQueue
│   │   ├── sqlite_queue.py    # SQLiteJobQueue — implementação padrão
│   │   └── redis_queue.py     # futuro, quando/se houver necessidade real de escalar
│   └── registry.py        # mapeia nome (string) → classe do plugin
├── processing/
│   ├── cleaner.py         # remove headers/footers, hifenização
│   ├── chunker.py         # divide texto em unidades de síntese
│   └── chapter_detector.py
├── api/
│   ├── main.py             # FastAPI app
│   ├── routes_books.py
│   └── routes_jobs.py
├── worker/
│   └── tasks.py            # loop de polling que consome a JobQueue configurada
├── storage/
│   ├── audio_store.py      # salvar/ler arquivos de áudio
│   └── db.py                # metadados (SQLite/Postgres)
├── player/                  # frontend web (HTML/CSS/JS puro, sem build step — decisão #12)
├── tests/
├── config.yaml
└── ARQUITETURA.md           # este arquivo
```

---

## 4. Contratos das interfaces (obrigatórios)

Todo plugin **deve** implementar a interface exatamente como definida abaixo. Agentes de IA não devem alterar a assinatura sem atualizar este documento primeiro.

### 4.1 Extractor

```python
# plugins/extractors/base.py
from abc import ABC, abstractmethod
from core.models import ExtractedPage

class Extractor(ABC):
    """Recebe um PDF (ou uma página) e devolve texto estruturado."""

    @abstractmethod
    def supports(self, pdf_path: str) -> bool:
        """Retorna True se este extractor consegue lidar com o arquivo/página.
        Ex: PyMuPDFExtractor retorna True só se a página tem camada de texto."""
        ...

    @abstractmethod
    def extract(self, pdf_path: str, page_range: tuple[int, int] | None = None) -> list[ExtractedPage]:
        """Extrai texto. Deve retornar confidence_score quando aplicável (OCR)."""
        ...
```

Regra de decisão do pipeline: tentar `PyMuPDFExtractor` primeiro (grátis, rápido). Se `supports()` retornar `False` ou a confiança vier baixa, cair para `TesseractOCR` → `EasyOCRExtractor` → `CloudOCRFallback`, nessa ordem de custo crescente.

**Heurística de "confiança baixa" (decisão #8/#9 em `PROJECT_STATE.md`, aprovada após spike da OS-005):** cair para o próximo extractor da cadeia quando `avg_confidence_words_normalized < 0.85` **ou** `words_counted == 0`. Preenchimento de `ExtractedPage.confidence` por extractor:

- **TesseractOCR:** coletar `conf` por palavra via `pytesseract.image_to_data()`, filtrar entradas com `text != ""` e `conf >= 0`, `confidence = mean(conf_filtrado) / 100.0`. Sem palavras válidas → `confidence = 0.0`.
- **EasyOCRExtractor:** coletar o `confidence` (0.0–1.0) de cada região de texto devolvida por `reader.readtext()`, `confidence = mean(confidences_da_página)`. Sem regiões reconhecidas → `confidence = 0.0`. (Decisão #13: substitui o PaddleOCR original do roadmap — mesma faixa 0.0–1.0 de confidence, então reaproveita o mesmo threshold `0.85` por analogia ao Tesseract, sem re-derivar; ver `PROJECT_STATE.md` decisão #13 para a ressalva.)

Evidência: `docs/report/OS-005-report.md`. Nota de limitação (registrada no spike, não invalida a decisão): as fixtures usadas cobriram bem os dois extremos (texto legível ~0.90-0.96 / falha total 0.0), mas não um caso de degradação intermediária — o valor `0.85` é uma margem de segurança abaixo do cluster de sucesso observado, não um ponto de corte fino validado empiricamente.

### 4.2 Speaker (TTS)

```python
# plugins/speakers/base.py
from abc import ABC, abstractmethod
from core.models import AudioChunk

class Speaker(ABC):
    """Recebe texto e devolve áudio sintetizado."""

    @abstractmethod
    def synthesize(
        self, text: str, voice: str | None = None, lang_code: str | None = None
    ) -> AudioChunk:
        ...

    @property
    @abstractmethod
    def cost_per_char(self) -> float:
        """0.0 para engines locais. Usado para estimar custo antes de rodar."""
        ...
```

`lang_code` foi adicionado na OS-025 como extensão aditiva do contrato (mesmo padrão das OS-021/022): força um idioma específico do engine, pulando a detecção automática; `None` preserva o comportamento anterior (para o `KokoroSpeaker`, detecção automática por chunk via `langdetect`, OS-020). O código é o do engine (`a`, `p`, `e`... no Kokoro), não o do `langdetect` — a tradução entre o que a API/UI expõe (`en`, `pt`, `es`...) e o código do engine fica a cargo de quem chama (`worker/tasks.py`, via `LANG_CODE_BY_LANGUAGE`).

Regra de decisão do pipeline: usar o Speaker definido em `config.yaml` como padrão (ex: `kokoro`). Só usar um Speaker cloud quando o usuário explicitamente pedir "voz premium" para aquele livro/capítulo.

### 4.3 JobQueue (fila de jobs)

Decisão #3/#11 (`PROJECT_STATE.md`): fila de jobs é plugin, pelo mesmo motivo que Extractor/Speaker são — "pode ser substituído por algo melhor no futuro" (`ARQUITETURA.md` seção 1). Hoje só existe uma implementação (`SQLiteJobQueue`), mas o contrato já existe para que trocar para Redis/Celery no futuro seja escrever uma nova classe + registrar, não reescrever `core/pipeline.py`, `api/` ou `worker/tasks.py`.

```python
# plugins/queues/base.py
from abc import ABC, abstractmethod
from core.models import Job

class JobQueue(ABC):
    """Enfileira e processa Jobs de forma assíncrona."""

    @abstractmethod
    def enqueue(self, job: Job) -> None:
        """Adiciona um Job à fila, status inicial 'queued'."""
        ...

    @abstractmethod
    def claim_next(self) -> Job | None:
        """Reivindica atomicamente o próximo Job 'queued', marcando como 'running'.
        None se a fila estiver vazia. Deve ser seguro para múltiplos workers
        chamando ao mesmo tempo — nenhum Job pode ser reivindicado duas vezes."""
        ...

    @abstractmethod
    def mark_done(self, job_id: str) -> None:
        """Marca um Job como concluído ('done')."""
        ...

    @abstractmethod
    def mark_failed(self, job_id: str, error_message: str) -> None:
        """Marca um Job como falho ('failed'), registrando a mensagem de erro."""
        ...

    @abstractmethod
    def get_job(self, job_id: str) -> Job | None:
        """Busca um Job pelo id. None se não existir."""
        ...

    @abstractmethod
    def requeue_orphaned(self) -> list[Job]:
        """Reseta para 'queued' todo Job preso em 'running' e devolve os Jobs resetados.
        Chamado na inicialização do worker: sem heartbeat/lease não há como distinguir
        um worker vivo de um que morreu no meio, então assume-se um único worker ativo
        por vez (decisão #11) e todo 'running' encontrado é tratado como órfão."""
        ...

    @abstractmethod
    def delete_jobs_for_book(self, book_id: str) -> None:
        """Remove todos os Jobs de um book_id. Nenhum efeito se não houver Jobs."""
        ...

    @abstractmethod
    def prioritize(self, job_id: str) -> None:
        """Dá ao Job uma prioridade maior que a de qualquer outro Job pendente (queued ou running)."""
        ...

    @abstractmethod
    def should_yield(self, job_id: str) -> bool:
        """Devolve True se existe um Job 'queued' com prioridade maior que a do Job informado."""
        ...

    @abstractmethod
    def requeue(self, job_id: str) -> None:
        """Devolve um Job individual para 'queued', preservando a prioridade."""
        ...

    @abstractmethod
    def get_job_for_book(self, book_id: str) -> Job | None:
        """Busca o Job de um book_id (o mais recente). None se o livro não tiver Job."""
        ...
```

Regra de decisão: `worker/tasks.py` só conhece `JobQueue` pela interface, resolvida via `registry`/`config` (mesma regra da seção 4.4) — nunca importa `SQLiteJobQueue` diretamente.

`requeue_orphaned()` foi adicionado na OS-022 como extensão aditiva do contrato original da OS-011 — nada foi removido ou alterado, mas toda implementação de `JobQueue` precisa passar a tê-lo. **Limitação conhecida e aceita:** o método assume um único worker ativo por vez. Com dois workers rodando ao mesmo tempo, o segundo a iniciar devolveria para a fila o Job que o primeiro está processando de verdade. Resolver isso exigiria heartbeat/lease por `Job` — fora do escopo de um projeto pessoal com um worker só (ver `docs/os/OS-022-retomar-processamento.md` seção 2).

`delete_jobs_for_book()` foi adicionado na OS-023 como extensão aditiva — usado pelo `DELETE /books/{id}` para limpar os `Job`s de um livro apagado. Mesmo padrão do `requeue_orphaned()`: nada existente muda de comportamento.

`prioritize()`, `should_yield()`, `requeue()` e `get_job_for_book()` foram adicionados na OS-032 (preempção de fila, "Processar agora"), mesma extensão aditiva. `claim_next()` ordena por `priority DESC, rowid` — sem prioridade definida (tudo `0`), o comportamento é idêntico ao FIFO original. A preempção é **cooperativa** (decisão #21): o worker pergunta `should_yield(job_id)` entre um chunk e outro e, se `True`, devolve o próprio `Job` para `queued` via `requeue()` (preservando a prioridade) e marca o `Book` como `paused` — nada é apagado, a retomada continua de onde parou via `skip_sequences` da OS-022. `get_job_for_book()` é usado pelo `POST /books/{id}/prioritize` para localizar o `Job` de um livro.

### 4.4 Registro de plugins

```python
# plugins/registry.py
EXTRACTORS = {
    "pymupdf": PyMuPDFExtractor,
    "tesseract": TesseractOCR,
    "easyocr": EasyOCRExtractor,
    "cloud_ocr": CloudOCRFallback,
}

SPEAKERS = {
    "kokoro": KokoroSpeaker,
    "piper": PiperSpeaker,
    "cloud_tts": CloudSpeaker,
}

QUEUES = {
    "sqlite": SQLiteJobQueue,
    "redis": RedisJobQueue,   # futuro, quando/se houver necessidade real de escalar
}
```

Nenhum outro módulo deve importar uma classe concreta de plugin diretamente — sempre passar pelo registry. Isso garante que trocar de engine (incluindo a fila) é uma mudança de config, não de código.

---

## 5. Modelos de dados (core/models.py)

```python
from pydantic import BaseModel
from datetime import datetime

class ExtractedPage(BaseModel):
    page_number: int
    text: str
    confidence: float = 1.0        # 1.0 para extração nativa
    source: str                    # nome do extractor usado

class Chapter(BaseModel):
    id: str
    title: str
    order: int
    text: str
    start_page: int = 1   # OS-027: intervalo de páginas (1-based, inclusivo)
    end_page: int = 1     # que o capítulo cobre no PDF

class AudioChunk(BaseModel):
    chapter_id: str
    sequence: int
    file_path: str
    duration_seconds: float
    engine_used: str

class Book(BaseModel):
    id: str
    title: str
    original_filename: str
    status: str                    # uploaded | extracting | processing | synthesizing | ready | error | paused
    chapters: list[Chapter] = []
    created_at: datetime
    error_message: str | None = None
    chunk_total: int | None = None  # total de chunks de síntese previsto (OS-024); None até a síntese começar
    language: str | None = None  # idioma forçado no upload (código tipo langdetect: en, pt, es...); None = detecção automática (OS-025)

class ReadingProgress(BaseModel):   # OS-028
    book_id: str
    sequence: int
    position_seconds: float
    updated_at: datetime

class Job(BaseModel):
    id: str
    book_id: str
    stage: str                     # extract | process | synthesize
    status: str                    # queued | running | done | failed
    error_message: str | None = None
    priority: int = 0              # maior número = atendido primeiro (OS-032)
```

---

## 6. Regras de custo e cache (não negociáveis)

1. **Nunca reprocessar** um livro cujo hash de conteúdo já existe no banco — checar antes de rodar qualquer plugin pago.
2. Extração local (PyMuPDF) sempre roda primeiro; OCR pago é o último recurso.
3. TTS local é o padrão; TTS cloud só é chamado com confirmação explícita do usuário para aquele conteúdo específico.
4. Todo `AudioChunk` gerado é persistido permanentemente — nunca gerar áudio "no fly" sem salvar.
5. Chunking deve ser por parágrafo/sentença, nunca por corte fixo de caracteres.

---

## 7. Convenções para os agentes de IA

- Nunca implementar uma nova engine de extração/TTS sem herdar da classe base correspondente.
- Toda função pública precisa de type hints e docstring de uma linha.
- Testes unitários obrigatórios para qualquer plugin novo — usar um PDF/texto de fixture, não chamar API paga em teste.
- Mudança de contrato de interface (`base.py`) exige atualizar a seção 4 deste documento no mesmo PR.
- Nenhum plugin deve conhecer detalhes do pipeline (orquestração) — comunicação é sempre via `core/pipeline.py`.

---

## 8. Roadmap de implementação (MVP → completo)

1. `core/models.py` + `PyMuPDFExtractor` + `KokoroSpeaker` + pipeline síncrono simples
2. API FastAPI com upload e status de job
3. Player web básico (play/pause, velocidade, retomar posição)
4. Fila assíncrona (Celery/RQ) + processamento em background
5. OCR (Tesseract → EasyOCR → cloud fallback) — decisão #13, substitui PaddleOCR do roadmap original
6. Opção de voz premium via TTS cloud
7. Detecção automática de capítulos
