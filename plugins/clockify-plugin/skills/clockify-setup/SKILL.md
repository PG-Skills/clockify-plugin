---
name: clockify-setup
description: Onboarding guiado do clockify-plugin — configura credenciais Clockify, link ICS do Outlook (opcional) e uma atividade padrão (opcional), com verificação final. Use na primeira vez ou para reconfigurar.
---

# Setup guiado do clockify-plugin

Conduza a configuração inicial em **português simples, sem jargão**, um passo de cada vez,
sempre delegando o I/O ao subcomando `clockify-plugin config`. Nunca escreva o arquivo de
config diretamente. **A pessoa é leiga: explique cada coisa em uma frase e deixe pular o que
for opcional.** São **3 perguntas**.

## Pré-checagem

1. Rode `clockify-plugin config path` para descobrir onde a config vai morar e mostre à pessoa.
   - Se o comando **não existir**, a CLI não foi instalada. Isso é raro (o plugin instala via
     SessionStart hook). A única dependência é o **`uv`** — **não é preciso ter Python**: o
     `uv` baixa um Python gerenciado sozinho. Cheque o `uv` (`command -v uv` no macOS/Linux,
     `Get-Command uv` no Windows). Se faltar, **ofereça instalá-lo (com consentimento)**:
     - **macOS/Linux:** `curl -LsSf https://astral.sh/uv/install.sh | sh`
     - **Windows (PowerShell):** `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
     Depois, peça para **reabrir a sessão do Claude Code** (o hook instala a CLI). Se mesmo
     assim não estiver no PATH, rode `uv tool update-shell` e reabra o terminal.
2. Rode `clockify-plugin config show`. Se já houver config, pergunte se a pessoa quer
   **reconfigurar** (sobrescreve campos) ou sair.

## Pergunta 1 — Conectar ao Clockify

"Cola sua chave do Clockify aqui. Onde pegar: abra o Clockify → canto superior direito
(seu perfil) → *Preferences* → aba *Advanced* (ou *Profile Settings → API*) → *Generate*."
Pegue a key e rode `clockify-plugin config set --api-key "<KEY>"`.

Depois, descubra o workspace: rode `clockify-plugin workspaces` (precisa só da api key).
- Se a key falhar (erro de auth), está errada — peça de novo.
- Se houver **um** workspace, escolha-o sozinho (sem perguntar).
- Se houver **vários**, liste-os **numerados** e peça o número.
Grave com `clockify-plugin config set --workspace-id "<ID>"`.

## Pergunta 2 — Agenda do Outlook (opcional, pode pular)

"Quer que eu puxe sua agenda automática? Cola o link do calendário publicado — ou **pula**,
que aí você me dita as horas e funciona igual."
- Como pegar o link: Outlook web → *Configurações* → *Calendário* → *Calendários
  compartilhados* → *Publicar um calendário* → escolha o calendário e a permissão → copie o
  link **.ics** (o ICS, não o HTML).
- Se a pessoa colar o link: `clockify-plugin config set --ics-url "<URL>"`.
- Se pular: não grave nada. (Sem ICS, `/horas` funciona pela ditada e `/lancar` funciona
  normalmente.)

## Pergunta 3 — Atividade padrão (opcional)

Explique e deixe pular: "Quer configurar uma **atividade padrão**? É a tarefa que entra na
maioria dos seus lançamentos — útil se a maior parte do seu dia é uma coisa só (ex.: trabalho
interno), porque você não reinforma toda vez. **Se você atua em vários projetos/clientes sem
uma atividade dominante, pode pular** — aí eu aprendo suas atividades conforme você lança e
pergunto quando precisar."

- Se **sim**: a partir da saída de `clockify-plugin meta`, mostre as **tarefas** e
  **etiquetas** reais como listas **numeradas**. Atenção ao formato: em `meta`, `tasks` vem
  com chave `"<projectId> :: <nome da tarefa>"` — use no `--task` **somente o nome da tarefa**
  (a parte depois de ` :: `), nunca o `projectId`. `tags` vem como `nome → id` — use o nome.
  Pergunte: tarefa padrão (número), etiqueta padrão (número), e "essas horas são faturáveis?
  (sim/não)". Grave numa chamada:
  `clockify-plugin config set --task "<nome da tarefa>" --tag "<nome da etiqueta>" --billable`
  (use `--no-billable` se não for faturável). **Só** se a tarefa escolhida existir em mais de
  um projeto, pergunte o projeto e acrescente `--project "<nome do projeto>"`; se for de nome
  único, não toque nisso (invisível).
- Se **não**: não grave nada. A meta diária fica 8h silenciosa (ajustável depois com
  `clockify-plugin config set --daily-target <n>`, se a pessoa pedir).

## Prova final

Rode `clockify-plugin config doctor` e mostre o resultado **em linguagem comum**. Tudo `OK` =
ótimo; `WARN` de ICS é normal para quem pulou a agenda; "sem atividade padrão" é normal para
quem pulou a pergunta 3; qualquer `FAIL` precisa ser corrigido (volte à pergunta
correspondente).

Ao final, diga em português comum: "Testei, tá tudo certo! ✅ Agora é só `/horas` (lança o
dia) ou `/lancar` (vários dias)." Reconfigurar é só rodar `/clockify-setup` de novo.
