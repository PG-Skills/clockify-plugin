# clockify-plugin

> Lança suas horas no Clockify automaticamente, a partir da sua agenda do Outlook —
> conversando com o Claude Code. Cada pessoa pluga as próprias credenciais;
> **nada seu fica no repositório.**

Ferramenta interna da **PG**, desenvolvida pelo time **AI Product Innovation**.
Funciona em **macOS, Windows e Linux**.

## O que ele faz

- 📅 Lê sua agenda do **Outlook** (link ICS) e transforma as reuniões do dia em lançamentos no **Clockify**.
- ✅ Mostra tudo em **simulação** primeiro — só grava depois do seu "pode lançar".
- 🧠 **Aprende** suas atividades recorrentes (ex.: "daily do projeto X" → projeto/tarefa certos), pra perguntar cada vez menos.
- 🗓️ Lança **um dia** (`/horas`) ou **vários de uma vez** (`/lancar`, ótimo pra fechar o mês retroativo).

## Pré-requisito (1 minuto): instalar o `uv`

A única dependência é o **`uv`**. **Você não precisa ter Python instalado** — o `uv` baixa um Python gerenciado sozinho.

- **macOS / Linux:**
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **Windows (PowerShell):**
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

Se você esquecer, o `/clockify-setup` avisa e mostra como instalar.

## Instalar (3 comandos no Claude Code)

```
/plugin marketplace add https://github.com/PG-Skills/clockify-plugin.git
/plugin install clockify-plugin@pg-clockify
/clockify-setup
```

- O `/clockify-setup` faz um **onboarding guiado**: sua API key do Clockify, o link ICS do Outlook (opcional) e uma atividade padrão (opcional). No fim, ele **valida** a configuração pra você.
- A CLI Python que faz o trabalho pesado **se instala sozinha** na primeira sessão (via `uv`). Você não precisa mexer nela.

## Usar no dia a dia

| Comando | O que faz |
|---|---|
| `/horas` | Lança **hoje** a partir da agenda do Outlook. |
| `/horas 2026-01-28` | Lança um **dia específico**. |
| `/lancar` | Lança **vários dias** de uma vez (ex.: o mês inteiro). Funciona **sem** ICS. |
| `/clockify-setup` | Reconfigura credenciais, ICS ou a atividade padrão. |

Em qualquer fluxo, o Claude **mostra um resumo** do que vai lançar e **espera sua confirmação** antes de gravar. Lançamento duplicado é evitado automaticamente (ele checa o que já existe no dia).

## Onde ficam os seus dados

Tudo é **por-usuário e fica fora do repositório**:

- **Sua config** (API key, ICS, atividade padrão):
  `~/.config/clockify-plugin/config.json` (macOS/Linux) ou
  `%APPDATA%\clockify-plugin\config.json` (Windows).
- **Atividades aprendidas** (palavra-chave → projeto/tarefa):
  `~/.config/clockify-plugin/learned.json` (ou `%APPDATA%`), só na sua máquina.

A **atividade padrão é opcional**: quem atua em vários clientes sem uma tarefa dominante pode
pular — o plugin aprende sozinho a cada lançamento. Não há **nenhum** dado de cliente nem
credencial no repositório.

## Problemas comuns

- **"Configuração faltando…"** → rode `/clockify-setup` (ou `clockify-plugin config doctor` pra um diagnóstico).
- **`uv` não encontrado** → instale o `uv` (seção acima) e abra uma nova sessão.
- **Lançou no projeto/tarefa errado** → ensine a atividade certa: o plugin pergunta e passa a
  reconhecer sozinho. Por baixo, isso vira uma entrada em `learned.json`.
- **O mesmo nome de tarefa existe em mais de um projeto** → qualifique pelo projeto
  (o `/clockify-setup` e o fluxo perguntam quando há ambiguidade).

---

## Para mantenedores / desenvolvedores

O "cérebro" é o slash command (orquestra a conversa); o "IO confiável" é uma CLI Python fina
(`clockify-plugin`). Código em `plugins/clockify-plugin/`.

```bash
cd plugins/clockify-plugin
uv sync
uv run pytest -q
uv run ruff check .
uv run pyright
uv run clockify-plugin --help
```

CLI direta (uso avançado):

```bash
clockify-plugin config show
clockify-plugin config doctor
clockify-plugin agenda --date 2026-01-28
clockify-plugin workspaces
clockify-plugin meta
clockify-plugin entries --date 2026-01-28
clockify-plugin business-days --start 2026-05-01 --end 2026-05-31
clockify-plugin add --file lancamentos.json --dry-run
clockify-plugin learned list
```

Variáveis de ambiente (`CLOCKIFY_API_KEY`, `CLOCKIFY_WORKSPACE_ID`, `OUTLOOK_ICS_URL`) têm
precedência sobre o arquivo de config (útil em CI).

Política de versão e processo de release: ver **`MAINTAINER.md`**.

---

<sub>Desenvolvido pelo time **AI Product Innovation** da PG.</sub>
