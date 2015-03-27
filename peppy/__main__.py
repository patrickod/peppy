"""
Copyright David R. MacIver (david@drmaciver.com), 2015.

This Source Code Form is subject to the terms of the Mozilla
Public License, v. 2.0. If a copy of the MPL was not distributed
with this file, You can obtain one at http://mozilla.org/MPL/2.0/.

Peppy is a small fuzzer for taking a set of python files and producing
a minimal set of examples of each error and warning category from the
pep8 checker.

There's really no sensible reason for it to exist or for you to use it,
but maybe the corpus of generated examples might be interesting for testing
things on.
"""


import subprocess
import re
import argparse
import os
import tempfile
import hashlib
from contextlib import contextmanager
import sys
import tokenize
from peppy.utils import is_valid_source, all_python_files


@contextmanager
def source_in_file(source):
    fno, filepath = tempfile.mkstemp(suffix='.py')
    os.close(fno)
    with open(filepath, 'w') as o:
        o.write(source)
    try:
        yield filepath
    finally:
        os.remove(filepath)


ERROR_CODE = re.compile('^[^\s]+ ([^\s]+) ')


def line_based_shrinking(s):
    lines = s.split('\n')

    for i in range(1, len(lines) - 1):
        yield '\n'.join(lines[:i])

    for i in range(len(lines) - 1, 0, -1):
        yield '\n'.join(lines[i:])

    for delete_length in range(
        len(lines) // 2, 0, -1
    ):
        for i in range(len(lines)):
            x = list(lines)
            del x[i:(i + delete_length)]
            yield '\n'.join(x)


def character_based_shrinking(s):
    for l in range(10, 0, -1):
        for i in range(len(s)):
            x = list(s)
            del x[i:(i + l)]
            yield ''.join(x)


def pep8(filepath):
    """Return the set of pep8 errors that are found in a python file.

    The pep8 checker just directly prints out and has no sensible API,
    so we launch it as a subprocess and scrape the output. Fun times.

    """

    try:
        subprocess.check_output(
            ['pep8', filepath],
            stderr=open("/dev/null")
        ).decode('ascii')
        return set()
    except subprocess.CalledProcessError as e:
        result = set()
        for l in e.output.decode('ascii').split('\n'):
            l = l.strip()
            if not l:
                continue
            match = ERROR_CODE.match(l)
            assert match is not None
            result.add(match.groups()[0])
        return result


parser = argparse.ArgumentParser(
    description='A script for producing small examples of pep8 errors')

parser.add_argument('--src',
                    default='.',
                    help='Location to look for source files')

parser.add_argument('--examples',
                    default='examples',
                    help='Location to put examples')

parser.add_argument(
    '--recycling', default="recycling",
    help="Directory to put all seen valid source code"
)

parser.add_argument(
    '--max-size', type=int, default=0,
    help="Stop when an example is under this size"
)


class Peppy(object):

    def __init__(
        self,
        src, examples, max_size, recycling,
    ):
        self.src = src
        self.examples = examples
        self.recycling = recycling
        self.max_size = max_size
        self.errors_cache = {}
        self.best_examples = {}

    def trash_file(self, source):
        return os.path.join(
            self.recycling,
            hashlib.md5(source.encode('utf-8')).hexdigest()[:8] + ".py",
        )

    def note_source(self, source):
        filename = self.trash_file(source)
        if not os.path.exists(self.recycling):
            os.makedirs(self.recycling)
        if not os.path.exists(filename):
            with open(filename, 'w') as o:
                o.write(source)

    def errors_in_source(self, source):
        key = hashlib.md5(source.encode('utf-8')).digest()
        if key in self.errors_cache:
            return self.errors_cache[key]
        self.note_source(source)
        with source_in_file(source) as filepath:
            result = pep8(filepath)
        self.errors_cache[key] = result
        for error in result:
            if (
                error not in self.best_examples or
                len(source) < len(self.best_examples[error])
            ):
                self.best_examples[error] = source
        return result

    def find_minimal_example(self, filename, is_example):
        with tokenize.open(filename) as i:
            return self.find_minimal_example_from_source(
                i.read(), is_example
            )

    def find_minimal_example_from_source(self, source, is_example):
        current_best = source

        seen = set()

        for shrinker in (
            line_based_shrinking, character_based_shrinking
        ):
            simplified = True
            while simplified:
                if len(current_best) <= self.max_size:
                    return current_best
                simplified = False
                for simpler in shrinker(current_best):
                    if not simpler:
                        continue
                    signature = hashlib.md5(simpler.encode('utf-8')).digest()
                    if signature in seen:
                        continue
                    seen.add(signature)

                    if len(simpler) >= len(current_best):
                        continue

                    if not is_valid_source(simpler):
                        continue

                    self.note_source(simpler)

                    if len(simpler) >= len(current_best):
                        continue

                    if is_example(simpler):
                        print('Shrinking with %s: %d -> %d (%s)' % (
                            shrinker.__name__,
                            len(current_best), len(simpler),
                            self.trash_file(simpler)
                        ))
                        current_best = simpler
                        simplified = True
                        break
        return current_best

    def example_file_for_error(self, error):
        return os.path.join(self.examples, error.lower() + '.py')

    def investigate_pep8_status(self, filename):
        sys.stdout.write("%s: " % (filename,))
        sys.stdout.flush()
        with tokenize.open(filename) as i:
            source = i.read()
        if not is_valid_source(source):
            return
        errors = self.errors_in_source(source)

        if errors:
            print(', '.join(errors))
        else:
            print('clean')
            return

        changed = True
        while changed:
            changed = False
            for error, source in list(self.best_examples.items()):
                self.note_source(source)
                target = self.example_file_for_error(error)
                if os.path.exists(target):
                    existing_length = len(tokenize.open(target).read())
                    if existing_length <= len(source):
                        continue
                    else:
                        print((
                            "A smaller example for %s (%d < %d). Simplifying "
                            "an example from %s"
                        ) % (
                            error,
                            len(source), existing_length,
                            self.trash_file(source)))

                else:

                    print(
                        '%s is new. Simplifying an example from %s' % (
                            error, self.trash_file(source)))

                changed = True
                example = self.find_minimal_example_from_source(
                    source,
                    is_example=lambda source:
                        error in self.errors_in_source(
                            source),
                )
                assert len(example) <= len(source)
                with open(target, 'w') as o:
                    o.write(example)

    def run(self):
        if not os.path.exists(self.examples):
            os.makedirs(self.examples)

        for filename in all_python_files(self.src):
            self.investigate_pep8_status(filename)


if __name__ == '__main__':
    Peppy(**vars(parser.parse_args())).run()
