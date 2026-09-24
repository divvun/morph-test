#!/usr/bin/env python3
"""Run the YAML test cases for morphology and morphophonology tests.

Reads a test file (YAML, or lexc with inline test comments), runs every
listed form through the configured transducers with an external lookup
tool, and reports which analyses and generated forms were missing,
unexpected, or explicitly unwanted.

License: CC0 (see LICENSE)
"""

from __future__ import annotations

import sys
from argparse import ArgumentParser
from typing import NoReturn

import yaml

from . import __version__
from .morphtest import MorphTest


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
                          choices=["normal", "compact", "terse", "final",
                                   "json"],
                          help="Desired output style: normal, compact, "
                          "terse, final, json (Default: normal)")
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
