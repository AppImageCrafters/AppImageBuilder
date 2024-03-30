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
import os
import pathlib

from appimagebuilder.utils.finder import Finder
from appimagebuilder.context import AppInfo, Context, BundleInfo
from appimagebuilder.commands.apt_deploy import AptDeployCommand
from appimagebuilder.commands.create_appimage import CreateAppImageCommand
from appimagebuilder.commands.file_deploy import FileDeployCommand
from appimagebuilder.commands.pacman_deploy import PacmanDeployCommand
from appimagebuilder.commands.run_script import RunScriptCommand
from appimagebuilder.commands.run_test import RunTestCommand
from appimagebuilder.commands.setup_app_info import SetupAppInfoCommand
from appimagebuilder.commands.setup_runtime import SetupRuntimeCommand
from appimagebuilder.commands.setup_symlinks import SetupSymlinksCommand
from appimagebuilder.commands.deploy_record import (
    WriteDeployRecordCommand,
)
from appimagebuilder.recipe.roamer import Roamer


class Orchestrator:
    """Transforms a recipe into a command list"""

    def process(self, recipe: Roamer, args):
        if recipe.version() == 1:
            return self._prepare_commands_for_recipe_v1(args, recipe)

        raise RuntimeError("Unknown recipe version:  %s" % recipe.version())

    def _prepare_commands_for_recipe_v1(self, args, recipe):
        context = self._extract_v1_recipe_context(args, recipe)
        commands = []
        if not args.skip_script:
            command = RunScriptCommand(context, recipe.script, "main script")
            commands.append(command)

        if not args.skip_build:
            commands.extend(self._create_app_dir_commands(context, recipe))

        if not args.skip_tests and recipe.AppDir.test:
            command = RunTestCommand(context, recipe.AppDir.test)
            commands.append(command)

        if not args.skip_appimage and recipe.AppImage:
            command = CreateAppImageCommand(context, recipe)
            commands.append(command)

        return commands

    def _create_app_dir_commands(self, context, recipe):
        commands = []

        commands.extend(self._create_deploy_commands(context, recipe))

        commands.extend(self._create_setup_commands(context, recipe))

        commands.append(WriteDeployRecordCommand(context))

        return commands

    def _create_deploy_commands(self, context, recipe):
        commands = []
        if recipe.AppDir.before_bundle:
            command = RunScriptCommand(
                context, recipe.AppDir.before_bundle, "before bundle script"
            )
            commands.append(command)
        apt_section = recipe.AppDir.apt
        if apt_section:
            command = self._generate_apt_deploy_command(context, apt_section)
            commands.append(command)
        pacman_section = recipe.AppDir.pacman
        if pacman_section:
            command = self._generate_pacman_deploy_command(context, pacman_section)
            commands.append(command)
        files_section = recipe.AppDir.files
        if files_section:
            command = FileDeployCommand(
                context,
                files_section.include() or [],
                files_section.exclude() or [],
            )
            commands.append(command)
        if recipe.AppDir.after_bundle:
            command = RunScriptCommand(
                context, recipe.AppDir.after_bundle, "after bundle script"
            )
            commands.append(command)

        return commands

    def _create_setup_commands(self, context, recipe):
        commands = []
        if recipe.AppDir.before_runtime:
            command = RunScriptCommand(
                context, recipe.AppDir.before_runtime, "before runtime script"
            )
            commands.append(command)

        finder = Finder(context.app_dir)
        commands.append(SetupSymlinksCommand(context, recipe, finder))

        commands.append(SetupRuntimeCommand(context, finder))

        commands.append(SetupAppInfoCommand(context))

        if recipe.AppDir.after_runtime:
            command = RunScriptCommand(
                context, recipe.AppDir.after_runtime, "after runtime script"
            )
            commands.append(command)

        return commands

    def _generate_apt_deploy_command(self, context, apt_section):
        apt_archs = apt_section.arch()
        if isinstance(apt_archs, str):
            apt_archs = [apt_archs]

        sources = []
        keys = []
        for item in apt_section.sources():
            if "sourceline" in item:
                sources.append(item["sourceline"])
            if "key_url" in item:
                keys.append(item["key_url"])

        return AptDeployCommand(
            context,
            apt_section.include(),
            apt_section.exclude() or [],
            apt_archs,
            sources,
            keys,
            apt_section.allow_unauthenticated() or False,
        )

    def _generate_pacman_deploy_command(self, context, pacman_section):
        return PacmanDeployCommand(
            context,
            pacman_section.include(),
            pacman_section.exclude(),
            pacman_section["Architecture"](),
            pacman_section.repositories(),
            pacman_section.options(),
        )

    def _extract_v1_recipe_context(self, args, recipe):
        if recipe.AppDir.path() and os.path.exists(recipe.AppDir.path()):
            app_dir_path = pathlib.Path(recipe.AppDir.path()).absolute()
        else:
            app_dir_path = pathlib.Path(args.appdir).absolute()

        build_dir_path = pathlib.Path(args.build_dir).absolute()

        app_info_section = recipe.AppDir.app_info
        app_info = AppInfo(
            app_info_section.id(),
            app_info_section.name() or app_info_section.id(),
            app_info_section.icon() or "application-vnd.appimage",
            app_info_section.version(),
            app_info_section.exec(),
            app_info_section.exec_args(),
        )
        bundle_info = BundleInfo(
            app_dir=app_dir_path,
            app_info=app_info,
            update_string=recipe.AppImage["update-information"]() or "guess",
            runtime_arch=recipe.AppImage.arch(),
            compression=recipe.AppImage.comp() or "xz",
            sign_key=recipe.AppImage["sign-key"]() or None,
            file_name=recipe.AppImage["file_name"] or None,
        )
        return Context(
            recipe=recipe,
            recipe_path=pathlib.Path(args.recipe),
            app_info=app_info,
            bundle_info=bundle_info,
            app_dir=app_dir_path,
            build_dir=build_dir_path,
        )
