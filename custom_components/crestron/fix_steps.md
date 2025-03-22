# Steps to Fix the Crestron Integration

The main issue was that the integration was trying to import a non-existent package named "crestron" in the config_flow.py file. Here's what we've fixed:

## 1. Run the Repository Fix Script

First, you'll need to run one of the fix structure scripts we created in the root directory:

For PowerShell:
```powershell
.\fix_structure.ps1
```

Or for Bash:
```bash
bash fix_structure.sh
```

This will fix the config flow issues and ensure proper HACS compatibility.

## 2. Fix Config Flow Error

The "Config flow could not be loaded" error happens because:
1. The config_flow.py file was trying to import a package called "crestron" which doesn't exist
2. The flow uses a step_id "authToken" but the front-end expects "password"

We've fixed these issues by:
1. Updating the config_flow.py file to use our internal API module instead of an external crestron package
2. Changing the step_id from "authToken" to "password" to match Home Assistant's expectations
3. Simplifying the validation process for host and token

## 3. Align API Classes and Methods

We've updated the following modules to ensure they all work together:
- api.py - Added a has_shade method
- api_errors.py - Created proper error classes
- coordinator.py - Simplified data handling
- entity.py - Updated to work with the dictionary-based shade data
- shade.py - Updated to use the API directly for actions

## 4. Manifest Updates

Updated the manifest.json file to correctly reference:
- The stack-four GitHub repository
- stack-four as the code owner
- Required dependencies

## 5. Next Steps

After applying these fixes, you should:

1. Restart Home Assistant
2. Try to add the integration again through the UI
3. If you still encounter issues, check the Home Assistant logs for specific errors

The integration should now function correctly and be compatible with HACS for easy installation.