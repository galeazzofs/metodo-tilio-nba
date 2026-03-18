# Telegram Message Format Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reescrever `_format_message` em `scrapers/telegram.py` para exibir entradas agrupadas por quadrante (Melhor da noite / Muito favorável) em vez de lista numerada.

**Architecture:** Única função alterada. Os grupos BEST OF THE NIGHT e VERY FAVORABLE são filtrados da lista de candidatos e renderizados em seções separadas. Helpers existentes (`_fmt_date`, `_truncate`) são reutilizados sem modificação.

**Tech Stack:** Python 3, pytest, Telegram Bot API (HTML parse mode)

---

## Chunk 1: Testes + Implementação

### Task 1: Escrever os testes para `_format_message`

**Files:**
- Create: `tests/test_telegram.py`

- [ ] **Step 1: Criar o arquivo de teste**

```python
# tests/test_telegram.py
"""Testes para scrapers/telegram.py — _format_message"""
import pytest
from scrapers.telegram import _format_message


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_candidate(player="LeBron James", position="SF", team="Lakers",
                    game="GSW @ LAL", rating="BEST OF THE NIGHT",
                    signals=None, line=22.5):
    return {
        "player": player,
        "position": position,
        "team": team,
        "game": game,
        "rating": rating,
        "signals": signals or [
            "Elite matchup vs GSW (DvP #2, 28 pts/g)",
            "Forma recente acima da média (24 pts vs 21 pts/g)",
            "Zone match: scores from paint",
        ],
        "line": line,
    }


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

def test_header_contains_date():
    msg = _format_message([], "2026-03-18", 3)
    assert "18/03/2026" in msg


def test_header_contains_game_count():
    msg = _format_message([], "2026-03-18", 5)
    assert "5 jogos" in msg


# ---------------------------------------------------------------------------
# Empty candidates
# ---------------------------------------------------------------------------

def test_empty_candidates_shows_no_section_headers():
    msg = _format_message([], "2026-03-18", 3)
    assert "Melhor da noite" not in msg
    assert "Muito favorável" not in msg


def test_empty_candidates_shows_fallback_text():
    msg = _format_message([], "2026-03-18", 3)
    assert "Nenhuma jogada" in msg


# ---------------------------------------------------------------------------
# Sections appear only when populated
# ---------------------------------------------------------------------------

def test_best_of_night_section_present_when_has_candidate():
    c = _make_candidate(rating="BEST OF THE NIGHT")
    msg = _format_message([c], "2026-03-18", 3)
    assert "Melhor da noite" in msg


def test_very_favorable_section_present_when_has_candidate():
    c = _make_candidate(rating="VERY FAVORABLE")
    msg = _format_message([c], "2026-03-18", 3)
    assert "Muito favorável" in msg


def test_best_of_night_section_absent_when_no_candidate():
    c = _make_candidate(rating="VERY FAVORABLE")
    msg = _format_message([c], "2026-03-18", 3)
    assert "Melhor da noite" not in msg


def test_very_favorable_section_absent_when_no_candidate():
    c = _make_candidate(rating="BEST OF THE NIGHT")
    msg = _format_message([c], "2026-03-18", 3)
    assert "Muito favorável" not in msg


# ---------------------------------------------------------------------------
# Section order: BEST OF THE NIGHT before VERY FAVORABLE
# ---------------------------------------------------------------------------

def test_best_of_night_appears_before_very_favorable():
    best = _make_candidate(rating="BEST OF THE NIGHT", player="Alpha")
    vf   = _make_candidate(rating="VERY FAVORABLE",    player="Beta")
    msg  = _format_message([vf, best], "2026-03-18", 3)
    assert msg.index("Melhor da noite") < msg.index("Muito favorável")


# ---------------------------------------------------------------------------
# Unknown rating is silently ignored
# ---------------------------------------------------------------------------

def test_unknown_rating_ignored():
    c = _make_candidate(rating="FAVORABLE")
    msg = _format_message([c], "2026-03-18", 3)
    assert "LeBron James" not in msg


# ---------------------------------------------------------------------------
# Player card fields
# ---------------------------------------------------------------------------

def test_card_shows_game():
    c = _make_candidate(game="BOS @ MIA")
    msg = _format_message([c], "2026-03-18", 3)
    assert "BOS @ MIA" in msg


def test_card_shows_player_name():
    c = _make_candidate(player="Jaylen Brown")
    msg = _format_message([c], "2026-03-18", 3)
    assert "Jaylen Brown" in msg


def test_card_shows_position_and_team():
    c = _make_candidate(position="PG", team="Celtics")
    msg = _format_message([c], "2026-03-18", 3)
    assert "PG" in msg
    assert "Celtics" in msg


def test_card_shows_line_with_pts_suffix():
    c = _make_candidate(line=18.5)
    msg = _format_message([c], "2026-03-18", 3)
    assert "18.5 pts" in msg


def test_card_shows_na_when_line_is_none():
    c = _make_candidate(line=None)
    msg = _format_message([c], "2026-03-18", 3)
    assert "N/A" in msg
    # Must not crash and must not show "None pts"
    assert "None pts" not in msg


# ---------------------------------------------------------------------------
# Signals capped at 3
# ---------------------------------------------------------------------------

def test_signals_capped_at_3():
    c = _make_candidate(signals=[f"sinal {i}" for i in range(6)])
    msg = _format_message([c], "2026-03-18", 3)
    assert "sinal 0" in msg
    assert "sinal 1" in msg
    assert "sinal 2" in msg
    assert "sinal 3" not in msg


def test_signals_fewer_than_3_all_shown():
    c = _make_candidate(signals=["único sinal"])
    msg = _format_message([c], "2026-03-18", 3)
    assert "único sinal" in msg


# ---------------------------------------------------------------------------
# Signals truncated at 80 chars
# ---------------------------------------------------------------------------

def test_signal_truncated_at_80_chars():
    long_signal = "x" * 100
    c = _make_candidate(signals=[long_signal])
    msg = _format_message([c], "2026-03-18", 3)
    # The truncated version is 79 chars + "…" = 80 chars total
    assert long_signal not in msg
    assert "x" * 79 + "…" in msg


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

def test_footer_present():
    msg = _format_message([], "2026-03-18", 3)
    assert "Análise gerada automaticamente" in msg
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

```bash
cd <worktree-path>
pytest tests/test_telegram.py -v
```

Esperado: a maioria passa trivialmente (header, footer) porque a função já existe, mas os testes de estrutura de seções (`Melhor da noite`, `Muito favorável`) devem **FALHAR** — confirmando que o novo formato ainda não está implementado.

---

### Task 2: Reescrever `_format_message`

**Files:**
- Modify: `scrapers/telegram.py` — apenas a função `_format_message` (linhas 69–108)

- [ ] **Step 1: Substituir `_format_message` pelo novo formato**

Substituir o bloco atual da função pelo código abaixo (todos os outros elementos do arquivo ficam inalterados):

```python
def _format_message(candidates: list, date_str: str, game_count: int) -> str:
    """Formata a mensagem HTML para o Telegram — agrupada por quadrante."""
    day_fmt = _fmt_date(date_str)

    header = [
        f"🏀 <b>Entradas de hoje — {day_fmt}</b>",
        f"{game_count} jogos analisados",
        "",
    ]

    if not candidates:
        return "\n".join(header + [
            "Nenhuma jogada favorável encontrada hoje.",
            "",
            "Análise gerada automaticamente pelo SCOUT.",
        ])

    # Separar por quadrante
    best   = [c for c in candidates if c.get("rating") == "BEST OF THE NIGHT"]
    vf     = [c for c in candidates if c.get("rating") == "VERY FAVORABLE"]

    lines = list(header)

    for section_title, group in [
        ("🔥 <b>Melhor da noite</b>", best),
        ("⚡ <b>Muito favorável</b>",  vf),
    ]:
        if not group:
            continue
        lines.append(section_title)
        lines.append("")
        for p in group:
            line_val = p.get("line")
            line_str = f"<b>{line_val} pts</b>" if line_val is not None else "N/A"

            lines.append(p.get("game", ""))
            lines.append(
                f"<b>{p.get('player', '?')}</b> ({p.get('position', '')}) "
                f"— {p.get('team', '')} · Linha: {line_str}"
            )
            for sig in p.get("signals", [])[:3]:
                lines.append(f"• {_truncate(sig, 80)}")
            lines.append("")

    lines.append("Análise gerada automaticamente pelo SCOUT.")
    return "\n".join(lines)
```

- [ ] **Step 2: Rodar todos os testes do arquivo**

```bash
pytest tests/test_telegram.py -v
```

Esperado: **todos os testes passam** (PASSED).

- [ ] **Step 3: Rodar a suite completa para garantir nenhuma regressão**

```bash
pytest tests/ -v
```

Esperado: todos os testes existentes continuam passando.

- [ ] **Step 4: Commit**

```bash
git add scrapers/telegram.py tests/test_telegram.py
git commit -m "feat(telegram): novo formato de mensagem agrupado por quadrante"
```

---

## Chunk 2: Push e verificação

- [ ] **Step 1: Push do branch**

```bash
git push origin claude/thirsty-mccarthy
```

- [ ] **Step 2: Testar manualmente no app**

1. Abrir a plataforma → aba Análise → clicar **Rodar Análise**
2. Nos logs, confirmar `[telegram] Mensagem enviada para o grupo ✓`
3. Verificar no grupo do Telegram que a mensagem chegou no novo formato (seções por quadrante)
