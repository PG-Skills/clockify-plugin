# Spec — clockify-cowork: agenda do Outlook (ICS) — v1.0 final

**Data:** 2026-06-08 · **Status:** aprovado no brainstorming, pronto para plano
**Complementa:** `2026-06-08-clockify-cowork-local-design.md` (traz o ICS, que era fase 2, para o escopo).
**Meta:** fechar a **v1.0 final = tracking + configuração + agenda (ICS opcional)**. **Fora:** `/clockify-report`.

---

## 1. Decisões (brainstorming 2026-06-08)

| # | Decisão |
|---|---|
| I1 | **ICS é OPCIONAL** (pulável). Sem ICS, o fluxo atual segue (a pessoa dita as atividades). |
| I2 | **Parser stdlib próprio** (zero-dependência) — busca o `.ics` e expande recorrências comuns na mão. Mantém o "roda em 3.10, sem instalar nada, não quebra". Recorrência exótica rara pode escapar; o **dry-run + confirmação humana** é a rede de segurança. |
| I3 | **Reusar verbatim** `_validate_ics_url` (anti-SSRF, já é stdlib) do `ics.py` antigo. `fetch_ics` passa de `httpx`→`urllib` (sem seguir redirects). `events_for_day` mantém o contrato `{title, start, end}`. |
| I4 | **Link da chave Clockify corrigido:** `https://app.clockify.me/manage-api-keys` (Perfil → Preferências → Avançado → "Gerenciar chaves de API"). |
| I5 | **Onboarding do ICS:** link exato `https://outlook.cloud.microsoft/mail/options/calendar/SharedCalendars`, avisando que é em **"Publicar calendário"** — **NÃO** "Compartilhar" (só o *Publicar* gera o `.ics` público). |
| I6 | **Compat 3.10:** sem `datetime.UTC`; `datetime.fromisoformat` só com strings completas; construir datetimes explicitamente quando o formato for parcial. |

---

## 2. Componentes

1. **`clockify_cli/ics.py`** (novo, stdlib):
   - `validate_ics_url(url)` — anti-SSRF: exige `https` e host que resolve só a IPs públicos (reuso verbatim do antigo `_validate_ics_url`).
   - `fetch_ics(url, timeout=30.0)` — valida e baixa o texto via `urllib` (GET, **sem** seguir redirects — anti-SSRF). Cap de tamanho.
   - `events_for_day(ics_text, target_date, tz="America/Sao_Paulo")` — PURO. Parse de VEVENTs, expande recorrência, devolve `[{title, start, end}]` (datetimes aware em hora local), ordenado por início. Ignora `STATUS:CANCELLED`, eventos all-day (VALUE=DATE) e ocorrências cujo início (local) não cai em `target_date`.

2. **CLI `agenda --date YYYY-MM-DD`** — lê `ics_url` da credencial; sem ICS → `{"ics": false, "eventos": []}`; com ICS → `{"ics": true, "eventos": [{title, start, end}]}` (start/end ISO local). Erros: `NO_KEY`/`INVALID_INPUT`/`HTTP_ERROR` no padrão atual; URL ICS inválida/inacessível → `{"error":"ICS_ERROR","reason":...}`.

3. **Onboarding (skill):** após a chave conectar, oferecer (opcional, pulável) conectar a agenda; se sim, instruir com o link I5 + aviso Publicar≠Compartilhar; gravar `ics_url` na `credentials.json`; validar via `agenda` numa data.

4. **`/clockify-tracking`:** no fluxo de um dia (e por dia no período), se houver `ics_url`, chamar `agenda --date` e **sugerir** lançamentos a partir das reuniões (título → atividade por precedência aprendida→padrão→perguntar; horário do evento). Sem ICS, comportamento atual (ditar).

5. **`/clockify`:** mostrar também se a agenda (ICS) está configurada; corrigir o link da chave (I4).

---

## 3. Parser stdlib — contrato de comportamento

- **Unfolding** (RFC 5545): linhas continuadas (CRLF + espaço/tab) são juntadas antes do parse.
- **Propriedades**: `NOME;PARAM=VAL:VALOR` — separar nome+params do valor no 1º `:`. Params viram dict (ex.: `TZID`, `VALUE`).
- **Texto** (SUMMARY): desescapar `\\,`→`,`, `\\;`→`;`, `\\n`/`\\N`→nova-linha, `\\\\`→`\\`.
- **DTSTART/DTEND**:
  - `VALUE=DATE` (8 dígitos) → all-day → **evento ignorado**.
  - sufixo `Z` → UTC (`YYYYMMDDTHHMMSSZ`).
  - `TZID=...` → naive + tz resolvida: IANA via `ZoneInfo`; se falhar, **mapa Windows→IANA** (inclui `E. South America Standard Time`→`America/Sao_Paulo`); se ainda falhar, **fallback = tz local**.
  - sem Z e sem TZID (floating) → tz local.
  - duração = `DTEND - DTSTART`; se faltar DTEND mas houver `DURATION` (ISO8601, ex.: `PT1H30M`), usa-a; se faltar ambos → evento ignorado.
- **Recorrência** (`RRULE`): match por-data via **janela de candidatos** (checa `target-1`, `target`, `target+1` na tz do evento p/ cobrir virada de fuso); para cada candidato, casar o padrão contra a data de DTSTART:
  - `FREQ=DAILY`: `delta=(cand-d0).days`; `delta>=0` e `delta % INTERVAL == 0`; respeita `COUNT` (exato) e `UNTIL`.
  - `FREQ=WEEKLY`: dias = `BYDAY` (MO..SU→0..6) ou `{d0.weekday()}`; `cand.weekday()` no conjunto; semanas entre as segundas de `d0` e `cand` divisível por `INTERVAL`; respeita `UNTIL`; `COUNT` best-effort (enumeração para frente, capada).
  - `FREQ=MONTHLY`: dia = `BYMONTHDAY` ou `d0.day`; `cand.day`==dia; meses entre `d0` e `cand` divisível por `INTERVAL`; respeita `UNTIL`; `COUNT` best-effort.
  - `EXDATE`: datas excluídas — candidato batendo uma EXDATE é descartado.
  - `INTERVAL` default 1. `FREQ` não suportado (ex.: `YEARLY`/`HOURLY`) → trata como não-recorrente (só DTSTART) e segue (não estoura).
- **Não-recorrente** (sem RRULE): ocorre se a data local de DTSTART == `target_date`.
- **Cap de segurança:** nenhuma expansão ilimitada — a janela de candidatos é O(3) e o `COUNT` best-effort tem teto de iterações.

---

## 4. Compat / segurança / limitações

- **3.10:** construir datetimes campo-a-campo onde o formato for parcial; usar `timezone.utc`; `fromisoformat` só em timestamps completos.
- **Anti-SSRF:** `validate_ics_url` (https + IP público) ANTES do fetch; `fetch_ics` não segue redirects.
- **Tamanho:** cap no corpo baixado (ex.: 5 MB) p/ não estourar memória do sandbox.
- **Limitação declarada:** recorrências raras (ex.: `BYSETPOS`, `BYMONTHDAY` negativo, `YEARLY` complexo, `COUNT` com múltiplos `BYDAY`) podem não ser 100% — aceitável porque a pessoa **revê e confirma** no dry-run antes de gravar. O log/skill deve deixar claro "puxei o que reconheci da agenda; confira".

---

## 5. Testing strategy

- **Parser puro** (`events_for_day`): fixtures ICS curtas cobrindo: evento simples no dia; fora do dia; all-day (ignorado); CANCELLED (ignorado); unfolding; SUMMARY com escapes; DTSTART com `Z`, com `TZID` IANA, com `TZID` Windows (`E. South America Standard Time`), floating; DAILY/WEEKLY(BYDAY)/MONTHLY com INTERVAL; UNTIL; COUNT (daily exato); EXDATE; FREQ não suportado (vira não-recorrente, sem crash).
- **`validate_ics_url`**: rejeita http, host privado/loopback/link-local; aceita https público (mockar `getaddrinfo`).
- **`fetch_ics`**: mock de `urlopen` (sucesso; 3xx não seguido → erro; non-https → ValueError).
- **CLI `agenda`**: `NO_KEY`; sem `ics_url` → `{"ics":false}`; com `ics_url` (mock fetch) → eventos; `ICS_ERROR` em URL inválida.
- Tudo **stdlib**, sem rede real, determinístico. Roda em 3.10+ (CI roda no 3.12 local; código evita APIs 3.11+).

---

## 6. Fora de escopo

- `/clockify-report` (fase posterior).
- Integração Microsoft Graph (substituir ICS) — futuro.
- Recorrências exóticas com fidelidade total (ver §4).
