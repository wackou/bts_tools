#!/bin/bash
#
# setupVPS - Script to setup new VPS host running Ubuntu Linux Server version 14.04
#

#set -e

# config variables
export PAUSE={{ 1 if pause else 0 }}  # Pause between installation steps
export IS_DEBIAN={{ 1 if is_debian else 0 }}
export IS_UBUNTU={{ 1 if is_ubuntu else 0 }}
export INSTALL_COMPILE_DEPENDENCIES={{ 1 if compile_on_new_host else 0 }}

export UNIX_HOSTNAME="{{ unix_hostname }}"
export UNIX_USER="{{ unix_user }}"
export UNIX_PASSWORD="{{ unix_password }}"
export GIT_NAME="{{ git_name }}"
export GIT_EMAIL="{{ git_email }}"
export NGINX_SERVER_NAME="{{ nginx_server_name }}"
export UWSGI_USER="$UNIX_USER"
export UWSGI_GROUP="$UNIX_USER"

if [ -f /root/base_graphene_installed ]; then
    echo "---- Base system already installed, skipping it"
    exit
fi

echo "---- Installing base system"

#if [ ! -f /tmp/newVPS.tgz ]; then
#  echo "No newVPS.tgz file!"
#  echo "This script needs to run as root. It should be copied to /tmp with scp"
#  echo "along with newVPS.tgz and executed."
#else
#  pushd /tmp
#  echo "Uncompressing the install tarball..."
#  tar xzf newVPS.tgz
#fi
#if [ $PAUSE -eq 1 ]; then read -p "Press [Enter] key to continue..."; fi

# setting hostnamec
echo "* Setting hostname to $UNIX_HOSTNAME..."
echo "!! Please reboot after install for this to take effect !!"
echo "$UNIX_HOSTNAME" > /etc/hostname

# install ssh keys for root
if [ -f /tmp/authorized_keys ]; then
  echo "* Installing ssh keys for root user..."
  cat /tmp/authorized_keys >> ~/.ssh/authorized_keys
fi


# Install packages
echo "* Updating system..."
apt-get -y update >> /tmp/setupVPS.log 2>&1
apt-get -yfV dist-upgrade >> /tmp/setupVPS.log 2>&1
echo "* Installing packages for running the client..."
apt-get install -yfV git autoconf automake libtool doxygen zip virtualenvwrapper moreutils tmux rsync ntp\
  python3-dev libyaml-dev qt5-default qttools5-dev-tools >> /tmp/setupVPS.log 2>&1

if [ $INSTALL_COMPILE_DEPENDENCIES -eq 1 ]; then
  echo "* Installing packages for compiling the client..."
  apt-get install -yfV libreadline-dev uuid-dev g++ libdb++-dev libdb-dev  >> /tmp/setupVPS.log 2>&1
  apt-get install -yfV libssl-dev openssl build-essential autotools-dev >> /tmp/setupVPS.log 2>&1
  apt-get install -yfV libicu-dev libbz2-dev cmake ncurses-dev >> /tmp/setupVPS.log 2>&1
  apt-get install -yfV nodejs-legacy nodejs npm mc >> /tmp/setupVPS.log 2>&1
fi

if [ $IS_DEBIAN -eq 1 ]; then
  apt-get install -yfV vim >> /tmp/setupVPS.log 2>&1
  apt-get remove -yfV vim-tiny >> /tmp/setupVPS.log 2>&1

  # on debian, this needs to be installed from testing:
  #apt-get install -yfV cmake libboost-all-dev >> /tmp/setupVPS.log 2>&1
fi

echo "* Cleaning up..."
apt-get -y autoremove >> /tmp/setupVPS.log 2>&1
if [ $PAUSE -eq 1 ]; then read -p "Press [Enter] key to continue..."; fi

# Install the boost libraries
if [ $IS_DEBIAN -eq 1 ]; then
  #if [ $INSTALL_COMPILE_DEPENDENCIES -eq 1 ]; then
  # always install boost, as it pulls in other dependencies we need for running (eg: newer libstdc++, etc)
    # get boost from testing
    echo "* Getting boost from testing distribution..."
    mv /etc/apt/sources.list /etc/apt/sources.list.orig
    (echo "deb http://debian.mirror.constant.com/ testing main"; cat /etc/apt/sources.list.orig) > /etc/apt/sources.list
    apt-get update >> /tmp/setupVPS.log 2>&1

    echo " installing libc first"
    apt-get install -t testing -yfV libc-bin >> /tmp/setupVPS.log 2>&1
    echo " installing boost-dev"

    apt-get install -t testing -yfV cmake libboost-all-dev >> /tmp/setupVPS.log 2>&1
    # reset to stable apt sources
    cp /etc/apt/sources.list.orig /etc/apt/sources.list
    apt-get update >> /tmp/setupVPS.log 2>&1
    if [ $PAUSE -eq 1 ]; then read -p "Press [Enter] key to continue..."; fi
  #fi
elif [ $IS_UBUNTU -eq 1 ]; then
    apt-get install -yfV cmake libboost-all-dev >> /tmp/setupVPS.log 2>&1
fi

if [ $PAUSE -eq 1 ]; then read -p "Press [Enter] key to continue..."; fi



install_user () {
  USER="$1"
  PASSWORD="$2"

  if [ ! -f /home/$USER ]; then
    echo "* Adding user $USER..."
    useradd -m -s /bin/bash $USER
    echo "$USER:$PASSWORD" | chpasswd
  fi

  su -c "/bin/bash /tmp/install_user.sh" $USER >> /tmp/setupVPS.log 2>&1
}

install_user $UNIX_USER $UNIX_PASSWORD
if [ $PAUSE -eq 1 ]; then read -p "Press [Enter] key to continue..."; fi


# Install and configure nginx web server for use with python monitor
if [ ! -d /etc/nginx-original ]; then
    # Install nginx
    echo "* Installing nginx..."
    apt-get install -yfV nginx >> /tmp/setupVPS.log 2>&1
    pushd /etc
    cp -R nginx nginx-original

    pushd /
    tar xzf /tmp/etcNginx.tgz
    popd

    # set $SERVER_NAME in nginx config
    #cat /etc/nginx/sites-available/default |
    #  sed "s/server_name\(.*\)/server_name $NGINX_SERVER_NAME;/" |
    #  sed "s/auth_basic_user_file\(.*\)/auth_basic_user_file \/home\/$UNIX_USER\/.htpasswd;/" |
    #  sponge /etc/nginx/sites-available/default
    chown -R root nginx
    chgrp -R root nginx
    service nginx restart
    popd
fi
if [ $PAUSE -eq 1 ]; then read -p "Press [Enter] key to continue..."; fi

# Install and configure uwsgi
if [ ! -d /etc/uwsgi-original ]; then
    # Install uwsgi
    echo "* Installing uwsgi..."
    apt-get install -yfV uwsgi uwsgi-plugin-python3 >> /tmp/setupVPS.log 2>&1
    pushd /etc
    cp -R uwsgi uwsgi-original

    pushd /
    tar xzf /tmp/etcUwsgi.tgz
    popd

    #mv /tmp/etc/uwsgi uwsgi
    # set user/group in uwsgi config
#    cat /etc/uwsgi/apps-available/bts_tools.ini |
#      sed "s/uid = \(.*\)/uid = $UWSGI_USER/" |
#      sed "s/gid = \(.*\)/gid = $UWSGI_GROUP/" |
#      sed "s/virtualenv = \(.*\)/virtualenv = \/home\/$UWSGI_USER\/.virtualenvs\/bts_tools/" |
#      sponge /etc/uwsgi/apps-available/bts_tools.ini
    chown -R root uwsgi
    chgrp -R root uwsgi
    service uwsgi restart
    popd
fi
if [ $PAUSE -eq 1 ]; then read -p "Press [Enter] key to finish!"; fi

echo ""
echo "Please reboot in order for the hostname to take effect"

touch /root/base_graphene_installed
cp /tmp/setupVPS.log /root/
exit
echo "not exited"
