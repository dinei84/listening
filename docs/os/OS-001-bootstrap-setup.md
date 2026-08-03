# OS-001 — Bootstrap do repositório e instalação de dependências

## 1. Objetivo

Criar o esqueleto de pastas do projeto exatamente como definido em `ARQUITETURA.md` seção 3, configurar o ambiente Python, instalar e travar (pin) as dependências necessárias, e deixar um smoke test passando que confirma que o ambiente está funcional. Nenhuma lógica de negócio é implementada nesta OS — é infraestrutura pura.

## 2. Escopo

**Dentro do escopo:**

- Criar a estrutura de pastas completa de `ARQUITETURA.md` seção 3 (`core/`, `plugins/extractors/`, `plugins/speakers/`, `processing/`, `api/`, `worker/`, `storage/`, `player/`, `tests/`), cada módulo Python com um `__init__.py` vazio e, quando fizer sentido, um stub mínimo (ex: `base.py` das interfaces já pode ser criado aqui vazio com apenas o `class X(ABC): ...`, mas **sem métodos implementados** — a implementação dos contratos é de outra OS).
- Configurar ambiente virtual Python (`venv`), documentado no `README.md` do próprio código (não confundir com o `README.md` deste repositório de arquitetura).
- Criar `requirements.txt` (dependências de produção) e `requirements-dev.txt` (dependências de desenvolvimento/teste), com versões travadas.
- Criar `config.yaml` stub com as chaves mínimas: `extractor: pymupdf` e `speaker: kokoro` (valores padrão, ainda sem uso real).
- Criar `.gitignore` adequado a projeto Python (venv, `__pycache__`, arquivos de áudio gerados, `.env`).
- Criar `pytest.ini` ou seção `[tool.pytest.ini_options]` mínima.
- Instalar as dependências e confirmar que o ambiente sobe sem erro.
- Escrever um smoke test (`tests/test_environment.py`) que confirma que todas as bibliotecas-chave importam corretamente.

**Fora do escopo:**

- Qualquer implementação dos métodos de `Extractor` ou `Speaker` (isso é OS-003+).
- `core/models.py` (isso é a OS-002).
- Qualquer chamada real a Kokoro, Tesseract ou qualquer engine — nesta OS só precisamos confirmar que a biblioteca *importa*, não que ela processa um PDF/texto de verdade.
- CI/CD (pipeline de integração contínua) — fica para uma OS futura, se decidirmos que vale a pena para um projeto pessoal.

## 3. Contratos envolvidos

`ARQUITETURA.md` seção 3 (estrutura de pastas). Esta OS não cria nem altera contratos de interface — apenas monta o esqueleto onde eles vão morar.

## 4. Dependências a instalar

Travar versões específicas no `requirements.txt` (usar a versão estável mais recente disponível no momento da execução da OS — o agente deve confirmar a versão exata ao instalar, não usar as versões abaixo como número fixo cego).

**Produção (`requirements.txt`):**

| Biblioteca | Finalidade |
|---|---|
| `pydantic` | Modelos de dados |
| `pymupdf` | Extração de texto nativo de PDF |
| `pytesseract` | Wrapper Python para o Tesseract OCR (requer o binário `tesseract-ocr` instalado no sistema — documentar isso claramente no README do código, é uma dependência de SO, não do `pip`) |
| `kokoro` + `soundfile` | TTS local (Kokoro-82M). Requer o pacote de sistema `espeak-ng` instalado via gerenciador de pacotes do SO — documentar no README |
| `fastapi` | API |
| `uvicorn` | Servidor ASGI para rodar a API |
| `pyyaml` | Leitura do `config.yaml` |
| `python-dotenv` | Variáveis de ambiente (chaves de API cloud, quando existirem) |

**Desenvolvimento (`requirements-dev.txt`):**

| Biblioteca | Finalidade |
|---|---|
| `pytest` | Framework de testes |
| `pytest-mock` | Mock de dependências externas em teste |
| `black` | Formatação |
| `ruff` | Lint |

**Deixar de fora nesta OS (adicionar quando a OS correspondente chegar):** `paddleocr` (pesado, só entra quando a OS de fallback de OCR for aberta), qualquer SDK de TTS/OCR cloud (OpenAI, ElevenLabs, Document AI — só entram quando a OS do respectivo plugin cloud for aberta), `celery`/`redis` (dependem da decisão #3 em aberto no `PROJECT_STATE.md`).

Dependências de sistema (fora do `pip`, precisam estar documentadas explicitamente no README do código):
- `tesseract-ocr` (binário do SO, necessário para `pytesseract` funcionar)
- `espeak-ng` (binário do SO, necessário para o Kokoro fazer G2P/fonemização)

## 5. Critérios de aceite (DoD específico desta OS)

- [ ] Estrutura de pastas criada idêntica à seção 3 de `ARQUITETURA.md`
- [ ] `requirements.txt` e `requirements-dev.txt` existem, com versões travadas (`==`, não `>=`)
- [ ] `pip install -r requirements.txt -r requirements-dev.txt` roda sem erro em ambiente limpo
- [ ] `config.yaml` existe com as chaves mínimas (`extractor`, `speaker`)
- [ ] `.gitignore` cobre `venv/`, `__pycache__/`, `*.pyc`, arquivos de áudio gerados (`*.mp3`, `*.wav` fora de `tests/fixtures/`), `.env`
- [ ] Smoke test (`tests/test_environment.py`) passa, confirmando import de: `pydantic`, `fitz` (pymupdf), `pytesseract`, `kokoro`, `fastapi`
- [ ] README do código (não deste repositório) documenta: como criar o venv, como instalar dependências, como instalar `tesseract-ocr` e `espeak-ng` no SO, e como rodar `pytest`
- [ ] Nenhum stub de plugin contém lógica além de `class X(ABC): pass` ou levantar `NotImplementedError`

## 6. Testes exigidos (mínimo)

- `test_pydantic_is_importable`
- `test_pymupdf_is_importable`
- `test_pytesseract_is_importable`
- `test_kokoro_is_importable`
- `test_fastapi_is_importable`
- `test_config_yaml_loads_and_has_required_keys`

Esses testes não testam comportamento de negócio — testam que o ambiente está corretamente montado. É aceitável que esta OS fuja um pouco do ciclo Red→Green clássico (não há "comportamento" para falhar antes de existir código), mas os testes ainda devem existir e ficar no repositório como guarda de regressão do ambiente.

## 7. Relatório

*A preencher pelo agente ao concluir a OS, seguindo o formato de `docs/os/TEMPLATE.md` seção 6.*
