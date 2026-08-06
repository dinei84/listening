import re

# Mapa de símbolo -> palavra em português (OS-040). Sem isso, o espeak recorre ao
# nome do símbolo em inglês dentro de texto em português (medido: '≠' -> "not equal to").
SYMBOL_TO_WORD = {
    "≠": "diferente de",
    "±": "mais ou menos",
    "≈": "aproximadamente",
    "≤": "menor ou igual a",
    "≥": "maior ou igual a",
    "×": "vezes",
    "÷": "dividido por",
    "→": "leva a",
    "←": "de volta a",
    "°": "graus",
    "%": "por cento",
    "§": "parágrafo",
    "&": "e",
}

_SYMBOL_RE = re.compile("|".join(re.escape(s) for s in SYMBOL_TO_WORD))

# Moeda é tratada à parte dos demais símbolos por duas razões, ambas encontradas na
# revisão da OS-040: `R$` é **real**, não dólar (mapear `$` sozinho gerava
# "Rdólares 50" em texto brasileiro), e em português a moeda vem **depois** do
# número ("cinquenta reais", não "reais cinquenta"). Ordem importa: `R$` antes de `$`.
CURRENCY_TO_WORD = [
    ("R$", "reais"),
    ("US$", "dólares"),
    ("$", "dólares"),
    ("€", "euros"),
    ("£", "libras"),
]

_CURRENCY_RE = re.compile(
    "(?:"
    + "|".join(re.escape(simbolo) for simbolo, _ in CURRENCY_TO_WORD)
    # O valor precisa TERMINAR em dígito: sem isso, "R$ 1.200,00." levava o ponto
    # final junto e a frase virava "1.200,00. reais".
    + r")\s*(\d[\d.,]*\d|\d)"
)

# Ênfase/negrito/código inline: remove o marcador, preserva o conteúdo. Exige
# abertura E fechamento — um * solto no meio de prosa não casa (falso positivo).
_EMPHASIS_RE = re.compile(r"\*\*(.+?)\*\*|\*([^\s*][^*]*?)\*|`([^`]+?)`")

# Marcadores de linha: títulos (#), citações (>) e itens de lista com bullet (- * +).
# O travessão de diálogo em português (—, U+2014) NÃO está aqui e sobrevive.
# Item NUMERADO ficou de fora deste regex de propósito — ver _NUMBERED_ITEM_RE.
_LINE_MARKER_RE = re.compile(r"(?m)^(?:#{1,6}\s*|>\s?|[-*+]\s+)")

# Item de lista numerada. Removê-lo em qualquer linha que comece com número comia
# frases legítimas ("42. Esse é o número da resposta." virava "Esse é o número...")
# — perda silenciosa de conteúdo encontrada na revisão da OS-040. Por isso o
# marcador só é removido quando a linha faz parte de uma sequência de **pelo menos
# dois** itens numerados consecutivos, que é o que caracteriza uma lista de verdade.
_NUMBERED_ITEM_RE = re.compile(r"^(\d{1,3}[.)])\s+(?=\S)")

# Linha de separador de tabela (ex: |---|---|): composta só de |, -, : e espaços.
# Uma linha de dados de tabela começa e termina com |.
_TABLE_SEPARATOR_CHARS = "|-: "

_URL_RE = re.compile(r"https?://[^\s<>'\"]+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# Pontuação de fim de frase que pode virar parte do match da URL; é devolvida
# ao texto ("Veja https://x.com." -> "Veja link."), não engolida.
_URL_TRAILING_PUNCT = ".,;:!?"

# Cerca de bloco de código: ``` ou ~~~ (com ou sem tag de idioma na abertura).
_FENCE_RE = re.compile(r"^(`{3,}|~{3,})\s*\w*$")


def sanitize_text(text: str) -> str:
    """Remove markup, símbolos, tabelas, URLs/e-mails e blocos de código que não se narram, preservando a prosa; aplicado antes do chunking (OS-040)."""
    text = _handle_code_blocks(text)
    text = _replace_urls_and_emails(text)
    text = _strip_markup(text)
    text = _handle_table_rows(text)
    text = _map_symbols(text)
    return text


def _handle_code_blocks(text: str) -> str:
    """Substitui blocos de código cercados (``` ou ~~~) por um anúncio legível, nunca narrando o conteúdo símbolo a símbolo."""
    lines = text.split("\n")
    result: list[str] = []
    in_code = False
    fence_char = ""
    for line in lines:
        match = _FENCE_RE.match(line.strip())
        if match is not None and len(match.group(1)) >= 3:
            if in_code and match.group(1)[0] == fence_char:
                in_code = False
                fence_char = ""
                result.append("trecho de código omitido")
            elif not in_code:
                in_code = True
                fence_char = match.group(1)[0]
            continue
        if not in_code:
            result.append(line)
    if in_code:
        result.append("trecho de código omitido")
    return "\n".join(result)


def _replace_urls_and_emails(text: str) -> str:
    """Troca URLs por 'link' e e-mails por 'endereço de e-mail', em vez de soletrar."""

    def _url_repl(match: re.Match) -> str:
        url = match.group(0)
        trailing = ""
        while url and url[-1] in _URL_TRAILING_PUNCT:
            trailing = url[-1] + trailing
            url = url[:-1]
        return "link" + trailing

    text = _URL_RE.sub(_url_repl, text)
    text = _EMAIL_RE.sub("endereço de e-mail", text)
    return text


def _strip_markup(text: str) -> str:
    """Remove marcadores de ênfase, código inline, títulos, citações e itens de lista."""
    text = _EMPHASIS_RE.sub(
        lambda match: next(group for group in match.groups() if group is not None),
        text,
    )
    # Os numerados são tratados ANTES dos bullets: a decisão depende de enxergar as
    # linhas vizinhas ainda com seus marcadores (um "1." colado num "- item" é
    # lista; sozinho no meio da prosa, é frase começando com número).
    text = _strip_numbered_list_markers(text)
    return _LINE_MARKER_RE.sub("", text)


def _strip_numbered_list_markers(text: str) -> str:
    """Remove o marcador de itens numerados apenas onde há lista de verdade (vizinho é outro item de lista), preservando frase que só começa com número."""
    lines = text.split("\n")
    numerada = [_NUMBERED_ITEM_RE.match(line) is not None for line in lines]
    # Bullet ainda visível aqui — daí esta função rodar antes de _LINE_MARKER_RE.
    item_de_lista = [
        num or re.match(r"^[-*+]\s+\S", line) is not None
        for num, line in zip(numerada, lines)
    ]

    resultado: list[str] = []
    for i, line in enumerate(lines):
        vizinho_e_item = (i > 0 and item_de_lista[i - 1]) or (
            i + 1 < len(lines) and item_de_lista[i + 1]
        )
        if numerada[i] and vizinho_e_item:
            resultado.append(_NUMBERED_ITEM_RE.sub("", line))
        else:
            resultado.append(line)
    return "\n".join(resultado)


def _handle_table_rows(text: str) -> str:
    """Remove linhas de separador de tabela e transforma linhas de dados em texto legível (células unidas por vírgula)."""
    lines = text.split("\n")
    result: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            result.append(line)
            continue
        if (
            stripped.endswith("|")
            and "-" in stripped
            and all(char in _TABLE_SEPARATOR_CHARS for char in stripped)
        ):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        result.append(", ".join(cell for cell in cells if cell))
    return "\n".join(result)


def _map_symbols(text: str) -> str:
    """Traduz símbolos matemáticos/comuns para a palavra em português, com a moeda reposicionada depois do valor."""
    text = _map_currency(text)
    return _SYMBOL_RE.sub(lambda match: SYMBOL_TO_WORD[match.group(0)], text)


def _map_currency(text: str) -> str:
    """Troca 'R$ 50' por '50 reais' — moeda depois do número, como se fala em português."""

    def _repl(match: re.Match) -> str:
        prefixo = match.group(0)[: match.start(1) - match.start(0)].strip()
        for simbolo, palavra in CURRENCY_TO_WORD:
            if prefixo.endswith(simbolo):
                return f"{match.group(1)} {palavra}"
        return match.group(0)

    return _CURRENCY_RE.sub(_repl, text)
