import os
import shutil
from typing import List
from ...package import Package
from ...util import Namespace, run, apply_patch, download, qjoin
from ..gnu import AutoMake


class LibUnwind(Package):
    """
    :identifier: libunwind-<version>
    :param version: version to download
    """

    def __init__(self, version: str, glibc: Package = None):
        self.version = version
        self.patches = []
        self.glibc = glibc

    def ident(self):
        name = 'libunwind-'
        if self.glibc is not None:
            name += self.glibc.ident()
        else:
            name += self.version
        return name

    def is_fetched(self, ctx):
        return os.path.exists('src')

    def fetch(self, ctx):
        urlbase = 'http://download.savannah.gnu.org/releases/libunwind/'
        tarname = 'libunwind-' + self.version + '.tar.gz'
        untaredname = 'libunwind-' + self.version
        download(ctx, urlbase + tarname)
        run(ctx, ['tar', '-xf', tarname])
        shutil.move(untaredname, 'src')
        os.remove(tarname)

    def is_built(self, ctx):
        return os.path.exists('obj/src/.libs/libunwind.so')

    def _apply_patches(self, ctx):
        os.chdir(self.path(ctx, 'src'))

        gcc_version = run(ctx, '/usr/bin/gcc --version').stdout.strip().splitlines()[0].split()[-1] # libunwind is built with the default system's compiler, not ctx.cc
        gcc_major = int(gcc_version.split('.')[0])
        if gcc_major >= 10 or self.glibc is not None:
            self.patches.insert(0, '0001-Fix-compilation-with-fno-common')

        config_root = os.path.dirname(os.path.abspath(__file__))
        for path in self.patches:
            if '/' not in path:
                path = '%s/%s.patch' % (config_root, path)
            if apply_patch(ctx, path, 1):
                ctx.log.warning('applied patch %s to libunwind '
                                'directory' % path)
        os.chdir(self.path(ctx))

    def build(self, ctx):
        ctx = ctx.copy()
        self._apply_patches(ctx)
        os.makedirs('obj', exist_ok=True)
        os.chdir('obj')
        if not os.path.exists('Makefile'):
            cmd = ['../src/configure', '--prefix=' + self.path(ctx, 'install')]
            if self.glibc is not None:
                self.glibc.package_configure(ctx)
                # trick libunwind into thinking that we are cross-compiling because our target architecture
                # is newer than our current one and ./configure tries to compile and run a small C program
                # Also, we have messed up the sysroot path so ./configure won't find the libraries
                cmd += ['--host=aarch64-unknown-linux-gnu']
            else:
                ctx.cc  = '/usr/bin/gcc'
                ctx.cxx = '/usr/bin/g++'
                ctx.cflags = []
                ctx.cxxflags = []
                ctx.ldflags = []
            ctx.runenv.update({
                'CC': ctx.cc,
                'CXX': ctx.cxx,
                'CFLAGS': qjoin(ctx.cflags),
                'CXXFLAGS': qjoin(ctx.cxxflags),
                'LDFLAGS': qjoin(ctx.ldflags),
            })
            run(ctx, cmd)
        run(ctx, 'make -j%d' % ctx.jobs)

    def is_installed(self, ctx):
        return os.path.exists('install/lib/libunwind.so')

    def install(self, ctx):
        os.chdir('obj')
        run(ctx, 'make install')

    def configure(self, ctx):
        ctx.ldflags += ['-L' + self.path(ctx, 'install/lib'), '-lunwind']


class Gperftools(Package):
    """

    Finally, you may specify a list of patches to apply before building. These
    may be paths to .patch files that will be applied with ``patch -p1``, or
    choices from the following built-in patches:

    - **musl-sbrk** disables the use of __sbrk which is glibc-specific (latest upstream has a better fix for this). This has been taken from https://github.com/vusec/typeisolation.

    - **musl-test-build-hacks** modifies makefiles to not build tests (because they don't link with musl). This has been taken from https://github.com/vusec/typeisolation.

    :identifier: gperftools-<version>
    :param commit: git branch/commit to check out after cloning
    :param libunwind_version: libunwind version to use
    :param patches: optional patches to apply before building
    """

    def __init__(self, commit: str, libunwind_version='1.4-rc1', glibc: Package = None, patches: List[str] = []):
        self.commit = commit
        self.libunwind = LibUnwind(libunwind_version, glibc)
        self.glibc = glibc
        self.patches = patches

    def ident(self):
        return 'gperftools-' + self.commit

    def dependencies(self):
        yield AutoMake.default()
        yield self.libunwind

    def is_fetched(self, ctx):
        return os.path.exists('src')

    def fetch(self, ctx):
        run(ctx, 'git clone https://github.com/gperftools/gperftools.git src')
        os.chdir('src')
        run(ctx, ['git', 'checkout', self.commit])

    def is_built(self, ctx):
        return os.path.exists('obj/.libs/libtcmalloc.so')

    def _apply_patches(self, ctx):
        os.chdir(self.path(ctx, 'src'))
        config_root = os.path.dirname(os.path.abspath(__file__))
        for path in self.patches:
            if '/' not in path:
                path = '%s/%s.patch' % (config_root, path)
            if apply_patch(ctx, path, 1):
                ctx.log.warning('applied patch %s to gperftools '
                                'directory' % path)
        os.chdir(self.path(ctx))

    def build(self, ctx):
        self._apply_patches(ctx)

        if not os.path.exists('src/configure') or not os.path.exists('src/INSTALL'):
            os.chdir('src')
            run(ctx, 'autoreconf -vfi')
            self.goto_rootdir(ctx)

        os.makedirs('obj', exist_ok=True)
        os.chdir('obj')
        if not os.path.exists('Makefile'):
            prefix = self.path(ctx, 'install')
            if self.glibc is not None:
                assert(False) # FIXME: Implement me! See CustomGperftools
            run(ctx, [
                '../src/configure',
                'CPPFLAGS=-I' + self.libunwind.path(ctx, 'install/include'),
                'LDFLAGS=-L' + self.libunwind.path(ctx, 'install/lib'),
                '--prefix=' + prefix
            ])
        run(ctx, 'make -j%d' % ctx.jobs)

    def is_installed(self, ctx):
        return os.path.exists('install/lib/libtcmalloc.so')

    def install(self, ctx):
        os.chdir('obj')
        run(ctx, 'make install')

    def configure(self, ctx: Namespace):
        """
        Set build/link flags in **ctx**. Should be called from the
        ``configure`` method of an instance.

        Sets the necessary ``-I/-L/-l`` flags, and additionally adds
        ``-fno-builtin-{malloc,calloc,realloc,free}`` to CFLAGS.

        :param ctx: the configuration context
        """
        self.libunwind.configure(ctx)
        cflags = ['-fno-builtin-' + fn
                  for fn in ('malloc', 'calloc', 'realloc', 'free')]
        cflags += ['-I', self.path(ctx, 'install/include/gperftools')]
        ctx.cflags += cflags
        ctx.cxxflags += cflags
        ctx.ldflags += ['-L' + self.path(ctx, 'install/lib'),
                        '-ltcmalloc', '-lpthread']
