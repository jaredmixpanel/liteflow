---
name: flow-auth
description: Manage service credentials (add, list, test, remove)
argument-hint: "<service | 'list' | 'test' | 'remove'> [service-name]"
allowed-tools: ["Bash", "Read"]
---

Handle credential management for workflow integrations. IMPORTANT: Never display actual credential values. Show masked versions only (e.g., `sk-****abcd`).

### `flow-auth list`
Run `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py auth list` to show all configured services with their credential type and status. Never show actual secret values.

### `flow-auth test <service-name>`
Run `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py auth test --service <service-name>` to test whether the stored credentials are valid. Report the result (valid/invalid/expired).

### `flow-auth remove <service-name>`
Run `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py auth remove --service <service-name>` to delete stored credentials for the service. Confirm with the user before removing.

### `flow-auth <service-name>` (set up credentials)
Interactively set up credentials for a service:
1. Ask the user for the credential type: token, webhook URL, or service account JSON.
2. Ask the user for the credential value.
3. Store it via `python ${CLAUDE_PLUGIN_ROOT}/lib/cli.py auth set --service <service-name> --token <value>`.
4. Confirm storage and suggest testing with `flow-auth test <service-name>`.

If no argument is provided, run `flow-auth list` by default.
