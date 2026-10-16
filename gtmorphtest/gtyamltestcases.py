#!/usr/bin/env -O python3
"""Run yaml testcases from a glob in a json config.

Replaces the bash based runner: run-yaml-tests.sh, run-morph-tester.sh."""

import json
import subprocess
import sys
import tempfile
from argparse import ArgumentParser, FileType, Namespace
from glob import glob
from os.path import basename
from typing import TextIO

from termcolor import colored

from . import __version__


def print_json_log(json_fails: dict, options: Namespace):
    """Write json log to file."""
    json.dump(json_fails, options.json_log, indent=2, ensure_ascii=False)
    options.json_log.write("\n")

def main():
    """Run CLI stuffs for yaml runner with json configs."""
    argp = ArgumentParser()
    argp.add_argument("-V", "--version", action="version",
                      version=f"%(prog)s {__version__}",
                      help="print version info")
    argp.add_argument("-v", "--verbose", action="store_true",
                      help="print verbose output")
    argp.add_argument("-c", "--config", type=open, metavar="CONFIG",
                      help="read configuration from json file CONFIG",
                      required=True)
    argp.add_argument("-E", "--editor", type=str, metavar="EDITOR",
                      help="open logs with EDITOR after failed test")
    argp.add_argument("-J", "--json-log", type=FileType("w"), metavar="JSONLOG",
                      help="write log in json in JSONLOG")
    argp.add_argument("-D", "--driver", choices=["python", "rust", "self"],
                      default="python",
                      help="select which morph test to use for single tests")
    argp.add_argument("-P", "--test-group", type=str, metavar="GROUP",
                      help="read configs from GROUP section of json config",
                      required=True)
    argp.add_argument("-L", "--logfile", type=FileType("w"), metavar="LOGFILE",
                      help="write permanent markdown log in LOGFILE")
    argp.add_argument("-T", "--time-out", type=int, metavar="TIMEOUT",
                      help="set timeout for each test in seconds",
                      default=60)
    options = argp.parse_args()
    if options.logfile:
        dostuff(options, options.logfile)
    else:
        with tempfile.NamedTemporaryFile(prefix="gtyamltest", suffix=".md",
                                         mode="w", delete=False,
                                         encoding="UTF-8") as logfile:
            dostuff(options, logfile)
    print(colored("SUCCESS", "green"))

def dostuff(options: Namespace, logfile: TextIO):
    """Run the tests and write logs to logfile."""
    configuration = json.load(options.config)
    if options.test_group not in configuration:
        print(colored("SKIP", "cyan"), f"{options.test_group} not found "
              "in config file {options.config.name}")
        sys.exit(77)
    logfile.write(f"# YAML test log for {options.test_group}\n\n")
    testoptions = []
    if options.driver == "python":
        testoptions.append("gtmorphtest")
    elif options.driver == "self":
        testoptions.extend(["python3", "-m", "gtmorphtest.gtmorphtest"])
    elif options.driver == "rust":
        testoptions.append("morph-test2")
        # testoptions.append("--pool")
    else:
        print(colored("ERROR", "red"), f"unknown driver {options.driver}")
        sys.exit(1)
    testoptions.extend(["--output", "json", "--ignore-extra-analyses",
                        "--hide-passes"])
    analyser = configuration[options.test_group]["analyser"]
    generator = configuration[options.test_group]["generator"]
    testoptions.extend(["--morph", analyser])
    testoptions.extend(["--gen", generator])
    logfile.write(f"* Running on `{testoptions}`\n\n")
    fails = 0
    json_fails = {"group": options.test_group, "tests": []}
    for yamlglob in configuration[options.test_group]["globs"]:
        yamlfilenames = glob(yamlglob)
        if not yamlfilenames:
            logfile.write(f"## `{yamlglob}` not found\n\n")
        for yamlfilename in yamlfilenames:
            testname = basename(yamlfilename)
            fields = testname.split(".")
            gentests = False
            anatests = False
            if fields[-1] == "gen":
                gentests = True
            elif fields[-1] == "ana":
                anatests = True
            elif fields[-1] in ["hfst", "xfst", "~hfst", "~xfst"]:
                pass
            if gentests or anatests and fields[-2] in ["hfst", "xfst"]:
                pass
            if anatests:
                testoptions.append("--surface")
            elif gentests:
                testoptions.append("--lexical")
            rv = subprocess.run([*testoptions, yamlfilename],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=options.time_out, check=False)
            if rv.returncode != 0:
                if options.verbose:
                    print(colored("FAIL", "red"), f"{testname} failed with "
                          f"return code {rv.returncode}")
                logfile.write(f"## {testname} **failed**\n\n")
                fails += 1
                errs = rv.stderr.decode("utf-8")
                if "Invalid output mode" in errs:
                    print(colored("ERROR", "red"), f"{testoptions} failed with "
                          f"return code {rv.returncode}")
                    print(colored("ERROR", "red"), "Update morph-test to "
                          "latest version or use different -D driver")
                    sys.exit(1)
                elif "Ugyldig verdi" in errs and "json" in errs:
                    print(colored("ERROR", "red"), f"{testoptions} failed with "
                          f"return code {rv.returncode}")
                    print(colored("ERROR", "red"), "Update morph-test2 to "
                          "latest version or use different -D driver")
                    sys.exit(1)
                resultjson = rv.stdout.decode("utf-8")
                results = json.loads(resultjson)
                for result in results:
                    if "fails" in result and result["fails"] > 0:
                        logfile.write(f"* `{result['title']}`: "
                                      f"{result['fails']} fails:\n")
                        for fail in result["tests"]:
                            logfile.write(f"  * `{fail['input']}` => "
                                          f"{fail['output']} \n")
                            for err in fail["errors"]:
                                logfile.write(f"    * `{err}`\n")
                logfile.write(f"\n* {results[-1]['total_fails']} failures\n\n")
                json_fails["tests"].append({"testname": testname,
                              "returncode": rv.returncode,
                              "results": results})
            else:
                if options.verbose:
                    print(colored("PASS", "green"), f"{testname} passed")
                logfile.write(f"## {testname} passed\n")
                logfile.write("\n* all tests passed\n\n")
    if options.json_log:
        print_json_log(json_fails, options)
    if fails > 0:
        print(colored("FAIL", "red"), f"{fails} tests failed")
        print("See log in", colored(logfile.name, "magenta"))
        if options.editor:
            subprocess.run([options.editor, logfile.name],
                           check=False)
        sys.exit(1)
    else:
        print(colored("PASS", "green"), "all tests passed")


if __name__ == "__main__":
    main()
