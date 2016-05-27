
Appendix: tips and tricks
=========================

This is a collection of various tips and tricks that didn't fit in any
particular section, but that you probably want to know, or at least
want to know that they exist :)


Use clang as a compiler on linux instead of gcc
-----------------------------------------------

When running on debian/ubuntu, the best solution (the "native" one) is to
change your default compiler, like that::

    sudo apt-get install clang
    sudo update-alternatives --config c++

Alternatively, you can set the following in your ``config.yaml`` file::

    CONFIGURE_OPTS = ['CC=/usr/bin/clang', 'CXX=/usr/bin/clang++']


Compiling Steem without dependency on Qt5
-----------------------------------------

Add the following to your ``config.yaml`` file::

    build_environments:
        steem:
            cmake_args: ['-DENABLE_CONTENT_PATCHING=OFF', '-DLOW_MEMORY_NODE=ON']
