---
description: "Lança horas no Clockify em vários dias de uma vez (ex: mês retroativo)"
---

Você vai lançar horas no Clockify em VÁRIOS dias de uma vez. Conduza em português simples,
um passo de cada vez. **A pessoa é leiga: nunca mostre JSON, IDs ou termos técnicos.**

Antes de tudo, rode `clockify-horas config show`. Se falhar (sem config), peça para a
pessoa rodar `/clockify-setup` e pare. Os `defaults` (se existirem) são a atividade padrão.

Rode `clockify-horas learned list` **uma vez** e guarde as **atividades aprendidas** (cada
uma com `match`, `project_name`, `task_name`, `tag_names`, `billable`) para reconhecer as
reuniões.

1. **Período.** Pergunte o intervalo (ex: "maio", "01–15/05"). Converta para AAAA-MM-DD e
   rode `clockify-horas business-days --start <ini> --end <fim>`. Apresente os dias úteis.

2. **Podar exceções.** Pergunte quais dias remover (feriados, férias, dias sem trabalho).

3. **Anti-duplicata.** Rode `clockify-horas entries --start <ini> --end <fim>`. Para cada
   dia que JÁ tem lançamento, avise e pergunte se pula ou soma.

4. **Reconhecer atividades por dia.** Para CADA dia selecionado, na ordem:
   a. Rode `clockify-horas agenda --date <dia>` para puxar as reuniões. Se não houver ICS,
      siga só com o que a pessoa ditar.
   b. Para cada reunião ou item ditado, escolha para onde lançar pela **precedência**:
      **(1) atividade aprendida** (título igual/parecido ou que contenha a palavra-chave
      `match` — use os campos dela direto), **(2) atividade padrão** (default, se existir),
      **(3) perguntar** de qual cliente/projeto é.
   c. Mostre os candidatos do dia e pergunte: confirma? O que mais fez? Algum é de outro
      cliente?
   Atalho: a pessoa pode dizer "mesma coisa nos próximos dias" para clonar. Para itens fora
   do conhecido, valide a tarefa/etiqueta contra `clockify-horas meta`.

5. **Revisão.** Mostre uma tabela por dia (data, reunião, "vou lançar em", duração) e o total
   por dia, sem jargão. Avise dias fora da meta (8h ou `daily_target_hours`) sem bloquear.

6. **Aprender um padrão (opcional, com consentimento).** Se uma palavra aparecer sempre
   ligada ao mesmo cliente, pergunte UMA vez ("Toda vez que aparecer '<palavra>', já lanço
   em <projeto> faturável?") e, só com o "sim", rode
   `clockify-horas learned add --match "<palavra>" --project "..." --task "..." --tag "..." --billable`
   (`--no-billable` se não for faturável; `--tag` e `--project` são opcionais — omita
   `--project` se a tarefa tiver nome único). Nunca diga "override".

7. **Conferir e gravar.** Monte internamente UM JSON com todos os lançamentos de todos os
   dias — uma lista de objetos com EXATAMENTE estes campos (`tag_names` é **lista**;
   `start`/`end` em ISO8601 com hora):

   ```json
   [
     {
       "description": "Atividade do dia",
       "start": "2026-05-04T09:00:00",
       "end": "2026-05-04T13:00:00",
       "task_name": "<tarefa>",
       "tag_names": ["<etiqueta>"],
       "billable": false,
       "project_name": "<projeto, se a tarefa não for de nome único; senão omita>"
     }
   ]
   ```

   Inclua `project_name` quando a tarefa existir em mais de um projeto; omita se o nome for
   único. Salve num arquivo temporário e rode `clockify-horas add --file <tmp> --dry-run`.
   **O `--dry-run` imprime o JSON cru no terminal — descarte essa saída; ao usuário, mostre
   só as tabelas por dia do passo 5** e peça confirmação. Só após "pode lançar", rode
   `clockify-horas add --file <tmp>` (sem `--dry-run`) e reporte por dia, em linguagem comum.
   Se o `add` sair com código ≠ 0 (falha parcial), ele informa quantos itens gravou — monte
   um novo JSON SÓ com os restantes (não regrave os já lançados) e rode de novo.

Nunca grave sem conferir antes (passo 7). Em lotes grandes, confirme o total de dias e de
horas antes de gravar.

**Dedupe (importante):** a única proteção determinística contra duplicata é o passo 3
(`entries`) + você OMITIR do JSON os dias já lançados. Não há trava no `add`.
