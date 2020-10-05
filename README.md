# morph-test
An open-source test tool for rule-based FST moprhological analysers. `morph-test` is at the core of the morphological testing regime in the [GiellaLT](https://github.com/giellalt) infrastructure.

# Installation

Clone or download and run as shown below.

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

## Controlling output

### Output modes

The different output modes (`-o OUTPUT, --output OUTPUT`) will render the as follows:

- **normal** (default): all details, full report:

```
-----------------------------------------------------
Test 0: Adjective - antisosiálla (Lexical/Generation)
-----------------------------------------------------
[1/7][PASS] antisosiálla+A+Attr => antisosiála
[1/7][PASS] antisosiálla+A+Attr => antisosiálalasj
[2/7][PASS] antisosiálla+A+Sg+Nom => antisosiálla
[2/7][PASS] antisosiálla+A+Sg+Nom => antisosiálalasj
[3/7][PASS] antisosiálla+A+Sg+Gen => antisosiála
[3/7][PASS] antisosiálla+A+Sg+Gen => antisosiálalattja
[4/7][PASS] antisosiálla+A+Der/Comp+A+Sg+Nom => antisosiálalabbo
[4/7][PASS] antisosiálla+A+Der/Comp+A+Sg+Nom => antisosiálap
[5/7][PASS] antisosiálla+A+Der/Superl+A+Sg+Nom => antisosiálamus
[5/7][PASS] antisosiálla+A+Der/Superl+A+Sg+Nom => antisosiálalamos
[6/7][PASS] antisosiálla+A+Der/AAdv+Adv => antisosiálalattjat
[7/7][PASS] antisosiálla+A+Attr+Der/vuota+N+Sg+Nom => <No lexical/generation>

Test 0 - Passes: 12, Fails: 0, Total: 12
----------------------------------------------------
Test 1: Adjective - aspektuálla (Lexical/Generation)
----------------------------------------------------
[1/7][PASS] aspektuælla+A+Attr => aspektuella
[1/7][PASS] aspektuælla+A+Attr => aspektuellalasj
[1/7][FAIL] aspektuælla+A+Attr => Unexpected results: aspektuälla
[2/7][PASS] aspektuælla+A+Sg+Nom => aspektuælla
[2/7][PASS] aspektuælla+A+Sg+Nom => aspektuälla
[2/7][PASS] aspektuælla+A+Sg+Nom => aspektuellalasj
[3/7][PASS] aspektuælla+A+Sg+Acc => aspektuellav
[3/7][PASS] aspektuælla+A+Sg+Acc => aspektuellalattjav
[3/7][FAIL] aspektuælla+A+Sg+Acc => Unexpected results: aspektuällav
[4/7][PASS] aspektuælla+A+Der/Comp+A+Sg+Nom => aspektuellalabbo
[4/7][PASS] aspektuælla+A+Der/Comp+A+Sg+Nom => aspektuellap
[4/7][FAIL] aspektuælla+A+Der/Comp+A+Sg+Nom => Unexpected results: aspektuällap
[5/7][PASS] aspektuælla+A+Der/Superl+A+Sg+Nom => aspektuellamus
[5/7][PASS] aspektuælla+A+Der/Superl+A+Sg+Nom => aspektuellalamos
[5/7][FAIL] aspektuælla+A+Der/Superl+A+Sg+Nom => Unexpected results: aspektuällamus
[6/7][PASS] aspektuælla+A+Der/AAdv+Adv => aspektuellalattjat
[7/7][PASS] aspektuælla+A+Attr+Der/vuota+N+Sg+Nom => <No lexical/generation>

Test 1 - Passes: 13, Fails: 4, Total: 17
--------------------------------------------------
Test 2: Adjective - paralælla (Lexical/Generation)
--------------------------------------------------
[1/5][PASS] paralælla+A+Attr => paralellalasj
[1/5][PASS] paralælla+A+Attr => paralella
[1/5][FAIL] paralælla+A+Attr => Unexpected results: paralälla
[2/5][PASS] paralælla+A+Sg+Nom => paralälla
[2/5][PASS] paralælla+A+Sg+Nom => paralellalasj
[2/5][PASS] paralælla+A+Sg+Nom => paralælla
[3/5][PASS] paralælla+A+Sg+Gen => paralellalattja
[3/5][PASS] paralælla+A+Sg+Gen => paralella
[3/5][FAIL] paralælla+A+Sg+Gen => Unexpected results: paralälla
[4/5][PASS] paralælla+A+Der/Comp+A+Sg+Nom => paralellap
[4/5][PASS] paralælla+A+Der/Comp+A+Sg+Nom => paralellalabbo
[4/5][FAIL] paralælla+A+Der/Comp+A+Sg+Nom => Unexpected results: paralällap
[5/5][PASS] paralælla+A+Der/Superl+A+Sg+Nom => paralellamus
[5/5][PASS] paralælla+A+Der/Superl+A+Sg+Nom => paralellalamos
[5/5][FAIL] paralælla+A+Der/Superl+A+Sg+Nom => Unexpected results: paralällamus

Test 2 - Passes: 11, Fails: 4, Total: 15
---------------------------------------------------
Test 3: Adjective - antisosiálla (Surface/Analysis)
---------------------------------------------------
[1/9][PASS] antisosiála => antisosiálla+A+Attr
[1/9][PASS] antisosiála => antisosiálla+A+Sg+Gen
[2/9][PASS] antisosiálalasj => antisosiálla+A+Attr
[2/9][PASS] antisosiálalasj => antisosiálla+A+Sg+Nom
[3/9][PASS] antisosiálla => antisosiálla+A+Sg+Nom
[4/9][PASS] antisosiálalattja => antisosiálla+A+Sg+Gen
[5/9][PASS] antisosiálalabbo => antisosiálla+A+Der/Comp+A+Sg+Nom
[6/9][PASS] antisosiálap => antisosiálla+A+Der/Comp+A+Sg+Nom
[7/9][PASS] antisosiálalamos => antisosiálla+A+Der/Superl+A+Sg+Nom
[8/9][PASS] antisosiálamus => antisosiálla+A+Der/Superl+A+Sg+Nom
[9/9][PASS] antisosiálalattjat => antisosiálla+A+Der/AAdv+Adv

Test 3 - Passes: 11, Fails: 0, Total: 11
--------------------------------------------------
Test 4: Adjective - aspektuálla (Surface/Analysis)
--------------------------------------------------
[ 1/11][PASS] aspektuella => aspektuælla+A+Attr
[ 2/11][PASS] aspektuellalasj => aspektuælla+A+Attr
[ 2/11][PASS] aspektuellalasj => aspektuælla+A+Sg+Nom
[ 3/11][PASS] aspektuælla => aspektuælla+A+Sg+Nom
[ 4/11][PASS] aspektuälla => aspektuælla+A+Sg+Nom
[ 5/11][PASS] aspektuellav => aspektuælla+A+Sg+Acc
[ 6/11][PASS] aspektuellalattjav => aspektuælla+A+Sg+Acc
[ 7/11][PASS] aspektuellalabbo => aspektuælla+A+Der/Comp+A+Sg+Nom
[ 8/11][PASS] aspektuellap => aspektuælla+A+Der/Comp+A+Sg+Nom
[ 9/11][PASS] aspektuellalamos => aspektuælla+A+Der/Superl+A+Sg+Nom
[10/11][PASS] aspektuellamus => aspektuælla+A+Der/Superl+A+Sg+Nom
[11/11][PASS] aspektuellalattjat => aspektuælla+A+Der/AAdv+Adv

Test 4 - Passes: 12, Fails: 0, Total: 12
------------------------------------------------
Test 5: Adjective - paralælla (Surface/Analysis)
------------------------------------------------
[1/9][PASS] paralella => paralælla+A+Sg+Gen
[1/9][PASS] paralella => paralælla+A+Attr
[2/9][PASS] paralellalasj => paralælla+A+Sg+Nom
[2/9][PASS] paralellalasj => paralælla+A+Attr
[3/9][PASS] paralælla => paralælla+A+Sg+Nom
[4/9][PASS] paralälla => paralælla+A+Sg+Nom
[5/9][PASS] paralellalattja => paralælla+A+Sg+Gen
[6/9][PASS] paralellalabbo => paralælla+A+Der/Comp+A+Sg+Nom
[7/9][PASS] paralellap => paralælla+A+Der/Comp+A+Sg+Nom
[8/9][PASS] paralellalamos => paralælla+A+Der/Superl+A+Sg+Nom
[9/9][PASS] paralellamus => paralælla+A+Der/Superl+A+Sg+Nom

Test 5 - Passes: 11, Fails: 0, Total: 11
Total passes: 70, Total fails: 8, Total: 78

```
- **compact**: Report the test names and result for each, and print a summary:

```
[PASS] Test 0: Adjective - antisosiálla (Lexical/Generation) 12/0/12
[FAIL] Test 1: Adjective - aspektuálla (Lexical/Generation) 13/4/17
[FAIL] Test 2: Adjective - paralælla (Lexical/Generation) 11/4/15
[PASS] Test 3: Adjective - antisosiálla (Surface/Analysis) 11/0/11
[PASS] Test 4: Adjective - aspektuálla (Surface/Analysis) 12/0/12
[PASS] Test 5: Adjective - paralælla (Surface/Analysis) 11/0/11
Total passes: 70, Total fails: 8, Total: 78
```
- **terse**: print one `.` for each PASS, and one `!` for each fail, and report PASS or FAIL:

```
............
..!.....!..!..!..
..!.....!..!..!
...........
............
...........
FAIL
```

- **final**: only prints a summary of PASSed/FAILed/TOTAL tests:

```
70/8/78
```

### Verbose and silent modes

Verbose mode (`-v, --verbose`) adds test run metadata:

```
`/usr/local/bin/hfst-optimized-lookup` will be used for parsing dictionaries.
Generating...
Morphing...
Done!
[... test results ...]
```

Silent or quiet mode (`-q, --silent `) blocks all output, and only returns the exit value (`0` for `PASS`, `1` for `FAIL`).

### Other output options

`-f, --hide-fails` removes the fails from the output, to make finding passes easier.

`-p, --hide-passes` removes passes from the output, to make finding fails easier.

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