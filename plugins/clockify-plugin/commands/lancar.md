---
description: Lança horas do dia no Clockify a partir da agenda do Outlook
---

Você vai lançar as horas do dia no Clockify de forma colaborativa, conversando em
português simples. O argumento opcional `$ARGUMENTS` pode conter uma data (AAAA-MM-DD);
se vazio, use hoje. **A pessoa é leiga: nunca mostre JSON, IDs, nomes de campo ou termos
técnicos — você cuida do encanamento.**

Antes de tudo, rode `clockify-plugin config show`. Se falhar (sem config), peça para a
pessoa rodar `/clockify-setup` e pare. Os `defaults` (se existirem) são a **atividade
padrão**; nem todo mundo tem uma — se não houver, tudo bem.

Em seguida, rode `clockify-plugin learned list` **uma vez** e guarde a lista de **atividades
aprendidas** (cada uma tem `match`, `project_name`, `task_name`, `tag_names`, `billable`).
Você usa essa lista para reconhecer as reuniões do dia.

Siga este fluxo, um passo de cada vez:

1. **Ler a agenda.** Rode `clockify-plugin agenda --date <data>`. Se o comando avisar que o
   ICS não está configurado, pule a agenda — sem ela a pessoa dita as atividades no passo 4 e
   o resto do fluxo é igual.

2. **Anti-duplicata (antes de mais nada).** Rode `clockify-plugin entries --date <data>`. Se já
   houver lançamentos nessa data, avise, mostre o que existe, e pergunte se quer continuar
   mesmo assim. Se a pessoa não quiser, pare aqui — assim você não refaz o trabalho à toa.

3. **Reconhecer cada reunião.** Para cada evento, escolha para onde lançar pela
   **precedência**:
   1. **Atividade aprendida** — se o título for igual, parecido, ou contiver a palavra-chave
      (`match`) de alguma atividade aprendida, use os campos dela
      (`project_name`/`task_name`/`tag_names`/`billable`) direto, sem renomear.
   2. **Atividade padrão** — se não reconhecer e existir um default, proponha o default.
   3. **Perguntar** — se não reconhecer e não houver default, pergunte em linguagem comum de
      qual cliente/projeto é aquilo.

4. **Trabalho avulso.** Pergunte o que mais a pessoa fez no dia além das reuniões (com
   horário de início/fim). Acrescente, reconhecendo pela mesma precedência.

5. **Revisão simples.** Mostre tudo numa tabela limpa, sem jargão — coluna da reunião e
   coluna "vou lançar em", com uma nota curta de onde veio:

   ```
   Reunião                  | Vou lançar em                            |
   AI Innovation - Daily    | Equipe Demo · Inovação · não-faturável    (você sempre lança assim)
   Revisão do Cliente       | Proj Demo · Assinatura · faturável        (aprendi com você)
   Conversa com fornecedor  | ❓ não reconheci — de qual cliente é?
   ```

   Aceite ajustes em qualquer linha ("esse é do projeto Z", "essa é faturável"). Se a pessoa
   citar uma tarefa/etiqueta que você não conhece, valide contra `clockify-plugin meta`; se
   não existir, mostre as opções.

6. **Total do dia.** Some as durações e informe o total. Se fugir muito da meta (8h, ou o
   `daily_target_hours` da config), avise sem bloquear.

7. **Aprender um padrão (opcional, com consentimento).** Se você perceber que uma palavra
   aparece sempre ligada ao mesmo cliente, pergunte UMA vez, em português: "Toda vez que
   aparecer '<palavra>', já lanço em <projeto> faturável?". Só com o "sim", rode
   `clockify-plugin learned add --match "<palavra>" --project "..." --task "..." --tag "..." --billable`
   (use `--no-billable` se não for faturável; `--tag` e `--project` são opcionais — omita
   `--project` se a tarefa tiver nome único). Nunca diga "override".

8. **Conferir e gravar.** Monte internamente o JSON da lista — uma lista de objetos com
   EXATAMENTE estes campos (`tag_names` é **lista**, mesmo com uma etiqueta só; `start`/`end`
   em ISO8601 com hora):

   ```json
   [
     {
       "description": "Daily da equipe",
       "start": "2026-06-04T09:00:00",
       "end": "2026-06-04T10:00:00",
       "task_name": "<tarefa>",
       "tag_names": ["<etiqueta>"],
       "billable": false,
       "project_name": "<projeto, se a tarefa não for de nome único; senão omita>"
     }
   ]
   ```

   Inclua `project_name` quando a tarefa existir em mais de um projeto (a maioria, em
   consultoria); omita se o nome da tarefa for único. Salve num arquivo temporário e rode
   `clockify-plugin add --file <tmp> --dry-run` para conferir. **O `--dry-run` imprime o JSON
   cru no terminal — descarte essa saída; ao usuário, mostre só a tabela do passo 5** e peça
   confirmação. Só após o "pode lançar", rode `clockify-plugin add --file <tmp>` (sem
   `--dry-run`) e reporte o que foi criado, em linguagem comum.

Nunca grave sem conferir antes (passo 8). A pessoa nunca precisa ver JSON, IDs ou termos
técnicos.
