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
import subprocess
import re
import os

from appimagebuilder.utils import shell

CLI_REQUIRE = ["dpkg-query"]


class FilePackageResolver:
    """Resolve which deb packages provide a given file using `dpkg-query -S`"""

    def __init__(self):
        self.logger = logging.getLogger(str(self.__class__.__name__))
        self._cli_tools = shell.require_executables(CLI_REQUIRE)

    def resolve(self, files) -> {}:
        stdout_data = self._run_dpkg_query_s(files)
        results = self._parse_dpkg_query_s_output(stdout_data)

        return results

    def _run_dpkg_query_s(self, files):
        command = "{dpkg-query} -S {files}"
        command = command.format(**self._cli_tools, files=" ".join(files))
        self.logger.info(command)
        _proc = subprocess.run(command, stdout=subprocess.PIPE, shell=True)
        stdout_data = _proc.stdout.decode()
        return stdout_data

    def _extract_package_names(self, pkg_names):
        match = re.match(r"diversion by (.+?) (to|from)", pkg_names)
        if match:
            extracted_names = match.group(1).strip()
            return extracted_names
        else:
            return pkg_names.strip()

    def _parse_dpkg_query_s_output(self, stdout_data):
        results = {}
        for line in stdout_data.splitlines():
            line_parts = line.split(sep=": ", maxsplit=1)
            pkg_names = self._extract_package_names(line_parts[0])
            file_path = line_parts[1]
            for pkg_name in pkg_names.split(","):
                pkg_name = pkg_name.strip()
                results[file_path] = pkg_name
        return results
