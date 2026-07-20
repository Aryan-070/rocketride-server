import json5
import sys
import os
from typing import Dict, Any
from rocketlib import getServiceDefinition, IJson


class Config:
    """
    Loads and parses the aiconfig.json file (deprecated).
    """

    _config: Dict[str, Any] | None = None

    # Profile name assumed for a node that declares no profiles of its own
    DEFAULT_PROFILE = 'default'

    @staticmethod
    def getModelCacheFolder():
        """
        Get the model cache folder.

        This is where we will store the models.
        """
        # Get the base directory
        base = sys.base_exec_prefix

        # Get the models folder
        folder = base + '/' + 'models'

        # If it does not exist, create it
        if not os.path.exists(folder):
            # Create the directory
            os.makedirs(folder)

        # Return it
        return folder

    @staticmethod
    def getConfig(force_reload=False) -> Dict:
        """
        Read the aiconfig.json file and returns a dictionary with the values.

        Args:
                force_reload (bool, optional): If set to true,
                the config file will be read from disk even if
                it has already been loaded.

        Returns:
                Dict: Configuration dictionary
        """
        # If it is already loaded, return it
        if Config._config is not None and not force_reload:
            return Config._config

        # Get the path
        path = os.path.dirname(os.path.abspath(__file__))

        # Build the config file name
        configPath = os.path.join(path, '..', 'aiconfig.json')

        # Read the json file
        with open(configPath) as f:
            jsonStr = f.read()
            f.close()

        # parse JSON object as a dictionary
        Config._config = json5.loads(jsonStr)

        # Return the config
        return Config._config

    @staticmethod
    def getNodeConfig(logicalType: str, connConfig: Dict):
        """
        Get the resolved configuration for a node.

        On entry, connConfig is of the following forms:

                {
                        "profile": "myProfile",     a profile from the node's type:"enum" field,
                                                    plus any overrides under that profile key:
                        "myProfile": {
                                "model": "myModel"
                        }
                }

        or
                {
                        the direct configuration like:
                        "model": "myModel"
                }

        The node's profiles live in its "config" (a type:"enum" field). Each
        branch supplies preset defaults -- field defaults plus a runtime-only
        "preset" block. Those defaults are merged under connConfig, so keys the
        user provides win over the defaults.

        * If no "profile" key is given, the default profile is the enum field's
        own default and connConfig is used directly.
        * If a "profile" key is given, its defaults come from that branch and are
        merged under connConfig[profile].
        """

        def merge(userConfig: Dict[str, Any], defaultConfig: Dict[str, Any]) -> Dict[str, Any]:
            """
            Recursively merge userConfig with defaultConfig.

            - Unspecified or None values in userConfig are replaced with those in defaultConfig.
            - If both values are dictionaries, merge them recursively.
            """
            merged = defaultConfig.copy()

            for key, userValue in userConfig.items():
                defaultValue = defaultConfig.get(key)

                if isinstance(defaultValue, dict) or isinstance(defaultValue, IJson):
                    # Recursively merge nested dictionaries
                    merged[key] = merge(userValue, defaultValue)
                elif userValue is not None:
                    # Override with user value if it's not None
                    merged[key] = userValue

            return merged

        # Output the requested configuration
        service = getServiceDefinition(logicalType)

        # If we couldn't get it, error out
        if service is None:
            raise Exception(f'The service {logicalType} was not found')

        # See if there is a profile key in the configuration
        profile = connConfig.get('profile', None)

        # Resolve the selected profile (explicit, else the enum field's own
        # default) and its preset defaults from the node's "config".
        resolvedProfile, defaultConfig = Config._resolveProfile(service, profile)

        if profile is None:
            # Use the connConfig directly as it is not using profiles
            userConfig = connConfig

            # Some UIs nest a node's fields under a sub-object named after the
            # default profile (e.g. connConfig["default"] = {"instructions": [...]})
            # instead of at the top level. That nesting is otherwise invisible
            # here — merge() below never descends into it — so those fields would
            # be lost. Overlay the nested object's keys as a lower-priority layer,
            # with real top-level keys still winning, so both shapes resolve.
            # No-op unless such a sub-object exists.
            nested = connConfig.get(resolvedProfile)
            if isinstance(nested, (dict, IJson)):
                combined = dict(IJson.toDict(nested) if isinstance(nested, IJson) else nested)
                for key, value in connConfig.items():
                    # Only real (non-None) top-level values override the nested block; a
                    # None placeholder must not clobber a populated nested value.
                    if key != resolvedProfile and value is not None:
                        combined[key] = value
                userConfig = combined
        else:
            # Overrides for the chosen profile live under its key.
            userConfig = connConfig.get(profile, {})
            if not userConfig:
                userConfig = {}

        # Merge the preset defaults under the user configuration
        return merge(userConfig, defaultConfig)

    @staticmethod
    def _resolveProfile(service: Dict, profile):
        """
        Resolve a config-based node's profile.

        Returns ``(profileName, presets)``. Locates the type:"enum" profile
        field, selects the requested branch (or the field's own default), and
        collects that branch's preset values: a runtime-only "preset" block plus
        each node-local field default (inline ``{"field", "default"}`` overrides
        and local ``fields`` entries). A field default that lives only in a
        global definition contributes nothing (it falls back at read time).

        A node need not declare profiles at all (no type:"enum" field); it then
        has no presets and its profile name is the implicit ``default``, which is
        the sub-object name the caller looks under for the nested config shape.
        """
        fields = service.get('fields') or {}

        # The profile selector is a fields entry of type "enum".
        enumFields = [f for f in fields.values() if isinstance(f, (dict, IJson)) and f.get('type') == 'enum']
        if not enumFields:
            return profile or Config.DEFAULT_PROFILE, {}

        # Pick the enum that owns this profile; else the first, using its default.
        if profile:
            enumField = next((f for f in enumFields if profile in (f.get('enum') or {})), enumFields[0])
        else:
            enumField = enumFields[0]
            profile = enumField.get('default')

        branch = (enumField.get('enum') or {}).get(profile)
        if not isinstance(branch, (dict, IJson)):
            return profile or Config.DEFAULT_PROFILE, {}

        def leaf(fieldId: str) -> str:
            return fieldId.rsplit('.', 1)[-1]

        preset: Dict[str, Any] = {}

        # Runtime-only preset values declared on the branch (never emitted to the
        # schema); merged first so config field defaults can still override.
        branchPreset = branch.get('preset')
        if isinstance(branchPreset, (dict, IJson)):
            preset.update(IJson.toDict(branchPreset) if isinstance(branchPreset, IJson) else dict(branchPreset))

        for entry in branch.get('config') or []:
            if isinstance(entry, str):
                fdef = fields.get(entry)
                if isinstance(fdef, (dict, IJson)) and 'default' in fdef:
                    preset[leaf(entry)] = fdef['default']
            elif isinstance(entry, (dict, IJson)) and 'field' in entry:
                if 'default' in entry:
                    preset[leaf(entry['field'])] = entry['default']
                else:
                    fdef = fields.get(entry['field'])
                    if isinstance(fdef, (dict, IJson)) and 'default' in fdef:
                        preset[leaf(entry['field'])] = fdef['default']
        return profile, preset

    @staticmethod
    def getProviderConfig(providerConfig: Dict[str, any]):
        """
        Get the provider and the configuration for the provider.

        {
                "provider": "embedding_transformer",
                "embedding_transformer": {
                        "model": "..."
                }
        }
        """
        # Get the provider
        provider = providerConfig.get('provider')
        if not provider:
            raise Exception('Provider config does not have a provider specified')

        # It may actually be None, but it needs to be there
        if provider in providerConfig:
            connConfig = providerConfig.get(provider)
        elif 'config' in providerConfig:
            connConfig = providerConfig.get('config')
        else:
            raise Exception(f'Config not specified for provider {provider}')

        # Return the provider and the configuration
        return provider, connConfig

    @staticmethod
    def getMultiProviderConfig(section: str, multiConfig: Dict[str, any]):
        """
        Get the provider and the configuration for the provider for the given section.

            "embedding": {
                    "provider": "embedding_transformer",
                    "embedding_transformer": {
                            "model": "..."
                    }
            },
            "preprocessor": {
                    "provider": "langchain",
                    "langchain": {
                            "profile": "string",
                            "tokens": 512
                    }
            }
        """
        # Get the driver we are looking for
        config = multiConfig.get(section)
        if not config:
            raise Exception(f'Multiconfig does not have the {section} section')

        # Get the provider from it
        return Config.getProviderConfig(config)
