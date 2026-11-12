"""Trechos literais de consultas encenadas que justificam revisão humana.

As regras são transparentes e não produzem diagnóstico nem avaliação de gravidade.
Mantemos o texto exato reconhecido, para que a equipe confira a evidência.
"""

from __future__ import annotations

import re

# Ordem intencional: padrões específicos antes de padrões gerais.
_PATTERNS = (
    ("CHEST_PAIN", "Dor torácica relatada", r"\bdor(?:es)?\s+no\s+peito\b"),
    ("RESPIRATORY_COMPLAINT", "Queixa respiratória", r"\bfalta\s+de\s+ar\b|\bdificuldade\s+(?:para|de)\s+respirar\b"),
    ("FAINTING", "Desmaio relatado", r"\bdesmaio\b|\bdesmaiei\b"),
    ("DIZZINESS", "Tontura relatada", r"\btonturas?\b"),
    ("PAIN", "Dor relatada", r"\bdor(?:es)?\b(?:\s+(?:nas?|nos?|d[ao]s?|e|m[aã]os|punhos|dedos|bra[cç]os|pernas|costas|joelhos|ombros)){0,8}"),
    ("FUNCTIONAL_LIMITATION", "Limitação funcional relatada",
     r"\b(?:t[eê]m(?:\s+me)?\s+impedido|me\s+imped(?:e|em|ido)|n[aã]o\s+consigo|"
     r"dificuldade\s+(?:para|de)\s+(?:fazer|realizar|caminhar))\b"
     r"(?:\s+(?:de|para|fazer|realizar|tarefas|simples|atividades|di[aá]rias|caminhar|meus|minhas|movimentos)){0,7}"),
    ("FATIGUE", "Cansaço relatado", r"\bcansa[cç]o\b|\bcansad[ao]s?\b"),
)

_NEGATED_PAIN = re.compile(r"(?:\bn[aã]o\s+(?:tenho|sinto|estou\s+com)|\bsem)\s*$", re.IGNORECASE)


def critical_evidence(text: str) -> list[dict]:
    """Extrai trechos exatos do texto (índices e categoria), sem inferência clínica."""
    findings = []
    ranges = []
    for code, category, pattern in _PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            start, end = match.span()
            if any(start < other_end and end > other_start for other_start, other_end in ranges):
                continue
            if code in {"PAIN", "CHEST_PAIN", "FATIGUE"} and _NEGATED_PAIN.search(text[max(0, start - 35):start]):
                continue
            phrase = text[start:end].strip()
            if not phrase:
                continue
            findings.append({"code": code, "category": category,
                             "text": phrase, "start": start, "end": end})
            ranges.append((start, end))
    return sorted(findings, key=lambda item: item["start"])


def critical_terms(text: str) -> list[str]:
    """Compatibilidade: devolve as próprias expressões encontradas no relato."""
    return [item["text"] for item in critical_evidence(text)]
