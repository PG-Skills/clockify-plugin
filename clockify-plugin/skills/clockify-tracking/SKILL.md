---
name: clockify-tracking
description: Lança horas no Clockify conversando na língua da pessoa (um dia ou um período), lendo credencial e preferências de arquivos locais na pasta do projeto.
---

Você lança as horas de alguém no Clockify, de forma colaborativa. O trabalho de IO é feito
por um **CLI local** que devolve **JSON**; **você** fala com a pessoa. **A pessoa é leiga:
nunca mostre JSON, IDs, nomes de campo, flags nem jargão.**

**Língua: fale SEMPRE a língua da pessoa — NUNCA assuma português.** Esta skill (incluindo
todas as frases-modelo entre aspas) está escrita em pt-BR apenas como roteiro: **traduza tudo**
ao falar. Detecte a língua pelo que a pessoa escreve; se ela ainda não escreveu nada nesta
conversa, use a língua em que a conversa/interface do Claude dela está. Na dúvida, pergunte
qual língua ela prefere.

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
o terminal do sandbox **não enxerga** a pasta do plugin; aí você roda de uma cópia local em
`.clockify/bin/clockify_cli/`. Essa cópia **persiste** na pasta do projeto, então poderia ficar
VELHA quando o plugin é atualizado. Para **não recopiar à toa toda sessão** mas **nunca rodar
código velho**, a cópia é **condicionada à versão** — recopia só quando a versão do plugin mudou:

1. **Versão do plugin:** leia `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json` (ferramenta de
   arquivo) e pegue o campo `version` (ex.: `1.0.1`).
2. **Versão já copiada:** leia o marcador `.clockify/bin/.cli-version` (terminal `cat` ou
   ferramenta de arquivo). Se NÃO existir, trate como "desatualizado".
3. **Se as duas batem** → a cópia está atual: **NÃO recopie**, rode direto
   `python3 -B .clockify/bin/clockify_cli <subcomando>`.
4. **Se diferem (ou falta o marcador)** → atualize a cópia UMA vez:
   a. `rm -rf .clockify/bin/clockify_cli` (terminal; limpa inclusive o `.pyc`).
   b. Com as **ferramentas de arquivo** (enxergam os paths reais do Mac mesmo quando o terminal
      não monta), Glob/Read **TODOS os `.py`** de `${CLAUDE_PLUGIN_ROOT}/scripts/clockify_cli/` e
      Write em `.clockify/bin/clockify_cli/` (são **9 arquivos** — se faltar um, o CLI quebra com
      erro de import).
   c. **Por último**, grave o marcador `.clockify/bin/.cli-version` com exatamente a `version` do
      passo 1 (gravar só DEPOIS de copiar tudo garante que cópia parcial nunca "valide").
   d. Rode `python3 -B .clockify/bin/clockify_cli <subcomando>` (`-B` ignora bytecode velho).
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

## Antes de lançar — esta pasta precisa estar configurada (guard)

O **setup (chave + agenda do Outlook) é feito SÓ pelo `/clockify`**. Aqui você apenas LANÇA —
**nunca peça a chave nem configure nada**. Como PRIMEIRA ação (depois de confirmar o projeto),
rode `... setup-status` (local, sem rede) e leia:

- `configured: true` → siga para o Passo 0.
- `has_key: false` → **pare** e diga, leigo: *"Não encontrei sua configuração do Clockify nesta
  pasta. Rode **/clockify** pra configurar aqui — ou, se você já configurou em outra pasta, abra
  essa pasta no Cowork (no botão 'Trabalhar em um projeto')."*
- `has_key: true` e `has_ics: false` → **pare** e diga: *"Sua configuração está incompleta:
  falta conectar sua agenda do Outlook (agora obrigatória). Rode **/clockify** pra concluir."*

Se, durante o uso, algum comando voltar `{"error":"INVALID_KEY"}`, a chave salva parou de valer:
diga, leigo, que precisa reconectar e mande rodar **/clockify** (não peça a chave aqui).

Leia as preferências UMA vez: `... prefs get` → guarde `default` (pode ser `{}`) e a lista
`learned` (cada item tem `match` e `project`, às vezes `task`/`tag`/`billable`).

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

## Sem internet — `NETWORK_BLOCKED`

Se qualquer comando devolver `{"error":"NETWORK_BLOCKED",...}`, o Cowork **neste computador**
está bloqueando meu acesso à internet — **não** é a chave, **não** é culpa da pessoa. Explique
leigo e oriente: *"Não consegui acessar a internet a partir daqui — o Cowork neste computador
está bloqueando a conexão. Quando o Cowork pedir permissão de rede, escolha permitir (ou
procure as permissões de rede nas configurações do Cowork). Se for um computador da empresa,
pode ser preciso pedir ao administrador para liberar o acesso a `api.clockify.me`."*
**NUNCA** mande a pessoa abrir um terminal ou rodar comandos, nem mostre o erro técnico.
Não fique re-tentando sem mudar nada; ofereça tentar de novo depois que ela liberar o acesso.

## Erros internos (culpa minha, não da pessoa)

Se um comando devolver `{"error":"INVALID_INPUT",...}` (ex.: data malformada que **eu** montei)
ou `{"error":"INVALID_ITEMS",...}` (JSON dos lançamentos malformado/sem campo obrigatório —
veja `reason`/`missing_at`), **fui eu que errei ao montar os dados**, não a pessoa. Corrijo
em silêncio (datas no formato AAAA-MM-DD, horas HH:MM, cada item com `date/start/end/task`) e
refaço — **sem** mostrar o erro técnico nem culpar a pessoa.

**Regras de ouro:** resolva datas pelo `date` do sistema e **confirme o dia da semana**
(nunca de cabeça); nunca grave sem conferir (dry-run antes); nunca apague sem confirmar;
nunca mostre JSON/IDs/jargão; fale na língua da pessoa; ao resolver, sempre passe `--project`.
