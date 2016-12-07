#!/usr/bin/env bash

echo "CALLING install_user.sh WITH ARGS: $@"

set -o nounset
USER="{{ unix_user }}"
GIT_NAME="{{ git['name'] }}"
GIT_EMAIL="{{ git['email'] }}"
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

# upgrade pip and setuptools to ensure a modern installation (and no problem when installing dependencies)
pip install -U pip setuptools

rm -fr dist; python setup.py sdist && (pip uninstall -y bts_tools; pip install dist/bts_tools-*.tar.gz)

# ensure we have a ~/.bts_tools folder with default config.yaml
bts list >/dev/null 2>&1


if [ -f /tmp/config.yaml ]; then
    # FIXME: unnecessary due to line 52, right?
    if [ -f ~/.bts_tools/config.yaml ]; then
        echo "config yaml found in .bts_tools"
    else
        echo "ERROR: still no config yaml in .bts_tools"
    fi
    mkdir -p /home/$USER/.bts_tools
    cp /tmp/config.yaml bts_tools/config.yaml                    # copy config.yaml to local dev dir
    cp bts_tools/config.yaml /home/$USER/.bts_tools/config.yaml  # copy config.yaml to bts_tools config dir
    echo "------------------------------------"
    echo "installed config.yaml"
    cat /home/$USER/.bts_tools/config.yaml
    echo "------------------------------------"
else
    echo "no config.yaml file given"
fi

{% if compile_on_new_host %}
    # compile client locally
    {% for client in config_yaml['clients'] %}
        {% set client_type = config_yaml['clients'][client].get('type', client) %}
        echo "Building {{ client_type }} client for {{ client }}"
        {{ client_type }} build
    {% endfor %}
{% else %}
    echo "Not building client locally"
{% endif %}


# copy api_access.json files, if given
# try copying any genesis file also in the home directory
cp /tmp/*.json ~/

popd
