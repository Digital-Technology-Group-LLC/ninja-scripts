# NinjaOne Script Change Plan Generator

This Python script automates the process of comparing local PowerShell scripts with the scripts in your NinjaOne instance. It generates a clear and actionable "change plan" that you can use to manually synchronize your scripts, ensuring your NinjaOne environment stays consistent with your version-controlled repository.

## Features

- **OAuth 2.0 Authentication**: Securely connects to the NinjaOne API using client credentials.
- **Intelligent PowerShell Parsing**: Automatically extracts script metadata directly from your `.ps1` files:
    - **Description**: Parses the `.DESCRIPTION` block from comment-based help.
    - **Parameters**: Parses the `Param()` block to define script variables, including their type, name, description, default value, and mandatory status.
    - **OS & Architecture**: Reads special comments (`# NINJA_OS:` and `# NINJA_ARCH:`) to determine target operating systems and architectures.
- **Change Detection**: Compares local scripts against the list of scripts in NinjaOne to identify what's new and what has changed.
- **Detailed Change Plan**:
    - For **new scripts**, it provides a complete guide for manual creation in the NinjaOne UI.
    - For **existing scripts**, it details the specific metadata differences (like description or parameters) that require a manual update.

## How It Works

The script performs a read-only comparison:

1.  It authenticates with the NinjaOne API to get an access token.
2.  It fetches a list of all scripts currently in your NinjaOne instance.
3.  It scans your local `scripts/` directory for PowerShell files.
4.  For each local script, it parses the file to build a "local" version of the script's metadata.
5.  It then compares this local version to the data fetched from NinjaOne and prints a detailed plan for any necessary manual creations or updates.

## Setup

1.  **Prerequisites**:
    - Python 3.6+
    - `requests` and `python-dotenv` libraries. Install them with:
      ```bash
      pip install requests python-dotenv
      ```

2.  **Configuration**:
    - Create a `.env` file in the root of this repository.
    - Add your NinjaOne API credentials to the `.env` file:
      ```env
      NINJAONE_INSTANCE_URL="https://app.ninjarmm.com"
      NINJAONE_CLIENT_ID="YOUR_CLIENT_ID"
      NINJAONE_CLIENT_SECRET="YOUR_CLIENT_SECRET"
      ```
      *(Replace with your actual instance URL if it's different)*

3.  **Directory Structure**:
    - Place your PowerShell scripts inside the `scripts/powershell/` directory. The script will automatically scan this location.

## Usage

To run the script and generate a change plan for all scripts, simply execute it from your terminal:

```bash
python sync_scripts.py
```

The script will output a series of change plans to the console, detailing the manual steps required to sync your local repository with NinjaOne.
