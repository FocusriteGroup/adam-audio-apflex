import yaml

class VTSClient:
    """
    A client class to load configuration from a YAML file and convert it into a dictionary.
    """

    def __init__(self, config_path):
        """
        Initialize the VTSClient with the path to the YAML configuration file.

        Args:
            config_path (str): Path to the YAML configuration file.
        """
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self):
        """
        Load the configuration from the YAML file and return it as a dictionary.

        Returns:
            dict: Configuration dictionary.
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                config_data = yaml.safe_load(file)
                return config_data.get('config', {})
        except Exception as e:
            raise RuntimeError(f"Failed to load configuration: {e}")

# Example usage:
# client = VTSClient("c:\\Users\\ThiloRode\\OneDrive - Focusrite Group\\Dokumente\\Repos\\Audio-Precision\\config.yml")
# print(client.config)