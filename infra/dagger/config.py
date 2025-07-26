# infra/dagger/config.py

from pathlib import Path

import yaml


def _load_yaml(filename, key):
    """
    Loads a YAML file and returns the value for the given top-level key.
    Searches in repo root and infra/dagger/.
    """
    search_paths = [Path(filename), Path(__file__).parent / filename]
    for path in search_paths:
        if path.exists():
            with open(path) as f:
                data = yaml.safe_load(f)
                if key not in data:
                    raise KeyError(f"Key '{key}' not found in {filename}")
                return data[key]
    raise FileNotFoundError(f"{filename} not found in repo root or infra/dagger/")


def load_services_config():
    return _load_yaml("services.yaml", "services")


def load_pipelines_config():
    return _load_yaml("pipelines.yaml", "pipelines")
