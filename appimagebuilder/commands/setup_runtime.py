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
from appimagebuilder.context import Context
from appimagebuilder.modules.setup.apprun_2.apprun2 import AppRunV2Setup
from appimagebuilder.commands.command import Command
from packaging import version

from appimagebuilder.modules.setup.apprun_3.apprun3 import AppRunV3Setup


class SetupRuntimeCommand(Command):
    def __init__(self, context: Context, finder):
        super().__init__(context, "runtime setup")
        self.context = context
        self._finder = finder

    def id(self):
        return "runtime-setup"

    def __call__(self, *args, **kwargs):
        apprun_version = self.context.recipe.AppDir.runtime.version() or "v2.0.0"
        apprun_version = version.parse(apprun_version)
        runtime_setup = None
        if version.parse("v2.0.0") <= apprun_version < version.parse("v3.0.0"):
            runtime_setup = AppRunV2Setup(self.context, self._finder)

        if not runtime_setup and version.parse("v3.0.0") <= apprun_version < version.parse("v4.0.0"):
            runtime_setup = AppRunV3Setup(self.context)

        if not runtime_setup:
            raise RuntimeError("Unsupported runtime version: %s" % apprun_version)

        runtime_setup.setup()
