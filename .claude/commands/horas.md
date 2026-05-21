---
description: Lança horas do dia no Clockify a partir da agenda do Outlook
---

Você vai lançar as horas do dia no Clockify de forma colaborativa. O argumento opcional
`$ARGUMENTS` pode conter uma data (AAAA-MM-DD); se vazio, use hoje.

Siga EXATAMENTE este fluxo, um passo de cada vez, conversando em português:

1. **Ler a agenda.** Rode `uv run clockify-horas agenda --date <data>`. Cada evento vira
   um lançamento candidato: descrição = título do evento, horários = os do evento, e
   aplique os defaults de `defaults.json` (tarefa `.Célula de Inovação: Time IA`,
   etiqueta default, faturável default).

2. **Anti-duplicata.** Rode `uv run clockify-horas entries --date <data>`. Se a saída
   não for vazia, JÁ existem lançamentos nessa data — AVISE o usuário, mostre o que já
   existe, e pergunte se quer continuar mesmo assim antes de seguir.

3. **Trabalho avulso.** Pergunte ao usuário o que mais fez no dia além das reuniões,
   pedindo descrição e horários de início/fim. Acrescente como lançamentos.

4. **Edição colaborativa.** Mostre a lista completa em tabela (descrição, horário,
   tarefa, etiqueta, faturável, duração). Aceite ajustes em qualquer campo de qualquer
   item. Se o usuário citar tarefa/etiqueta fora dos defaults, valide contra a saída de
   `meta`; se não existir, liste as opções disponíveis e peça correção.

5. **Total do dia.** Some as durações e informe o total. Se fugir de ~8h além de 15min,
   avise (mas não bloqueie).

6. **Confirmação + dry-run.** Monte o JSON da lista, salve em arquivo temporário e rode
   `uv run clockify-horas add --file <tmp> --dry-run`. Mostre os payloads. Peça
   confirmação explícita do usuário.

7. **Gravar.** Só após o "pode lançar", rode `uv run clockify-horas add --file <tmp>`
   (sem `--dry-run`). Reporte o resumo do que foi criado.

Nunca pule a confirmação do passo 6. Nunca grave sem dry-run antes.
