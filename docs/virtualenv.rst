
Appendix: dealing with virtualenvs
==================================

TODO: write properly

It is very recommended to install inside a virtualenv. See :doc:`install` for more
Actually, that's the whole point of the virtualenvs, is that you don't need to install anything as root, so you don't mess up your system. Everything is contained in your project, which you should run as a normal user anyway. The only thing really needed to install as root with apt-get are: python3, virtualenvwrapper, and maybe python3-pip. All the rest, creation of the virtualenv and pip installing stuff inside should be run as a normal user. I will also add this to the doc.

