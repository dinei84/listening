# Audiobook Pessoal

App que converte PDF em audiobook (estilo Audible), com pipeline plugável de extração de texto/OCR e TTS, otimizado para baixo custo.

## Setup

### 1. Criar ambiente virtual

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Instalar dependências

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

### 3. Instalar dependências de sistema

```bash
# Tesseract OCR (necessário para pytesseract)
sudo apt-get install tesseract-ocr

# espeak-ng (necessário para Kokoro fazer G2P/fonemização)
sudo apt-get install espeak-ng
```

### 4. Executar testes

```bash
pytest
```

## Estrutura

```
audiobook/
├── core/           Modelos de dados, pipeline, config
├── plugins/        Extractors (OCR) e Speakers (TTS) plugáveis
├── processing/     Limpeza, chunking, detecção de capítulos
├── api/            API FastAPI para upload e status de jobs
├── worker/         Fila de jobs assíncrona
├── storage/        Persistência de áudio e metadados
├── player/         Frontend web (React)
├── tests/          Testes unitários e de integração
├── config.yaml     Configuração (extractor, speaker)
└── README.md       Este arquivo
```

## Arquitetura

Ver `docs/ARQUITETURA.md` para contratos de interfaces e detalhes de design.