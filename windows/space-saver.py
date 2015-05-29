#/usr/bin/env python3
"""
This file is part of the MusiKernel project, Copyright MusiKernel Team

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; version 3 of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
"""

# This script for for creating clean, minimal installs of MSYS2, suitable
# for creating NSIS installers from

import fnmatch
import os
import shutil
import stat

SAVED = 0

DELETE_DIRS = (
    ('share', 'qt5', 'doc'),
    ('mingw64', 'share', 'doc'),
    ('mingw64', 'include'),
    ('share', 'man'),
    ('lib', 'python3.4', 'test', '__pycache__'))

# TODO:  implement this:

DELETE_FILES = (
    ('bin', 'tiff*.exe'),
    ('bin', 'q*.exe'),
    ('bin', 'sndfile*.exe'),
    ('bin', 'pm-*.exe'),
    ('bin', 'pg_*.exe')
    #('bin', 'x86_64-w64-*.exe'),
)

QT_DLLS = set([
    "Qt5Core.dll", "Qt5Widgets.dll", "Qt5Gui.dll",
    "Qt5WinExtras.dll", "Qt5OpenGL.dll"
])

SAFE_EXES = (
    "musikernel", "rubberband", "python3"
)

SAFE_FILES = (
    "musikernel", "qt", "python3"
)

WARN_SIZE = (1024 * 1024 * 5)

def on_error(func, path, exc_info):
    """
    Error handler for ``shutil.rmtree``.

    If the error is due to an access error (read only file)
    it attempts to add write permission and then retries.

    If the error is for another reason it re-raises the error.

    Usage : ``shutil.rmtree(path, onerror=on_error)``
    """
    if not os.access(path, os.W_OK):
        # Is the error an access error ?
        os.chmod(path, stat.S_IWUSR)
        func(path)
    else:
        raise

def delete_path(a_path):
    if os.path.isdir(a_path):
        shutil.rmtree(a_path, onerror=on_error)
    else:
        os.remove(a_path)

def delete_it_all(a_path):
    global SAVED

    bin_path = os.path.join(a_path, "bin")
    lib_path = os.path.join(a_path, "lib")
    share_path = os.path.join(a_path, "share")

    for filename in os.listdir(bin_path):
        if (filename.startswith("Qt") and filename.endswith(".dll") and \
        filename not in QT_DLLS) or (
        filename.endswith(".exe") and not
        [x for x in SAFE_EXES if x in filename.lower()]):
            os.remove(os.path.join(bin_path, filename))

    for filename in os.listdir(lib_path):
        if not [x for x in SAFE_FILES if x in filename.lower()]:
            delete_path(os.path.join(lib_path, filename))

    for filename in os.listdir(share_path):
        if not [x for x in SAFE_FILES if x in filename.lower()]:
            delete_path(os.path.join(share_path, filename))

    for dir_tuple in DELETE_DIRS:
        path = os.path.join(a_path, *dir_tuple)
        if os.path.isdir(path):
            shutil.rmtree(path, onerror=on_error)

    for (dirpath, dirnames, filenames) in os.walk(a_path):
        filename_set = set(filenames)
        dir_size = 0
        for name in filenames:
            path = os.path.join(dirpath, name)
            size = os.path.getsize(path)
            dir_size += size
            if name.endswith(".a") or (
            name.endswith("d.dll") and name[:-5] + ".dll" in filename_set):
                print("Deleting " + path)
                os.remove(path)
                SAVED += size
#            elif size >= WARN_SIZE:
#                print("Warning:  '{}' is {} MB".format(
#                    path, round(size / (1024 * 1024), 2)))
        if dir_size > WARN_SIZE:
            print("Warning:  '{}' is {} MB".format(dirpath, dir_size))
    pkg_dir = os.path.join(a_path, r'var\cache\pacman\pkg')
    if os.path.isdir(pkg_dir) and os.listdir(pkg_dir):
        print("Warning:  '{}' is not empty".format(pkg_dir))

delete_it_all(r'C:\musikernel1-64\mingw64')
delete_it_all(r'C:\musikernel1-32\mingw32')

MB = round(SAVED / (1024 * 1024), 2)

print("Saved {} MB (not including directories)".format(MB))

shutil.copy('gpl-3.0.txt', r'C:\musikernel1-64')
