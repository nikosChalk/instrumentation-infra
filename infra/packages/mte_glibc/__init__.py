import os
import shutil
import pathlib
from typing import List, Optional
from ...package import Package
from ...util import Namespace, run, apply_patch, download, qjoin
from ..gnu import AutoMake
from ..llvm import LLVM

class MTEglibc(Package):
    """
    Custom glibc to use. The glibc to use is assumed to be already built and installed
    as building it requires already an existing crosstool-ng toolchain.
    It is assumed to be installed in self.host_sysroot, and the C runtime from the crosstool-ng toolchain
    should also be copied there.
    MTEglibc is built with the "--enable-memory-tagging" flag
    On the target system insall your self.host_sysroot under self.target_sysroot, run the binaries as:
    ```
    export TDI_LD_LIBRARY_PATH="<sysroot>/lib64:<sysroot>/usr/lib64"
    LD_LIBRARY_PATH="${TDI_LD_LIBRARY_PATH}" <./my-binary>
    ```
    """

    def __init__(self, version: str, host_sysroot: str, target_sysroot: str, llvm: Package):
        self.version = version
        self.host_sysroot = host_sysroot
        self.target_sysroot = target_sysroot
        self.llvm = llvm

        self.cflags = [
            f'-I{self.host_sysroot}/usr/include',
            f'--sysroot={self.host_sysroot}',
            '-march=armv8.5-a+memtag',
        ]
        self.cxxflags = [
            f'-I{self.host_sysroot}/usr/include',
            f'-I{self.host_sysroot}/usr/include/c++/11.2.0',
            f'-I{self.host_sysroot}/usr/include/c++/11.2.0/aarch64-unknown-linux-gnu',
            f'--sysroot={self.host_sysroot}',
            '-march=armv8.5-a+memtag',
        ]
        self.ldflags = [
            f'-L{self.host_sysroot}/lib64',
            f'-L{self.host_sysroot}/lib64/gcc/aarch64-unknown-linux-gnu/11.2.0',
            f'-L{self.host_sysroot}/usr/lib64',
            f'--sysroot={self.host_sysroot}',
            f'-Wl,-rpath={self.target_sysroot}/lib64',
            f'-Wl,--dynamic-linker={self.target_sysroot}/lib64/ld-linux-aarch64.so.1',
            '-march=armv8.5-a+memtag',
        ]

    def ident(self):
        return 'glibc-' + self.version

    def dependencies(self):
        yield from super().dependencies()
    def is_fetched(self, ctx):
        return True
    def fetch(self, ctx):
        pass
    def is_built(self, ctx):
        return True

    def build(self, ctx):
        pass
    def is_installed(self, ctx):
        return os.path.exists(f'{self.host_sysroot}/lib64/libc.so.6')
    def install(self, ctx):
        pass

    def package_configure(self, ctx):
        """
        Set build/link flags in **ctx** for packages that are to be linked against
        this glibc.
        """
        self.llvm.configure(ctx) # this will clear cflags, cxxflags, and ldflags
        ctx.cflags += self.cflags
        ctx.cxxflags += self.cxxflags
        ctx.ldflags += self.ldflags

    def configure(self, ctx, static: bool, enable_gperftools:bool):
        """
        Set build/link flags in **ctx**. Should be called from the
        ``configure`` method of an instance.

        :param ctx: the configuration context
        """
        ctx.cflags += ['-fPIE', '-pie'] + self.cflags
        ctx.cxxflags += ['-fPIE', '-pie'] + self.cxxflags
        ctx.ldflags += ['-Wl,--verbose', '-fPIE', '-pie'] + self.ldflags

        if static:
            ctx.log.warning(f"!!! DISABLE relink.py as it produces wrong binaries with '-static' !!!")
            ctx.ldflags += [
                '-static', '-static-libgcc',
                '-Bstatic', '--no-undefined',
                '-Wl,--start-group'
            ]
            if not enable_gperftools:
                ctx.extra_libs = ['-lgcc', '-lstdc++', '-lc', '-lm', '-Wl,--end-group']
            else:
                ctx.extra_libs = [
                    # oder matters!
                    '-Wl,-whole-archive', '-lunwind', '-Wl,-no-whole-archive',
                    '-lgcc', '-lstdc++',
                    '-ltcmalloc',
                    '-lc', '-lm',
                    '-Wl,--end-group',
                ]
