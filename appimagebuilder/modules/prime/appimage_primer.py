#  Copyright  2022 Alexis Lopez Zubieta
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
import hashlib
import logging
import os
import pathlib
import shutil
import stat
import subprocess
from urllib import request

import gnupg
import lief

from appimagebuilder.modules.prime.base_primer import BasePrimer
from appimagebuilder.utils import shell


class AppImagePrimer(BasePrimer):
    def __init__(self, context):
        super().__init__(context)
        self.logger = logging.getLogger("AppImagePrimer")
        self.config = self.context.recipe.AppImage
        self.bundle_main_arch = self.config.arch()
        self.carrier_path = (
            self.context.build_dir / "prime" / ("runtime-%s" % self.bundle_main_arch)
        )

        appimage_file_name = self._resolve_appimage_file_name()
        self.appimage_path = pathlib.Path.cwd() / appimage_file_name

    def prime(self):
        if not self.carrier_path.exists():
            self._get_appimage_kit_runtime()

        # create payload
        payload_path = self._make_squashfs(self.context.app_dir)

        # prepare carrier (a.k.a. "runtime" using a different name to differentiate from the AppRun settings)
        shutil.copyfile(self.carrier_path, self.appimage_path)
        self._add_payload(payload_path)

        carrier_binary = lief.parse(self.carrier_path.__str__())
        self._add_appimage_update_information(carrier_binary)
        (bundle_md5, bundle_sha256) = self._generate_checksums()
        # md5 digest skips sections instead of using 0 which differ from how the signature checksum is generated
        # this will be skipped is not a mandatory on the spec
        # self._add_md5_digest(carrier_binary, bundle_md5)
        self._sign_bundle_sha256_digest(carrier_binary, bundle_sha256)

        self._generate_zsync_file()
        self._make_appimage_executable()

    def _resolve_appimage_file_name(self):
        if not self.context.recipe.AppImage.file_name():
            appimage_file_name = "%s-%s-%s.AppImage" % (
                self.context.app_info.name,
                self.context.app_info.version,
                self.bundle_main_arch,
            )
        else:
            appimage_file_name = self.context.recipe.AppImage.file_name()

        return appimage_file_name

    def _make_squashfs(self, appdir: pathlib.Path):
        payload_path = appdir.with_suffix(".squashfs")
        mksquashfs_bin = shell.require_executable("mksquashfs")
        command = [
            mksquashfs_bin,
            str(appdir),
            str(payload_path),
            "-root-owned",
            "-noappend",
            "-reproducible",
        ]

        # I think this is better than hardcoding the supported compressions
        # If the team behind AppImageKit adds a new compression
        # we wouldn't need to update the code and release a new version just for a new compression method
        comp = self.config.comp() or "xz"
        if comp != "None":
            command += [ "-comp", comp]
        else:
            command += ["-no-compression"]

        self.logger.info("Creating squashfs from AppDir")
        self.logger.debug(" ".join(command))
        subprocess.run(command, check=True)
        return payload_path

    def _get_appimage_kit_runtime(self):
        url = (
            "https://github.com/AppImage/AppImageKit/releases/download/continuous/runtime-%s"
            % self.bundle_main_arch
        )
        logging.info("Downloading: %s" % url)

        os.makedirs(self.carrier_path.parent, exist_ok=True)
        request.urlretrieve(url, self.carrier_path)

    def _add_payload(self, payload_path):
        try:
            with open(self.appimage_path, "ab") as appimage_file:
                with open(payload_path, "rb") as payload_file:
                    shutil.copyfileobj(payload_file, appimage_file)
        except RuntimeError:
            raise
        finally:
            payload_path.unlink(missing_ok=True)

    def _make_appimage_executable(self):
        st = os.stat(self.appimage_path)
        os.chmod(self.appimage_path, st.st_mode | stat.S_IEXEC)

    def _add_appimage_update_information(self, binary):
        update_information = self.config["update-information"]()
        if update_information:
            self.logger.info('Setting update information: "%s"' % update_information)
            section = binary.get_section(".upd_info")
            self._patch_appimage(
                section.file_offset, bytes(update_information, "utf-8")
            )

    def _sign_bundle_sha256_digest(
        self, carrier_elf: lief.Binary, bundle_sha256: bytes
    ):
        sign_key = self.config["sign-key"]()
        if sign_key:
            gpg = gnupg.GPG()
            # sign both files as if they were together

            signature = gpg.sign(bundle_sha256.hex(), keyid=sign_key, detach=True)
            signature_section = carrier_elf.get_section(".sha256_sig")
            self._patch_appimage(signature_section.file_offset, signature.data)

            # resolve secret key id in case a key fingerprint was used
            key = gpg.export_keys(keyids=[sign_key])
            signature_key_section = carrier_elf.get_section(".sig_key")
            self._patch_appimage(signature_key_section.file_offset, bytes(key, "utf-8"))

    def _generate_checksums(self):
        md5 = hashlib.md5()
        sha256 = hashlib.sha256()
        with open(self.appimage_path, "rb") as appimage_file:
            while True:
                data = appimage_file.read(2 ** 10)
                if not data:
                    break
                md5.update(data)
                sha256.update(data)

        return md5.digest(), sha256.digest()

    def _add_md5_digest(self, carrier_binary, bundle_md5):
        md5_digest_section = carrier_binary.get_section(".digest_md5")
        if md5_digest_section:
            self._patch_appimage(md5_digest_section.file_offset, bundle_md5)

    def _patch_appimage(self, offset, data):
        # using manual patch over lief as the elf structure should not be changed
        with open(self.appimage_path, "r+b") as appimage_file:
            appimage_file.seek(offset, 0)
            appimage_file.write(data)

    def _generate_zsync_file(self):
        if self.config["update-information"]:
            zsyncmake_bin = shell.require_executable("zsyncmake")
            command = [
                zsyncmake_bin,
                "-u",
                self.appimage_path.name,
                self.appimage_path.__str__(),
            ]
            self.logger.debug(command)
            subprocess.run(command, check=True)
