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
import os
import logging
from urllib import request

from appimagebuilder.context import Context
from appimagebuilder.utils.appimagetool import AppImageToolCommand


class AppImageCreator:
    def __init__(self, context: Context):
        self.context = context
        self.app_dir = context.app_dir
        self.app_name = context.app_info.name
        self.app_version = context.app_info.version

        self.target_arch = context.recipe.AppImage.arch()
        self.update_information = (
            context.recipe.AppImage["update-information"]() or "None"
        )
        self.guess_update_information = False

        if self.update_information == "None":
            self.update_information = None
        elif self.update_information == "guess":
            # appimagetool supports a param --guess, -g
            # this automatically generates the update_information based on CI
            # variables, perhaps, we should use that
            self.update_information = None
            self.guess_update_information = True

        self.sing_key = context.recipe.AppImage["sign-key"]() or "None"
        if self.sing_key == "None":
            self.sing_key = None

        fallback_file_name = os.path.join(
            os.getcwd(),
            "%s-%s-%s.AppImage" % (self.app_name, self.app_version, self.target_arch),
        )
        self.target_file = context.recipe.AppImage.file_name() or fallback_file_name

    def create(self):
        self._assert_target_architecture()

        runtime_url = self._get_runtime_url()
        runtime_path = self._get_runtime_path()
        self._download_runtime_if_required(runtime_path, runtime_url)

        self._generate_appimage(runtime_path)

    def _generate_appimage(self, runtime_path):
        appimage_tool = AppImageToolCommand(self.app_dir, self.target_file)

        # appimagetool uses different architecture names than AppImageKit runtime releases
        if self.target_arch == "aarch64":
            appimage_tool_arch = "arm_aarch64"
        elif self.target_arch == "armhf":
            appimage_tool_arch = "arm"
        else:
            appimage_tool_arch = self.target_arch

        appimage_tool.target_arch = appimage_tool_arch
        appimage_tool.update_information = self.update_information
        appimage_tool.guess_update_information = self.guess_update_information
        appimage_tool.sign_key = self.sing_key
        appimage_tool.runtime_file = runtime_path
        appimage_tool.run()

    def _download_runtime_if_required(self, runtime_path, runtime_url):
        if not os.path.exists(runtime_path):
            logging.info("Downloading runtime: %s" % runtime_url)
            request.urlretrieve(runtime_url, runtime_path)

    def _get_runtime_path(self):
        os.makedirs(self.context.build_dir, exist_ok=True)
        runtime_path = self.context.build_dir / ("runtime-%s" % self.target_arch)

        return str(runtime_path)

    def _get_runtime_url(self):
        runtime_url_template = "https://github.com/AppImage/type2-runtime/releases/tag/continuous/runtime-%s"
        runtime_url = runtime_url_template % self.target_arch
        return runtime_url

    def _assert_target_architecture(self):
        supported_architectures = ["i686", "aarch64", "armhf", "x86_64"]
        if self.target_arch not in supported_architectures:
            logging.error(
                "There is not a prebuild runtime for the %s architecture."
                " You will have to build the AppImage runtime manually."
                % self.target_arch
            )
