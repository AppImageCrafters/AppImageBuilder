#  Copyright  2021 Alexis Lopez Zubieta
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
import subprocess

from appimagebuilder.utils import shell


class FilePackageResolver:
    """Resolve which package provide a given file using `pacman -F`"""

    REQUIRED_COMMANDS = ["pacman"]

    def __init__(self):
        self.logger = logging.getLogger(str(self.__class__.__name__))
        self._cli_tools = shell.require_executables(self.REQUIRED_COMMANDS)

    def resolve(self, files) -> {}:
        output = self._run_pacman_f(files)
        results = self._parse_pacman_f_output(output)
        return results

    def _run_pacman_f(self, files):
        # make sure that the files are str
        files = [str(file) for file in files]
        files = [f for f in files if not f.startswith('/home/')]

        files = list(set(files))
        command = ['pacman', '-F'] + files

        # ensure C locale is used to avoid locales affecting the output format
        env = os.environ.copy()
        env["LC_ALL"] = "C"

        self.logger.info(command)
        _proc = subprocess.run(
            command, stdout=subprocess.PIPE, shell=False, env=env)
        stdout_data = _proc.stdout.decode()
        return stdout_data

    @staticmethod
    def _parse_pacman_f_output(output):
        results = {}
        for match in re.findall(
            r"(?P<file>.*) is owned by (?P<pkg_name>.*) (?P<pkg_version>.*)", output
        ):
            file = pathlib.Path(match[0])
            pkg_name = match[1]
            pkg_name = pkg_name.split("/")[-1]
            results[file] = pkg_name
        return results
