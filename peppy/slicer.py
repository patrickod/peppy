"""
Copyright David R. MacIver (david@drmaciver.com), 2015.

This Source Code Form is subject to the terms of the Mozilla
Public License, v. 2.0. If a copy of the MPL was not distributed
with this file, You can obtain one at http://mozilla.org/MPL/2.0/.

This is a small script that takes a python source file and tries
to produce a smaller one.
"""

import tokenize
import hashlib
import os
import argparse
from peppy.utils import is_valid_source, all_python_files


parser = argparse.ArgumentParser(
    description='A script for producing small examples of pep8 errors')

parser.add_argument('--src',
                    default='.',
                    help='Source file to slice')

parser.add_argument('--target',
                    default='.',
                    help='Target directory')


def write_if_valid(target, source):
    if is_valid_source(source):
        source_id = hashlib.md5(
            source.encode('utf-8')).hexdigest()[:8]
        with open(
            os.path.join(target, source_id + ".py"), "w"
        ) as o:
            o.write(source)


def main():
    args = parser.parse_args()
    if not os.path.exists(args.target):
        os.makedirs(args.target)

    for filename in all_python_files(args.src):
        with tokenize.open(filename) as f:
            source = f.read()

        for i in range(len(source)):
            for j in range(i + 1, len(source)):
                write_if_valid(args.target, source[i:j])
                write_if_valid(args.target, source[:i] + source[j:])

if __name__ == '__main__':
    main()
