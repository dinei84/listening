"""Spike de comparação de provedores de TTS cloud (OS-041) — medição fora do caminho de produção.

Compara a MESMA amostra de texto em português brasileiro entre o Kokoro (linha de base local,
sem custo) e os provedores cloud candidatos ao nível premium (decisão #23): Google Cloud TTS
(Chirp), Amazon Polly (neural), OpenAI TTS e ElevenLabs.

Requisitos da OS-041:
  - Chamadas a APIs pagas exigem credenciais do dono do projeto e aprovação de orçamento.
    O script NÃO entra em pytest e só faz chamada paga se a credencial estiver na variável de
    ambiente correspondente. Sem credencial, o provedor é registrado como "skip (sem credencial)".
  - As credenciais são lidas de variável de ambiente, nunca commitadas:
      GOOGLE_APPLICATION_CREDENTIALS (caminho do JSON de service account)
      GOOGLE_CLOUD_PROJECT
      AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY (+ região AWS_DEFAULT_REGION)
      OPENAI_API_KEY
      ELEVENLABS_API_KEY
      AZURE_SPEECH_KEY + AZURE_SPEECH_REGION (padrão brazilsouth)
        opcionais: AZURE_SPEECH_VOICE (padrão pt-BR-FranciscaNeural),
                   AZURE_SPEECH_STYLE (padrão calm)
  - Áudios salvos fora do repositório, em AUDIO_OUTPUT_DIR (padrão /tmp/os041-audio).

Executar:
    venv/bin/python scripts/spike_tts_cloud.py
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.request
import wave
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ---------------------------------------------------------------------------
# Amostra fixa (a mesma em todos os provedores e no Kokoro).
# Texto real extraído do "Arquitetura Limpa" (livro do acervo), com os casos
# difíceis embutidos de propósito (ver comentários abaixo).
# ---------------------------------------------------------------------------
SAMPLE_TEXT = """O software é formado por declarações if, declarações de atribuição e laços while, e assim permanece desde os anos 1960. Programamos em Java, C# e Ruby e usamos o design orientado a objetos, mas o código continua a ser apenas uma reunião de sequências, seleções e iterações.

Para documentar a arquitetura, os times desenham diagramas de classes em UML e definem contratos entre módulos usando a API interna do sistema. Em um contexto de microsserviços, um serviço que consome a API exposta por outro precisa respeitar os contratos de interface. Um exemplo comum de estrangeirismo no dia a dia: o desenvolvedor diz "vou subir o Docker" ao se referir ao contêiner que vai rodar o serviço.

A regra de ouro do arquiteto é priorizar as decisões que custam caro para mudar depois, mesmo que a implementação imediata custe apenas R$ 50 por mês em infraestrutura.

E a medida mais importante de todas é aquela que todo time precisa aprender a repetir todos os dias sem que ninguém precise lembrar cada detalhe de como ela deve ser executada e quando ela deve ser executada e quem é o responsável por executar a medida e o que fazer quando a medida falha porque esse é o momento em que a disciplina do time é realmente testada e a arquitetura que resiste é a que foi construída sobre princípios e não sobre acaso.

Uma arquitetura boa vem de compreendê-la mais como uma jornada do que como um destino, mais como um processo contínuo de investigação do que como um artefato congelado. Admitimos que operamos com conhecimento incompleto, mas também sabemos que, como seres humanos, operar com conhecimento incompleto é o que fazemos de melhor. As regras da arquitetura de software são princípios para ordenar e montar os blocos de construção de programas, e já que esses blocos são universais e não mudaram, as regras para ordená-los também são universais e imutáveis."""

# Os casos difíceis (critério de aceite da OS-041, comentados um a um):
#   - Sigla "UML": palavras só de maiúsculas costumam ser lidas letra a letra ou
#     com sotaque pelo espeak-ng.
#   - Sigla "API": idem; também muito presente em texto técnico.
#   - Estrangeirismo "design": G2P por regras tende a ler como "designe".
#   - Estrangeirismo "Docker": espeak-ng tende a ler com sons de vogal do português.
#   - Número/moeda "R$ 50": o sanitizador (OS-040) expande símbolos, mas a forma
#     como cada TTS lê o número importa para a comparação.
#   - Frase longa sem pontuação interna (o 4º parágrafo inteiro): estressa o
#     respirar e a divisão em segmentos de cada engine.

# ---------------------------------------------------------------------------
# Amostra curta de EXPRESSIVIDADE (2026-08-11). A amostra da OS-041 é prosa
# expositiva e não tem uma única interrogação ou exclamação — serve para medir
# pronúncia, não entonação. Esta cobre os dois, e é ~metade do tamanho para
# render mais execuções dentro da franquia gratuita da ElevenLabs.
#
# A original NÃO foi substituída: os números do relatório da OS-041 e as medições
# de Kokoro e Chatterbox foram feitos sobre ela, e trocá-la invalidaria a
# comparação já registrada. Escolha com OS041_SAMPLE=curta.
SAMPLE_TEXT_EXPRESSIVA = """Você já parou para pensar em quanto do seu código sobrevive ao próximo ano?

O software é formado por declarações if, atribuições e laços while, e assim permanece desde 1960. Programamos em Java, C# e Ruby, desenhamos diagramas em UML e consumimos a API interna do sistema. Mas será que isso mudou alguma coisa de verdade?

Que descoberta incrível! O arquiteto experiente já sabia: o que custa caro é mudar depois, mesmo quando a infraestrutura sai por R$ 50 por mês.

— E agora? — perguntou o estagiário, vendo o Docker subir pela primeira vez.

— Agora você espera — respondeu o líder técnico, sem levantar os olhos.

A regra que todo time precisa repetir todos os dias sem que ninguém precise lembrar cada detalhe de como ela deve ser executada e quando ela deve ser executada é sempre a mesma, e ela resiste porque foi construída sobre princípios e não sobre acaso.

Incrível, não é? O bom design é uma jornada, nunca um destino."""

# Casos de ENTONAÇÃO que a amostra da OS-041 não cobria:
#   - Interrogativa sim/não ("Você já parou...?") — a curva deve SUBIR no fim.
#   - Interrogativa longa ("Mas será que isso mudou alguma coisa de verdade?").
#   - Interrogativa curta e seca ("E agora?").
#   - Pergunta-eco ("Incrível, não é?") — sobe no "não é".
#   - Exclamação ("Que descoberta incrível!") — o caso que o Kokoro não entrega.
#   - Travessão de diálogo (—) com troca de turno entre duas falas.
#   - Dois-pontos anunciando continuação.
# Mantidos da amostra original: UML, API, design, Docker, C#, R$ 50, 1960 e a
# frase longa sem vírgula. Fim reconhecível: "nunca um destino".

SAMPLE_TEXT = (
    SAMPLE_TEXT_EXPRESSIVA
    if os.environ.get("OS041_SAMPLE", "").lower() in ("curta", "expressiva")
    else SAMPLE_TEXT
)


def _texto_de_pdf(caminho: str, capitulo: int | None) -> str:
    """Extrai o texto de um PDF real (opcionalmente de um capítulo só), já sanitizado como a síntese o receberia."""
    from core import pipeline
    from processing.sanitizer import sanitize_text

    capitulos = pipeline.extract_chapters(caminho)
    if capitulo is not None:
        capitulos = [capitulos[capitulo]]
    return sanitize_text("".join(c.text for c in capitulos))


# OS041_PDF aponta para um PDF do acervo e OS041_CAPITULO escolhe um capítulo
# (índice 0). Serve para medir o que interessa de verdade: um capítulo inteiro,
# não uma amostra de laboratório — inclusive o custo real da chamada.
_PDF = os.environ.get("OS041_PDF", "")
if _PDF:
    SAMPLE_TEXT = _texto_de_pdf(
        _PDF,
        int(os.environ["OS041_CAPITULO"]) if os.environ.get("OS041_CAPITULO") else None,
    )

# Dimensões reais do acervo (OS-041 seção 2), usadas para estimar custo por livro.
BOOKS_CHARS = {
    "Arquitetura Limpa": 533_371,
    "O Programador Pragmático": 648_877,
    "DDD Referência": 84_879,
}

# pf_dora e não af_heart: o "af" é American Female. Com lang_code="p" a
# fonemização sai correta em português, mas renderizada no timbre de uma voz
# inglesa — o sotaque que isso produz foi percebido de ouvido em 11/08/2026.
# O app usa VOICE_BY_LANG_CODE["p"] = "pf_dora", então a linha de base do spike
# precisa usar a mesma voz para representar o que o produto realmente entrega.
KOKORO_VOICE = os.environ.get("KOKORO_VOICE", "pf_dora")
SAMPLE_RATE = 24000

AUDIO_OUTPUT_DIR = Path(os.environ.get("AUDIO_OUTPUT_DIR", "/tmp/os041-audio"))
LATENCY_CALLS = int(os.environ.get("OS041_LATENCY_CALLS", "3"))

# Filtro opcional de provedores: OS041_ONLY=chatterbox roda só esse e pula os
# demais, inclusive o baseline Kokoro. Existe porque provedores locais podem
# exigir dependências incompatíveis entre si — o Chatterbox puxa torch 2.6 e o
# Kokoro do projeto roda em 2.13, então cada um vive no seu venv e o script é
# chamado uma vez por ambiente.
ONLY = {p.strip() for p in os.environ.get("OS041_ONLY", "").split(",") if p.strip()}


def _should_run(key: str) -> bool:
    """True quando o provedor deve rodar nesta execução (sem filtro, roda todos)."""
    return not ONLY or key in ONLY


# ---------------------------------------------------------------------------
# Registro dos provedores: limites de caracteres por requisição conforme a
# documentação oficial (levantado na seção de preços do relatório).
# ---------------------------------------------------------------------------
PROVIDERS = {
    "google": {
        "label": "Google Cloud TTS (Chirp 3: HD)",
        "env_var": "GOOGLE_APPLICATION_CREDENTIALS",
        "char_limit_per_request": 5000,  # limite por requisição documentado na API
        "char_limit_note": "5.000 caracteres por chamada text:synthesize (documentação da API; a confirmar na medição com credencial)",
        "pricing_source": "https://cloud.google.com/text-to-speech/pricing",
    },
    "polly": {
        "label": "Amazon Polly (neural)",
        "env_var": "AWS_ACCESS_KEY_ID",
        "char_limit_per_request": 3000,  # 3000 caracteres "cobráveis" (6000 totais, SSML excluído)
        "char_limit_note": "SynthesizeSpeech: até 3.000 caracteres cobráveis (6.000 totais) por chamada; StartSpeechSynthesisTask: até 100.000 cobráveis",
        "pricing_source": "https://aws.amazon.com/polly/pricing/",
    },
    "openai": {
        "label": "OpenAI TTS",
        "env_var": "OPENAI_API_KEY",
        "char_limit_per_request": 4096,
        "char_limit_note": "4.096 caracteres por chamada (API Reference)",
        "pricing_source": "https://platform.openai.com/docs/pricing",
    },
    "elevenlabs": {
        "label": "ElevenLabs (eleven_multilingual_v2)",
        "env_var": "ELEVENLABS_API_KEY",
        "char_limit_per_request": 5000,
        "char_limit_note": "5.000 caracteres por chamada (API Reference)",
        "pricing_source": "https://elevenlabs.io/pricing/",
    },
    # Azure entra depois dos demais (2026-08-07): é o único provedor com controle
    # de ESTILO DE FALA em pt-BR (<mstts:express-as>), que é a variável decisiva
    # para a entonação — o motivo pelo qual o nível premium existe. Duas entradas
    # de propósito: sem estilo e com estilo, para isolar quanto o estilo entrega.
    "azure": {
        "label": "Azure Neural (sem estilo)",
        "env_var": "AZURE_SPEECH_KEY",
        "char_limit_per_request": None,
        "char_limit_note": "limitado por tamanho do corpo SSML e por 10 min de áudio por chamada, não por contagem fixa de caracteres (a confirmar na medição)",
        "pricing_source": "https://azure.microsoft.com/en-us/pricing/details/cognitive-services/speech-services/",
    },
    "azure_style": {
        "label": "Azure Neural (com <mstts:express-as>)",
        "env_var": "AZURE_SPEECH_KEY",
        "char_limit_per_request": None,
        "char_limit_note": "idem 'azure'",
        "pricing_source": "https://azure.microsoft.com/en-us/pricing/details/cognitive-services/speech-services/",
    },
}

# Preço oficial por 1M de caracteres (moeda das fontes: USD), levantado em 2026-08-06.
# Conversão para BRL é deixada ao dono — câmbio muda, e o objetivo é comparar provedores,
# não fixar um câmbio no código.
PRICE_PER_MILLION_CHARS = {
    "Google Chirp 3: HD": {
        "usd": 30.00,
        "source": "https://cloud.google.com/text-to-speech/pricing",
        "date": "2026-08-06",
        "note": "US$0,00003/caractere; 1M de caracteres grátis/mês antes do cobrado",
    },
    "Google Neural2": {
        "usd": 16.00,
        "source": "https://cloud.google.com/text-to-speech/pricing",
        "date": "2026-08-06",
        "note": "vozes neuronais tradicionais, sem o salto de qualidade do Chirp 3",
    },
    "Amazon Polly neural": {
        "usd": 16.00,
        "source": "https://aws.amazon.com/polly/pricing/",
        "date": "2026-08-06",
        "note": "free tier: 1M caracteres/mês por 12 meses",
    },
    "Amazon Polly generative": {
        "usd": 30.00,
        "source": "https://aws.amazon.com/polly/pricing/",
        "date": "2026-08-06",
        "note": "vozes gerativas, o patamar mais alto da Polly em pt-BR",
    },
    "OpenAI tts-1": {
        "usd": 15.00,
        "source": "https://platform.openai.com/docs/pricing",
        "date": "2026-08-06",
        "note": "US$15/1M caracteres (preço por caractere)",
    },
    "OpenAI tts-1-hd": {
        "usd": 30.00,
        "source": "https://platform.openai.com/docs/pricing",
        "date": "2026-08-06",
        "note": "US$30/1M caracteres (preço por caractere)",
    },
    "OpenAI gpt-4o-mini-tts": {
        "usd": None,  # cobrada por token, não por caractere
        "source": "https://platform.openai.com/docs/pricing",
        "date": "2026-08-06",
        "note": "US$0,60/1M tokens de texto + US$12,00/1M tokens de áudio — não é diretamente comparável por caractere",
    },
    "ElevenLabs (multilingual v2)": {
        "usd": None,  # modelo de créditos, não dólar por caractere
        "source": "https://elevenlabs.io/pricing/",
        "date": "2026-08-06",
        "note": "1 caractere = 1 crédito; planos mensais: Starter $6/30k créditos, Creator $22/121k, Pro $99/600k (~US$165/1M no Pro)",
    },
    "Azure Neural": {
        "usd": 16.00,
        "source": "https://azure.microsoft.com/en-us/pricing/details/cognitive-services/speech-services/",
        "date": "2026-08-07",
        "note": "franquia de 0,5M caracteres/mês. ATENÇÃO: o Azure cobra a marcação SSML como caractere (exceto <speak> e <voice>) — ver SSML_BILLING_NOTE",
    },
    "Azure Neural HD": {
        "usd": 22.00,
        "source": "https://azure.microsoft.com/en-us/pricing/details/cognitive-services/speech-services/",
        "date": "2026-08-07",
        "note": "reduzido de US$30 para US$22/1M em março de 2026; tiers de commitment chegam a US$7,50/1M",
    },
}

# Achado que muda o desenho, não só o orçamento (levantado 2026-08-07): no Azure,
# toda marcação SSML no corpo da requisição é cobrada como caractere, exceto
# <speak> e <voice>. Medido sobre "Arquitetura Limpa" (533.371 chars, ~5.333 frases)
# a US$16/1M:
#     texto puro, estilo aplicado 1x no documento ... US$  8,53   (+0%)
#     + <break/> por frase ......................... US$ 10,33  (+21%)
#     + estilo por frase ........................... US$ 13,14  (+54%)
#     + break E estilo por frase ................... US$ 14,93  (+75%)
# Consequência prática: a pausa da OS-045, inserida no ÁUDIO depois da síntese,
# continua custando zero mesmo com motor pago — fazer a mesma pausa via <break/>
# custaria +21% no livro inteiro. Aplicar estilo uma vez por documento (ou por
# capítulo) em vez de por frase é a diferença entre US$8,53 e US$13,14.
SSML_BILLING_NOTE = (
    "https://learn.microsoft.com/en-us/azure/ai-services/speech-service/faq-tts"
)


def _b64(byte_data: bytes) -> str:
    return base64.b64encode(byte_data).decode("ascii")


def _write_wav(path: Path, raw_audio: bytes, sample_rate: int = SAMPLE_RATE) -> None:
    """Escreve bytes de áudio (PCM16 mono little-endian) como .wav."""
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(raw_audio)


def _latency_and_result(fn) -> tuple[bytes | None, float, str]:
    """Executa uma chamada de síntese medindo a latência; devolve (áudio, segundos, status)."""
    start = time.perf_counter()
    try:
        audio = fn()
    except Exception as exc:  # noqa: BLE001 — o spike registra e segue
        return None, time.perf_counter() - start, f"erro: {exc}"
    return audio, time.perf_counter() - start, "ok"


def _save(name: str, audio: bytes | None) -> None:
    """Grava o áudio do provedor como .wav, montando o contêiner só quando os bytes são PCM cru."""
    if audio is None:
        return
    AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    destino = AUDIO_OUTPUT_DIR / f"{name}.wav"
    # Provedores divergem no que devolvem: Kokoro, Chatterbox e Azure (formato
    # 'raw-') mandam PCM16 sem cabeçalho, enquanto ElevenLabs, OpenAI e Google
    # (LINEAR16) já devolvem um WAV completo. Envelopar um WAV em outro WAV gera
    # cabeçalho duplicado e arquivo corrompido, então a decisão é pelo conteúdo:
    # 'RIFF' nos primeiros bytes significa contêiner pronto, é só gravar.
    if audio[:4] == b"RIFF":
        destino.write_bytes(audio)
        return
    _write_wav(destino, audio)


# --------------------------- Kokoro (linha de base) -------------------------


def synthesize_kokoro(text: str) -> tuple[bytes | None, dict]:
    """Síntese local com Kokoro (baseline, custo zero). Devolve PCM16 como bytes."""
    import torch
    from kokoro import KPipeline

    pipeline = KPipeline(lang_code="p", repo_id="hexgrad/Kokoro-82M")
    segments = list(pipeline(text, voice=KOKORO_VOICE, speed=1.0))
    parts = [s.output.audio for s in segments if s.output is not None]
    if not parts:
        return None, {"error": "Kokoro gerou áudio vazio"}
    audio = torch.cat(parts, dim=-1)
    pcm16 = (audio.numpy().flatten() * 32767.0).astype("int16").tobytes()
    return pcm16, {"segments": len(parts)}


# ------------------------------ Google Cloud -------------------------------


def synthesize_google(text: str) -> tuple[bytes | None, str]:
    """Chamada ao endpoint REST do Cloud TTS com service account (ADC em GOOGLE_APPLICATION_CREDENTIALS)."""
    creds_path = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    with open(creds_path, encoding="utf-8") as f:
        creds = json.load(f)

    # Acesso via token OAuth com a própria service account (scope cloud-platform).
    import jwt

    now = int(time.time())
    signed = jwt.encode(
        {
            "iss": creds["client_email"],
            "scope": "https://www.googleapis.com/auth/cloud-platform",
            "aud": creds["token_uri"],
            "iat": now,
            "exp": now + 3600,
        },
        creds["private_key"],
        algorithm="RS256",
    )
    token_req = urllib.request.Request(
        creds["token_uri"],
        data=json.dumps(
            {
                "assertion": signed,
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            }
        ).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(token_req) as resp:
        token = json.loads(resp.read().decode())["access_token"]

    body = {
        "audioConfig": {"audioEncoding": "LINEAR16", "pitch": 0, "speakingRate": 1.0},
        "input": {"text": text},
        "voice": {"languageCode": "pt-BR", "name": "pt-BR-Chirp3-HD-Falcon"},
    }
    req = urllib.request.Request(
        "https://texttospeech.googleapis.com/v1/text:synthesize",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "x-goog-user-project": project,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        payload = json.loads(resp.read().decode())
    audio = base64.b64decode(payload["audioContent"])
    return audio, _b64(audio)[:64]


# ------------------------------ Amazon Polly -------------------------------


def synthesize_polly(text: str) -> tuple[bytes | None, str]:
    """Chamada ao endpoint REST do Polly via AWS Signature V4 (neural, pt-BR)."""
    import datetime as _dt
    import hashlib
    import hmac
    import xml.etree.ElementTree as ET

    access = os.environ["AWS_ACCESS_KEY_ID"]
    secret = os.environ["AWS_SECRET_ACCESS_KEY"]
    region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    service = "polly"
    host = f"polly.{region}.amazonaws.com"
    voice = "Camila"
    engine = "neural"
    text_type = "text"
    output_format = "pcm"

    now = _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    body = json.dumps(
        {
            "Engine": engine,
            "LanguageCode": "pt-BR",
            "OutputFormat": output_format,
            "Text": text,
            "TextType": text_type,
            "VoiceId": voice,
        }
    )

    def _sign(key, msg):
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    def _hex(data):
        return hashlib.sha256(data).hexdigest()

    canonical_uri = "/v1/speech"
    canonical_headers = (
        f"content-type:application/x-amz-json-1.0\nhost:{host}\n"
        f"x-amz-date:{amz_date}\n"
    )
    signed_headers = "content-type;host;x-amz-date"
    payload_hash = _hex(body.encode("utf-8"))
    canonical_request = f"POST\n{canonical_uri}\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
    scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = f"AWS4-HMAC-SHA256\n{amz_date}\n{scope}\n{_hex(canonical_request.encode('utf-8'))}"
    k_date = _sign(("AWS4" + secret).encode("utf-8"), date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, service)
    k_signing = _sign(k_service, "aws4_request")
    signature = hmac.new(
        k_signing, string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    authorization = (
        f"AWS4-HMAC-SHA256 Credential={access}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    req = urllib.request.Request(
        f"https://{host}/v1/speech",
        data=body.encode("utf-8"),
        headers={
            "Content-Type": "application/x-amz-json-1.0",
            "X-Amz-Date": amz_date,
            "Authorization": authorization,
        },
    )
    with urllib.request.urlopen(req) as resp:
        root = ET.fromstring(resp.read().decode())
    # <AudioStream> contém o PCM64 — Polly devolve base64 dentro do XML.
    stream_b64 = root.findtext(".//AudioStream", "").strip()
    audio = base64.b64decode(stream_b64)
    return audio, _b64(audio)[:64]


# -------------------------------- OpenAI -----------------------------------


# A gpt-4o-mini-tts aceita `instructions`: uma descrição em linguagem natural de
# COMO falar, separada do que falar. É o controle de estilo mais direto entre os
# provedores testados — nem SSML nem parâmetro numérico, e não altera o texto
# faturado do `input`. Para o nosso caso (entonação de ! e ?) é exatamente a
# alavanca que falta no Kokoro. Vazio = sem instrução, para medir a linha de base.
OPENAI_INSTRUCTIONS = os.environ.get(
    "OPENAI_INSTRUCTIONS",
    "Narre como um audiolivro em português do Brasil: ritmo pausado, dicção clara. "
    "Faça a entonação subir nas perguntas e dê ênfase real nas exclamações.",
)


def synthesize_openai(text: str) -> tuple[bytes | None, str]:
    """Chamada ao endpoint /v1/audio/speech da OpenAI; `instructions` controla o estilo de narração."""
    api_key = os.environ["OPENAI_API_KEY"]
    payload = {
        "model": os.environ.get("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
        "input": text,
        # A voz é configurável: as vozes variam bastante em como lidam com
        # português, e 'alloy' era só o padrão histórico do spike.
        "voice": os.environ.get("OPENAI_TTS_VOICE", "nova"),
        # wav volta com cabeçalho RIFF, que o _save reconhece e grava direto.
        "response_format": "wav",
    }
    if OPENAI_INSTRUCTIONS.strip():
        payload["instructions"] = OPENAI_INSTRUCTIONS
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/audio/speech",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        audio = resp.read()
    return audio, _b64(audio)[:64]


def _wav_frames(data: bytes) -> bytes:
    """Extrai o PCM de dentro de um WAV, descartando o cabeçalho — necessário para concatenar respostas."""
    import io

    with wave.open(io.BytesIO(data), "rb") as wf:
        return wf.readframes(wf.getnframes())


def synthesize_openai_longo(text: str) -> tuple[bytes | None, str]:
    """Sintetiza texto acima do limite de 4.096 chars da OpenAI, dividindo por frase e concatenando o PCM."""
    from processing.chunker import chunk_text

    limite = PROVIDERS["openai"]["char_limit_per_request"]
    if len(text) <= limite:
        return synthesize_openai(text)

    # Concatenar WAVs inteiros empilharia cabeçalhos no meio do áudio; o certo é
    # extrair o PCM de cada resposta e deixar o _save montar um contêiner só.
    partes = [_wav_frames(synthesize_openai(p)[0]) for p in chunk_text(text, limite)]
    return b"".join(partes), f"pedacos={len(partes)}"


# ------------------------------- ElevenLabs --------------------------------


def _elevenlabs_first_voice(api_key: str) -> str:
    """Devolve o voice_id da primeira voz disponível NA CONTA; o catálogo varia por conta e por plano."""
    req = urllib.request.Request(
        "https://api.elevenlabs.io/v1/voices", headers={"xi-api-key": api_key}
    )
    with urllib.request.urlopen(req) as resp:
        vozes = json.loads(resp.read().decode()).get("voices", [])
    if not vozes:
        raise RuntimeError(
            "a conta ElevenLabs não expõe nenhuma voz — verifique o plano"
        )
    return vozes[0]["voice_id"]


def synthesize_elevenlabs(text: str) -> tuple[bytes | None, str]:
    """Chamada ao endpoint /v1/text-to-speech da ElevenLabs (voz pt-BR)."""
    api_key = os.environ["ELEVENLABS_API_KEY"]
    # Sem ELEVENLABS_VOICE_ID, a voz é descoberta na conta. O padrão fixo anterior
    # era um voice_id do catálogo público, escrito quando ninguém tinha credencial
    # para testar: numa conta que não o enxerga, a API responde 404 — que parece
    # erro de endpoint, e não "essa voz não existe para você".
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID") or _elevenlabs_first_voice(api_key)
    body = json.dumps(
        {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
    ).encode()
    # output_format na QUERY, não no header Accept: a ElevenLabs ignora o Accept e
    # devolve MP3 por padrão. Como MP3 não começa com 'RIFF', o _save o tratava como
    # PCM cru e envelopava num cabeçalho WAV — o player lia dado comprimido como
    # amostra e saía estática, com duração falsa de 43s para um áudio de ~120s.
    # pcm_24000 casa com SAMPLE_RATE e com o Kokoro, mantendo a comparação justa.
    formato = os.environ.get("ELEVENLABS_OUTPUT_FORMAT", "pcm_24000")
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format={formato}",
        data=body,
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        audio = resp.read()
    return audio, _b64(audio)[:64]


# ------------------------------- Chatterbox ---------------------------------
# Provedor LOCAL, como o Kokoro: custo zero por livro, sem credencial e sem rede
# depois do download do modelo. Entra no spike (2026-08-07) porque é o único
# candidato que tem controle de emoção — o parâmetro `exaggeration` — sem cobrar
# por caractere. Se a qualidade em pt-BR se sustentar, cai a premissa de que
# expressividade exige motor pago, que é o que sustenta o nível premium hoje.
#
# Vive em venv separado: puxa torch 2.6, e o venv do projeto roda 2.13 — instalar
# junto rebaixaria o torch e quebraria o Kokoro. Daí o filtro OS041_ONLY.
#     python3 -m venv venv-chatterbox && venv-chatterbox/bin/pip install chatterbox-tts
#     OS041_ONLY=chatterbox venv-chatterbox/bin/python scripts/spike_tts_cloud.py


def _chatterbox_model():
    """Carrega o modelo multilíngue uma vez por processo (o download inicial é de alguns GB)."""
    global _CHATTERBOX_MODEL
    if _CHATTERBOX_MODEL is None:
        import torch
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS

        device = os.environ.get(
            "CHATTERBOX_DEVICE", "cuda" if torch.cuda.is_available() else "cpu"
        )
        _CHATTERBOX_MODEL = ChatterboxMultilingualTTS.from_pretrained(device=device)
    return _CHATTERBOX_MODEL


_CHATTERBOX_MODEL = None


# A amostra inteira (1.858 chars) numa chamada só estourou a VRAM de uma RTX 3060
# (11,6 GiB): "CUDA out of memory", medido em 2026-08-07. O Chatterbox é desenhado
# para enunciados curtos, e a memória de atenção cresce com o comprimento.
#
# Isso NÃO invalida o provedor: é o mesmo modo de falha que a OS-034 encontrou no
# Kokoro (truncamento em 510 fonemas), e o pipeline de produção já divide o texto
# antes de chamar o Speaker. Enviar 1.858 chars de uma vez é justamente o que
# produção nunca faz. Aqui o spike divide igual, para a medição ser representativa.
CHATTERBOX_MAX_CHARS = int(os.environ.get("CHATTERBOX_MAX_CHARS", "300"))


def synthesize_chatterbox(text: str, exaggeration: float = 0.5) -> tuple[bytes, str]:
    """Síntese local com Chatterbox Multilingual em pt; divide por sentença e concatena, devolvendo PCM16."""
    import torch

    from processing.chunker import chunk_text

    model = _chatterbox_model()
    partes = []
    for pedaco in chunk_text(text, max_chars=CHATTERBOX_MAX_CHARS):
        wav = model.generate(
            pedaco,
            language_id=os.environ.get("CHATTERBOX_LANGUAGE", "pt"),
            exaggeration=exaggeration,
            cfg_weight=float(os.environ.get("CHATTERBOX_CFG_WEIGHT", "0.5")),
        )
        partes.append(wav.detach().cpu().numpy().flatten())
        # A VRAM não é liberada sozinha entre gerações: sem isto, um livro inteiro
        # acumula até estourar mesmo com os pedaços pequenos.
        del wav
        torch.cuda.empty_cache()

    import numpy as np

    audio = np.concatenate(partes)
    pcm16 = (audio * 32767.0).astype("int16").tobytes()
    return pcm16, f"sr={model.sr} exaggeration={exaggeration} pedacos={len(partes)}"


def synthesize_chatterbox_expressive(text: str) -> tuple[bytes, str]:
    """Mesma síntese com o exagero emocional alto — é a variável que o spike quer isolar."""
    return synthesize_chatterbox(
        text, exaggeration=float(os.environ.get("CHATTERBOX_EXAGGERATION", "1.2"))
    )


def _run_chatterbox(results: dict[str, dict]) -> None:
    """Roda as duas variantes locais do Chatterbox (neutra e expressiva) e registra o resultado."""
    for key, fn, label in (
        ("chatterbox", synthesize_chatterbox, "Chatterbox Multilingual (neutro)"),
        (
            "chatterbox_expressive",
            synthesize_chatterbox_expressive,
            "Chatterbox Multilingual (exaggeration alto)",
        ),
    ):
        latencies: list[float] = []
        statuses: list[str] = []
        for i in range(LATENCY_CALLS):
            audio, elapsed, status = _latency_and_result(
                lambda fn=fn: fn(SAMPLE_TEXT)[0]
            )
            latencies.append(elapsed)
            statuses.append(status)
            if i == 0:
                _save(f"{key}_pt-BR", audio)
        results[key] = {
            "label": label,
            "credential_status": "local, sem custo",
            "audio_file": str(AUDIO_OUTPUT_DIR / f"{key}_pt-BR.wav"),
            "latency_seconds": latencies,
            "statuses": statuses,
            "char_limit_per_request": None,
        }
        print(json.dumps({key: results[key]}, indent=2, ensure_ascii=False))


# --------------------------------- Azure -----------------------------------


def _azure_ssml(text: str, voice: str, style: str | None) -> str:
    """Monta o corpo SSML da requisição, escapando o texto; style=None sai sem <mstts:express-as>."""
    corpo = xml_escape(text)
    if style:
        corpo = f"<mstts:express-as style='{style}'>{corpo}</mstts:express-as>"
    return (
        "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' "
        "xmlns:mstts='https://www.w3.org/2001/mstts' xml:lang='pt-BR'>"
        f"<voice name='{voice}'>{corpo}</voice></speak>"
    )


def synthesize_azure(text: str, style: str | None = None) -> tuple[bytes | None, str]:
    """Chamada ao endpoint REST de TTS do Azure (pt-BR); style aplica <mstts:express-as>."""
    key = os.environ["AZURE_SPEECH_KEY"]
    region = os.environ.get("AZURE_SPEECH_REGION", "brazilsouth")
    voice = os.environ.get("AZURE_SPEECH_VOICE", "pt-BR-FranciscaNeural")
    ssml = _azure_ssml(text, voice, style)
    req = urllib.request.Request(
        f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
        data=ssml.encode("utf-8"),
        headers={
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": "application/ssml+xml",
            # 'raw-' e não 'riff-': _write_wav monta o container WAV, então pedir
            # riff traria um cabeçalho próprio que sairia duplicado no arquivo.
            # 24 kHz casa com SAMPLE_RATE, o mesmo do Kokoro — comparação justa.
            "X-Microsoft-OutputFormat": "raw-24khz-16bit-mono-pcm",
            # Exigido pela API; sem ele a requisição volta 400.
            "User-Agent": "os041-spike-tts-cloud",
        },
    )
    with urllib.request.urlopen(req) as resp:
        audio = resp.read()
    return audio, _b64(audio)[:64]


def synthesize_azure_style(text: str) -> tuple[bytes | None, str]:
    """Mesma chamada, com o estilo de fala configurado — é a variável que o spike quer isolar."""
    return synthesize_azure(text, style=os.environ.get("AZURE_SPEECH_STYLE", "calm"))


def _env_available(*names: str) -> bool:
    return all(os.environ.get(n) for n in names)


def main() -> None:
    print("# spike_tts_cloud (OS-041)")
    print(f"sample_chars: {len(SAMPLE_TEXT)}")
    print(f"audio_output_dir: {AUDIO_OUTPUT_DIR}")
    print(f"latency_calls_per_provider: {LATENCY_CALLS}")
    print(
        "credenciais detectadas: "
        + ", ".join(
            p
            for p in ("google", "polly", "openai", "elevenlabs", "azure")
            if _env_available(PROVIDERS[p]["env_var"])
        )
        or "nenhuma"
    )

    # Prévia sem gastar: com OS041_DRY_RUN=1 o script mostra o que FARIA e sai.
    # Existe porque um capítulo inteiro num motor pago é a primeira chamada deste
    # spike com custo não-desprezível, e ver o valor antes é mais barato que depois.
    if os.environ.get("OS041_DRY_RUN"):
        chars = len(SAMPLE_TEXT)
        print("\n# DRY RUN — nenhuma chamada será feita")
        print(f"caracteres: {chars}")
        for chave in sorted(ONLY) or ["(todos)"]:
            print(f"provedor: {chave}")
        # US$0,015 por 933 chars, medido no painel da OpenAI em 11/08/2026.
        print(f"custo estimado OpenAI:  US$ {chars / 933 * 0.015:.2f}")
        print(f"custo estimado Azure:   US$ {chars / 1_000_000 * 16:.2f}")
        print(f"chamadas OpenAI (limite 4096 chars): {-(-chars // 4096)}")
        print("Kokoro e Chatterbox: sem custo")
        return

    results: dict[str, dict] = {}

    # Kokoro — linha de base local sem custo; só é pulado sob filtro explícito.
    if _should_run("kokoro"):
        _run_kokoro(results)
    if _should_run("chatterbox"):
        _run_chatterbox(results)

    _run_cloud_providers(results)
    _print_cost_table()


def _run_kokoro(results: dict[str, dict]) -> None:
    """Roda a linha de base local e registra latência, status e arquivo de áudio."""
    latencies: list[float] = []
    statuses: list[str] = []
    for i in range(LATENCY_CALLS):
        audio, elapsed, status = _latency_and_result(
            lambda: synthesize_kokoro(SAMPLE_TEXT)[0]
        )
        latencies.append(elapsed)
        statuses.append(status)
        if i == 0:
            _save(f"kokoro_pt-BR_{KOKORO_VOICE}", audio)
    results["kokoro"] = {
        "label": "Kokoro (baseline local)",
        "credential_status": "local, sem custo",
        "audio_file": str(AUDIO_OUTPUT_DIR / f"kokoro_pt-BR_{KOKORO_VOICE}.wav"),
        "latency_seconds": latencies,
        "statuses": statuses,
        "char_limit_per_request": None,
    }
    print(json.dumps({"kokoro": results["kokoro"]}, indent=2, ensure_ascii=False))


def _run_cloud_providers(results: dict[str, dict]) -> None:
    """Roda cada provedor cloud que tenha credencial e não esteja filtrado por OS041_ONLY."""

    for key in ("google", "polly", "openai", "elevenlabs", "azure", "azure_style"):
        if not _should_run(key):
            continue
        meta = PROVIDERS[key]
        fn = {
            "google": synthesize_google,
            "polly": synthesize_polly,
            "openai": synthesize_openai_longo,
            "elevenlabs": synthesize_elevenlabs,
            "azure": synthesize_azure,
            "azure_style": synthesize_azure_style,
        }[key]
        label = meta["label"]
        if not _env_available(meta["env_var"]):
            print(
                json.dumps(
                    {
                        key: {
                            "label": label,
                            "credential_status": f"skip — variável de ambiente {meta['env_var']} ausente",
                            "pricing_source": meta["pricing_source"],
                        }
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
            continue

        latencies = []
        statuses = []
        for i in range(LATENCY_CALLS):
            audio, elapsed, status = _latency_and_result(
                lambda fn=fn: fn(SAMPLE_TEXT)[0]
            )
            latencies.append(elapsed)
            statuses.append(status)
            if i == 0:
                _save(f"{key}_pt-BR", audio)
        results[key] = {
            "label": label,
            "credential_status": "ok",
            "audio_file": str(AUDIO_OUTPUT_DIR / f"{key}_pt-BR.wav"),
            "latency_seconds": latencies,
            "statuses": statuses,
            "char_limit_per_request": meta["char_limit_per_request"],
        }
        print(json.dumps({key: results[key]}, indent=2, ensure_ascii=False))


def _print_cost_table() -> None:
    """Imprime o custo estimado por livro do acervo, provedor a provedor."""
    print(
        "\n# custo estimado por livro (USD — preço oficial das fontes, levantado em 2026-08-06)"
    )
    for provider, per_m in PRICE_PER_MILLION_CHARS.items():
        if per_m["usd"] is None:
            continue
        print(
            f"\n{provider}: US$ {per_m['usd']:.2f} por 1M chars (fonte: {per_m['source']}, {per_m['date']})"
        )
        for book, chars in BOOKS_CHARS.items():
            cost = per_m["usd"] * chars / 1_000_000
            print(f"  {book}: US$ {cost:.2f}")


if __name__ == "__main__":
    main()
