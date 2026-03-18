# Design: Novo Formato da Mensagem Telegram

**Data:** 2026-03-18
**Arquivo afetado:** `scrapers/telegram.py`
**Escopo:** Somente reformatação visual — zero mudança em lógica de negócio.

---

## Objetivo

Substituir o formato atual (lista numerada sequencial) por uma mensagem agrupada em quadrantes de prioridade, mais legível no contexto de um grupo do Telegram.

---

## Formato Atual

```
🏀 SCOUT · 18/03/2026
3 jogos · 2 jogada(s) destacada(s)

🔥 #1 Jaylen Brown (SF) — Celtics
   BEST OF THE NIGHT
   Jogo: LAL @ BOS · Linha: 22.5 pts
   › sinal 1
   › sinal 2
```

---

## Formato Novo

```
🏀 Entradas de hoje — 18/03/2026
3 jogos analisados

🔥 Melhor da noite

LAL @ BOS
Jaylen Brown (SF) — Celtics · Linha: 22.5 pts
• Elite matchup vs Lakers (DvP #2, 28 pts/g)
• Forma recente acima da média (24 pts vs 21 pts/g)

⚡ Muito favorável

BKN @ MIA
Jimmy Butler (SF) — Heat · Linha: 18.5 pts
• Elite matchup vs Nets (DvP #4, 25 pts/g)
• Zone match: scores from paint — Nets concedem mais lá

Análise gerada automaticamente pelo SCOUT.
```

---

## Regras de Formatação

### Header
- Linha 1: `🏀 Entradas de hoje — DD/MM/YYYY`
- Linha 2: `N jogos analisados`

### Seções
- `🔥 Melhor da noite` → candidates com `rating == "BEST OF THE NIGHT"`
- `⚡ Muito favorável` → candidates com `rating == "VERY FAVORABLE"`
- Candidates com qualquer outro valor de `rating` são ignorados silenciosamente
- Uma seção só é incluída se tiver ao menos 1 jogador
- Ordem: BEST OF THE NIGHT primeiro, depois VERY FAVORABLE

### Card do jogador
```
{game}
<b>{player}</b> ({position}) — {team} · Linha: <b>{line} pts</b>
• {sinal 1}
• {sinal 2}
• {sinal 3}  ← só se existir, máximo 3
```
- `line` exibe `N/A` (sem sufixo `pts`) se o campo for `None`; quando presente, exibe `{line} pts`
- Sinais: máximo 3 (campo `signals` do candidate dict), cada sinal truncado a 80 caracteres via `_truncate(sig, 80)` (helper existente, sem alteração)
- Header da mensagem em `<b>`, títulos de seção em `<b>`, nome do jogador em `<b>`, valor da linha em `<b>`
- Nenhum outro campo usa tags HTML

### Caso sem candidatos
```
🏀 Entradas de hoje — DD/MM/YYYY
N jogos analisados

Nenhuma jogada favorável encontrada hoje.
```

### Footer
```
Análise gerada automaticamente pelo SCOUT.
```

---

## Implementação

### Único ponto de mudança
Reescrever a função `_format_message(candidates, date_str, game_count)` em `scrapers/telegram.py`.

### O que NÃO muda
- `send_analysis()` — assinatura e comportamento inalterados
- `send_error()` — inalterado
- `_get_config()`, `_fmt_date()`, `_truncate()` — inalterados
- Todos os chamadores (`scheduler.py`, `app.py`) — inalterados

---

## Critérios de Aceitação

1. Mensagem com candidatos dos dois ratings exibe ambas as seções na ordem correta
2. Mensagem com apenas um tipo de rating exibe somente a seção relevante
3. Jogador sem linha (`line = None`) exibe `N/A` sem erro
4. Máximo 3 sinais por jogador
5. Mensagem sem candidatos exibe texto simplificado sem seções
6. `send_error()` não é afetado
