# Lançador de Horas Clockify — Design

**Data:** 2026-05-21
**Autor:** vbjuliani (PG Consulting)
**Status:** Aprovado (design) — pendente plano de implementação

## Problema

Como consultor da Procurement Garage (PG Consulting), preciso lançar horas em todos os
dias úteis no Clockify, separadas por projeto e atividade. Hoje isso é manual e repetitivo.
Quero automatizar **sob demanda** (eu disparo o fluxo no fim do dia), de forma colaborativa:
o agente propõe os lançamentos a partir da minha agenda e do que fiz, ajustamos juntos, e
ele grava no Clockify.

## Decisões tomadas (brainstorming)

| Tema | Decisão |
|---|---|
| Disparo | Sob demanda, fim do dia. Eu invoco o fluxo. |
| Fonte da agenda | Microsoft Outlook via **link ICS** publicado (read-only). |
| Reuniões → lançamentos | Reunião do calendário vira lançamento com **descrição = nome da reunião** e **horário real** do evento. |
| Trabalho avulso | Eu informo no chat o que mais fiz, com horários; o agente encaixa. |
| Projeto/Tarefa | Campo "Tarefa" combina projeto+tarefa. **Default ~99%: `.Célula de Inovação: Time IA`.** Exceções (ex: `.Atividades Internas: 08. Outros`) sinalizadas na conversa. |
| Etiquetas (Tags) | **Campo obrigatório.** Conjunto pequeno de tags fixas; agente mostra e eu escolho, ou infere pelo projeto. |
| Faturável | Toggle nativo Sim/Não do Clockify. |
| Horários | **Início/fim precisos.** Reuniões herdam do calendário; trabalho avulso eu informo os horários. |
| Meta diária | Geralmente ~8h, não obrigatória. Agente mostra total e **avisa** se fugir, **sem travar**. |
| API key | Usuário precisa de ajuda para gerar (Clockify → Profile Settings → API). |
| Abordagem | **A — Skill/slash command + script CLI fino.** |

## Modelo de dados de um lançamento (Clockify time entry)

Campos obrigatórios observados na UI ("Editar registro de tempo"):

- **Descrição** (obrigatório) — texto livre. Reunião → nome da reunião; avulso → o que fiz.
- **Tarefa** (obrigatório) — projeto + tarefa. Default `.Célula de Inovação: Time IA`.
- **Etiquetas / Tags** (obrigatório) — ao menos uma tag, de um conjunto pequeno fixo.
- **Faturável** — toggle Sim/Não.
- **Hora e data** — duração + início + fim + data. Horários reais.

## Arquitetura

Separação proposital entre **cérebro** (o agente Claude, que conversa e decide) e
**camada de I/O confiável** (script `clockify.py`, que só executa). O script é testado uma
vez e tratado como confiável; o usuário nunca o edita no dia a dia.

```
Fim do dia → /horas
   │
   ▼
Claude (orquestrador)
   • chama o script p/ buscar agenda + metadata
   • monta proposta aplicando defaults
   • conversa e edita com o usuário
   • valida total do dia
   • na confirmação, manda gravar
   │ chama
   ▼
clockify.py (I/O)
   agenda → lê ICS do Outlook → eventos do dia
   meta   → lista projetos/tarefas/tags (cache local)
   add    → cria lançamentos via API REST
   │
   ├─ Outlook ICS (read-only)
   └─ Clockify API (api.clockify.me/api/v1)
```

## Componentes

### `clockify.py` (CLI)

| Comando | Função | Saída |
|---|---|---|
| `agenda --date AAAA-MM-DD` | Baixa ICS, filtra eventos do dia | JSON: título, início, fim, duração |
| `meta` | Lista projetos/tarefas/tags do workspace (cacheia local) | JSON de IDs ↔ nomes |
| `add` | Recebe lançamentos (JSON via stdin/arquivo) e cria via `POST /workspaces/{id}/time-entries` | Confirmação + links |

Flags transversais: `--dry-run` (imprime o payload sem gravar).

### Configuração

- `.env` (fora do git): `CLOCKIFY_API_KEY`, `CLOCKIFY_WORKSPACE_ID`, `OUTLOOK_ICS_URL`.
- `defaults.json`: tarefa default, etiqueta default correlata, faturável default, meta diária (~8h).
  Editável sem mexer no código.

### `/horas` (slash command / skill)

Prompt de orquestração que executa o fluxo de um dia (abaixo).

## Fluxo de um dia típico

1. Usuário dispara `/horas` (assume hoje; aceita outra data como argumento).
2. Agente roda `agenda` → apresenta reuniões já como lançamentos (descrição = nome,
   horário real, tarefa+tag default, faturável default).
3. Agente pergunta o **trabalho avulso** — usuário informa o quê + horários.
4. Edição colaborativa no chat (qualquer campo de qualquer item).
5. Agente mostra **total do dia** e avisa se fugir de ~8h (não trava).
6. Usuário **confirma** → agente roda `add` → devolve resumo dos lançamentos criados.

## Error handling

- **Dry-run primeiro**: nada vai ao Clockify sem confirmação da lista final.
- **Anti-duplicata**: antes de gravar, checar se já há lançamentos naquela data e avisar.
- **ICS incompleto/atrasado**: se vier vazio/defasado, avisar e permitir colar a agenda manualmente (fallback).
- **Tarefa/tag não resolvida**: listar disponíveis e perguntar.
- **Credencial faltando/ inválida**: setup guiado (inclui gerar API key).
- **Timezone**: tratar conversão UTC ↔ local do ICS de forma explícita.

## Testes

- Unitários da lógica pura: parsing do ICS, construção do payload do lançamento, cálculo do total do dia.
- Mock da API do Clockify — nenhum teste lança hora real.
- `--dry-run` imprime exatamente o payload que iria à API.

## Stack

Python 3.12+ com uv, ruff, pyright (convenções do usuário). `httpx` para API REST,
`icalendar` para parsing do ICS.

## Pontos em aberto (não bloqueiam o plano)

- Nome exato da etiqueta default correlata a `.Célula de Inovação: Time IA`.
- Descoberta do Workspace ID (o próprio `meta` lista).
- Validar que o ICS expõe a agenda completa (eventos privados/atraso de sync).

## Fora de escopo (YAGNI por ora)

- Automação agendada/autônoma (Abordagem C) — possível evolução futura.
- Edição/remoção de lançamentos já gravados.
- Relatórios e dashboards.
