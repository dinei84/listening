"""Testes da OS-058: manifest, mediaSession e CSS responsivo.

Esta OS não toca Python de produção — o que dá para travar aqui é o que o
servidor entrega ao navegador. A verificação de comportamento real (tela
bloqueada, largura de celular) está na seção 4 do relatório.
"""

import json

import pytest
from fastapi.testclient import TestClient

from api.main import app
from storage import audio_store as audio_store_module
from storage import db as db_module
from storage import progress_store as progress_store_module


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    for modulo in (db_module, audio_store_module, progress_store_module):
        monkeypatch.setattr(modulo, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(audio_store_module, "AUDIO_DIR", tmp_path / "audio")
    with TestClient(app) as cliente:
        yield cliente


# --------------------------------------------------------------------------
# Manifest: é o que torna o player instalável
# --------------------------------------------------------------------------


def test_manifest_is_served_and_valid_json(client):
    resposta = client.get("/manifest.webmanifest")
    assert resposta.status_code == 200
    json.loads(resposta.text)


@pytest.mark.parametrize(
    "campo", ["name", "short_name", "start_url", "display", "theme_color"]
)
def test_manifest_has_required_fields(client, campo):
    manifesto = json.loads(client.get("/manifest.webmanifest").text)
    assert manifesto.get(campo), f"manifest sem `{campo}`"


def test_manifest_display_is_standalone(client):
    """`standalone` é o que tira a barra do navegador: instalado, parece app."""
    manifesto = json.loads(client.get("/manifest.webmanifest").text)
    assert manifesto["display"] == "standalone"


def test_index_links_manifest_and_theme_color(client):
    html = client.get("/").text
    assert 'rel="manifest"' in html
    assert 'name="theme-color"' in html


# --------------------------------------------------------------------------
# mediaSession: controle de tela bloqueada
# --------------------------------------------------------------------------


def test_player_serves_nowplaying_module(client):
    resposta = client.get("/nowplaying.js")
    assert resposta.status_code == 200
    assert "function build" in resposta.text


def test_player_loads_nowplaying_before_app(client):
    """Procura a TAG, não o nome solto: um comentário acima dos scripts cita
    "app.js" e fazia este teste falhar com a ordem correta na tela."""
    html = client.get("/").text
    assert html.index('src="nowplaying.js"') < html.index('src="app.js"')


@pytest.mark.parametrize(
    "acao",
    [
        "play",
        "pause",
        "previoustrack",
        "nexttrack",
        "seekbackward",
        "seekforward",
        "seekto",
    ],
)
def test_app_registers_media_session_handler(client, acao):
    """Sem estes handlers, pausar exige desbloquear a tela e achar a aba — que é
    exatamente o que separa demo de produto num audiobook.

    Asserção deliberadamente frouxa: casar `setActionHandler("play"` fixaria a
    FORMA do código (uma chamada literal por ação) em vez do comportamento, e
    reprovaria um laço sobre a lista de ações, que é o código melhor. A prova de
    que as sete ficam mesmo registradas é a verificação em navegador, na seção 4
    do relatório — `app.js` publica `registeredMediaActions` para isso."""
    js = client.get("/app.js").text
    assert "setActionHandler" in js
    assert f'"{acao}"' in js


def test_app_reports_position_state(client):
    """`setPositionState` é o que faz a barra da tela bloqueada andar."""
    assert "setPositionState" in client.get("/app.js").text


def test_app_guards_missing_media_session(client):
    """mediaSession não existe em todo navegador; ausência não pode derrubar o player."""
    js = client.get("/app.js").text
    assert '"mediaSession" in navigator' in js


# --------------------------------------------------------------------------
# CSS: 88 linhas com zero @media era o estado antes desta OS
# --------------------------------------------------------------------------


def test_css_has_width_breakpoint(client):
    css = client.get("/style.css").text
    assert "@media" in css
    assert "width:" in css.split("@media", 1)[1]


def test_css_has_dark_mode_query(client):
    """Audiobook é ouvido à noite."""
    assert "prefers-color-scheme: dark" in client.get("/style.css").text


def test_css_declares_touch_target_minimum(client):
    """44px é o mínimo de alvo de toque; os botões estavam no tamanho default."""
    assert "44px" in client.get("/style.css").text


def test_css_pins_player_controls_on_narrow_screens(client):
    """No celular, o player fica depois de três seções: sem fixar os controles,
    pausar exige rolar a página inteira.

    Exige `fixed`, e NÃO aceita `sticky`: a primeira versão desta regra usava
    sticky e este teste passava, mas sticky só segura o elemento depois que a
    rolagem passa pela posição natural dele — medido no navegador a 375px, os
    controles ficavam em y=981 numa viewport de 836px com a página no topo.
    O teste passava e o critério de aceite não era cumprido."""
    css = client.get("/style.css").text
    assert "position: fixed" in css
    assert "position: sticky" not in css
