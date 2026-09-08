# NOVA Language Support (VS Code)

Editor support for the [NOVA](https://github.com/ieeecsopen/NOVA)
programming language.

## Features

| Feature | How it works |
| :--- | :--- |
| **Syntax highlighting** | TextMate grammar (`syntaxes/nova.tmLanguage.json`). Works with no toolchain installed. |
| **Live diagnostics** | Starts `nova lsp` and shows type / effect / capability errors as you type. |
| **Completion** | Keywords, the prelude capabilities (`Runtime`, `Clock`, `Filesystem`, `Network`), core types. |
| **Formatting** | `Format Document` runs `nova fmt`. |
| **Commands** | `NOVA: Check`, `NOVA: Run current file`, `NOVA: Build current file` (in the editor context menu and command palette). |

The language server is intentionally minimal today — no hover, no
go-to-definition. See [`../../lsp/README.md`](../../lsp/README.md).

## Requirements

The `nova` toolchain must be reachable. If it is not on your `PATH`, set
**`nova.toolchainPath`** in settings to an absolute path — for a repo
checkout that is the `nova` script at the repo root.

Diagnostics can be turned off with **`nova.languageServer.enabled: false`**
(syntax highlighting stays).

## Building from source

```bash
cd editors/vscode
npm install
npm run build          # bundle to out/extension.js
npm run package        # produce nova-lang-<version>.vsix
```

Then in VS Code: **Extensions → … → Install from VSIX…**, or press `F5`
in this folder to launch an Extension Development Host.

## License

Apache-2.0, same as NOVA.
