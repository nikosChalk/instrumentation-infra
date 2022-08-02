import os
from typing import List
from ...package import Package
from ...util import Namespace, FatalError, run
from ..llvm import LLVM


class LLVMPlugins(Package):
    """
    LLVM plugins dependency. Use this to add your own passes as a dependency to
    your own instances. In your own plugins directory, your Makefile should look
    like this (see the `skeleton
    <https://github.com/vusec/instrumentation-skeleton/blob/master/llvm-plugins/Makefile>`_
    for an example)::

        BUILD_SUFFIX = <build_suffix>
        LLVM_VERSION = <llvm_version>
        SETUP_SCRIPT = <path_to_setup.py>
        SUBDIRS      = <optional list of subdir names containing passes>
        include <path_to_infra>/infra/packages/llvm_plugins/Makefile

    The makefile can be run as-is using ``make`` in your plugins directory
    during development, without invoking the setup script directly. It creates
    two shared objects in
    ``build/packages/llvm-plugins-<build_suffix>/install``:

    - ``libplugins-opt.so``: used to run the passes with LLVM's ``opt`` utility.
      Can be used in a customized build system or for debugging.

    The passes are invoked at compile time.
    The passes are invoked by adding their registered names to the flags passed to the LLVM opt.
    In other words, by adding ``-mllvm <passname>`` to ``ctx.cflags``
    in the ``configure`` method of your instance. The
    :func:`LLVM.add_plugin_flags` helper also adds them at link time. Before using
    passes, you must call ``llvm_plugins.configure(ctx)`` to load the passes
    into the plugin.

    For the :ref:`pkg-config <usage-pkg-config>` command of this package, the
    ``--objdir`` option points to the build directory.

    :identifier: llvm-plugins-<build_suffix>
    :param llvm: LLVM package to link against
    :param srcdir: source directory containing your LLVM passes
    :param build_suffix: identifier for this set of passes
    :param use_builtins: whether to include :doc:`built-in LLVM passes
                         <passes>` in the shared object
    :param debug: enable to compile passes with ``-O0 -ggdb``
    :todo: extend this to support compile-time plugins
    """

    def __init__(self, llvm: LLVM,
                       srcdir: str,
                       build_suffix: str,
                       use_builtins: bool,
                       debug = False):
        self.llvm = llvm
        self.custom_srcdir = os.path.abspath(srcdir)
        self.build_suffix = build_suffix
        self.builtin_passes = BuiltinLLVMPlugins(llvm) if use_builtins else None
        self.debug = debug

    def ident(self):
        return 'llvm-plugins-' + self.build_suffix

    def _srcdir(self, ctx):
        if not os.path.exists(self.custom_srcdir):
            raise FatalError('llvm-plugins dir "%s" does not exist' %
                             self.custom_srcdir)
        return self.custom_srcdir

    def dependencies(self):
        yield self.llvm
        # yield self.llvm.binutils # for ld.gold TODO: Is this still needed? Test for it on a clean repo
        if self.builtin_passes:
            yield self.builtin_passes

    def fetch(self, ctx):
        pass

    def build(self, ctx):
        os.makedirs('obj', exist_ok=True)
        os.chdir(self._srcdir(ctx))
        self._run_make(ctx, '-j%d' % ctx.jobs)

    def install(self, ctx):
        os.chdir(self._srcdir(ctx))
        self._run_make(ctx, 'install')

    def _run_make(self, ctx, *args, **kwargs):
        return run(ctx, [
            'make', *args,
            'OBJDIR=' + self.path(ctx, 'obj'),
            'PREFIX=' + self.path(ctx, 'install'),
            'USE_BUILTINS=' + str(bool(self.builtin_passes)).lower(),
            'DEBUG=' + str(self.debug).lower()
        ], **kwargs)

    def is_fetched(self, ctx):
        return True

    def is_built(self, ctx):
        return False

    def is_installed(self, ctx):
        return False

    def pkg_config_options(self, ctx):
        yield ('--objdir',
               'absolute build path',
               self.path(ctx, 'obj'))
        yield from super().pkg_config_options(ctx)

    def configure(self, ctx: Namespace):
        """
        Set build/link flags in **ctx**. Should be called from the ``configure``
        method of an instance.

        :param ctx: the configuration context
        """
        libpath = self.path(ctx, 'install/libplugins-opt.so')
        cflags = ['-Xclang', '-load', '-Xclang', libpath]
        ctx.cflags += cflags
        ctx.cxxflags += cflags
        ctx.ldflags += cflags

    def runtime_cflags(self, ctx: Namespace) -> List[str]:
        """
        Returns a list of CFLAGS to pass to a runtime library that depends on
        features from passes. These set include directories for header includes
        of built-in pass functionalities such as the ``NOINSTRUMENT`` macro.

        :param ctx: the configuration context
        """
        if self.builtin_passes:
            return self.builtin_passes.runtime_cflags(ctx)
        return []


class BuiltinLLVMPlugins(LLVMPlugins):
    """
    Subclass of :class:`LLVMPlugins` for :doc:`built-in passes <passes>`. Use
    this if you don't have any custom passes and just want to use the built-in
    passes. Configuration happens in the same way as described above: by
    calling the :func:`configure` method.

    In addition to the shared objects listed above, this package also produces
    a static library called ``libplugins-builtin.a`` which is used by the
    :class:`LLVMPlugins` to include built-in passes when ``use_builtins`` is
    ``True``.

    For the :ref:`pkg-config <usage-pkg-config>` command of this package, the
    following options are added in addition to
    ``--root``/``--prefix``/``--objdir``:

    - ``--cxxflags`` lists compilation flags for custom passes that depend on
      built-in analysis passes (sets include path for headers).

    - ``--runtime-cflags`` prints the value of
      :func:`LLVMPlugins.runtime_cflags`.

    :identifier: llvm-plugins-builtin-<llvm.version>
    :param llvm: LLVM package to link against
    """

    def __init__(self, llvm: LLVM):
        super().__init__(llvm, '.', 'builtin-' + llvm.version, False)
        self.custom_srcdir = None

    def _srcdir(self, ctx, *subdirs):
        return os.path.join(ctx.paths.infra, 'llvm-plugins',
                            self.llvm.version, *subdirs)

    def is_built(self, ctx):
        files = ('libplugins-builtin.a', 'libplugins-opt.so')
        return all(os.path.exists('obj/' + f) for f in files)

    def is_installed(self, ctx):
        files = ('libplugins-builtin.a', 'libplugins-opt.so')
        return all(os.path.exists('install/' + f) for f in files)

    def pkg_config_options(self, ctx):
        yield ('--cxxflags',
               'pass compile flags',
               ['-I', self._srcdir(ctx, 'include')])
        yield ('--runtime-cflags',
               'runtime compile flags',
               self.runtime_cflags(ctx))
        yield from super().pkg_config_options(ctx)

    def runtime_cflags(self, ctx):
        return ['-I', self._srcdir(ctx, 'include/runtime')]
