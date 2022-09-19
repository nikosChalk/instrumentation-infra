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
    It is assumed to be installed in self.sysroot, and the C runtime from the crosstool-ng toolchain
    should also be copied there.
    MTEglibc is built with the "--enable-memory-tagging" flag
    """

    def __init__(self, version: str, sysroot: str, llvm: Package):
        self.version = version
        self.sysroot = sysroot
        self.llvm = llvm

        self.cflags = [
            f'-I{self.sysroot}/usr/include',
            f'--sysroot={self.sysroot}',
            '-march=armv8.5-a+memtag',
        ]
        self.cxxflags = [
            f'-I{self.sysroot}/usr/include',
            f'-I{self.sysroot}/usr/include/c++/11.2.0',
            f'-I{self.sysroot}/usr/include/c++/11.2.0/aarch64-unknown-linux-gnu',
            f'--sysroot={self.sysroot}',
            '-march=armv8.5-a+memtag',
        ]
        self.ldflags = [
            f'-L{self.sysroot}/usr/lib64',
            f'--sysroot={self.sysroot}',
            '-Wl,-rpath=/sysroot/lib64',
            '-Wl,--dynamic-linker=/sysroot/lib64/ld-linux-aarch64.so.1',
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
        return os.path.exists(f'{self.sysroot}/lib64/libc.so.6')
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

    def configure(self, ctx):
        """
        Set build/link flags in **ctx**. Should be called from the
        ``configure`` method of an instance.

        :param ctx: the configuration context
        """
        ctx.cflags += ['-fPIE', '-pie'] + self.cflags
        ctx.cxxflags += ['-fPIE', '-pie'] + self.cxxflags
        ctx.ldflags += ['-Wl,--verbose', '-fPIE', '-pie'] + self.ldflags
