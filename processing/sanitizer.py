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
    "€": "euros",
    "$": "dólares",
    "£": "libras",
}

_SYMBOL_RE = re.compile("|".join(re.escape(s) for s in SYMBOL_TO_WORD))

# Ênfase/negrito/código inline: remove o marcador, preserva o conteúdo. Exige
# abertura E fechamento — um * solto no meio de prosa não casa (falso positivo).
_EMPHASIS_RE = re.compile(r"\*\*(.+?)\*\*|\*([^\s*][^*]*?)\*|`([^`]+?)`")

# Marcadores de linha: títulos (#), citações (>), e itens de lista (- * + e N. / N) ).
# O travessão de diálogo em português (—, U+2014) NÃO está aqui e sobrevive.
_LINE_MARKER_RE = re.compile(r"(?m)^(?:#{1,6}\s*|>\s?|[-*+]\s+|(?:\d{1,3}[.)]\s+))")

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
    return _LINE_MARKER_RE.sub("", text)


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
    """Traduz símbolos matemáticos/comuns para a palavra em português."""
    return _SYMBOL_RE.sub(lambda match: SYMBOL_TO_WORD[match.group(0)], text)
