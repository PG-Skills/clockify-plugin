---
description: Lança horas no Clockify em vários dias de uma vez (ex: maio retroativo)
---

Você vai lançar horas no Clockify em VÁRIOS dias de uma vez. Não há agenda do Outlook
para ler (uso típico: retroativo). Conduza em português, um passo de cada vez:

1. **Período.** Pergunte o intervalo (ex: "maio", "01–15/05"). Converta para datas
   AAAA-MM-DD e rode `uv run clockify-horas business-days --start <ini> --end <fim>`.
   Apresente os dias úteis listados.

2. **Podar exceções.** Pergunte quais dias remover (feriados, férias, dias sem trabalho).
   Remova-os da lista de trabalho.

3. **Anti-duplicata.** Rode `uv run clockify-horas entries --start <ini> --end <fim>`.
   Para cada dia que JÁ tem lançamento, AVISE e pergunte se pula ou soma.

4. **Ditar atividades — SEMPRE puxando do Outlook primeiro, dia a dia.** Para CADA dia
   selecionado, na ordem:
   a. Rode `uv run clockify-horas agenda --date <dia>` para puxar as reuniões daquele dia.
   b. MOSTRE ao usuário as reuniões do dia como lançamentos candidatos (descrição = título,
      horário real, defaults `Time IA` / `Célula de Inovação` / não-faturável aplicados).
   c. PERGUNTE: confirma essas reuniões? O que mais fez no dia (trabalho avulso, com
      horários)? Algum item é de outro projeto/tarefa/tag/faturável?
   Só depois de fechar o dia, passe ao próximo. Atalho: o usuário pode dizer "mesma coisa
   nos próximos dias" para clonar.
   Aplique os defaults de `defaults.json`. Para itens fora do default, valide o nome da
   tarefa/etiqueta contra `uv run clockify-horas meta` e ajuste a tag correlata
   (ex: projeto de cliente AMS → tag `AMS`).

5. **Revisão.** Mostre uma tabela por dia (data, descrição, horário, tarefa, tag,
   faturável, duração) e o total de horas por dia. Avise dias fora de ~8h (não bloqueie).

6. **Dry-run.** Monte UM JSON com todos os lançamentos de todos os dias, salve em arquivo
   temporário e rode `uv run clockify-horas add --file <tmp> --dry-run`. Mostre os payloads.
   Peça confirmação explícita.

7. **Gravar.** Só após "pode lançar", rode `uv run clockify-horas add --file <tmp>`
   (sem `--dry-run`). Reporte o resumo por dia. Se o `add` sair com código ≠ 0 (falha
   parcial), ele informa quantos itens gravou antes de parar — monte um novo JSON SÓ com
   os itens restantes (não regrave os já lançados) e rode de novo.

Nunca pule a confirmação do passo 6. Nunca grave sem dry-run antes. Em lotes grandes
(mês inteiro), confirme o total de dias e de horas antes de gravar.

**Dedupe (importante):** a única proteção determinística contra duplicata é o passo 3
(`entries`) + você OMITIR do JSON os dias já lançados. Não há trava no `add` — se incluir
um dia já lançado no JSON, ele será gravado de novo. Por isso: sempre rode o passo 3 e
exclua explicitamente os dias já preenchidos antes do dry-run.
