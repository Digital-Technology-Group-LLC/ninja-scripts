import os
import requests
import sys
import json
import base64
import re

# Configuration from environment variables
NINJAONE_INSTANCE_URL = os.environ.get("NINJAONE_INSTANCE_URL") # e.g., https://eu.ninjarmm.com
NINJAONE_CLIENT_ID = os.environ.get("NINJAONE_CLIENT_ID")
NINJAONE_CLIENT_SECRET = os.environ.get("NINJAONE_CLIENT_SECRET")

def parse_powershell_metadata(content):
    metadata = {
        "description": "",
        "variables": [],
        "operatingSystems": [],
        "architecture": []
    }

    # Extract OS and Architecture from comments
    os_match = re.search(r'(?i)#\s*NINJA_OS:\s*([\w\s,]+)', content)
    if os_match:
        metadata["operatingSystems"] = [o.strip().upper() for o in os_match.group(1).split(',')]
    
    arch_match = re.search(r'(?i)#\s*NINJA_ARCH:\s*([\w\s,]+)', content)
    if arch_match:
        metadata["architecture"] = [a.strip().upper() for a in arch_match.group(1).split(',')]

    # Extract Comment-Based Help
    help_block = re.search(r'<#([\s\S]*?)#>', content)
    param_helps = {}
    if help_block:
        help_text = help_block.group(1)
        
        # Description
        desc_match = re.search(r'(?i)\.DESCRIPTION\s+([\s\S]*?)(?=\r?\n\s*\.|\r?\n\s*#>|\Z)', help_text)
        if desc_match:
            metadata["description"] = desc_match.group(1).strip()
        
        # Parameter descriptions from help
        param_matches = re.finditer(r'(?i)\.PARAMETER\s+(\w+)\s+([\s\S]*?)(?=\r?\n\s*\.|\r?\n\s*#>|\Z)', help_text)
        for m in param_matches:
            param_helps[m.group(1).lower()] = m.group(2).strip()

    # Extract Param block
    param_block = re.search(r'(?i)param\s*\(([\s\S]*?)\)', content)
    if param_block:
        params_text = param_block.group(1)
        # Match attributes, types and variables: [Attribute] [type] $Name = Default
        # Group 1: Attributes, Group 2: Type, Group 3: Name, Group 4: Default
        param_pattern = r'((?:\[[^\]]+\]\s*)*)(?:\[(\w+)\]\s*)?\$(\w+)(?:\s*=\s*([^,\r\n\)]+))?'
        matches = re.finditer(param_pattern, params_text)
        
        type_map = {
            'int': 'INTEGER',
            'string': 'TEXT',
            'bool': 'CHECKBOX',
            'switch': 'CHECKBOX',
            'decimal': 'DECIMAL',
            'double': 'DECIMAL',
            'float': 'DECIMAL',
            'datetime': 'DATETIME'
        }

        for m in matches:
            attributes = m.group(1) or ""
            p_type_raw = m.group(2).lower() if m.group(2) else "string"
            p_name = m.group(3)
            p_default = m.group(4).strip() if m.group(4) else None
            
            # Clean up default value (remove quotes)
            if p_default:
                p_default = p_default.strip("'\"")

            ninja_type = type_map.get(p_type_raw, 'TEXT')
            
            variable = {
                "name": p_name,
                "description": param_helps.get(p_name.lower(), f"Variable {p_name}"),
                "type": ninja_type,
                "required": False,
                "source": "LITERAL"
            }
            if p_default is not None:
                variable["defaultValue"] = p_default
            
            # Check for Mandatory in attributes
            if re.search(r'(?i)Mandatory\s*=\s*\$true', attributes):
                 variable["required"] = True

            metadata["variables"].append(variable)

    return metadata

def get_token():
    url = f"{NINJAONE_INSTANCE_URL}/oauth/token"
    payload = {
        'grant_type': 'client_credentials',
        'client_id': NINJAONE_CLIENT_ID,
        'client_secret': NINJAONE_CLIENT_SECRET,
        'scope': 'monitoring management control'
    }
    response = requests.post(url, data=payload)
    response.raise_for_status()
    return response.json()['access_token']

def get_scripts(token):
    url = f"{NINJAONE_INSTANCE_URL}/v2/automation/scripts"
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def sync_script(token, file_path, existing_scripts):
    file_name = os.path.basename(file_path)
    script_name = os.path.splitext(file_name)[0]
    extension = os.path.splitext(file_name)[1].lower()

    language_map = {
        '.ps1': 'POWERSHELL',
        '.sh': 'SHELL',
        '.bat': 'BATCH',
        '.cmd': 'BATCH'
    }

    if extension not in language_map:
        print(f"Skipping {file_path}: Unknown extension")
        return

    script_language = language_map[extension]

    with open(file_path, 'r') as f:
        script_text = f.read()

    # Parse metadata
    script_description = f"Synced from GitHub: {file_name}"
    script_variables = []
    metadata = {}
    
    if extension == '.ps1':
        metadata = parse_powershell_metadata(script_text)
        if metadata["description"]:
            script_description = metadata["description"]
        script_variables = metadata["variables"]

    # Find existing script by name
    existing_script = next((s for s in existing_scripts if s['name'] == script_name), None)

    # Preserve variable IDs if they exist to maintain task compatibility
    if existing_script and 'scriptVariables' in existing_script:
        id_map = {v['name']: v['id'] for v in existing_script['scriptVariables']}
        for v in script_variables:
            if v['name'] in id_map:
                v['id'] = id_map[v['name']]

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    payload = {
        "name": script_name,
        "description": script_description,
        "scriptConfig": {
            "scriptLanguage": script_language,
            "scriptText": script_text
        },
        "scriptVariables": script_variables
    }

    if metadata.get("operatingSystems"):
        payload["operatingSystems"] = metadata["operatingSystems"]
    if metadata.get("architecture"):
        payload["architecture"] = metadata["architecture"]

    if existing_script:
        # Update existing
        script_id = existing_script['id']
        url = f"{NINJAONE_INSTANCE_URL}/v2/automation/scripts/{script_id}"
        print(f"Updating existing script: {script_name} (ID: {script_id})")
        # Note: PUT might not be supported if it's not in the API yet, 
        # but usually it matches the resource.
        response = requests.put(url, headers=headers, json=payload)
    else:
        # Create new
        url = f"{NINJAONE_INSTANCE_URL}/v2/automation/scripts"
        print(f"Creating new script: {script_name}")
        response = requests.post(url, headers=headers, json=payload)

    if response.status_code not in [200, 201, 204]:
        print(f"Error syncing {script_name}: {response.status_code} - {response.text}")
    else:
        print(f"Successfully synced {script_name}")

if __name__ == "__main__":
    if not all([NINJAONE_INSTANCE_URL, NINJAONE_CLIENT_ID, NINJAONE_CLIENT_SECRET]):
        print("Missing required environment variables.")
        sys.exit(1)

    changed_files = sys.argv[1:]
    if not changed_files:
        print("No files to sync.")
        sys.exit(0)

    try:
        token = get_token()
        existing_scripts = get_scripts(token)

        for file_path in changed_files:
            if file_path.startswith('scripts/'):
                if os.path.isfile(file_path):
                    sync_script(token, file_path, existing_scripts)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
