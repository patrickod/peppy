import os
import fnmatch
import random


def is_valid_source(s):
    try:
        compile(s, "<string>", "exec")
        return True
    except SyntaxError:
        return False


def all_python_files(src):
    if src[-3:] == ".py":
        return [src]
    files = []
    for root, dirnames, filenames in os.walk(os.path.expanduser(src)):
        for f in fnmatch.filter(filenames, '*.py'):
            files.append(os.path.join(root, f))
    random.shuffle(files)
    return files
