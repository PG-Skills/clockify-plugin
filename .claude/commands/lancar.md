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

4. **Ditar atividades.** Pergunte o que lançar. Aceite dois modos:
   - "mesma atividade em todos os dias restantes" → clone a mesma descrição + horários
     em cada dia ainda ativo;
   - por dia → o usuário dita descrição + início/fim de cada dia.
   Aplique os defaults de `defaults.json` (tarefa `Time IA`, tag `Célula de Inovação`,
   não-faturável). Aceite overrides de tarefa/etiqueta/faturável; valide nomes fora do
   default contra `uv run clockify-horas meta`.

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
