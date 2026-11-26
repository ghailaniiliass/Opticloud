"""Petits outils de test sur le HTML produit."""
import re
from html.parser import HTMLParser

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class _Balance(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.problems = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.problems.append(f"</{tag}> inattendu (pile : {self.stack[-3:]})")
            if tag in self.stack:
                while self.stack and self.stack.pop() != tag:
                    pass
        else:
            self.stack.pop()


def html_problems(html: str) -> list[str]:
    """Balises mal fermées ou non fermées (liste vide = HTML bien formé)."""
    parser = _Balance()
    parser.feed(html)
    parser.close()
    return parser.problems + [f"<{t}> jamais fermé" for t in parser.stack]


def internal_links(html: str) -> set[str]:
    """Liens <a href> internes (hors fichiers statiques)."""
    return {h for h in re.findall(r'<a [^>]*href="(/[^"#]*)"', html) if not h.startswith("/static/")}
