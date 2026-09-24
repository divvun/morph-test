#!/usr/bin/env python3
"""Lexc stuff."""

import re
from collections import OrderedDict
from io import StringIO
from typing import IO, Any, Mapping

from .utils import string_to_list

# Debug regex at: https://debuggex.com
# Visualisation of the TEST_RE regex:
# https://debuggex.com/i/kURzt7XS3t83-dvT.png
# Link to debuggex page with this regex:
# https://debuggex.com/r/kURzt7XS3t83-dvT
HEADER_RE = re.compile(r"^\!\!€([^\s.:]+)(?:.[^\s:]+)?:\s*([^#]+)\s*#?")
TEST_RE = re.compile(r"^\!\!([€\$])\s+(\S.*):\s+(\S+|\S.*\S)(\s*$|\s+[#!])")
POS = "€"
NEG = "$"


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
                    out.write(f"    {left}: [{' '.join(rights)}]\n")
    return out.getvalue()


if __name__ == "__main__":
    pass
