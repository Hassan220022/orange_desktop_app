<!-- gitnexus:start -->
# GitNexus — Code Intelligence (CLI Only)

This project is indexed by GitNexus as **orange_desktop_app** (8191 symbols, 14693 relationships, 298 execution flows).

**IMPORTANT: ALWAYS use the `gitnexus` CLI via shell commands. NEVER use GitNexus MCP or code-review-graph MCP tools in this repository.** The local CLI is installed at `/opt/homebrew/bin/gitnexus`, and all GitNexus operations must go through CLI commands.

Because multiple repositories are indexed globally, every graph command for this repo must include `-r orange_desktop_app`.

> If the index is stale, run `gitnexus analyze` in terminal first, then rerun the GitNexus command.

## Always Do

- **MUST run `gitnexus status` at the start of code work** to confirm the index is available and current.
- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus impact -r orange_desktop_app -d upstream <symbol>` and report the blast radius to the user.
- **MUST run `gitnexus detect-changes -r orange_desktop_app --scope all` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, run `gitnexus query -r orange_desktop_app "<concept>"` before Grep/Glob/Read.
- When you need full context on a specific symbol, run `gitnexus context -r orange_desktop_app <symbolName>`.

## Never Do

- NEVER use GitNexus MCP tools, code-review-graph MCP tools, or `gitnexus://...` MCP resources for this repo.
- NEVER edit a function, class, or method without first running `gitnexus impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER commit changes without running `gitnexus detect-changes` to check affected scope.

## CLI Commands

All commands require `-r orange_desktop_app` because multiple repos are indexed.

| Command | Use when |
|---------|---------|
| `gitnexus analyze` | Index or re-index the repository |
| `gitnexus status` | Check if index is up-to-date |
| `gitnexus list` | List all indexed repositories |
| `gitnexus query -r orange_desktop_app "<concept>"` | Find execution flows by concept |
| `gitnexus context -r orange_desktop_app <symbol>` | 360-degree view of a symbol |
| `gitnexus impact -r orange_desktop_app -d upstream\|downstream <symbol>` | Blast radius analysis |
| `gitnexus detect-changes -r orange_desktop_app --scope all` | Analyze uncommitted git changes |
| `gitnexus wiki` | Generate repository wiki |
| `gitnexus clean` | Delete index for current repo |
| `gitnexus doctor` | Check runtime capabilities |

<!-- gitnexus:end -->
