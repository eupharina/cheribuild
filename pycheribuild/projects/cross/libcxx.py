#
# Copyright (c) 2016 Alex Richardson
# All rights reserved.
#
# This software was developed by SRI International and the University of
# Cambridge Computer Laboratory under DARPA/AFRL contract FA8750-10-C-0237
# ("CTSRD"), as part of the DARPA CRASH research programme.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#

from ..cheribsd import BuildCHERIBSD
from .crosscompileproject import *
from ..llvm import BuildLLVM
from ..run_qemu import LaunchQEMU
from ...configloader import ConfigLoader
from ...utils import statusUpdate

installToCXXDir = ConfigLoader.ComputedDefaultValue(
    function=lambda config, project: BuildCHERIBSD.rootfsDir(config) / "extra/c++",
    asString="$CHERIBSD_ROOTFS/extra/c++")


class BuildLibCXXRT(CrossCompileCMakeProject):
    repository = "https://github.com/CTSRD-CHERI/libcxxrt.git"
    defaultInstallDir = installToCXXDir

    def __init__(self, config: CheriConfig):
        self.linkDynamic = True  # Hack: we always want to use the dynamic toolchain file, build system adds -static
        super().__init__(config)
        self.add_cmake_options(CHERI_PURE=True)

    def install(self, **kwargs):
        self.installFile(self.buildDir / "lib/libcxxrt.a", self.installDir / "usr/libcheri/libcxxrt.a", force=True)
        self.installFile(self.buildDir / "lib/libcxxrt.so", self.installDir / "usr/libcheri/libcxxrt.so", force=True)


class BuildLibCXX(CrossCompileCMakeProject):
    repository = "https://github.com/CTSRD-CHERI/libcxx.git"
    defaultInstallDir = installToCXXDir
    dependencies = ["libcxxrt"]

    @classmethod
    def setupConfigOptions(cls, **kwargs):
        super().setupConfigOptions(**kwargs)
        cls.qemu_host = cls.addConfigOption("qemu-host", help="The QEMU SSH hostname to connect to for running tests",
                                            default=lambda c, p: "localhost:" + str(LaunchQEMU.sshForwardingPort))
        cls.qemu_user = cls.addConfigOption("qemu-user", default="root", help="The CheriBSD used for running tests")

    def __init__(self, config: CheriConfig):
        self.linkDynamic = True  # Hack: we always want to use the dynamic toolchain file, build system adds -static
        super().__init__(config)
        # TODO: do I even need the toolchain file to cross compile?
        self.add_cmake_options(
            LIBCXX_ENABLE_SHARED=False,  # not yet
            LIBCXX_ENABLE_STATIC=True,
            LIBCXX_ENABLE_EXPERIMENTAL_LIBRARY=False,  # not yet
            LIBCXX_INCLUDE_BENCHMARKS=False,
            LIBCXX_INCLUDE_DOCS=False,
            # exceptions and rtti still missing:
            LIBCXX_ENABLE_EXCEPTIONS=False,
            LIBCXX_ENABLE_RTTI=False,
        )
        # select libcxxrt as the runtime library
        self.add_cmake_options(
            LIBCXX_CXX_ABI="libcxxrt",
            LIBCXX_CXX_ABI_INCLUDE_PATHS=BuildLibCXXRT.sourceDir / "src",
            LIBCXX_CXX_ABI_LIBRARY_PATH=BuildLibCXXRT.buildDir / "lib",
            LIBCXX_ENABLE_STATIC_ABI_LIBRARY=True,
        )
        # add the config options required for running tests:
        self.add_cmake_options(
            LIBCXX_INCLUDE_TESTS=True,
            LIBCXX_SYSROOT=config.sdkDir / "sysroot",
            LIBCXX_TARGET_TRIPLE=self.targetTriple,
            LLVM_CONFIG_PATH=BuildLLVM.buildDir / "bin/llvm-config",
            LIBCXXABI_USE_LLVM_UNWINDER=False,  # we have a fake libunwind in libcxxrt
            LIBCXX_EXECUTOR="SSHExecutor('{host}', username='{user}')".format(host=self.qemu_host, user=self.qemu_user),
            LIBCXX_TARGET_INFO="libcxx.test.target_info.CheriBSDRemoteTI",
        )
