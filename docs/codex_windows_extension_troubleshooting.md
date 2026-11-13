# Native Windows Codex extension startup investigation

Investigated November 12, 2026. Drought and GIS processing were paused during this work.

## Confirmed cause and correction

Windows VS Code user settings contained:

```json
"chatgpt.cliExecutable": "/home/linuxbrew/.linuxbrew/bin/codex"
```

The extension host repeatedly reported `Error: spawn /home/linuxbrew/.linuxbrew/bin/codex ENOENT`. The Codex output log reported `Failed to spawn codex mcp process at /home/linuxbrew/.linuxbrew/bin/codex`, followed by requests to destroyed stdin and `Codex process is not available`. These are a failed backend launch followed by downstream errors. They occur before a usable backend exists; they do not implicate project data or ArcPy.

Removed only that override from the Windows user settings. All remaining settings were preserved and parsed to confirm equivalence. The extension can now choose its bundled Windows executable. No extension downgrade, authentication reset, conversation deletion, sandbox change, or MCP configuration change was performed.

The location is application-wide Windows user settings, rather than a setting in this repository. Therefore, this cause can affect other native Windows workspaces using the same settings/profile. No empty-workspace GUI comparison was performed. Linux can use the configured executable path; the separately working Agents host launches a different, Windows-native backend. Whether Settings Sync originally introduced the override was not established.

Uninstalling extension files leaves user settings intact, which explains why reinstalling stable/prerelease versions did not remove this failure. The official [OpenAI Docs settings reference](https://learn.chatgpt.com/docs/ide/settings) identifies this override as a development setting and cautions that overriding the bundled executable can break extension behavior.

## Evidence and backups

- Windows settings: `C:/Users/ALEJANDROSVEGANOGALE/AppData/Roaming/Code/User/settings.json`.
- Exact backup and change metadata: [settings_change.json](../output/codex_windows_diagnostics/settings_change.json). The backup is beside the user settings, outside the repository.
- Original Codex log: `C:/Users/ALEJANDROSVEGANOGALE/AppData/Roaming/Code/logs/20261112T200545/window1/exthost/openai.chatgpt/Codex.log`.
- Original extension-host log: `C:/Users/ALEJANDROSVEGANOGALE/AppData/Roaming/Code/logs/20261112T200545/window1/exthost/exthost.log`.
- Selected startup failures: [startup_failure_evidence.txt](../output/codex_windows_diagnostics/startup_failure_evidence.txt).
- Machine-local diagnostic evidence is under ignored [output/codex_windows_diagnostics](../output/codex_windows_diagnostics/). Do not publish full settings backups or unsanitized logs in a bug report.

## Validation

VS Code is 1.146.0 x64. Selected extension: `openai.chatgpt@26.51106.51428`. Its bundled native executable reports `codex-cli 0.167.0-alpha.4.1`.

A separate stdio app-server process was launched from this project with the existing user Codex configuration, without substituting a clean profile or disabling MCP servers. Only read-only startup/protocol requests were issued; no model turn or GIS processing was requested.

| Request | Result | Response time |
|---|---|---:|
| initialize | Native Windows initialization succeeded | 0.144 s |
| config/read | Configuration loaded; ArcGIS MCP entry present | 0.007 s |
| thread/list | Existing conversation listing succeeded | 0.002 s |
| mcpServerStatus/list | ArcGIS exposes 103 tools; other configured tool inventories returned | 1.408 s |

The probe completed in 1.584 seconds; diagnostic stderr was empty. See [bundled_app_server_probe.json](../output/codex_windows_diagnostics/bundled_app_server_probe.json) and [bundled_app_server_stderr.log](../output/codex_windows_diagnostics/bundled_app_server_stderr.log). Tool discovery confirms registration and startup; this probe did not execute an ArcGIS tool or validate a model response.

## Sidebar confirmation and further diagnostics

Run **Developer: Reload Window** in the affected VS Code window, then open Codex. The failed extension instance needs a fresh backend launch. This reload can briefly interrupt the current chat. Backend startup has been verified; sidebar rendering remains pending user confirmation.

If the sidebar still hangs, open **View → Output → Codex** and inspect the new entries after reload. Use **Developer: Open Logs Folder** to find the latest window's extension-host and renderer logs. Check **Preferences: Open User Settings (JSON)** for `chatgpt.cliExecutable`; it should remain absent. Also inspect profile settings if using a different profile. If the override returns, review Settings Sync and exclude this machine-specific executable override from syncing, or remove the override on each platform and use bundled executables.

Keep native Windows execution for ArcPy. Reopening this repository in WSL changes the runtime and does not verify the native Windows bridge.

## Older VSIX

The provided archive exists and its package manifest identifies publisher `openai`, extension `chatgpt`, version `26.51021.22027`, VS Code engine `^1.96.2`. Its SHA-256 is `1d61f22d00f1537abee70fd2437ec0c3e432a51395b067846110c89426576e09`. This is a local integrity fingerprint, not an independent signature/authenticity verification.

It was not installed: the invalid executable override would also affect an older extension, and the installed backend already passes startup checks. Retain it for a controlled regression comparison only if a fresh, correctly configured extension launch reveals a separate failure.
