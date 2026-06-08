---
name: clockify-report
description: Mostra um relatório das horas lançadas no Clockify (diário por mês, ou mensal por um intervalo de meses), conversando na língua da pessoa.
---

Você mostra à pessoa um relatório das horas que ela já lançou no Clockify. **Converse SEMPRE
na língua da pessoa.** O CLI devolve **JSON**; **você** verbaliza. **Nunca** mostre JSON/IDs/jargão.

## Como rodar o CLI
Igual à skill `clockify-tracking`: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/clockify_cli <cmd>`.
Se o terminal não enxergar o plugin, use a cópia local **atualizada** (sempre
`rm -rf .clockify/bin/clockify_cli` + recopiar os `.py` de `${CLAUDE_PLUGIN_ROOT}/scripts/clockify_cli/`
com ferramentas de arquivo + rodar com `python3 -B .clockify/bin/clockify_cli`). Nunca reuse cópia velha.

## Pré-requisitos
1. **Projeto (pasta local):** rode `pwd`; se for temporário (`/sessions/...` sem `/mnt/`) ou
   `CLAUDE_PROJECT_DIR` vazio, peça pra pessoa abrir um projeto (igual ao tracking) e pare.
2. **Configuração desta pasta (guard).** O report é **só leitura** — nunca faça setup aqui.
   Como primeira ação, rode `... setup-status` (local, sem rede) e leia:
   - `configured: true` → siga.
   - `has_key: false` → **pare**: *"Não encontrei sua configuração do Clockify nesta pasta. Rode
     **/clockify** pra configurar aqui — ou, se você já configurou em outra pasta, abra essa pasta
     no Cowork (no botão 'Trabalhar em um projeto')."*
   - `has_key: true` e `has_ics: false` → **pare**: *"Sua configuração está incompleta: falta
     conectar a agenda do Outlook (agora obrigatória). Rode **/clockify** pra concluir."*
   Se algum comando voltar `{"error":"INVALID_KEY"}`, a chave parou de valer → mande rodar
   **/clockify**.

## Datas — pelo sistema, nunca de cabeça
Você erra calendário. Pegue o "hoje" real (`date +"%Y-%m"`) e resolva meses pelo `date` do
terminal quando a pessoa falar relativo ("mês passado", "últimos 3 meses"): ex.
`date -d "last month" +%Y-%m`. **Confirme com a pessoa o(s) mês(es) antes de gerar.**

## Fluxo
1. Pergunte: **"Quer ver dia a dia de um mês, ou um resumo mensal de vários meses?"**
2. **Diário:** pergunte qual mês → resolva/confirme (AAAA-MM) → rode
   `... report --month AAAA-MM`. Apresente uma lista limpa: cada dia com horas (formate
   bonito, ex. "8h", "7h30") e o **total** do mês. Dias sem lançamento simplesmente não
   aparecem (mencione se a pessoa perguntar). Depois **enriqueça** com o que vier no JSON:
   - `summary`: diga em UMA frase a **média por dia** (`avg_hours`) e o **dia mais cheio**
     (`max_day` → data + horas). Ex.: *"média de 8h12/dia, dia mais cheio foi qua 03/06 (9h)"*.
   - `by_project`: liste as horas **por projeto** (`[{project, hours}]`, já ordenado do maior
     pro menor). Ex.: *"Por projeto: Farmácia San Pablo 24h · Interno 17h"*. Se `project` vier
     `null`, chame de **"Sem projeto"**; se vier algo que pareça um código (sem espaços, tipo
     ID), diga **"projeto sem nome"** em vez de mostrar o código.
   - `gaps`: dias **úteis sem registro** (anteriores a hoje). Se a lista não estiver vazia,
     avise gentil: *"Faltou lançar (dias úteis sem registro): qui 04/06, sex 06/06 — confira se
     algum foi feriado ou folga."* Se estiver vazia, pode dizer que está tudo em dia.
3. **Mensal:** pergunte o intervalo de meses (**máx 12**) → resolva/confirme início e fim →
   rode `... report --start AAAA-MM --end AAAA-MM`. Apresente cada mês com seu total + o
   total geral. Depois enriqueça: `summary` → **média por mês** (`avg_hours`) e **mês mais
   cheio** (`max_month`); `by_project` → horas por projeto no período (mesma regra do diário).
   O modo mensal **não** tem lacunas (`gaps`). Se vier
   `{"error":"INVALID_INPUT","reason":"max_12_meses"}`, explique gentil que o limite é 12
   meses e peça um intervalo menor.
4. Formate horas de forma humana (ex.: 7.5 → "7h30", 8.0 → "8h"). Nunca despeje números crus
   sem contexto nem JSON.

**Regras de ouro:** resolva meses pelo sistema e confirme antes; nunca mostre JSON/IDs;
fale na língua da pessoa; o report é só leitura (não grava nada).
