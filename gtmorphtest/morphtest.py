#!/usr/bin/env python3

from __future__ import annotations

import os
import re
import sys
from argparse import Namespace
from collections import OrderedDict
from collections.abc import Iterable
from io import StringIO
from subprocess import PIPE, Popen
from typing import Any

from .lexc import parse_lexc_trans
from .testfile import TestCase, TestFile
from .utils import COLORS, check_path_exists, colourise, string_to_list
from .yaml import yaml_load_ordered


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

    class JsonOutput(AllOutput):
        """JSON formatter: one object per test case, plus a summary object."""
        def title(self, text: str) -> None:
            """Write a JSON object for the test heading."""
            self.write(f"{{\"title\": {text}}}\n")

        def success(
            self, case: int, total: int, left: str, right: str,
        ) -> None:
            """Write a JSON object for one passing case."""
            out = f"{{\"case\": {case}, \"total\": {total}, "\
                  f"\"input\": {left}, \"output\": {right}, "\
                  f"\"result\": \"PASS\"}}"
            if not self.args.hide_pass:
                self.write(out + "\n")

        def failure(
            self, case: int, total: int, left: str, right: str,
            errlist: Iterable[str],
        ) -> None:
            """Write a JSON object for one failing case."""
            out = f"{{\"case\": {case}, \"total\": {total}, "\
                  f"\"input\": {left}, \"output\": {right}, "\
                  f"\"result\": \"FAIL\", "\
                  f"\"errors\": {list(errlist)}}}"
            if not self.args.hide_fail:
                self.write(out + "\n")

        def result(
            self, title: str, test: str, counts: dict[str, int],
        ) -> None:
            """Write a single JSON object summarising the test."""
            p = counts["Pass"]
            f = counts["Fail"]
            out = f"{{\"title\": {title}, \"passes\": {p}, \"fails\": {f}}}"
            if counts["Fail"] > 0:
                if not self.args.hide_fail:
                    self.write(out)
            elif not self.args.hide_pass:
                self.write(out)

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
                                                                  args.section),
                                                 args.section)
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
                "final": MorphTest.FinalOutput,
                "json": MorphTest.NoOutput  # TODO: implement JSON output
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
        if self.out is None:
            raise AttributeError("Output formatter not configured.")
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
        if self.out is None:
            raise AttributeError("Output formatter not configured.")
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
        if self.out is None:
            raise AttributeError("Output formatter not configured.")
        if is_lexical:
            desc = "Lexical/Generation"
            f = "gen"
            tests = self.config.surface_tests[data]

        else:  # surface
            desc = "Surface/Analysis"
            f = "morph"
            tests = self.config.lexical_tests[data]

        res = self.results[f]

        if self.results.get("err"):
            raise LookupError(f"`{self.program}` had an "
                              f"error:\n{self.results['err']}")

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
                    if key not in parsed:
                        parsed[key] = set()
                    # This test is needed because xfst's lookup
                    # sometimes output strings like
                    # bearkoe\tbearkoe\t+N+Sg+Nom, instead of the expected
                    # bearkoe\tbearkoe+N+Sg+Nom
                    if len(results) > 2 and results[2][0] == "+":
                        parsed[key].add(results[1].strip() +
                                        results[2].strip())
                    else:
                        parsed[key].add(results[1].strip())
        return parsed

    def __str__(self) -> str:
        """Return everything the output formatter has collected."""
        return str(self.out)


if __name__ == "__main__":
    pass
