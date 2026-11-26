"""
Analyse d'un dump SQL (phpMyAdmin / mysqldump) : CREATE TABLE + INSERT.

Sans dépendance externe. Le fichier n'est JAMAIS modifié : il est ouvert en lecture binaire.
Toute construction non reconnue lève une `DumpParseError` (jamais d'interprétation silencieuse).
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path


class DumpParseError(Exception):
    pass


_ESCAPES = {"0": "\0", "'": "'", '"': '"', "b": "\b", "n": "\n", "r": "\r", "t": "\t", "Z": "\x1a", "\\": "\\"}
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")
_INT_TYPES = {"tinyint", "smallint", "mediumint", "int", "integer", "bigint"}
_DECIMAL_TYPES = {"decimal", "numeric"}
_STRING_TYPES = {"char", "varchar", "tinytext", "text", "mediumtext", "longtext", "enum"}
_DATE_TYPES = {"date"}
_DATETIME_TYPES = {"datetime", "timestamp"}
SUPPORTED_TYPES = _INT_TYPES | _DECIMAL_TYPES | _STRING_TYPES | _DATE_TYPES | _DATETIME_TYPES


# ---------------------------------------------------------------------------
# Découpage en instructions
# ---------------------------------------------------------------------------
def split_statements(text: str) -> list[str]:
    """Découpe sur ';' hors guillemets/backticks, en ignorant les commentaires SQL."""
    stmts: list[str] = []
    buf: list[str] = []
    i, n = 0, len(text)
    quote: str | None = None
    while i < n:
        c = text[i]
        if quote:
            buf.append(c)
            if c == "\\" and quote in ("'", '"') and i + 1 < n:
                buf.append(text[i + 1])
                i += 2
                continue
            if c == quote:
                if quote in ("'", '"') and i + 1 < n and text[i + 1] == quote:
                    buf.append(text[i + 1])
                    i += 2
                    continue
                quote = None
            i += 1
            continue
        if c in ("'", '"', "`"):
            quote = c
            buf.append(c)
            i += 1
        elif c == "-" and text.startswith("--", i) and (i + 2 >= n or text[i + 2] in " \t\r\n"):
            while i < n and text[i] != "\n":
                i += 1
        elif c == "#":
            while i < n and text[i] != "\n":
                i += 1
        elif c == "/" and text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
        elif c == ";":
            s = "".join(buf).strip()
            if s:
                stmts.append(s)
            buf = []
            i += 1
        else:
            buf.append(c)
            i += 1
    tail = "".join(buf).strip()
    if tail:
        stmts.append(tail)
    return stmts


def _unescape_char(c: str) -> str:
    if c in _ESCAPES:
        return _ESCAPES[c]
    if c in "%_":
        return "\\" + c          # règle MySQL : \% et \_ conservent l'antislash
    return c


def _read_quoted(s: str, i: int) -> tuple[str, int]:
    """Lit une chaîne SQL à partir de s[i] (guillemet ouvrant). Retourne (valeur, index après la chaîne)."""
    q = s[i]
    i += 1
    out: list[str] = []
    n = len(s)
    while i < n:
        c = s[i]
        if c == "\\" and q in ("'", '"') and i + 1 < n:
            out.append(_unescape_char(s[i + 1]))
            i += 2
            continue
        if c == q:
            if i + 1 < n and s[i + 1] == q:
                out.append(q)
                i += 2
                continue
            return "".join(out), i + 1
        out.append(c)
        i += 1
    raise DumpParseError("Chaîne SQL non terminée")


def parse_values(s: str) -> list[list[str | None]]:
    """Analyse `(v1,v2,…),(…)` -> liste de lignes. Valeurs : str (texte ou nombre brut) ou None (NULL)."""
    rows: list[list[str | None]] = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c in " \t\r\n,":
            i += 1
            continue
        if c != "(":
            raise DumpParseError(f"Caractère inattendu {c!r} dans la liste VALUES (position {i})")
        i += 1
        row: list[str | None] = []
        while True:
            while i < n and s[i] in " \t\r\n":
                i += 1
            if i >= n:
                raise DumpParseError("Ligne VALUES non terminée")
            c = s[i]
            if c in ("'", '"'):
                val, i = _read_quoted(s, i)
                row.append(val)
            else:
                j = i
                while j < n and s[j] not in ",)":
                    j += 1
                tok = s[i:j].strip()
                i = j
                if tok.upper() == "NULL":
                    row.append(None)
                elif _NUMBER.fullmatch(tok):
                    row.append(tok)
                else:
                    raise DumpParseError(f"Valeur non prise en charge : {tok!r}")
            while i < n and s[i] in " \t\r\n":
                i += 1
            if i < n and s[i] == ",":
                i += 1
                continue
            if i < n and s[i] == ")":
                i += 1
                break
            raise DumpParseError("Séparateur attendu dans une ligne VALUES")
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Structures
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Column:
    name: str
    base_type: str
    length: int | None = None
    precision: int | None = None
    scale: int | None = None
    enum_values: tuple[str, ...] = ()
    nullable: bool = True
    default: str | None = None
    has_default: bool = False
    auto_increment: bool = False


@dataclass
class Table:
    name: str
    columns: list[Column]
    primary_key: list[str] = field(default_factory=list)
    unique_keys: list[tuple[str, list[str]]] = field(default_factory=list)
    keys: list[tuple[str, list[str]]] = field(default_factory=list)
    foreign_keys: list[str] = field(default_factory=list)
    auto_increment: int | None = None
    engine: str | None = None
    charset: str | None = None
    rows: list[list[str | None]] = field(default_factory=list)

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]

    @property
    def key_columns(self) -> list[str]:
        """Clé effective : PRIMARY KEY, sinon premier UNIQUE KEY dont toutes les colonnes sont NOT NULL."""
        if self.primary_key:
            return self.primary_key
        by_name = {c.name: c for c in self.columns}
        for _, cols in self.unique_keys:
            if all(not by_name[c].nullable for c in cols):
                return cols
        return []

    def typed_rows(self) -> list[list]:
        return [[to_python(col, raw) for col, raw in zip(self.columns, row)] for row in self.rows]


@dataclass
class Dump:
    path: str
    sha256: str
    tables: dict[str, Table]
    ignored_statements: list[str]

    def row_counts(self) -> dict[str, int]:
        return {name: len(t.rows) for name, t in self.tables.items()}


# ---------------------------------------------------------------------------
# CREATE TABLE
# ---------------------------------------------------------------------------
def _matching_paren(s: str, start: int) -> int:
    depth = 0
    i, n = start, len(s)
    while i < n:
        c = s[i]
        if c in ("'", '"'):
            _, i = _read_quoted(s, i)
            continue
        if c == "`":
            i = s.index("`", i + 1) + 1
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise DumpParseError("Parenthèse fermante introuvable")


def _split_top_level(body: str) -> list[str]:
    parts: list[str] = []
    depth, last, i, n = 0, 0, 0, len(body)
    while i < n:
        c = body[i]
        if c in ("'", '"'):
            _, i = _read_quoted(body, i)
            continue
        if c == "`":
            i = body.index("`", i + 1) + 1
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif c == "," and depth == 0:
            parts.append(body[last:i].strip())
            last = i + 1
        i += 1
    tail = body[last:].strip()
    if tail:
        parts.append(tail)
    return parts


def _idents(s: str) -> list[str]:
    return re.findall(r"`([^`]+)`", s)


def _parse_column(defn: str) -> Column:
    m = re.match(r"`([^`]+)`\s+([A-Za-z]+)", defn)
    if not m:
        raise DumpParseError(f"Définition de colonne illisible : {defn[:80]!r}")
    name, base = m.group(1), m.group(2).lower()
    if base not in SUPPORTED_TYPES:
        raise DumpParseError(f"Type de colonne non pris en charge : {base} ({name})")
    rest = defn[m.end():].lstrip()
    length = precision = scale = None
    enum_values: tuple[str, ...] = ()
    if rest.startswith("("):
        end = _matching_paren(rest, 0)
        inner = rest[1:end]
        rest = rest[end + 1:]
        if base == "enum":
            vals, i = [], 0
            while i < len(inner):
                if inner[i] == "'":
                    v, i = _read_quoted(inner, i)
                    vals.append(v)
                else:
                    i += 1
            enum_values = tuple(vals)
        elif base in _DECIMAL_TYPES:
            p, _, sc = inner.partition(",")
            precision, scale = int(p), int(sc or 0)
        elif base in ("char", "varchar"):
            length = int(inner)
    elif base in _DECIMAL_TYPES:
        precision, scale = 10, 0
    up = rest.upper()
    nullable = "NOT NULL" not in up
    dm = re.search(r"DEFAULT\s+('(?:[^'\\]|\\.|'')*'|[^\s,]+)", rest, re.I)
    default = None
    has_default = False
    if dm:
        has_default = True
        raw = dm.group(1)
        default = None if raw.upper() == "NULL" else (_read_quoted(raw, 0)[0] if raw.startswith("'") else raw)
    return Column(
        name=name, base_type=base, length=length, precision=precision, scale=scale,
        enum_values=enum_values, nullable=nullable, default=default, has_default=has_default,
        auto_increment="AUTO_INCREMENT" in up,
    )


def parse_create_table(stmt: str) -> Table:
    m = re.match(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`([^`]+)`\s*\(", stmt, re.I)
    if not m:
        raise DumpParseError(f"CREATE TABLE illisible : {stmt[:80]!r}")
    open_idx = m.end() - 1
    close_idx = _matching_paren(stmt, open_idx)
    body, tail = stmt[open_idx + 1:close_idx], stmt[close_idx + 1:]
    table = Table(name=m.group(1), columns=[])
    for part in _split_top_level(body):
        up = part.upper()
        if up.startswith("PRIMARY KEY"):
            table.primary_key = _idents(part[part.index("("):])
        elif up.startswith(("UNIQUE KEY", "UNIQUE INDEX")):
            table.unique_keys.append((_idents(part)[0], _idents(part[part.index("("):])))
        elif up.startswith(("KEY", "INDEX")):
            table.keys.append((_idents(part)[0], _idents(part[part.index("("):])))
        elif up.startswith(("CONSTRAINT", "FOREIGN KEY")):
            table.foreign_keys.append(part)
        elif up.startswith(("FULLTEXT", "SPATIAL", "CHECK")):
            raise DumpParseError(f"Élément de table non pris en charge : {part[:60]!r}")
        else:
            table.columns.append(_parse_column(part))
    am = re.search(r"AUTO_INCREMENT\s*=\s*(\d+)", tail, re.I)
    table.auto_increment = int(am.group(1)) if am else None
    em = re.search(r"ENGINE\s*=\s*(\w+)", tail, re.I)
    table.engine = em.group(1) if em else None
    cm = re.search(r"CHARSET\s*=\s*(\w+)", tail, re.I)
    table.charset = cm.group(1) if cm else None
    return table


def parse_insert(stmt: str) -> tuple[str, list[str], list[list[str | None]]]:
    m = re.match(r"INSERT\s+(?:IGNORE\s+)?INTO\s+`([^`]+)`\s*(?:\(([^)]*)\))?\s*VALUES\s*", stmt, re.I | re.S)
    if not m:
        raise DumpParseError(f"INSERT illisible : {stmt[:80]!r}")
    cols = _idents(m.group(2)) if m.group(2) else []
    return m.group(1), cols, parse_values(stmt[m.end():])


# ---------------------------------------------------------------------------
# Conversion typée
# ---------------------------------------------------------------------------
def to_python(col: Column, raw: str | None):
    if raw is None:
        return None
    t = col.base_type
    try:
        if t in _INT_TYPES:
            return int(raw)
        if t in _DECIMAL_TYPES:
            return Decimal(raw).quantize(Decimal(1).scaleb(-(col.scale or 0)))
        if t in _STRING_TYPES:
            return raw
        if t in _DATE_TYPES:
            return date.fromisoformat(raw)
        if t in _DATETIME_TYPES:
            return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
    except (ValueError, ArithmeticError) as exc:
        raise DumpParseError(f"Valeur {raw!r} invalide pour {col.name} ({t})") from exc
    raise DumpParseError(f"Type non géré : {t}")


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------
def parse_dump_text(text: str, path: str = "<texte>", sha256: str = "") -> Dump:
    tables: dict[str, Table] = {}
    ignored: list[str] = []
    for stmt in split_statements(text):
        head = stmt[:20].upper()
        if head.startswith("CREATE TABLE"):
            t = parse_create_table(stmt)
            tables[t.name] = t
        elif head.startswith("INSERT"):
            name, cols, rows = parse_insert(stmt)
            if name not in tables:
                raise DumpParseError(f"INSERT sur une table non déclarée : {name}")
            t = tables[name]
            if cols and cols != t.column_names:
                idx = [cols.index(c) for c in t.column_names] if set(cols) == set(t.column_names) else None
                if idx is None:
                    raise DumpParseError(f"Colonnes de l'INSERT incohérentes pour {name}")
                rows = [[r[i] for i in idx] for r in rows]
            for r in rows:
                if len(r) != len(t.columns):
                    raise DumpParseError(f"Nombre de valeurs incorrect dans {name} : {len(r)} au lieu de {len(t.columns)}")
            t.rows.extend(rows)
        else:
            ignored.append(stmt.splitlines()[0][:80])
    return Dump(path=path, sha256=sha256, tables=tables, ignored_statements=ignored)


def parse_dump_file(path: str | Path) -> Dump:
    """Lit le dump en LECTURE SEULE (rb) et exige de l'UTF-8 valide."""
    raw = Path(path).read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DumpParseError(
            f"Le dump n'est pas de l'UTF-8 valide ({exc}). Exportez-le à nouveau depuis phpMyAdmin en UTF-8."
        ) from exc
    if text.startswith("\ufeff"):
        raise DumpParseError("Le dump commence par un BOM UTF-8 : exportez-le sans BOM.")
    return parse_dump_text(text, path=str(path), sha256=hashlib.sha256(raw).hexdigest())
