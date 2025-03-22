# Crestron Integration for Home Assistant

This integration allows Home Assistant to control Crestron shades through the Crestron API.

## Features

- Control Crestron shades (open, close, set position, stop)
- Automatic discovery of Crestron hubs via zeroconf
- Regular status updates from the Crestron API
- Robust error handling and automatic reconnection

## Installation

### Manual Installation

1. Copy the `crestron` folder to your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Go to **Settings** > **Devices & Services** > **Add Integration** and search for "Crestron".

### HACS Installation

1. Make sure [HACS](https://hacs.xyz/) is installed.
2. Add this repository as a custom repository in HACS:
   - Go to HACS > Integrations > ⋮ > Custom repositories
   - Add `https://github.com/stack-four/ha-crestron` as a repository with category "Integration"
3. Click on "Download" to install the integration.
4. Restart Home Assistant.
5. Go to **Settings** > **Devices & Services** > **Add Integration** and search for "Crestron".

## Configuration

The integration can be set up via the UI:

1. Go to **Settings** > **Devices & Services** > **Add Integration**.
2. Search for "Crestron" and select it.
3. Enter the following information:
   - **Host**: The IP address of your Crestron hub (e.g., 192.168.10.200)
   - **Authentication Token**: The authentication token for the API
   - **Scan Interval**: How often to poll for updates (in seconds)
4. Click on "Submit" to add the integration.

## Usage

### Entities

The integration creates cover entities for each shade connected to your Crestron hub. The entities support the following features:
- Open
- Close
- Stop
- Set position

### Services

The integration provides the following services:

- **crestron.set_position**: Set the position of a specific shade.
- **crestron.open_shade**: Open a specific shade.
- **crestron.close_shade**: Close a specific shade.
- **crestron.stop_shade**: Stop a specific shade.

Example service call:
```yaml
service: crestron.set_position
data:
  shade_id: 1
  position: 50
```

## Troubleshooting

If you encounter issues:

1. Check your connection to the Crestron hub.
2. Verify the authentication token.
3. Restart Home Assistant.
4. Check the Home Assistant logs for any error messages related to the Crestron integration.
5. If you see any issues, please report them on the [GitHub issue tracker](https://github.com/stack-four/ha-crestron/issues).

## Acknowledgements

This integration uses the Crestron REST API to communicate with Crestron hardware.