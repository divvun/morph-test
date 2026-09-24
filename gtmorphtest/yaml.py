#!/usr/bin/env python3
"""Yaml stuff."""


from collections import OrderedDict
from typing import IO, Any, Generator

import yaml


# Courtesy of https://gist.github.com/844388. Thanks!
class _OrderedDictYAMLLoader(yaml.Loader):
    """A YAML loader that loads mappings into ordered dictionaries."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Register the constructors that map YAML mappings to OrderedDicts."""
        yaml.Loader.__init__(self, *args, **kwargs)

        self.add_constructor("tag:yaml.org,2002:map",
                             type(self).construct_yaml_map)
        self.add_constructor("tag:yaml.org,2002:omap",
                             type(self).construct_yaml_map)

    def construct_yaml_map(
        self, node: yaml.Node,
    ) -> Generator[dict[Any, Any], None, None]:
        """Construct an OrderedDict from a YAML mapping node.

        Yields the (initially empty) dict before populating it so that
        recursive and self-referential structures can be resolved.

        Args:
            node: The YAML mapping node being constructed.

        Yields:
            The OrderedDict, empty on the first yield and filled afterwards.
        """
        data: OrderedDict[Any, Any] = OrderedDict()
        yield data
        value = self.construct_mapping(node)
        data.update(value)

    def construct_mapping(
        self, node: yaml.Node, deep: bool = False,
    ) -> OrderedDict[Any, Any]:
        """Build an OrderedDict from a mapping node, preserving key order.

        Args:
            node: The node to convert; must be a `yaml.MappingNode`.
            deep: Whether to construct child objects eagerly.

        Returns:
            An OrderedDict of the node's key/value pairs.

        Raises:
            yaml.constructor.ConstructorError: If the node is not a mapping,
                or if a key is not hashable.
        """
        if isinstance(node, yaml.MappingNode):
            self.flatten_mapping(node)
        else:
            raise yaml.constructor.ConstructorError(None, None,
                                                    "expected a mapping node, "
                                                    f"but found {node.id}",
                                                    node.start_mark)

        mapping = OrderedDict()
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                hash(key)
            except TypeError as exc:
                raise yaml.constructor.ConstructorError("while constructing "
                                                        "a mapping",
                                                        node.start_mark,
                                                        "found unacceptable "
                                                        "key"
                                                        f"({exc})",
                                                        key_node.start_mark)
            value = self.construct_object(value_node, deep=deep)
            mapping[key] = value
        return mapping


def yaml_load_ordered(f: IO[str] | str) -> Any:
    """Load a YAML document while preserving the order of its keys.

    Args:
        f: An open file object or a YAML string.

    Returns:
        The parsed document, with mappings as OrderedDicts.
    """
    return yaml.load(f, _OrderedDictYAMLLoader)


if __name__ == "__main__":
    pass
