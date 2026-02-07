# NinjaOne Script Synchronization

This repository contains automation scripts for the NinjaOne MSP platform. These scripts are automatically synchronized with the NinjaOne Script Library whenever changes are pushed to the `main` branch.

## Directory Structure

- `scripts/powershell/`: PowerShell scripts (.ps1)
- `scripts/bash/`: Bash scripts (.sh)
- `scripts/cmd/`: Batch scripts (.bat, .cmd)

## How to add a new script

1. Create a new script file in the appropriate directory under `scripts/`.
2. The name of the file (without extension) will be used as the script name in NinjaOne.
3. Commit and push your changes to the `main` branch.

## Script Metadata (PowerShell)

The synchronization engine automatically extracts metadata from PowerShell scripts to configure NinjaOne UI settings.

### Supported Tags

| Feature | PowerShell Construct | NinjaOne Usage |
|---------|-----------------------|----------------|
| **Description** | `.DESCRIPTION` in help block | Populates the "Description" field in NinjaOne. |
| **Variables** | `param()` block variables | Creates Script Variables (Parameters). |
| **Var Description**| `.PARAMETER <Name>` in help | Hover-over info for the variable. |
| **Var Type** | `[int]`, `[string]`, `[bool]` | Sets variable type (INTEGER, TEXT, CHECKBOX). |
| **Default Value**| `$Var = "Value"` | Sets the default value in NinjaOne. |
| **Required** | `[Parameter(Mandatory=$true)]`| Marks the variable as required. |
| **OS Support** | `# NINJA_OS: WINDOWS, MAC` | Sets applicable Operating Systems. |
| **Architecture** | `# NINJA_ARCH: X64` | Sets applicable Architectures. |

### Example Structure

```powershell
<#
.SYNOPSIS
    My Awesome Script
.DESCRIPTION
    This script performs complex operations.
.PARAMETER ServerId
    The ID of the server to target.
#>

# NINJA_OS: WINDOWS
# NINJA_ARCH: X64

param(
    [Parameter(Mandatory=$true)]
    [int]$ServerId = 1234
)
```

## Configuration

The GitHub Action requires the following secrets to be configured in the repository:

- `NINJAONE_INSTANCE_URL`: Your NinjaOne instance URL (e.g., `https://eu.ninjarmm.com` or `https://app.ninjarmm.com`).
- `NINJAONE_CLIENT_ID`: Your API Client ID.
- `NINJAONE_CLIENT_SECRET`: Your API Client Secret.

### NinjaOne Portal Setup
When creating the **Client App** in NinjaOne, use the following settings:
- **Application Platform**: `API Services (machine-to-machine)`
- **Allowed Grant Types**: `Client credentials`
- **Scopes**: `Monitoring`, `Management`, `Control`

Make sure your API Client has the following scopes:
- `monitoring`
- `management`
- `control`
- `automation` (if available)

## Sync Script

The synchronization is handled by `sync_scripts.py`. This script checks for existing scripts in your NinjaOne library by name; if a script with the same name exists, it updates it. Otherwise, it creates a new one.
