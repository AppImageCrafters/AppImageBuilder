#  Copyright  2020 Alexis Lopez Zubieta
#
#  Permission is hereby granted, free of charge, to any person obtaining a
#  copy of this software and associated documentation files (the "Software"),
#  to deal in the Software without restriction, including without limitation the
#  rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
#  sell copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in
#  all copies or substantial portions of the Software.
import logging
import os
import pathlib
import re
from functools import reduce
from pathlib import Path
from typing import Optional

from packaging import version

from appimagebuilder.utils.finder import Finder
from .base_helper import BaseHelper
from ..environment import Environment


class InterpreterHandlerError(RuntimeError):
    pass


class AppRun2LibC(BaseHelper):
    """AppRun v2 glibc setup"""

    def __init__(self, app_dir, finder):
        super().__init__(app_dir, finder)

        self.priority = 100

    def get_glibc_path(self) -> str:
        path = self.finder.find_one("*/libc.so.*", [Finder.is_elf_shared_lib])
        if not path:
            raise InterpreterHandlerError("Unable to find libc.so")

        logging.info("Libc found at: %s" % os.path.relpath(path, self.app_dir))
        return path

    def get_glibc_versioned_path(self) -> Optional[Path]:
        path = self.finder.find_one("*/libc-*.so", [Finder.is_elf_shared_lib])
        if path:
            return pathlib.Path(path)
        else:
            return None

    def configure(self, env: Environment, preserve_files: [pathlib.Path]):
        try:
            env.set("APPDIR_LIBC_LIBRARY_PATH", self._get_libc_library_paths())
            env.set("APPDIR_LIBC_VERSION", self._guess_libc_version())
        except InterpreterHandlerError as err:
            logging.warning("%s" % err)
            logging.warning(
                "The resulting bundle will not be backward compatible as libc is not present"
            )

    def _guess_libc_version(self):
        version_in_filename = self._read_libc_version_from_filename()
        if version_in_filename:
            logging.info("Taking libc version from filename: %s" % version_in_filename)
            return version_in_filename

        libc_path = self.get_glibc_path()
        version_in_embed_strings = self.read_libc_version_from_embed_strings(libc_path)
        if version_in_embed_strings:
            logging.info(
                "Taking libc version from embed strings: %s" % version_in_embed_strings
            )
            return version_in_embed_strings

        raise InterpreterHandlerError("Unable to determine glibc version")

    def _read_libc_version_from_filename(self):
        libc_versioned_path = self.get_glibc_versioned_path()
        if libc_versioned_path:
            version_str = libc_versioned_path.stem.split("-")[-1]
            if re.match(r"\d+\.\d+\.?\d*", version_str):
                return version_str

        return None

    def _get_libc_library_paths(self):
        paths = self.finder.find_dirs_containing(
            pattern="*/runtime/compat/*.so*",
            file_checks=[Finder.is_file, Finder.is_elf_shared_lib],
        )
        return [path.__str__() for path in paths]

    @staticmethod
    def read_libc_version_from_embed_strings(libc_path):
        glib_version_re = re.compile(r"GLIBC_(?P<version>\d+\.\d+\.?\d*)")
        with open(libc_path, "rb") as f:
            content = str(f.read())
            glibc_version_strings = glib_version_re.findall(content)
            if glibc_version_strings:
                glibc_version_strings = map(version.parse, glibc_version_strings)
                max_glibc_version = reduce(
                    (lambda x, y: max(x, y)), glibc_version_strings
                )
                return str(max_glibc_version)
            else:
                raise InterpreterHandlerError("Unable to determine glibc version")
