---
description: Lança horas no Clockify em vários dias de uma vez (ex: mês retroativo)
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
   b. MOSTRE as reuniões como lançamentos candidatos (defaults aplicados; overrides
      aplicados quando a descrição casar com algum `match`).
   c. PERGUNTE: confirma essas reuniões? O que mais fez no dia? Algum item é de outro
      projeto/tarefa/tag/faturável?
   Atalho: a pessoa pode dizer "mesma coisa nos próximos dias" para clonar. Para itens
   fora do default, valide o nome da tarefa/etiqueta contra `clockify-horas meta`.

5. **Revisão.** Mostre uma tabela por dia (data, descrição, horário, tarefa, tag,
   faturável, duração) e o total por dia. Avise dias fora do `daily_target_hours` (sem bloquear).

6. **Dry-run.** Monte UM JSON com todos os lançamentos de todos os dias, salve em arquivo
   temporário e rode `clockify-horas add --file <tmp> --dry-run`. Mostre os payloads.
   Peça confirmação explícita.

7. **Gravar.** Só após "pode lançar", rode `clockify-horas add --file <tmp>` (sem
   `--dry-run`). Reporte o resumo por dia. Se o `add` sair com código ≠ 0 (falha parcial),
   ele informa quantos itens gravou — monte um novo JSON SÓ com os itens restantes (não
   regrave os já lançados) e rode de novo.

Nunca pule a confirmação do passo 6. Nunca grave sem dry-run antes. Em lotes grandes,
confirme o total de dias e de horas antes de gravar.

**Dedupe (importante):** a única proteção determinística contra duplicata é o passo 3
(`entries`) + você OMITIR do JSON os dias já lançados. Não há trava no `add`.
