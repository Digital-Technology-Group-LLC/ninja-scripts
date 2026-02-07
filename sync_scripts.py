import os
import requests
import sys
import json
import base64
import re
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Configuration from environment variables
NINJAONE_INSTANCE_URL = os.environ.get("NINJAONE_INSTANCE_URL") # e.g., https://app.ninjarmm.com
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

def log_change_plan(local, remote):
    """Logs a pretty change set of what needs to be updated in the UI."""
    script_name = local['name']
    print("\n" + "="*60)
    print(f"CHANGE PLAN for '{script_name}'")
    print("="*60)
    print("Manual update required in NinjaOne Web UI. Current API does not support script creation or updates.\n")

    # Compare Description
    if local.get('description') != remote.get('description'):
        print("  - DESCRIPTION:")
        print(f"    - CURRENT : {remote.get('description', '')}")
        print(f"    + PROPOSED: {local.get('description', '')}")

    # Note that code cannot be compared
    print("  - SCRIPT CODE:")
    print("    ~ The API does not allow fetching remote script code, so a manual comparison is required.")

    # Compare Script Variables
    def normalize_vars(variables):
        # Normalize for comparison, ignoring fields that might not exist or differ in non-critical ways
        return sorted([
            {
                "name": v.get("name"),
                "description": v.get("description"),
                "type": v.get("type"),
                "required": v.get("required", False),
                "defaultValue": v.get("defaultValue", None) # Use None for consistent comparison
            } for v in variables
        ], key=lambda x: x['name'])

    local_vars = normalize_vars(local.get('scriptVariables', []))
    remote_vars = normalize_vars(remote.get('scriptVariables', []))

    if local_vars != remote_vars:
        print("  - SCRIPT PARAMETERS (VARIABLES):")
        remote_vars_map = {v['name']: v for v in remote_vars}
        for l_var in local_vars:
            r_var = remote_vars_map.get(l_var['name'])
            if not r_var:
                print(f"    + ADD: Parameter '{l_var['name']}'")
                print(f"      - Details: {l_var}")
            elif l_var != r_var:
                print(f"    ~ MODIFY: Parameter '{l_var['name']}'")
                for key in l_var:
                    # Use .get() to avoid KeyErrors if a key is missing
                    if l_var.get(key) != r_var.get(key):
                        print(f"      - {key}: {r_var.get(key)}")
                        print(f"      + {key}: {l_var.get(key)}")
        
        local_vars_map = {v['name']: v for v in local_vars}
        for r_var in remote_vars:
            if r_var['name'] not in local_vars_map:
                print(f"    - REMOVE: Parameter '{r_var['name']}'")

    print("="*60 + "\n")



def sync_script(token, file_path, existing_scripts_list):
    file_name = os.path.basename(file_path)
    script_name = os.path.splitext(file_name)[0]
    extension = os.path.splitext(file_name)[1].lower()

    language_map = {
        '.ps1': 'powershell',
        '.sh': 'shell',
        '.bat': 'batch',
        '.cmd': 'batch'
    }

    if extension not in language_map:
        print(f"Skipping {file_path}: Unknown extension")
        return

    script_language = language_map[extension]

    with open(file_path, 'r', encoding='utf-8') as f:
        script_text = f.read()

    # Parse metadata
    metadata = parse_powershell_metadata(script_text) if extension == '.ps1' else {}
    
    # Find existing script by name in the list
    existing_script = next((s for s in existing_scripts_list if s['name'] == script_name), None)

    # Prepare local payload representation
    encoded_code = base64.b64encode(script_text.encode('utf-8')).decode('utf-8')

    architectures = []
    if "X86" in metadata.get("architecture", []):
        architectures.append("32")
    if "AMD64" in metadata.get("architecture", []):
        architectures.append("64")

    operating_systems = []
    if "WINDOWS" in metadata.get("operatingSystems", []):
        operating_systems.append("Windows")
    if "MAC" in metadata.get("operatingSystems", []):
        operating_systems.append("Mac")
    if "LINUX" in metadata.get("operatingSystems", []):
        operating_systems.append("Linux")

    script_variables = []
    for var_meta in metadata.get("variables", []):
        script_variables.append({
            "name": var_meta['name'],
            "description": var_meta.get('description', ''),
            "type": var_meta.get('type', 'TEXT'),
            "source": "LITERAL",
            "defaultValue": var_meta.get('defaultValue'),
            "required": var_meta.get('required', False),
            "valueList": []
        })

    local_payload = {
        "name": script_name,
        "description": metadata.get("description", f"From {file_name}"),
        "language": script_language,
        "operatingSystems": operating_systems,
        "architecture": architectures,
        "code": encoded_code,
        "scriptVariables": script_variables
    }

    if existing_script:
        # Script exists, generate change plan based on metadata comparison
        print(f"Found existing script '{script_name}' (ID: {existing_script['id']}). Comparing metadata...")
        log_change_plan(local_payload, existing_script)
    else:
        # Script does not exist, log a plan to create it
        print("\n" + "="*60)
        print(f"CHANGE PLAN for '{script_name}' (NEW SCRIPT)")
        print("="*60)
        print("This script does not exist in NinjaOne. Manual creation is required.\n")
        print("  - Name: " + local_payload['name'])
        print("  - Description: " + local_payload['description'])
        print("  - Language: " + local_payload['language'])
        print("  - Operating Systems: " + ", ".join(local_payload['operatingSystems']))
        print("  - Architecture: " + ", ".join(local_payload['architecture']))
        print("\n  - Parameters to create:")
        for var in local_payload['scriptVariables']:
            print(f"    - {var['name']} (Type: {var['type']}, Required: {var['required']})")
        print("\n  - Code: Copy the contents of the local file.")
        print("="*60 + "\n")

def main():
    """Main function to run the sync process."""
    if not all([NINJAONE_INSTANCE_URL, NINJAONE_CLIENT_ID, NINJAONE_CLIENT_SECRET]):
        print("ERROR: Required environment variables (NINJAONE_INSTANCE_URL, NINJAONE_CLIENT_ID, NINJAONE_CLIENT_SECRET) are not set.", file=sys.stderr)
        sys.exit(1)

    try:
        token = get_token()
        print("Successfully authenticated with NinjaOne.")
        
        print("Fetching list of existing scripts from NinjaOne...")
        existing_scripts = get_scripts(token)
        print(f"Found {len(existing_scripts)} existing scripts.")

    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to communicate with NinjaOne API. {e}", file=sys.stderr)
        sys.exit(1)

    scripts_dir = 'scripts'
    if not os.path.isdir(scripts_dir):
        print(f"ERROR: '{scripts_dir}' directory not found.", file=sys.stderr)
        sys.exit(1)
    
    print(f"\nScanning '{scripts_dir}' directory for scripts to process...")
    for root, _, files in os.walk(scripts_dir):
        for file in files:
            file_path = os.path.join(root, file)
            sync_script(token, file_path, existing_scripts)

if __name__ == "__main__":
    main()
