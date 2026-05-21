# Lançador Batch Multi-dia Clockify — Design

**Data:** 2026-05-21
**Autor:** vbjuliani (PG Consulting)
**Status:** Aprovado (design) — pendente plano de implementação
**Relacionado:** estende [[2026-05-21-lancador-horas-clockify-design]] (`clockify-horas` + `/horas`)

## Problema

Preciso lançar horas no Clockify **retroativamente** (ex: maio inteiro) e, em geral, em
**vários dias de uma vez** numa única sessão — ditando a atividade de cada dia, sem ter
agenda do Outlook pra ler (passado). O `/horas` atual cobre um dia por vez a partir do
calendário; falta um fluxo multi-dia conversacional.

## Decisão de escopo (importante)

A ideia inicial era **criar eventos no Outlook** (via Microsoft Graph) pra alimentar o
`/horas`. **Descartado:** o registro de app no Azure AD está bloqueado pelo TI do tenant
`pgconsulting-group.com`, e o alvo real é o lançamento no Clockify — não a agenda Outlook.
Logo: lançar **direto no Clockify**, sem Outlook, sem Graph, sem dependência de TI.

## Decisões tomadas (brainstorming)

| Tema | Decisão |
|---|---|
| Alvo | Entries direto no Clockify. Outlook fora de escopo. |
| Seleção de dias | Dias úteis (seg–sex) de um período; ferramenta lista, usuário poda exceções (feriados/férias) na conversa. |
| Conteúdo por dia | Decidido por dia na conversa, com atalho "mesma atividade em todos os dias". |
| Campos | Mesmos do `/horas`: descrição, tarefa, etiqueta, faturável, início/fim. Defaults `Time IA` / `Célula de Inovação` / não-faturável. |
| Escrita | Reusa `clockify-horas add` (já grava entries de datas diferentes num JSON único). |
| Abordagem | **B** — skill `/lancar` + 2 helpers CLI pequenos e testáveis. |

## Arquitetura

Reusa a separação cérebro/IO do projeto base. O `add` existente já grava lançamentos
multi-data; o trabalho novo é **listar dias úteis** e **checar duplicata por intervalo**
de forma determinística, mais a **orquestração** da conversa multi-dia.

```
/lancar (retroativo ou futuro)
   │
   ▼
Claude (orquestrador)
   • business-days período  → lista dias úteis
   • usuário poda exceções
   • usuário dita atividades (atalho "todos os dias" ou por dia)
   • entries intervalo       → anti-duplicata do período
   • monta JSON multi-dia → add --dry-run → confirma → add
   │ chama
   ▼
clockify-horas (CLI)
   business-days  (NOVO)  → dias úteis seg–sex de um intervalo
   entries        (ESTENDIDO) → aceita --start/--end (intervalo)
   add            (REUSO)  → grava entries multi-data
```

## Componentes

### `business-days` (novo subcomando)

`clockify-horas business-days --start AAAA-MM-DD --end AAAA-MM-DD`
→ JSON com a lista de datas seg–sex no intervalo (inclusive).
Não filtra feriados (usuário poda na conversa) — mantém o helper puro e previsível.

### `entries` (estendido para intervalo)

Hoje aceita só `--date`. Adicionar `--start/--end` para retornar os lançamentos
existentes no intervalo, agrupados por data — anti-duplicata do mês inteiro em uma chamada.
`--date` continua funcionando (atalho para um dia). A janela usa instantes UTC do
intervalo local (mesma lógica já usada em `get_entries_for_date`).

### `/lancar` (novo slash command)

Orquestra o fluxo (passos abaixo). Reusa `add` para gravar.

## Fluxo

1. Usuário dispara `/lancar` e informa o período (ex: "maio", "01–15/05").
2. Agente roda `business-days` → apresenta os dias úteis.
3. Usuário poda exceções (feriados, férias, dias sem trabalho).
4. Agente roda `entries --start --end` → marca dias **já lançados** e avisa.
5. Usuário dita as atividades: por dia, ou "mesma coisa em todos os dias restantes"
   (descrição + início/fim; defaults aplicam; overrides de tarefa/tag/faturável aceitos).
6. Agente monta o JSON multi-dia e roda `add --dry-run` → mostra tudo + total por dia.
7. Usuário confirma → `add` (real) → resumo por dia.

## Error handling

- **Dry-run obrigatório** antes de gravar (igual `/horas`).
- **Anti-duplicata por dia**: dias com lançamento existente são sinalizados; usuário decide pular ou somar.
- **Tarefa/tag não resolvida**: `add`/`build_payload` já levantam KeyError com o nome ofensor.
- **Período inválido** (start > end): `business-days` retorna erro claro.
- **Feriados**: não automatizados — podados manualmente (YAGNI: lib de feriados só se virar dor real).

## Testes

- `business-days`: intervalo normal, intervalo de 1 dia, fim de semana excluído, start > end (erro).
- `entries` intervalo: agrupa por data, janela UTC correta, vazio.
- Reuso de `add` já coberto pelos testes existentes.

## Fora de escopo (YAGNI)

- Criação de eventos no Outlook / Microsoft Graph (bloqueado por TI; alvo é Clockify).
- Biblioteca de feriados brasileiros (poda manual por ora).
- Edição/remoção de lançamentos existentes.
- Templates persistidos de atividade (atalho "todos os dias" é em memória da conversa).
