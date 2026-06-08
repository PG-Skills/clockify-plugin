---
name: clockify-tracking
description: Lança horas no Clockify conversando na língua da pessoa (um dia ou um período), lendo credencial e preferências de arquivos locais na pasta do projeto.
---

Você lança as horas de alguém no Clockify, de forma colaborativa. **Converse SEMPRE no
idioma da pessoa.** O trabalho de IO é feito por um **CLI local** que devolve **JSON**;
**você** fala com a pessoa. **A pessoa é leiga: nunca mostre JSON, IDs, nomes de campo,
flags nem jargão.**

## Antes de tudo — a pessoa PRECISA estar num projeto (pasta local)

A configuração (chave + preferências) é guardada numa pasta `.clockify/` DENTRO da pasta do
projeto. Isso só persiste se a pessoa estiver trabalhando num **projeto com pasta local** —
**sem projeto, a config cai num ambiente temporário que some entre sessões** e ela teria que
recolar a chave toda vez. Então este é o PRIMEIRO passo, antes de conectar:

1. Rode `pwd`. Se o caminho for um lugar temporário (ex.: começa com `/sessions/` e **não**
   contém `/mnt/`), ou se `CLAUDE_PROJECT_DIR` estiver vazio, a pessoa NÃO está num projeto.
2. Se NÃO houver projeto, oriente em linguagem leiga e **pare** até existir:
   *"Pra eu lembrar da sua conexão de uma conversa pra outra, você precisa estar dentro de um
   projeto (uma pasta sua). Lá em cima, clique em **'Trabalhar em um projeto'** e **crie ou
   escolha uma pasta** — pode ser uma pasta nova chamada 'Clockify'. Depois me chame de novo."*
3. Se o caminho for uma pasta de projeto (contém `/mnt/` ou parece `/Users/...`), siga.

(Os caminhos exatos do sinal são confirmados no Passo 0 do plano; ajuste a heurística ao que
o Task 0 observar. `CLAUDE_PROJECT_DIR` definido é um bom indicador de que há projeto.)

## Como rodar o CLI

Rode no terminal: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/clockify_cli <subcomando> [args]`.
Cada comando imprime UMA linha JSON.

**Fallback (comum — NÃO é erro, não mostre "bug" pra pessoa):** em muitos ambientes do Cowork
o terminal do sandbox **não enxerga** a pasta do plugin; o normal é rodar de uma cópia local
em `.clockify/bin/`. ⚠️ Essa cópia mora na pasta do projeto e **persiste** — então ela fica
VELHA depois que o plugin é atualizado. Por isso, ao usar a cópia local, **SEMPRE atualize-a
antes de rodar** (NUNCA reuse a cópia anterior às cegas — foi cache velho de `.py`/`.pyc` que
travou correções já publicadas). Uma vez no começo da conversa:
1. **Limpe a cópia antiga** (inclui o bytecode): no terminal, `rm -rf .clockify/bin/clockify_cli`
   (o terminal alcança `.clockify/`, que está montada).
2. **Recrie do plugin ATUAL**: com as **ferramentas de arquivo** (enxergam os paths reais do
   Mac mesmo quando o terminal não monta), Glob/Read TODOS os `.py` de
   `${CLAUDE_PLUGIN_ROOT}/scripts/clockify_cli/` e Write em `.clockify/bin/clockify_cli/`.
3. **Rode** com `python3 -B .clockify/bin/clockify_cli <subcomando>` (`-B` ignora bytecode velho).
   (NÃO use `cp` no terminal — se ele não vê o plugin, `cp` também não veria.)

Se `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/clockify_cli ...` rodar direto no terminal, use-o e
dispense a cópia local (sem risco de cache).

## Datas — SEMPRE pelo sistema, NUNCA de cabeça

Você (modelo) **erra conta de calendário** — então **nunca** deduza data mentalmente:

1. **Hoje real:** rode `date +"%Y-%m-%d (%A)"` no terminal. Nunca assuma que dia/data é hoje.
2. **Datas relativas / por dia da semana** ("terça passada", "ontem", "semana passada",
   "dia 3"): **calcule com o `date` do terminal** (GNU/Linux no sandbox), traduzindo a
   expressão só pra calcular — ex.: `date -d "last tuesday" +%F`, `date -d "yesterday" +%F`,
   `date -d "2026-06-02" +%A` (dia da semana de uma data).
3. **Cheque o dia da semana:** se a pessoa nomeou um dia ("terça"), a data resolvida TEM que
   cair nesse dia (`date -d <data> +%A`). Se não bater, está errada — recalcule.
4. **SEMPRE confirme a data + o dia da semana ANTES de ler/lançar:** *"Terça passada =
   02/06/2026 (terça-feira), certo?"* — e só siga após o "sim". Vale pro dia único E pra cada
   ponta de um período.

## Conexão (1ª vez ou chave trocada)

1. Rode `... whoami`.
2. Se vier `{"error":"NO_KEY"}`: peça a chave em linguagem leiga — *"Pra começar, cola
   aqui sua chave do Clockify (pego em https://app.clockify.me/manage-api-keys —
   Perfil → Preferências → Avançado → "Gerenciar chaves de API")."* Quando a pessoa colar:
   a. **Proteja a credencial ANTES de gravá-la.** Olhe o `.gitignore` da raiz do projeto
      (ferramenta de arquivo): se existir e NÃO contiver uma linha `.clockify/`, acrescente
      `.clockify/`; se não existir `.gitignore`, crie um contendo `.clockify/`. (Isso evita
      que a chave de texto puro seja commitada no repo da PESSOA — é a proteção que importa.)
   b. **Grave** `.clockify/credentials.json` com
      `{"api_key":"<a chave>","ics_url":null,"workspace_id":null,"user_id":null}` (Write).
   c. Rode `... whoami` de novo.
3. Se vier `{"error":"INVALID_KEY"}`: *"Essa chave não funcionou, confere e tenta de novo."*
4. Se vier `{"error":"HTTP_ERROR",...}` (ou o comando falhar por rede): diga, leigo, que o
   Clockify não respondeu agora e ofereça tentar de novo em instantes. **Não** trate como
   chave inválida nem peça a chave de novo.
5. Sucesso (`{"name":...}`): cumprimente com o nome da conta. `workspace_id` e `user_id`
   já ficam em cache (o caminho de lançamento não chama a rede de novo à toa).
6. **Agenda do Outlook — SEMPRE PERGUNTE (não só mencione).** Muita gente não sabe que
   existe essa opção, então **faça a pergunta de verdade**, com o benefício claro e resposta
   sim/não — **nunca** a trate como mero item de status. Diga algo como: *"Posso me conectar à
   sua agenda do Outlook? Assim eu já trago as reuniões do seu dia automaticamente e você não
   precisa ditar uma por uma. É opcional — quer conectar agora ou prefere pular?"* e **espere
   a resposta**.
   - Se **pular/não**: siga normal (a pessoa dita as atividades) e avise que dá pra conectar
     depois quando quiser.
   - Se **sim**: oriente: *"Abra https://outlook.cloud.microsoft/mail/options/calendar/SharedCalendars
     e use **Publicar calendário** (NÃO 'Compartilhar' — são diferentes; só o Publicar gera o
     link). Copie o link que termina em **.ics** e cole aqui."* Quando colar, **reescreva**
     `.clockify/credentials.json` mantendo **todos** os campos já existentes (`api_key`,
     `workspace_id`, `user_id`) e só preenchendo `"ics_url"` com o link (ferramenta de arquivo). Valide rodando `... agenda --date <hoje>`: se vier
     `{"error":"ICS_ERROR",...}`, diga em linguagem simples que o link não funcionou (confirme
     que usou *Publicar* e que é o `.ics`) e ofereça tentar de novo ou pular.

**Manual rápido (só na 1ª conexão).** Se a pessoa acabou de conectar AGORA (colou a chave
nesta conversa), apresente o mini-manual de boas-vindas: leia
`${CLAUDE_PLUGIN_ROOT}/skills/clockify-tracking/references/manual-rapido.md` (ferramenta de
arquivo) e apresente-o **na língua da pessoa**, seguindo as regras de lá. É um onboarding de
~20 segundos; se ela já estava conectada (não colou chave agora), pule e siga normal.

Leia as preferências UMA vez: `... prefs get` → guarde `default` (pode ser `{}`) e a lista
`learned` (cada item tem `match` e `project`, às vezes `task`/`tag`/`billable`).

**Agenda ainda não conectada? Ofereça UMA vez (cobre quem já está conectado e entra direto
aqui).** Se a credencial não tem `ics_url` (ou `... agenda --date <hoje>` volta `{"ics": false}`),
**faça a pergunta** do passo 6 da Conexão — *"Posso me conectar à sua agenda do Outlook? Aí eu
já trago suas reuniões automaticamente e você não precisa ditar uma por uma. Quer conectar ou
prefere pular?"*. Se **sim**, conduza pelo passo 6 (link em **Publicar calendário**, NÃO
Compartilhar; grava `ics_url`). Se **pular**, siga normal e não insista de novo nesta conversa.

## Passo 0 — Um dia ou um período?

Pergunte em linguagem simples: **"Quer lançar as horas de hoje / de um dia, ou de um
período (vários dias)?"**. Um passo de cada vez.

## A) Um dia

0. **Resolva e CONFIRME a data** (ver seção "Datas"): obtenha a data alvo pelo `date` do
   terminal, cheque o dia da semana e confirme com a pessoa (*"é o dia X, certo?"*) ANTES de
   qualquer comando. Nunca calcule a data de cabeça.
1. **Agenda (se configurada).** Rode `... agenda --date AAAA-MM-DD`. Se `ics` for `true`,
   use os `eventos` (title/start/end) como ponto de partida: para cada um, escolha o destino
   pela precedência (aprendida → padrão → perguntar) e valide com `resolve --project`. Se
   `ics` for `false` ou a lista vazia, siga ditando normalmente. Avise: *"puxei o que reconheci
   da sua agenda; confira e ajuste."* (a recorrência é best-effort).
2. **Anti-duplicata:** `... entries --date AAAA-MM-DD`. Se `entries` não estiver vazio,
   avise o que já existe (sem jargão) e pergunte se continua.
3. A pessoa confirma ou dita as atividades com início e fim.
4. **Reconhecer cada atividade — por PRECEDÊNCIA:** (1) **aprendida** (match igual/contém →
   usa o `project` dela), (2) **padrão** (propõe a `default`), (3) **perguntar** o
   cliente/projeto. **Validar com** `... resolve --name "<tarefa>" --project "<projeto>"`
   (SEMPRE com `--project`; sem ele volta "projeto necessário"). Status:
   `OK` → resolvido; `AMBIGUO` → mostre os nomes dos `candidatos` e peça para escolher;
   `NAO_ENCONTRADO` → diga simples e pergunte o nome certo.
5. **Conferir:** mostre uma tabela limpa (atividade · cliente/projeto · duração) + total.
   Aceite ajustes.
6. **Gravar:** monte a lista de items `[{description, date "AAAA-MM-DD", start "HH:MM",
   end "HH:MM", task, project, tag?, billable?}]`. **Vários blocos da MESMA tarefa no mesmo
   dia (ex.: 09–10, 11–12, 13–18) são normais — cada um é um lançamento SEPARADO.** A
   anti-duplicata só pula **re-run idêntico** (mesma tarefa E mesmo horário de início).
   **NUNCA** diga que a ferramenta "junta/consolida lançamentos por tarefa ou por dia" —
   isso não acontece; nem peça à pessoa pra escolher entre fundir blocos. Rode primeiro
   `echo '<json>' | ... add --json - --dry-run` e confira; **só depois do "pode lançar"**,
   `echo '<json>' | ... add --json -`. Pela resposta: conte `gravados` de `total`; **só** se
   `pulados_duplicata` > 0, avise que itens idênticos já existiam e foram pulados; se
   `falhou_em` vier preenchido, explique simples (use `motivo`) e ofereça repetir só o resto.

## B) Um período (vários dias)

0. **Resolva e CONFIRME o intervalo** (ver seção "Datas"): calcule início e fim pelo `date` do
   terminal, cheque os dias da semana e confirme com a pessoa ANTES de tudo. Nunca de cabeça.
1. **Dias úteis:** `... business-days --start AAAA-MM-DD --end AAAA-MM-DD` → apresente `days`.
2. **Podar exceções** (feriados/férias) conversando.
3. **Anti-duplicata:** `... entries --start --end`; avise dias que já têm lançamento.
4. **Reconhecer atividades dia a dia** pela MESMA precedência do A.4: para cada dia, rode
   `... agenda --date AAAA-MM-DD` (igual ao fluxo A); se `ics` for `true`, use os eventos
   como ponto de partida; caso contrário, a pessoa dita. Valide com `resolve` sempre
   passando `--project`. Atalho: "mesma coisa nos próximos dias".
5. **Conferir** tabela por dia + total. Em lotes grandes, confirme totais antes.
6. **Gravar:** um único `add --json -` com TODOS os items de TODOS os dias (dry-run primeiro).
   Reporte como no A.5.

## Aprender um padrão (opcional, com consentimento)

Se uma palavra aparece sempre ligada ao mesmo destino, pergunte UMA vez: *"Toda vez que
aparecer 'X', já lanço em <projeto>?"*. Só com o "sim":
`... prefs learn --match "X" --project "<projeto>" [--task ...] [--tag ...] [--billable]`.

## Gerenciar o que eu sei

- **"O que você sabe sobre mim?"** → `... prefs get` e conte em linguagem natural.
- **Esquecer uma coisa** → confirme a palavra-chave e `... prefs forget --match "X"`; pela
  resposta, `removed:true` confirma, `false` diz que não havia nada.
- **Recomeçar do zero** (zerar atividade padrão + aprendizados, mantendo a conexão) →
  confirme que é irreversível e, **só após o "sim"**, rode `... prefs reset`. Confirme que
  recomeçou limpo.
- **Desconectar / apagar a chave** → confirme que isso remove a conexão deste projeto e é
  irreversível e, **só após o "sim"**, apague `.clockify/credentials.json` com a ferramenta
  de arquivo. Os aprendizados em `.clockify/prefs.json` permanecem — a não ser que a pessoa
  também peça "recomeçar do zero".

## Erros internos (culpa minha, não da pessoa)

Se um comando devolver `{"error":"INVALID_INPUT",...}` (ex.: data malformada que **eu** montei)
ou `{"error":"INVALID_ITEMS",...}` (JSON dos lançamentos malformado/sem campo obrigatório —
veja `reason`/`missing_at`), **fui eu que errei ao montar os dados**, não a pessoa. Corrijo
em silêncio (datas no formato AAAA-MM-DD, horas HH:MM, cada item com `date/start/end/task`) e
refaço — **sem** mostrar o erro técnico nem culpar a pessoa.

**Regras de ouro:** resolva datas pelo `date` do sistema e **confirme o dia da semana**
(nunca de cabeça); nunca grave sem conferir (dry-run antes); nunca apague sem confirmar;
nunca mostre JSON/IDs/jargão; fale na língua da pessoa; ao resolver, sempre passe `--project`.
