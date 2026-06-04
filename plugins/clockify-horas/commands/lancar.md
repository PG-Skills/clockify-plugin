---
description: "Lança horas no Clockify em vários dias de uma vez (ex: mês retroativo)"
---

Você vai lançar horas no Clockify em VÁRIOS dias de uma vez. Conduza em português, um
passo de cada vez.

Antes de tudo, rode `clockify-horas config show`. Se falhar (sem config), peça para a
pessoa rodar `/clockify-setup` e pare. Caso contrário, use `defaults` e `overrides` como base.

1. **Período.** Pergunte o intervalo (ex: "maio", "01–15/05"). Converta para AAAA-MM-DD e
   rode `clockify-horas business-days --start <ini> --end <fim>`. Apresente os dias úteis.

2. **Podar exceções.** Pergunte quais dias remover (feriados, férias, dias sem trabalho).

3. **Anti-duplicata.** Rode `clockify-horas entries --start <ini> --end <fim>`. Para cada
   dia que JÁ tem lançamento, AVISE e pergunte se pula ou soma.

4. **Ditar atividades — puxando do Outlook por dia (se ICS configurado).** Para CADA dia
   selecionado, na ordem:
   a. Rode `clockify-horas agenda --date <dia>` para puxar as reuniões. Se o comando
      avisar que não há ICS, siga só com o que a pessoa ditar.
   b. Para CADA atividade (reunião ou item ditado), rode
      `clockify-horas suggest --description "<título/descrição>"` e monte o candidato
      pela **precedência: (1) override** cujo `match` aparece na descrição (tem prioridade
      sobre a sugestão), **(2) sugestão do histórico** (se `suggest` retornar algo não-vazio,
      use seus campos — `project_name`/`task_name`/`tag_names`/`billable` — e informe "da
      última vez foi projeto X / tarefa Y — mantenho?"), **(3) defaults** da config. A saída
      do `suggest` já vem com as chaves do item do `add` — use-as **direto**, sem renomear.
   c. MOSTRE as atividades como lançamentos candidatos com a precedência acima aplicada.
   d. PERGUNTE: confirma? O que mais fez no dia? Algum item é de outro projeto/tarefa/tag/faturável?
   Atalho: a pessoa pode dizer "mesma coisa nos próximos dias" para clonar. Para itens
   fora do default, valide o nome da tarefa/etiqueta contra `clockify-horas meta`.

5. **Revisão.** Mostre uma tabela por dia (data, descrição, horário, tarefa, tag,
   faturável, duração) e o total por dia. Avise dias fora do `daily_target_hours` (sem bloquear).

6. **Dry-run.** Monte UM JSON com todos os lançamentos de todos os dias — uma lista de objetos
   com EXATAMENTE estes campos (`tag_names` é **lista**, mesmo com uma etiqueta só; `start`/`end`
   em ISO8601 com hora). Converta o `tag_name` (string) dos defaults/overrides para `tag_names`:

   ```json
   [
     {
       "description": "Atividade do dia",
       "start": "2026-05-04T09:00:00",
       "end": "2026-05-04T13:00:00",
       "task_name": "<task_name do default/override/histórico>",
       "tag_names": ["<tag_name>"],
       "billable": false,
       "project_name": "<projeto, se a tarefa não for de nome único; senão omita>"
     }
   ]
   ```

   Inclua `project_name` quando a tarefa existir em mais de um projeto (a maioria, em
   workspaces de consultoria); omita se o nome da tarefa for único.

   Salve em arquivo temporário e rode `clockify-horas add --file <tmp> --dry-run`. Mostre os
   payloads. Peça confirmação explícita.

7. **Gravar.** Só após "pode lançar", rode `clockify-horas add --file <tmp>` (sem
   `--dry-run`). Reporte o resumo por dia. Se o `add` sair com código ≠ 0 (falha parcial),
   ele informa quantos itens gravou — monte um novo JSON SÓ com os itens restantes (não
   regrave os já lançados) e rode de novo.

Nunca pule a confirmação do passo 6. Nunca grave sem dry-run antes. Em lotes grandes,
confirme o total de dias e de horas antes de gravar.

**Dedupe (importante):** a única proteção determinística contra duplicata é o passo 3
(`entries`) + você OMITIR do JSON os dias já lançados. Não há trava no `add`.
