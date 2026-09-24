#!/usr/bin/env python3
"""Test file."""

from collections import OrderedDict
from typing import Any, NamedTuple

from .utils import invert_dict, string_to_list


class TestCase(NamedTuple):
    """One test case: an input form and the forms it should produce."""

    input: str
    outputs: list[str]


class TestFile:
    """Accessor for one parsed test file.

    Wraps the raw data loaded from a YAML or lexc test file and exposes
    the test cases in both directions, plus the transducer paths and
    lookup command configured for the selected system section.
    """
    def __init__(
        self, data: dict[str, Any], system: str = "hfst",
    ) -> None:
        """Initialise testfile with file data and system.

        Args:
            data: Parsed test file, with `Tests` and optional `Config` keys.
            system: Which `Config` section to read, e.g. `hfst` or `xerox`.
        """
        self.data: dict[str, Any] = data
        self._system: str = system

    @property
    def surface_tests(self) -> OrderedDict[str, list[TestCase]]:
        """The test cases keyed by surface form.

        Returns:
            An OrderedDict mapping each test title to a list of TestCase
            entries whose input is a surface form and whose outputs are the
            expected analyses.
        """
        tests = OrderedDict()
        for title, cases in self.data["Tests"].items():
            new_cases = []
            for surface, lexical in cases.items():
                new_cases.append(TestCase(input=surface,
                                          outputs=string_to_list(lexical)))
            tests[title] = new_cases
        return tests

    @property
    def lexical_tests(self) -> OrderedDict[str, list[TestCase]]:
        """The test cases keyed by lexical form.

        Returns:
            An OrderedDict mapping each test title to a list of TestCase
            entries.
        """
        tests = OrderedDict()
        for title, cases in self.data["Tests"].items():
            new_cases = []
            for lexical, surface in invert_dict(cases).items():
                new_cases.append(TestCase(input=lexical,
                                          outputs=string_to_list(surface)))
            tests[title] = new_cases
        return tests

    @property
    def gen(self) -> str | None:
        """Path to the generator transducer, or None if not configured."""
        return self.data.get("Config", {}).get(self._system,
                                               {}).get("Gen", None)

    @property
    def morph(self) -> str | None:
        """Path to the analyser transducer, or None if not configured."""
        return self.data.get("Config", {}).get(self._system,
                                               {}).get("Morph", None)

    @property
    def app(self) -> list[str]:
        """The lookup command to run, as a list of arguments.

        Returns:
            The command and its flags, e.g. `["hfst-lookup"]`.

        Raises:
            Exception: If no command is configured and the system is not one
                of the known defaults.
        """
        a = self.data.get("Config", {}).get(self._system, {}).get("App", None)
        if a is None:
            if self._system == "hfst":
                return ["hfst-lookup"]
            elif self._system == "xerox":
                return ["lookup", "-flags", "mbTT"]
            else:
                raise ValueError(f"Unknown system: '{self._system}'")
        return a


if __name__ == "__main__":
    pass
