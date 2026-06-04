---
name: clockify-setup
description: Onboarding guiado do clockify-horas — configura credenciais Clockify, link ICS do Outlook e defaults (tarefa/etiqueta/faturável) por-usuário, com verificação final. Use na primeira vez ou para reconfigurar.
---

# Setup guiado do clockify-horas

Conduza a configuração inicial em português, **um passo de cada vez**, sempre delegando o
I/O ao subcomando `clockify-horas config`. Nunca escreva o arquivo de config diretamente.

## Pré-checagem

1. Rode `clockify-horas config path` para descobrir onde a config vai morar e mostre à pessoa.
   - Se o comando **não existir**, a CLI não foi instalada. Isso é raro (o plugin instala via
     SessionStart hook). A única dependência é o **`uv`** — **não é preciso ter Python**: o
     `uv` baixa um Python gerenciado sozinho. Cheque o `uv` (`command -v uv` no macOS/Linux,
     `Get-Command uv` no Windows). Se faltar, **ofereça instalá-lo para a pessoa (com
     consentimento)** rodando o instalador oficial do SO detectado:
     - **macOS/Linux:** `curl -LsSf https://astral.sh/uv/install.sh | sh`
     - **Windows (PowerShell):** `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
     Depois de instalar o `uv`, peça para **reabrir a sessão do Claude Code** (o SessionStart
     hook então instala a CLI — baixando o Python se necessário). Se mesmo assim o
     `clockify-horas` não estiver no PATH, rode `uv tool update-shell` e reabra o terminal.
2. Rode `clockify-horas config show`. Se já houver config, pergunte se a pessoa quer
   **reconfigurar** (sobrescreve campos) ou sair.

## Passos

1. **API key.** Explique o caminho: Clockify → canto inferior esquerdo (perfil) →
   *Preferences* → aba *Advanced* (ou *Profile Settings → API*) → *Generate*. Peça a key e
   rode `clockify-horas config set --api-key "<KEY>"`.

2. **Workspace.** Rode `clockify-horas meta`. Ele lista os workspaces e metadados.
   - Se o `meta` falhar com erro de auth, a key está errada — volte ao passo 1.
   - Se houver só **um** workspace, defina-o sozinho (sem perguntar).
   - Se houver vários, liste-os **numerados** e peça o número.
   - Grave com `clockify-horas config set --workspace-id "<ID>"`.
   - Reexecute `clockify-horas meta` se necessário para obter os metadados do workspace certo.

3. **Link ICS do Outlook.** Explique: Outlook web → *Configurações* → *Calendário* →
   *Calendários compartilhados* → *Publicar um calendário* → escolha o calendário e a
   permissão → copie o link **.ics** (ICS, não o HTML). Peça o link e rode
   `clockify-horas config set --ics-url "<URL>"`. Diga que isso é opcional para quem só usa
   `/lancar`, mas necessário para `/horas`.

4. **Defaults.** A partir da saída de `meta`, mostre as **tarefas** e **etiquetas** reais
   como listas **numeradas**. Peça:
   - tarefa padrão (número) → `--task "<nome>"`
   - etiqueta padrão (número) → `--tag "<nome>"`
   - faturável por padrão? (sim/não) → `--billable` ou `--no-billable`
   - meta diária de horas (Enter para 8) → `--daily-target <n>`
   Grave tudo numa chamada: `clockify-horas config set --task "..." --tag "..." --no-billable --daily-target 8`.

5. **Overrides de cliente (opcional, pulável).** Pergunte: "Quer pré-declarar algum cliente
   com tarefa/etiqueta/faturável diferentes do padrão? (pode pular e adicionar depois)".
   - Default: pular. Se sim, para cada cliente: peça palavra-chave (`match`), tarefa,
     etiqueta e faturável, e rode
     `clockify-horas config add-override --match "..." --task "..." --tag "..." --billable`.
   - Valide os nomes contra `meta`.

6. **Prova.** Rode `clockify-horas config doctor` e mostre o resumo. Linhas `OK` = ótimo;
   `WARN` de ICS é aceitável para quem não usa `/horas`; qualquer `FAIL` precisa ser
   corrigido (volte ao passo correspondente). Ofereça rodar `/horas <hoje>` em **dry-run**
   para a pessoa ver o fluxo sem gravar nada.

Ao final, diga que a pessoa já pode usar `/horas` (um dia via Outlook) e `/lancar`
(vários dias). Reconfigurar é só rodar `/clockify-setup` de novo.
