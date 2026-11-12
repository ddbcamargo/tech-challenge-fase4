"""Prepara dados de exibição do Azure sem misturar regras de negócio com UI."""

from __future__ import annotations


_SENTIMENT = {"positive": "Positivo", "negative": "Negativo",
              "neutral": "Neutro", "mixed": "Misto"}
_CATEGORIES = {"PersonType": "Tipo de pessoa", "DateTime": "Data / tempo",
               "Person": "Pessoa", "Location": "Local", "Organization": "Organização",
               "Quantity": "Quantidade", "Event": "Evento"}


def audio_view(report: dict) -> dict:
    """Produz uma apresentação estável também para análises armazenadas antigas."""
    azure = report.get("azure") or {}
    sentiment = azure.get("sentiment") or "unknown"
    phrases = []
    seen = set()
    for phrase in azure.get("key_phrases") or []:
        if not isinstance(phrase, str) or not phrase.strip():
            continue
        key = phrase.strip().casefold()
        if key not in seen:
            seen.add(key)
            phrases.append(phrase.strip())
    entities = []
    for item in azure.get("entities") or []:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category", ""))
        entities.append({"Texto": str(item.get("text", "")),
                         "Categoria": _CATEGORIES.get(category, category or "Não classificada")})
    evidences = []
    for item in report.get("critical_evidence") or []:
        if isinstance(item, dict) and item.get("text"):
            evidences.append({"Trecho original": item["text"],
                              "Motivo da revisão": item.get("category", "Trecho de interesse")})
    if not evidences:
        evidences = [{"Trecho original": text, "Motivo da revisão": "Trecho de interesse"}
                     for text in report.get("critical_terms") or []]
    acoustic = report.get("acoustic") or {}
    return {
        "transcript": report.get("transcript") or "Transcrição indisponível",
        "sentiment": _SENTIMENT.get(str(sentiment).lower(), str(sentiment)),
        "sentiment_code": sentiment,
        "sentiment_scores": {
            _SENTIMENT.get(str(key).lower(), str(key)): round(float(value) * 100, 1)
            for key, value in (azure.get("sentiment_scores") or {}).items()
            if isinstance(value, (int, float)) and 0 <= value <= 1
        },
        "key_phrases": phrases,
        "entities": entities,
        "critical_evidence": evidences,
        "voice_indicators": [item for item in report.get("voice_indicators") or []
                             if isinstance(item, dict)],
        "duration_seconds": acoustic.get("duration_seconds"),
        "rms_dbfs": acoustic.get("rms_dbfs"),
        "low_energy_fraction": acoustic.get("low_energy_fraction"),
        "clipped_fraction": acoustic.get("clipped_fraction"),
    }
