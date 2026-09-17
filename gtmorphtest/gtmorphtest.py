#!/usr/bin/env python3
"""Run the YAML test cases for morphology and morphophonology tests.

Reads a test file (YAML, or lexc with inline test comments), runs every
listed form through the configured transducers with an external lookup
tool, and reports which analyses and generated forms were missing,
unexpected, or explicitly unwanted.

License: CC0 (see LICENSE)
"""

from __future__ import annotations

import os
import os.path
import re
import shutil
import sys
from argparse import ArgumentParser, Namespace
from collections import OrderedDict
from collections.abc import Generator, Iterable, Mapping
from io import StringIO
from subprocess import PIPE, Popen
from typing import IO, Any, NamedTuple, NoReturn

import yaml

from . import __version__


class TestCase(NamedTuple):
    """One test case: an input form and the forms it should produce."""

    input: str
    outputs: list[str]


# SUPPORT FUNCTIONS

def string_to_list(data: bytes | str | list[str]) -> list[str]:
    """Normalise a scalar or sequence into a list of strings.

    Args:
        data: Bytes, a string, or an already-iterable value.

    Returns:
        A single-item list for bytes (decoded as UTF-8) or str input;
        otherwise `data` unchanged.
    """
    if isinstance(data, bytes):
        return [data.decode("utf-8")]
    elif isinstance(data, str):
        return [data]
    else:
        return data


def invert_dict(
    data: Mapping[str, str | list[str]],
) -> OrderedDict[str, list[str]]:
    """Invert a mapping, grouping the original keys under each value.

    Args:
        data: Mapping of key to a value or list of values.

    Returns:
        An OrderedDict mapping each value to the list of keys that
        pointed at it, in first-seen order.
    """
    tmp: OrderedDict[str, list[str]] = OrderedDict()
    for key, val in data.items():
        for v in string_to_list(val):
            d = tmp.setdefault(v, [])
            if key not in d:
                d.append(key)
    return tmp


COLORS: dict[str, str] = {
    "red": "\033[1;31m",
    "green": "\033[0;32m",
    "orange": "\033[0;33m",
    "yellow": "\033[1;33m",
    "blue": "\033[0;34m",
    "light_blue": "\033[0;36m",
    "reset": "\033[m"
}

def colourise(string: str, *args: Any, **kwargs: Any) -> str:
    """Format a string, exposing the ANSI colour codes as named fields.

    Args:
        string: A `str.format` template.
        *args: Positional arguments passed to `str.format`.
        **kwargs: Extra named fields; overridden by the colour names.

    Returns:
        The formatted string.
    """
    kwargs.update(COLORS)
    return string.format(*args, **kwargs)

def check_path_exists(program: str) -> str:
    """Locate an executable on $PATH.

    Args:
        program: Name of the executable to look for.

    Returns:
        The full path to the executable.

    Raises:
        EnvironmentError: If the program is not on $PATH.
    """
    out = shutil.which(program)
    if out is None:
        raise EnvironmentError(f"Cannot find `{program}`. Check $PATH.")
    return out

# SUPPORT CLASSES

class LookupError(Exception):
    """Raised when the external lookup tool exits with an error."""

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
                raise Exception(f"Unknown system: '{self._system}'")
        return a

class MorphTest:
    """Runs the test cases in a test file against the transducers.

    Loads the configuration, feeds every test input through the lookup
    tool once per direction, then compares the results against the
    expected (and explicitly unwanted) forms. Output is accumulated in
    one of the nested formatter classes rather than printed directly;
    `str(test)` returns everything collected so far.
    """
    class AllOutput():
        """Base output formatter, collecting text in an in-memory buffer.

        Only the summary line is implemented here. Subclasses override the
        per-test hooks (`title`, `success`, `failure`, `result`) to produce
        the various output styles; the no-op defaults mean a subclass can
        stay silent about anything it does not care to report.
        """
        def __init__(self, args: Namespace) -> None:
            """Args:
                args: The parsed command-line arguments.
            """
            self._io: StringIO = StringIO()
            self.args: Namespace = args

        def __str__(self) -> str:
            """Return everything written to this formatter so far."""
            return self._io.getvalue()

        def write(self, data: str) -> None:
            """Append raw text to the output buffer."""
            self._io.write(data)

        def info(self, data: str) -> None:
            """Report a progress or diagnostic message."""
            self.write(data)

        def title(self, *args: Any) -> None:
            """Write title."""
            pass

        def success(self, *args: Any) -> None:
            """Write success."""
            pass

        def failure(self, *args: Any) -> None:
            """Write failure."""
            pass

        def result(self, *args: Any) -> None:
            """Write results."""
            pass

        def final_result(self, hfst: MorphTest) -> None:
            """Write the overall pass/fail totals.

            Args:
                hfst: The MorphTest instance holding the `passes` and `fails`
                    counts.
            """
            self.write(colourise("Total passes: {green}{passes}{reset}, "
                                 "Total fails: {red}{fails}{reset}, "
                                 "Total: {light_blue}{total}{reset}\n",
                                 passes=hfst.passes,
                                 fails=hfst.fails,
                                 total=hfst.fails+hfst.passes))

    class NormalOutput(AllOutput):
        """Verbose formatter: one line per test case, plus per-test totals."""
        def title(self, text: str) -> None:
            """Write an underlined heading for a test."""
            self.write(colourise("{light_blue}-" * len(text) + "\n"))
            self.write(text + "\n")
            self.write(colourise("-" * len(text) + "{reset}\n"))

        def success(
            self, case: int, total: int, left: str, right: str,
        ) -> None:
            """Report one passing case.

            Args:
                case: Index of this case within the test, starting at 1.
                total: Number of cases in the test.
                left: The input form.
                right: The produced form.
            """
            x = colourise(("[{light_blue}{case:>%d}/{total}{reset}]"
                           "[{green}PASS{reset}]"
                           "{left} {blue}=>{reset} {right}\n") %
                          len(str(total)),
                          left=left, right=right, case=case, total=total)
            self.write(x)

        def failure(
            self, case: int, total: int, left: str, right: str,
            errlist: Iterable[str],
        ) -> None:
            """Report one failing case.

            Args:
                case: Index of this case within the test, starting at 1.
                total: Number of cases in the test.
                left: The input form.
                right: A short description of the kind of failure.
                errlist: The offending forms.
            """
            x = colourise(("[{light_blue}{case:>%d}/{total}{reset}]"
                           "[{red}FAIL{reset}] " +
                           "{left} {blue}=>{reset} {right}: {errlist}\n") %
                          len(str(total)),
                          left=left, right=right, case=case, total=total,
                          errlist=", ".join(errlist))
            self.write(x)

        def result(
            self, title: str, test: str, counts: dict[str, int],
        ) -> None:
            """Write the pass/fail totals for one test.

            Args:
                title: The full test heading.
                test: The test identifier used in the summary line.
                counts: Mapping with `Pass` and `Fail` counts.
            """
            p = counts["Pass"]
            f = counts["Fail"]
            text = colourise("\nTest {n} - Passes: {green}{passes}{reset}, "
                             "Fails: {red}{fails}{reset}, "
                             "Total: {light_blue}{total}{reset}\n",
                             n=test, passes=p, fails=f, total=p+f)
            self.write(text)

    class CompactOutput(AllOutput):
        """One line per test: a PASS/FAIL marker and the counts."""
        def result(
            self, title: str, test: str, counts: dict[str, int],
        ) -> None:
            """Write a single PASS or FAIL line summarising the test."""
            p = counts["Pass"]
            f = counts["Fail"]
            out = f"{title} {p}/{f}/{p+f}"
            if counts["Fail"] > 0:
                if not self.args.hide_fail:
                    self.write(colourise("[{red}FAIL{reset}] {}\n", out))
            elif not self.args.hide_pass:
                self.write(colourise("[{green}PASS{reset}] {}\n", out))

    class TerseOutput(AllOutput):
        """One character per case (`.` or `!`), then a final verdict."""
        def success(
            self, case: int, total: int, l: str, r: str,
        ) -> None:
            """Mark a passing case with a dot."""
            self.write(colourise("{green}.{reset}"))
        def failure(
            self, case: int, total: int, form: str, err: str,
            errlist: Iterable[str],
        ) -> None:
            """Mark a failing case with an exclamation mark."""
            self.write(colourise("{red}!{reset}"))
        def result(
            self, title: str, test: str, counts: dict[str, int],
        ) -> None:
            """End the line of markers for this test."""
            self.write("\n")
        def final_result(self, counts: MorphTest) -> None:
            """Write PASS or FAIL for the run as a whole."""
            if counts.fails > 0:
                self.write(colourise("{red}FAIL{reset}\n"))
            else:
                self.write(colourise("{green}PASS{reset}\n"))

    class FinalOutput(AllOutput):
        """Nothing but the totals, as `passes/fails/total`."""
        def final_result(self, counts: MorphTest) -> None:
            """Write the run totals in `passes/fails/total` form."""
            p = counts.passes
            f = counts.fails
            self.write(f"{p}/{f}/{p+f} ")

    class NoOutput(AllOutput):
        """Silent formatter: the exit code is the only result."""
        def final_result(self, *args: Any) -> None:
            """Write nothing."""
            pass

    def __init__(self, args: Namespace) -> None:
        """Args:
            args: Parsed command-line arguments; `args.test_file` is loaded
                immediately.
        """
        self.args: Namespace = args

        # TODO: check for null case

        self.fails: int = 0
        self.passes: int = 0

        self.count: OrderedDict[str, dict[str, int]] = OrderedDict()
        self.load_config(self.args.test_file)

    def run(self) -> int:
        """Run the configured tests.

        Returns:
            0 if every test passed, 1 otherwise, for use as an exit code.
        """
        # timing_begin = time.time()
        self.run_tests(self.args.test)
        # self.timer = time.time() - timing_begin
        if self.fails > 0:
            return 1
        else:
            return 0

    def load_config(self, fn: str) -> None:
        """Read the test file and resolve everything needed to run it.

        Parses the file as lexc or YAML depending on its extension, then
        changes into its directory so the paths it contains are interpreted
        relative to the file itself. Command-line overrides take precedence
        over the file's own `Config` section. Colour is switched off when
        not requested and stdout is not a terminal.

        Args:
            fn: Path to the test file.

        Raises:
            AttributeError: If neither Gen nor Morph is configured, or the
                requested output mode is unknown.
            IOError: If a configured transducer file does not exist.
        """
        args = self.args

        with open(fn, encoding="UTF-8") as configfile:
            if fn.endswith("lexc"):
                self.config: TestFile = TestFile(parse_lexc_trans(configfile,
                                       args.gen,
                                       args.morph,
                                       args.app,
                                       args.transducer,
                                       args.section), args.section)
            else:
                self.config = TestFile(yaml_load_ordered(configfile),
                                       args.section)

        d = os.path.dirname(fn)
        if d:
            os.chdir(os.path.dirname(fn))
        # we've loaded the test file, now let all paths be
        # relative to that file

        config = self.config

        app = args.app or config.app
        if isinstance(app, str):
            app = app.split(" ")
        self.program: list[str] = string_to_list(app)
        check_path_exists(self.program[0])

        self.gen: str | None = args.gen or config.gen
        self.morph: str | None = args.morph or config.morph

        if args.surface:
            self.gen = None
        if args.lexical:
            self.morph = None

        if self.gen is None and self.morph is None:
            raise AttributeError("One of Gen or Morph must be configured.")

        for i in (self.gen, self.morph):
            if i and not os.path.isfile(i):
                raise IOError(f"File {i} does not exist.")

        self.out: MorphTest.AllOutput | None = None
        if args.silent:
            self.out = MorphTest.NoOutput(args)
        else:
            self.out = {
                "normal": MorphTest.NormalOutput,
                "terse": MorphTest.TerseOutput,
                "compact": MorphTest.CompactOutput,
                "silent": MorphTest.NoOutput,
                "final": MorphTest.FinalOutput
            }.get(args.output, lambda x: None)(args)

        if self.out is None:
            raise AttributeError("Invalid output mode supplied: "
                                 f"{args.output}")

        if args.verbose:
            self.out.info(f"`{self.program[0]}` will be used "
                          "for parsing dictionaries.\n")

        if not args.colour and not sys.stdout.isatty():
            for key in list(COLORS.keys()):
                COLORS[key] = ""

    def run_tests(self, single_test: str | None = None) -> None:
        """Run every test, or just one, in the enabled directions.

        If neither `--surface` nor `--lexical` was given, both directions
        are run.

        Args:
            single_test: Test identifier to run on its own; None for all.
        """
        args = self.args
        config = self.config

        if args.surface is False and args.lexical is False:
            args.surface = args.lexical = True

        if single_test is not None:
            self.parse_fsts(single_test)
            if args.lexical:
                self.run_test(single_test, True)
            if args.surface:
                self.run_test(single_test, False)

        else:
            self.parse_fsts()

            if args.lexical:
                for t in config.lexical_tests:
                    self.run_test(t, True)

            if args.surface:
                for t in config.surface_tests:
                    self.run_test(t, False)

        self.out.final_result(self)

    def parse_fsts(self, key: str | None = None) -> None:
        """Run the lookup tool and cache its output for each direction.

        All inputs are fed to the transducer in one pass per direction, so
        the tool is started at most twice per run.

        Args:
            key: Restrict the inputs to a single test; None for all tests.
        """
        args = self.args
        self.results: dict[str, Any] = {"gen": {}, "morph": {}}

        def parser(
            self: MorphTest, d: str, f: str,
            tests: OrderedDict[str, list[TestCase]],
        ) -> None:
            """Feed one direction's inputs through the transducer.

            Stores the parsed results under `self.results[d]`, or the tool's
            error output under `self.results["err"]` if it exited non-zero.

            Args:
                self: The MorphTest instance (passed explicitly).
                d: Direction key, `gen` or `morph`.
                f: Path to the transducer to load.
                tests: Test cases supplying the input forms.
            """
            # TODO: handle ~ in file parser
            if key is not None:
                keys = [x.lstrip("~") for x in tests[key]]
            else:
                keys = [x[0].lstrip("~") for vals in tests.values()
                        for x in vals]
            app = Popen(self.program + [f], stdin=PIPE, stdout=PIPE,
                        stderr=PIPE, close_fds=True)
            args = "\n".join(keys) + "\n"

            resx, errx = app.communicate(args.encode("utf-8"))
            res = resx.decode("utf-8").split("\n\n")
            err = errx.decode("utf-8").strip()

            if app.returncode != 0:
                self.results["err"] = "\n".join(
                    [i for i in [res[0], err,
                                 f"(Error code:{app.returncode})"] if i != ""]
                )
            else:
                self.results[d] = self.parse_fst_output(res)

        if args.lexical:
            parser(self, "gen", self.gen, self.config.surface_tests)
            if self.args.verbose:
                self.out.info("Generating...\n")

        if args.surface:
            parser(self, "morph", self.morph, self.config.lexical_tests)
            if self.args.verbose:
                self.out.info("Morphing...\n")

        if self.args.verbose:
            self.out.info("Done!\n")

    def get_forms(
        self, test: str, forms: Iterable[str],
    ) -> tuple[str, set[str], set[str]]:
        """Split expected forms from explicitly unwanted ones.

        A `~` prefix marks a form that must *not* be produced. When the
        input itself is prefixed, the sense of the whole case is flipped.

        Args:
            test: The input form, possibly `~`-prefixed.
            forms: The listed output forms, each possibly `~`-prefixed.

        Returns:
            A tuple of the input with any prefix stripped, the set of
            detested forms, and the set of expected forms.
        """
        if test.startswith("~"):
            test = test.lstrip("~")
            detested = set()
            expected = set()
            for i in forms:
                if i.startswith("~"):
                    expected.add(i.lstrip("~"))
                else:
                    detested.add(i)
        else:
            detested = {i.lstrip("~") for i in forms if i.startswith("~")}
            expected = {i.lstrip("~") for i in forms if not i.startswith("~")}
        return test, detested, expected

    def run_test(self, data: str, is_lexical: bool) -> None:
        """Compare one test's cached results with its expectations.

        Missing, unexpected and detested forms are reported through the
        output formatter and tallied in `self.count`, which is then folded
        into the running totals. A case with no expected forms passes when
        the transducer returns nothing (a bare `+?`).

        Args:
            data: The test identifier.
            is_lexical: True to test generation (lexical input), False to
                test analysis (surface input).

        Raises:
            LookupError: If the lookup tool reported an error earlier.
        """
        if is_lexical:
            desc = "Lexical/Generation"
            f = "gen"
            tests = self.config.surface_tests[data]

        else: # surface
            desc = "Surface/Analysis"
            f = "morph"
            tests = self.config.lexical_tests[data]

        res = self.results[f]

        if self.results.get("err"):
            raise LookupError(f"`{self.program}` had an "
                              f"error:\n{self.results["err"]}")

        c = len(self.count)
        d = f"{data} ({desc})"
        title = f"Test {c}: {d}"
        self.out.title(title)

        self.count[d] = {"Pass": 0, "Fail": 0}

        caseslen = len(tests)
        for n, testcase in enumerate(tests):
            n += 1  # off by one annoyance

            test = testcase.input
            forms = testcase.outputs

            actual_results = set(res[test.lstrip("~")])
            test, detested_results, expected_results = self.get_forms(test,
                                                                      forms)

            missing = set()
            invalid = set()
            success = set()
            detested = set()
            missing_detested = set()

            for form in expected_results:
                if form not in actual_results:
                    missing.add(form)

            for form in detested_results:
                if form in actual_results:
                    detested.add(form)
                    actual_results.remove(form)
                else:
                    missing_detested.add(form)

            for form in actual_results:
                if form not in expected_results:
                    invalid.add(form)

            if len(expected_results) > 0:
                for form in actual_results:
                    if form not in (missing | invalid | detested):
                        # passed = True
                        success.add(form)
                        self.count[d]["Pass"] += 1
                        if not self.args.hide_pass:
                            self.out.success(n, caseslen, test, form)
                for form in missing_detested:
                    success.add(form)
                    self.count[d]["Pass"] += 1
                    if not self.args.hide_pass:
                        self.out.success(n, caseslen, test, f"<No '{form}' "
                                         f"{desc.lower()}>")
            else:
                if len(invalid) == 1 and list(invalid)[0].endswith("+?"):
                    invalid = set()
                    self.count[d]["Pass"] += 1
                    if not self.args.hide_pass:
                        self.out.success(n, caseslen, test,
                                         f"<No {desc.lower()}>")

            if len(missing) > 0:
                if not self.args.hide_fail:
                    self.out.failure(n, caseslen, test,
                                     "Missing results", missing)
                # self.count[d]["Fail"] += len(missing)

            if len(invalid) > 0:
                if not is_lexical and self.args.ignore_analyses:
                    invalid = set()  # hide this for the final check
                elif not self.args.hide_fail:
                    self.out.failure(n, caseslen, test,
                                     "Unexpected results", invalid)
                # self.count[d]["Fail"] += len(invalid)

            if len(detested) > 0:
                if self.args.colour:
                    msg = colourise("{red}BROKEN!{reset}")
                else:
                    msg = "BROKEN!"
                if not self.args.hide_fail:
                    self.out.failure(n, caseslen, test,
                                     msg + " Negative results", detested)
                # self.count[d]["Fail"] += len(detested)
            if len(detested) + len(missing) + len(invalid) > 0:
                self.count[d]["Fail"] += 1

        self.out.result(title, c, self.count[d])

        self.passes += self.count[d]["Pass"]
        self.fails += self.count[d]["Fail"]

    def parse_fst_output(self, fst: Iterable[str]) -> dict[str, set[str]]:
        """Parse the tab-separated output of the lookup tool.

        Works around xfst's lookup splitting a lemma from its tags into
        separate columns, rejoining them when the third column starts with
        a `+`.

        Args:
            fst: Blocks of tool output, one per input form.

        Returns:
            A dict mapping each input form to the set of forms produced.
        """
        parsed: dict[str, set[str]] = {}
        for item in fst:
            res = item.replace("\r\n", "\n").replace("\r", "\n").split("\n")
            for i in res:
                if i.strip() != "":
                    results = re.split(r"\t+", i)
                    key = results[0].strip()
                    if not key in parsed:
                        parsed[key] = set()
                    # This test is needed because xfst's lookup
                    # sometimes output strings like
                    # bearkoe\tbearkoe\t+N+Sg+Nom, instead of the expected
                    # bearkoe\tbearkoe+N+Sg+Nom
                    if len(results) > 2 and results[2][0] == "+":
                        parsed[key].add(results[1].strip() + results[2].strip())
                    else:
                        parsed[key].add(results[1].strip())
        return parsed

    def __str__(self) -> str:
        """Return everything the output formatter has collected."""
        return str(self.out)

# Debug regex at: https://debuggex.com
# Visualisation of the TEST_RE regex:
# https://debuggex.com/i/kURzt7XS3t83-dvT.png
# Link to debuggex page with this regex:
# https://debuggex.com/r/kURzt7XS3t83-dvT
def parse_lexc(
    f: IO[str] | str, fallback: str | None = None,
) -> dict[str, OrderedDict[str, OrderedDict[str, list[str]]]]:
    """Extract inline test cases from the comments of a lexc file.

    Tests are written as specially marked comments: `!!€` introduces a
    header or a positive case, `!!$` a negative one. Headers name the
    transducer and the test; without one, the enclosing LEXICON name is
    used as the test name and `fallback` as the transducer.

    Args:
        f: An open lexc file, or its contents as a string.
        fallback: Transducer name to assume when no header has been seen.

    Returns:
        A nested dict of transducer -> test name -> input -> outputs,
        with negative expectations prefixed by `~`.
    """
    HEADER_RE = re.compile(r"^\!\!€([^\s.:]+)(?:.[^\s:]+)?:\s*([^#]+)\s*#?")
    TEST_RE = re.compile(r"^\!\!([€\$])\s+(\S.*):\s+(\S+|\S.*\S)(\s*$|\s+[#!])")
    POS = "€"
    NEG = "$"

    output: dict[str, OrderedDict[str, OrderedDict[str, list[str]]]] = {}
    trans = None
    test = None
    if isinstance(f, str):
        f = StringIO(f)

    lines = f.readlines()
    for line in lines:
        if line.startswith("LEXICON"):
            test = line.split(" ", 1)[-1]
            if fallback is not None:
                trans = fallback

        elif line.startswith("!!"):
            match = HEADER_RE.match(line)
            if match:
                trans = match.group(1)
                test = match.group(2).strip()
                if output.get(trans) is None:
                    output[trans] = OrderedDict()
                if output[trans].get(test) is None:
                    output[trans][test] = OrderedDict()
                continue

            match = TEST_RE.match(line)
            if test is None or trans is None:
                continue

            if match:
                test_type = match.group(1).strip()
                left = match.group(3).strip()
                right = match.group(2).strip()

                if test_type == NEG:
                    right = "~" + right

                if output[trans][test].get(left) is None:
                    output[trans][test][left] = []
                output[trans][test][left].append(right)

    return dict(output)

def parse_lexc_trans(
    f: IO[str] | str,
    gen: str | None = None,
    morph: str | None = None,
    app: str | list[str] | None = None,
    fallback: str | None = None,
    lookup: str = "hfst",
) -> dict[str, Any]:
    """Build a test configuration from a lexc file.

    The transducer name is guessed from the filename of whichever of
    `gen` or `morph` was supplied, falling back to `fallback`.

    Args:
        f: An open lexc file, or its contents as a string.
        gen: Path to the generator transducer.
        morph: Path to the analyser transducer.
        app: Lookup command to use; defaults to one for `lookup`.
        fallback: Transducer name to use if it cannot be guessed.
        lookup: Name of the system section to write, e.g. `hfst`.

    Returns:
        A dict with `Config` and `Tests` keys, shaped like a parsed YAML
        test file.

    Raises:
        AttributeError: If the transducer name cannot be determined.
    """
    trans = None
    if gen is not None:
        trans = gen.split("/")[-1].rsplit(".", 1)[0].split("-", 1)[1]
    elif morph is not None:
        trans = morph.split("/")[-1].rsplit(".", 1)[0].split("-", 1)[1]
    elif fallback is not None:
        trans = fallback
    if trans is None or trans == "":
        raise AttributeError("Could not guess which transducer to use.")

    lexc = parse_lexc(f, fallback)[trans]
    if app is None:
        if lookup == "hfst":
            app = ["hfst-lookup"]
        else:
            app = ["lookup", "-flags", "mbTT"]
    config = {lookup: {"Gen": gen, "Morph": morph, "App": string_to_list(app)}}
    return {"Config": config, "Tests": lexc}

def lexc_to_yaml_string(
    data: Mapping[str, Mapping[str, Mapping[str, list[str]]]],
) -> str:
    """Render parsed lexc test cases as YAML source.

    Args:
        data: Nested dict as returned by `parse_lexc`.

    Returns:
        The tests as a YAML string, with multiple expected outputs
        written as a flow sequence.
    """
    out = StringIO()
    out.write("Tests:\n")
    for _, tests in data.items():
        for test, lines in tests.items():
            out.write(f"  {test}:\n")
            for left, rights in lines.items():
                if len(rights) == 1:
                    out.write(f"    {left}: {rights[0]}\n")
                elif len(rights) > 1:
                    out.write(f"    {left}: [{" ".join(rights)}]\n")
    return out.getvalue()


class UI(ArgumentParser):
    """Command-line interface for the test runner.

    Defines the options, parses them, and builds the MorphTest instance
    they describe.
    """
    def __init__(self) -> None:
        """Define the command-line options and parse them."""
        ArgumentParser.__init__(self)

        self.description = \
            """Test morphological transducers for consistency."""
        self.epilog = "Will run all tests in the test_file by default."

        self.add_argument("-V", "--version", action="version",
                          version=f"%(prog)s {__version__}",
                          help="print version info")
        self.add_argument("-c", "--colour", dest="colour",
                          action="store_true", help="Colours the output")
        self.add_argument("-o", "--output",
                          dest="output", default="normal",
                          help="Desired output style: normal, compact, "
                          "terse, final (Default: normal)")
        self.add_argument("-q", "--silent",
                          dest="silent", action="store_true",
                          help="Hide all output; exit code only")
        self.add_argument("-i", "--ignore-extra-analyses",
                          dest="ignore_analyses", action="store_true",
                          help="""Ignore extra analyses when there are
                          more than expected,
                          will PASS if the expected one is found.""")
        self.add_argument("-s", "--surface",
                          dest="surface", action="store_true",
                          help="Surface input/analysis tests only")
        self.add_argument("-l", "--lexical",
                          dest="lexical", action="store_true",
                          help="Lexical input/generation tests only")
        self.add_argument("-f", "--hide-fails",
                          dest="hide_fail", action="store_true",
                          help="Suppresses fails to make finding "
                          "passes easier")
        self.add_argument("-p", "--hide-passes",
                          dest="hide_pass", action="store_true",
                          help="Suppresses passes to make finding "
                          "fails easier")
        self.add_argument("-S", "--section", default="hfst",
                          dest="section", nargs="?", required=False,
                          help="The section to be used for testing "
                          "(default is `hfst`)")
        self.add_argument("-t", "--test",
                          dest="test", nargs="?", required=False,
                          help="""Which test to run (Default: all).
                          TEST = test ID, e.g.
                          'Noun - g\u00E5etie' (remember quotes if
                          the ID contains spaces)""")
        self.add_argument("-F", "--fallback",
                          dest="transducer", nargs="?", required=False,
                          help="""Which fallback transducer to use
                          (ignored, use --gen and --morph).""")
        self.add_argument("-v", "--verbose",
                          dest="verbose", action="store_true",
                          help="More verbose output.")

        self.add_argument("--app", dest="app", nargs="?", required=False,
                          help="Override application used for test")
        self.add_argument("--gen", dest="gen", nargs="?", required=False,
                          help="Override generation transducer used for test")
        self.add_argument("--morph", dest="morph", nargs="?", required=False,
                          help="Override morph transducer used for test")

        self.add_argument("test_file",
                          help="YAML file with test rules")

        self.test = MorphTest(self.parse_args())

    def start(self) -> NoReturn:
        """Run the tests, print the collected output, and exit.

        Never returns: exits with 0 if all tests passed, 1 otherwise.
        """
        ret = self.test.run()
        sys.stdout.write(str(self.test))
        sys.exit(ret)

def main() -> None:
    """Entry point. Exits 130 if interrupted, otherwise with the result."""
    try:
        ui = UI()
        ui.start()
    except KeyboardInterrupt:
        sys.exit(130)
    # except Exception as e:
    #    print("Error: %r" % e)
    #    sys.exit(1)


if __name__ == "__main__":
    main()
