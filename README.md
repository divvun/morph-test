# morph-test
An open-source test tool for rule-based FST moprhological analysers. `morph-test` is at the core of the morphological testing regime in the [GiellaLT](https://github.com/giellalt) infrastructure.

# Installation

Clone and run as shown below.

# Usage

```
python3 morph-test.py -h
usage: morph-test.py [-h] [-c] [-o OUTPUT] [-q] [-i] [-s] [-l] [-f] [-p] [-S [SECTION]]
                     [-t [TEST]] [-F [TRANSDUCER]] [-v] [--app [APP]]
                     [--gen [GEN]] [--morph [MORPH]]
                     test_file

Test morphological transducers for consistency.

positional arguments:
  test_file             YAML file with test rules

optional arguments:
  -h, --help            show this help message and exit
  -c, --colour          Colours the output
  -o OUTPUT, --output OUTPUT
                        Desired output style: compact, terse, final, normal (Default: normal)
  -q, --silent          Hide all output; exit code only
  -i, --ignore-extra-analyses
                        Ignore extra analyses when there are more than expected, will PASS
                        if the expected one is found.
  -s, --surface         Surface input/analysis tests only
  -l, --lexical         Lexical input/generation tests only
  -f, --hide-fails      Suppresses passes to make finding failures easier
  -p, --hide-passes     Suppresses failures to make finding passes easier
  -S [SECTION], --section [SECTION]
                        The section to be used for testing (default is `hfst`)
  -t [TEST], --test [TEST]
                        Which test to run (Default: all). TEST = test ID, e.g.
                        'Noun - gåetie' (remember quotes if the ID contains spaces)
  -F [TRANSDUCER], --fallback [TRANSDUCER]
                        Which fallback transducer to use.
  -v, --verbose         More verbose output.
  --app [APP]           Override application used for test
  --gen [GEN]           Override generation transducer used for test
  --morph [MORPH]       Override morph transducer used for test

Will run all tests in the test_file by default.
```

# Example test YAML file

The test files are written in [YAML](https://yaml.org) [syntax](https://en.wikipedia.org/wiki/YAML#Syntax), adhering to the following structure:

```yaml
Config:
  hfst:
    Gen: ../../../src/generator-gt-norm.hfst
    Morph: ../../../src/analyser-gt-norm.hfst
  xerox:
    Gen: ../../../src/generator-gt-norm.xfst
    Morph: ../../../src/analyser-gt-norm.xfst
    App: lookup

Tests:
  Pronoun - juoga: # Indefinitive
    juoga+Pron+Indef+Sg+Nom: juoga
    juoga+Pron+Indef+Sg+Gen: juoŋga
    juoga+Pron+Indef+Sg+Acc: juojddá
    juoga+Pron+Indef+Sg+Ine: [juonná, juonne]
    juoga+Pron+Indef+Sg+Ill: juosik
    juoga+Pron+Indef+Sg+Ela: juosstá
    juoga+Pron+Indef+Sg+Com: juojnak
    juoga+Pron+Indef+Pl+Nom: []
    juoga+Pron+Indef+Pl+Gen: []
    juoga+Pron+Indef+Pl+Acc: juojddájt
    juoga+Pron+Indef+Pl+Ine: []
    juoga+Pron+Indef+Pl+Ill: []
    juoga+Pron+Indef+Pl+Ela: []
    juoga+Pron+Indef+Pl+Com: []
    juoga+Pron+Indef+Ess: juonen
```

The `Config` section contains defaults to be used with the test files; these can be overriden on the command line. After the `Config` section comes the `Tests` section. Each test must have a name (`Pronoun - juoga` in the example above), followed by the actual test data.

Each line of test data contains:

- **morphological analysis**: e.g. `juoga+Pron+Indef+Sg+Gen`
- **separator**: `:`
- **expected word form(s)**: `juoŋga`

If more than one word form is expected, they must be in a `[]` list, comma separated.

If **no** word form is expected, that must be denoted with an empty `[]`.

Comments can be freely added, marked with an initial `#`.

A test run succeeds if all and only the listed word forms are generated, and the word forms listed only get the specified analyses.

All languages contain a certain amount of homonymy, which makes the `-i, --ignore-extra-analyses` option very useful: it makes the tests pass even if there are alternative analyses of a given word form. That is, homonym analyses won't destroy the test results.

# License

Licensed under [CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/).

# Contribution

Fork and PR on Github.

Unless you explicitly state otherwise, any contribution intentionally submitted for inclusion in the work by you shall be licensed as above, without any additional terms or conditions.