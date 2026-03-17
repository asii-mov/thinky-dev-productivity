# Cursor — Manual Onboarding

Cursor stores global settings in an internal database that cannot be configured via scripts. The setup script handles project-level rules automatically, but global settings require manual configuration.

## What the setup script does

- Copies `.mdc` rule files from this repo into your project's `.cursor/rules/` directory
- These rules are applied automatically when Cursor opens the project

## What you need to do manually

### 1. Model Configuration

1. Open Cursor
2. Go to **Cursor > Settings > Cursor Settings > Models**
3. Configure your preferred model (Claude, GPT-4, etc.)
4. If using AWS Bedrock: configure the API endpoint under model provider settings

### 2. API Key Setup

1. Go to **Cursor > Settings > Cursor Settings > Models**
2. Enter your API key for the configured provider
3. Alternatively, if your org provides a shared API proxy, enter that endpoint

### 3. Privacy Settings

1. Go to **Cursor > Settings > Cursor Settings > General > Privacy Mode**
2. Enable **Privacy Mode** if required by your org's data handling policy
3. This ensures code is not stored on Cursor's servers

### 4. Verify Rules Are Loaded

1. Open a project where setup.sh has been run
2. Check that `.cursor/rules/` contains the org rule files
3. Rules with `alwaysApply: true` will be active immediately
