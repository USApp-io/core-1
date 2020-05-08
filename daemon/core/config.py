"""
Common support for configurable CORE objects.
"""

import logging
from collections import OrderedDict
from typing import TYPE_CHECKING, Dict, List, Tuple, Type, Union

from core.emane.nodes import EmaneNet
from core.emulator.enumerations import ConfigDataTypes
from core.nodes.network import WlanNode

if TYPE_CHECKING:
    from core.location.mobility import WirelessModel

    WirelessModelType = Type[WirelessModel]


class ConfigGroup:
    """
    Defines configuration group tabs used for display by ConfigurationOptions.
    """

    def __init__(self, name: str, start: int, stop: int) -> None:
        """
        Creates a ConfigGroup object.

        :param name: configuration group display name
        :param start: configurations start index for this group
        :param stop: configurations stop index for this group
        """
        self.name = name
        self.start = start
        self.stop = stop


class Configuration:
    """
    Represents a configuration options.
    """

    def __init__(
        self,
        _id: str,
        _type: ConfigDataTypes,
        label: str = None,
        default: str = "",
        options: List[str] = None,
    ) -> None:
        """
        Creates a Configuration object.

        :param _id: unique name for configuration
        :param _type: configuration data type
        :param label: configuration label for display
        :param default: default value for configuration
        :param options: list options if this is a configuration with a combobox
        """
        self.id = _id
        self.type = _type
        self.default = default
        if not options:
            options = []
        self.options = options
        if not label:
            label = _id
        self.label = label

    def __str__(self):
        return f"{self.__class__.__name__}(id={self.id}, type={self.type}, default={self.default}, options={self.options})"


class ConfigurableOptions:
    """
    Provides a base for defining configuration options within CORE.
    """

    name = None
    bitmap = None
    options = []

    @classmethod
    def configurations(cls) -> List[Configuration]:
        """
        Provides the configurations for this class.

        :return: configurations
        """
        return cls.options

    @classmethod
    def config_groups(cls) -> List[ConfigGroup]:
        """
        Defines how configurations are grouped.

        :return: configuration group definition
        """
        return [ConfigGroup("Options", 1, len(cls.configurations()))]

    @classmethod
    def default_values(cls) -> Dict[str, str]:
        """
        Provides an ordered mapping of configuration keys to default values.

        :return: ordered configuration mapping default values
        """
        return OrderedDict(
            [(config.id, config.default) for config in cls.configurations()]
        )


class ConfigurableManager:
    """
    Provides convenience methods for storing and retrieving configuration options for
    nodes.
    """

    _default_node = -1
    _default_type = _default_node

    def __init__(self) -> None:
        """
        Creates a ConfigurableManager object.
        """
        self.node_configurations = {}

    def nodes(self) -> List[int]:
        """
        Retrieves the ids of all node configurations known by this manager.

        :return: list of node ids
        """
        return [x for x in self.node_configurations if x != self._default_node]

    def config_reset(self, node_id: int = None) -> None:
        """
        Clears all configurations or configuration for a specific node.

        :param node_id: node id to clear configurations for, default is None and clears all configurations
        :return: nothing
        """
        if not node_id:
            self.node_configurations.clear()
        elif node_id in self.node_configurations:
            self.node_configurations.pop(node_id)

    def set_config(
        self,
        _id: str,
        value: str,
        node_id: int = _default_node,
        config_type: str = _default_type,
    ) -> None:
        """
        Set a specific configuration value for a node and configuration type.

        :param _id: configuration key
        :param value: configuration value
        :param node_id: node id to store configuration for
        :param config_type: configuration type to store configuration for
        :return: nothing
        """
        node_configs = self.node_configurations.setdefault(node_id, OrderedDict())
        node_type_configs = node_configs.setdefault(config_type, OrderedDict())
        node_type_configs[_id] = value

    def set_configs(
        self,
        config: Dict[str, str],
        node_id: int = _default_node,
        config_type: str = _default_type,
    ) -> None:
        """
        Set configurations for a node and configuration type.

        :param config: configurations to set
        :param node_id: node id to store configuration for
        :param config_type: configuration type to store configuration for
        :return: nothing
        """
        logging.debug(
            "setting config for node(%s) type(%s): %s", node_id, config_type, config
        )
        node_configs = self.node_configurations.setdefault(node_id, OrderedDict())
        node_configs[config_type] = config

    def get_config(
        self,
        _id: str,
        node_id: int = _default_node,
        config_type: str = _default_type,
        default: str = None,
    ) -> str:
        """
        Retrieves a specific configuration for a node and configuration type.

        :param _id: specific configuration to retrieve
        :param node_id: node id to store configuration for
        :param config_type: configuration type to store configuration for
        :param default: default value to return when value is not found
        :return: configuration value
        """
        result = default
        node_type_configs = self.get_configs(node_id, config_type)
        if node_type_configs:
            result = node_type_configs.get(_id, default)
        return result

    def get_configs(
        self, node_id: int = _default_node, config_type: str = _default_type
    ) -> Dict[str, str]:
        """
        Retrieve configurations for a node and configuration type.

        :param node_id: node id to store configuration for
        :param config_type: configuration type to store configuration for
        :return: configurations
        """
        result = None
        node_configs = self.node_configurations.get(node_id)
        if node_configs:
            result = node_configs.get(config_type)
        return result

    def get_all_configs(self, node_id: int = _default_node) -> List[Dict[str, str]]:
        """
        Retrieve all current configuration types for a node.

        :param node_id: node id to retrieve configurations for
        :return: all configuration types for a node
        """
        return self.node_configurations.get(node_id)


class ModelManager(ConfigurableManager):
    """
    Helps handle setting models for nodes and managing their model configurations.
    """

    def __init__(self) -> None:
        """
        Creates a ModelManager object.
        """
        super().__init__()
        self.models = {}
        self.node_models = {}

    def set_model_config(
        self, node_id: int, model_name: str, config: Dict[str, str] = None
    ) -> None:
        """
        Set configuration data for a model.

        :param node_id: node id to set model configuration for
        :param model_name: model to set configuration for
        :param config: configuration data to set for model
        :return: nothing
        """
        # get model class to configure
        model_class = self.models.get(model_name)
        if not model_class:
            raise ValueError(f"{model_name} is an invalid model")

        # retrieve default values
        model_config = self.get_model_config(node_id, model_name)
        if not config:
            config = {}
        for key in config:
            value = config[key]
            model_config[key] = value

        # set as node model for startup
        self.node_models[node_id] = model_name

        # set configuration
        self.set_configs(model_config, node_id=node_id, config_type=model_name)

    def get_model_config(self, node_id: int, model_name: str) -> Dict[str, str]:
        """
        Retrieve configuration data for a model.

        :param node_id: node id to set model configuration for
        :param model_name: model to set configuration for
        :return: current model configuration for node
        """
        # get model class to configure
        model_class = self.models.get(model_name)
        if not model_class:
            raise ValueError(f"{model_name} is an invalid model")

        config = self.get_configs(node_id=node_id, config_type=model_name)
        if not config:
            # set default values, when not already set
            config = model_class.default_values()
            self.set_configs(config, node_id=node_id, config_type=model_name)

        return config

    def set_model(
        self,
        node: Union[WlanNode, EmaneNet],
        model_class: "WirelessModelType",
        config: Dict[str, str] = None,
    ) -> None:
        """
        Set model and model configuration for node.

        :param node: node to set model for
        :param model_class: model class to set for node
        :param config: model configuration, None for default configuration
        :return: nothing
        """
        logging.debug(
            "setting model(%s) for node(%s): %s", model_class.name, node.id, config
        )
        self.set_model_config(node.id, model_class.name, config)
        config = self.get_model_config(node.id, model_class.name)
        node.setmodel(model_class, config)

    def get_models(
        self, node: Union[WlanNode, EmaneNet]
    ) -> List[Tuple[Type, Dict[str, str]]]:
        """
        Return a list of model classes and values for a net if one has been
        configured. This is invoked when exporting a session to XML.

        :param node: network node to get models for
        :return: list of model and values tuples for the network node
        """
        all_configs = self.get_all_configs(node.id)
        if not all_configs:
            all_configs = {}

        models = []
        for model_name in all_configs:
            config = all_configs[model_name]
            if model_name == ModelManager._default_node:
                continue
            model_class = self.models[model_name]
            models.append((model_class, config))

        logging.debug("models for node(%s): %s", node.id, models)
        return models
