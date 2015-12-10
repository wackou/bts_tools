#!/usr/bin/env bash

set -o nounset
USER=$1
GIT_NAME=$2
GIT_EMAIL=$3
set +o nounset

cd ~

# install ssh keys file
if [ ! -f ~/.ssh/id_rsa ]; then
    ssh-keygen -b 4096 -N "" -f ~/.ssh/id_rsa
fi
if [ -f /tmp/authorized_keys ]; then
    cp /tmp/authorized_keys ~/.ssh/
fi

# install and activate virtualenvwrapper
cat <<EOF >> .bashrc

. /usr/share/virtualenvwrapper/virtualenvwrapper_lazy.sh
EOF

source /usr/share/virtualenvwrapper/virtualenvwrapper_lazy.sh

# clone git repo
if [ ! -d ~/bts_tools ]; then
    git clone https://github.com/wackou/bts_tools
fi
cd bts_tools
git config user.email "$GIT_EMAIL"
git config user.name "$GIT_NAME"

# create virtualenv
echo "create bts_tools virtualenv"
mkvirtualenv -p /usr/bin/python3 bts_tools

echo "install git version of the bts_tools"
pushd ~/bts_tools
workon bts_tools
git stash && git pull && git stash apply
rm -fr dist; python setup.py sdist && (pip uninstall -y bts_tools; pip install dist/bts_tools-*.tar.gz)

# FIXME: temporary fix, see: http://stackoverflow.com/questions/34157314/autobahn-websocket-issue-while-running-with-twistd-using-tac-file
pip install https://github.com/crossbario/autobahn-python/archive/master.zip

if [ -f /tmp/config.yaml ]; then
    # ensure we have a ~/.bts_tools folder
    bts2 list >/dev/null 2>&1
    echo "----------------------- HERE"
    if [ -f ~/.bts_tools/config.yaml ]; then
        echo "config yaml found in .bts_tools"
    else
        echo "ERROR: still no config yaml in .bts_tools"
    fi
    mkdir -p /home/$USER/.bts_tools
    cp /tmp/config.yaml bts_tools/config.yaml
    cp bts_tools/config.yaml /home/$USER/.bts_tools/config.yaml
    echo "------------------------------------"
    echo "installed config.yaml"
    cat /home/$USER/.bts_tools/config.yaml
    echo "------------------------------------"
else
    echo "no config.yaml file given"
fi

# copy bts client config.ini, if given
if [ -f /tmp/config.ini ]; then
    mkdir ~/.BitShares2/
    cp /tmp/config.ini ~/.BitShares2/
fi

# copy api_access.json, if given
if [ -f /tmp/api_access.json ]; then
    cp /tmp/api_access.json ~/
fi

# install dependencies for monitoring of graphene clients
#if [ -f /tmp/graphene-0.1.tar.gz ]; then
#    pip install /tmp/graphene-0.1.tar.gz autobahn
#fi


# try copying any genesis file in the home directory
cp /tmp/*.json ~/

popd
