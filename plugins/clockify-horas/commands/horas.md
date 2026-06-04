---
description: Lança horas do dia no Clockify a partir da agenda do Outlook
---

Você vai lançar as horas do dia no Clockify de forma colaborativa. O argumento opcional
`$ARGUMENTS` pode conter uma data (AAAA-MM-DD); se vazio, use hoje.

Antes de tudo, rode `clockify-horas config show`. Se falhar (sem config), peça para a
pessoa rodar `/clockify-setup` e pare. Caso contrário, use os `defaults` e `overrides`
retornados como base dos lançamentos.

Siga EXATAMENTE este fluxo, um passo de cada vez, conversando em português:

1. **Ler a agenda.** Rode `clockify-horas agenda --date <data>`. Cada evento vira um
   lançamento candidato: descrição = título do evento, horários = os do evento, e aplique
   os `defaults` da config (task_name, tag_name, billable).

2. **Anti-duplicata.** Rode `clockify-horas entries --date <data>`. Se a saída não for
   vazia, JÁ existem lançamentos nessa data — AVISE, mostre o que existe, e pergunte se
   quer continuar antes de seguir.

3. **Trabalho avulso.** Pergunte o que mais a pessoa fez no dia além das reuniões, com
   descrição e horários de início/fim. Acrescente como lançamentos.

4. **Overrides + edição colaborativa.** Para cada item, se a descrição casar com o campo
   `match` de algum override da config, aplique a tarefa/etiqueta/faturável daquele
   override. Mostre a lista completa em tabela (descrição, horário, tarefa, etiqueta,
   faturável, duração). Aceite ajustes em qualquer campo. Se a pessoa citar tarefa/etiqueta
   fora dos defaults/overrides, valide contra `clockify-horas meta`; se não existir, liste
   as opções e peça correção.

5. **Total do dia.** Some as durações e informe o total. Se fugir do `daily_target_hours`
   da config além de 15min, avise (sem bloquear).

6. **Confirmação + dry-run.** Monte o JSON da lista, salve em arquivo temporário e rode
   `clockify-horas add --file <tmp> --dry-run`. Mostre os payloads. Peça confirmação
   explícita.

7. **Gravar.** Só após o "pode lançar", rode `clockify-horas add --file <tmp>` (sem
   `--dry-run`). Reporte o resumo do que foi criado.

Nunca pule a confirmação do passo 6. Nunca grave sem dry-run antes.
