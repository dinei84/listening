"""OS-059 — divisão da estimativa de custo entre motor pago e motor local.

A estimativa já considera o roteamento desde a OS-056 (`core/pipeline.py`): cada
chunk é cobrado pelo motor que de fato vai sintetizá-lo. O que faltava é a
DIVISÃO — quanto é do pago, quanto é do local, quantos trechos de cada — que é o
que sustenta o número no banner de confirmação.
"""

import sqlite3

import pytest

from core import config as config_module
from core import pipeline
from storage import db
from tests.unit.test_routing import FakeConfig, FakeSpeaker
from plugins import registry as registry_module

# Chunk com 3 frases expressivas: no limiar 3, vai para o pago.
EXPRESSIVO = "Que beleza! Será mesmo? Não acredito! " * 30
# Prosa sem `!` nem `?`: fica no local.
NEUTRO = "A manhã seguia calma e o trabalho continuava no mesmo ritmo. " * 30


@pytest.fixture
def motores(monkeypatch):
    local = FakeSpeaker("local", custo=0.0)
    premium = FakeSpeaker("premium", custo=1.608e-05)
    monkeypatch.setattr(
        registry_module,
        "SPEAKERS",
        {"local": lambda: local, "premium": lambda: premium},
    )
    return local, premium


def _config(monkeypatch, **kwargs):
    cfg = FakeConfig(**kwargs)
    monkeypatch.setattr(config_module, "load_config", lambda: cfg)
    return cfg


# --------------------------------------------------------------------------
# O total não pode mudar: a trava da OS-042 e o teto max_cost_per_book usam ele
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "texto", [EXPRESSIVO, NEUTRO, EXPRESSIVO + NEUTRO, "", "Uma frase só."]
)
def test_breakdown_total_matches_estimate_cost(monkeypatch, motores, texto):
    """`estimate_cost` é o número que a trava de custo compara com o teto. Esta OS
    acrescenta a divisão; mudar o total seria mudar a decisão de gastar."""
    _config(monkeypatch, routing_enabled=True, routing_min_expressive=3)
    assert pipeline.estimate_breakdown(texto).total == pytest.approx(
        pipeline.estimate_cost(texto)
    )


def test_breakdown_total_matches_with_normalizer(monkeypatch, motores):
    _config(monkeypatch, routing_enabled=True, normalizer_cost_per_char=1.2e-06)
    assert pipeline.estimate_breakdown(
        EXPRESSIVO, normalize=True
    ).total == pytest.approx(pipeline.estimate_cost(EXPRESSIVO, normalize=True))


# --------------------------------------------------------------------------
# A divisão
# --------------------------------------------------------------------------


def test_breakdown_without_routing_puts_everything_on_configured_speaker(
    monkeypatch, motores
):
    """Roteamento desligado: nada vai para o pago, e a tela não pode sugerir que vai."""
    _config(monkeypatch, routing_enabled=False)
    divisao = pipeline.estimate_breakdown(EXPRESSIVO)
    assert divisao.premium_chunks == 0
    assert divisao.premium_cost == 0.0
    assert divisao.total_chunks > 0
    assert divisao.routing_enabled is False


def test_breakdown_with_routing_splits_by_threshold(monkeypatch, motores):
    """Só os chunks acima do limiar contam como pagos."""
    _config(monkeypatch, routing_enabled=True, routing_min_expressive=3)
    divisao = pipeline.estimate_breakdown(EXPRESSIVO + "\n\n" + NEUTRO)
    assert divisao.premium_chunks > 0
    assert divisao.premium_chunks < divisao.total_chunks
    assert divisao.premium_cost > 0
    assert divisao.routing_enabled is True


def test_breakdown_threshold_high_enough_routes_nothing(monkeypatch, motores):
    """Limiar acima do que qualquer chunk alcança: tudo no local, custo zero."""
    _config(monkeypatch, routing_enabled=True, routing_min_expressive=9999)
    divisao = pipeline.estimate_breakdown(EXPRESSIVO)
    assert divisao.premium_chunks == 0
    assert divisao.premium_cost == 0.0
    assert divisao.local_chunks == divisao.total_chunks


def test_breakdown_costs_add_up(monkeypatch, motores):
    """premium + local + normalizador tem de fechar o total, sem sobra nem falta."""
    _config(
        monkeypatch,
        routing_enabled=True,
        routing_min_expressive=3,
        normalizer_cost_per_char=1.2e-06,
    )
    d = pipeline.estimate_breakdown(EXPRESSIVO + "\n\n" + NEUTRO, normalize=True)
    assert d.premium_cost + d.local_cost + d.normalizer_cost == pytest.approx(d.total)


def test_breakdown_normalizer_cost_is_not_attributed_to_an_engine(
    monkeypatch, motores
):
    """O normalizador é um passe de LLM sobre o texto, não síntese: atribuí-lo a
    um dos motores faria a tela dizer que a voz local custa dinheiro."""
    _config(monkeypatch, routing_enabled=True, normalizer_cost_per_char=1.2e-06)
    sem = pipeline.estimate_breakdown(NEUTRO, normalize=False)
    com = pipeline.estimate_breakdown(NEUTRO, normalize=True)
    assert com.normalizer_cost > 0
    assert sem.normalizer_cost == 0.0
    assert com.premium_cost == sem.premium_cost
    assert com.local_cost == sem.local_cost


def test_breakdown_chunk_counts_add_up(monkeypatch, motores):
    _config(monkeypatch, routing_enabled=True, routing_min_expressive=3)
    d = pipeline.estimate_breakdown(EXPRESSIVO + "\n\n" + NEUTRO)
    assert d.premium_chunks + d.local_chunks == d.total_chunks


def test_breakdown_of_empty_text_is_all_zeros(monkeypatch, motores):
    _config(monkeypatch, routing_enabled=True)
    d = pipeline.estimate_breakdown("")
    assert d.total == 0.0
    assert d.total_chunks == 0
    assert d.premium_chunks == 0


def test_breakdown_is_additive_across_chapters(monkeypatch, motores):
    """O worker soma capítulo a capítulo; a divisão precisa somar do mesmo jeito."""
    _config(monkeypatch, routing_enabled=True, routing_min_expressive=3)
    a = pipeline.estimate_breakdown(EXPRESSIVO)
    b = pipeline.estimate_breakdown(NEUTRO)
    soma = a + b
    assert soma.total == pytest.approx(a.total + b.total)
    assert soma.premium_chunks == a.premium_chunks + b.premium_chunks
    assert soma.total_chunks == a.total_chunks + b.total_chunks
    assert soma.routing_enabled is True


# --------------------------------------------------------------------------
# Persistência (padrão de migração da OS-052)
# --------------------------------------------------------------------------


def test_db_migrates_breakdown_columns_on_existing_database(tmp_path):
    """Banco criado antes desta OS não pode quebrar nem ser apagado — foi o que
    aconteceu nas OS-018, OS-032 e OS-042 antes de a OS-052 criar o ensure_column."""
    db_path = str(tmp_path / "antigo.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE books (id TEXT PRIMARY KEY, title TEXT NOT NULL, "
        "original_filename TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL)"
    )
    conn.execute(
        "INSERT INTO books VALUES ('velho', 't', 'f.pdf', 'ready', '2026-01-01T00:00:00')"
    )
    conn.commit()
    conn.close()

    db.init_db(db_path)

    livro = db.get_book("velho", db_path)
    assert livro is not None
    assert livro.estimated_premium_cost is None
    assert livro.premium_chunk_count is None


def test_set_and_read_cost_breakdown(tmp_path):
    from datetime import UTC, datetime

    from core.models import Book

    db_path = str(tmp_path / "t.db")
    db.init_db(db_path)
    db.create_book(
        Book(
            id="livro",
            title="t",
            original_filename="f.pdf",
            status="uploaded",
            created_at=datetime.now(UTC),
        ),
        db_path,
    )

    db.set_book_cost_breakdown(
        "livro",
        premium_cost=0.85,
        premium_chunks=57,
        estimated_chunks=624,
        db_path=db_path,
    )

    livro = db.get_book("livro", db_path)
    assert livro.estimated_premium_cost == pytest.approx(0.85)
    assert livro.premium_chunk_count == 57
    assert livro.estimated_chunk_count == 624
