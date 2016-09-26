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
export GIT_NAME="{{ git['name'] }}"
export GIT_EMAIL="{{ git['email'] }}"
export NGINX_SERVER_NAME="{{ nginx['server_name'] }}"
export UWSGI_USER="$UNIX_USER"
export UWSGI_GROUP="$UNIX_USER"

if [ -f /root/base_graphene_installed ]; then
    echo "---- Base system already installed, skipping it"
    exit
fi

echo "---- Installing base system"

# setting hostname
echo "* Setting hostname to $UNIX_HOSTNAME..."
echo "!! Please reboot after install for this to take effect !!"
echo "$UNIX_HOSTNAME" > /etc/hostname

# install ssh keys for root
if [ -f /tmp/authorized_keys ]; then
    echo "* Installing ssh keys for root user..."
    cat /tmp/authorized_keys >> ~/.ssh/authorized_keys
fi


# see: http://serverfault.com/questions/227190/how-do-i-ask-apt-get-to-skip-any-interactive-post-install-configuration-steps#comment1000493_227194
export DEBIAN_FRONTEND=noninteractive    # required, "apt-get -y" is not sufficient

locale-gen "en_US.UTF-8"
dpkg-reconfigure locales

# Install packages
echo "* Updating system..."
if [ $IS_DEBIAN -eq 1 ]; then
    apt-get -y update >> /tmp/setupVPS.log 2>&1
    yes | apt-get -yqfV dist-upgrade >> /tmp/setupVPS.log 2>&1
elif [ $IS_UBUNTU -eq 1 ]; then
    apt-get -yfV install software-properties-common  >> /tmp/setupVPS.log 2>&1
    add-apt-repository universe
    echo "deb http://archive.ubuntu.com/ubuntu xenial-updates universe" >> /etc/apt/sources.list
    apt-get -y update >> /tmp/setupVPS.log 2>&1
    #yes | apt-get -yqfV upgrade >> /tmp/setupVPS.log 2>&1
fi

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
    # get boost from testing
    echo "* Getting boost from testing distribution..."
    mv /etc/apt/sources.list /etc/apt/sources.list.orig
    (echo "deb http://httpredir.debian.org/debian testing main"; cat /etc/apt/sources.list.orig) > /etc/apt/sources.list
    apt-get update >> /tmp/setupVPS.log 2>&1

    #echo " installing libc first"
    apt-get install -t testing -yfV libc-bin >> /tmp/setupVPS.log 2>&1
    #echo " installing boost-dev"

    apt-get install -t testing -yfV cmake libboost1.58-all-dev >> /tmp/setupVPS.log 2>&1

    # reset to stable apt sources
    cp /etc/apt/sources.list.orig /etc/apt/sources.list
    apt-get update >> /tmp/setupVPS.log 2>&1
    if [ $PAUSE -eq 1 ]; then read -p "Press [Enter] key to continue..."; fi
elif [ $IS_UBUNTU -eq 1 ]; then
    echo "* Installing boost..."
    apt-get install -yfV cmake libboost1.58-all-dev >> /tmp/setupVPS.log 2>&1
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


echo ""
echo "Please reboot in order for the hostname to take effect"

touch /root/base_graphene_installed
