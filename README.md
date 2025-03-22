# Home Assistant Crestron Integration

![Crestron Logo](custom_components/crestron/brand/logo.svg)

Control your Crestron devices through Home Assistant.

## About

This integration allows you to control Crestron devices through Home Assistant using the Crestron REST API. Currently, it supports controlling shades, with plans to add support for more device types in the future.

## Features

- **Shade Control**: Open, close, stop, and set specific positions for your Crestron-connected shades
- **Discovery**: Automatic discovery of Crestron hubs on your network
- **Status Updates**: Regular updates of device status
- **User Interface**: Full UI configuration with no YAML required
- **Reliability**: Robust error handling and automatic reconnection

## Installation

See the detailed [installation instructions](custom_components/crestron/README.md) in the integration folder.

## Usage

After installation, the integration adds entities for each Crestron shade to Home Assistant.

### Available Services

- **crestron.set_position**: Set the position of a shade
- **crestron.open_shade**: Open a shade
- **crestron.close_shade**: Close a shade
- **crestron.stop_shade**: Stop a shade

## Development

This integration follows the Home Assistant development standards and meets the requirements for a platinum-level integration.

To contribute:
1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## License

[MIT License](LICENSE)

## Resources

- [Home Assistant](https://www.home-assistant.io/)
- [Crestron](https://www.crestron.com/)
