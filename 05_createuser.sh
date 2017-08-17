#!/bin/bash

source /var/run/one-context/one_env

## create user and group
echo 'creating user and group ...' >> /tmp/context.log
groupadd -g $TRQ_GID -f $TRQ_GNAME && mkdir -p /home/$TRQ_GNAME && \
useradd -c 'user provisioned by ONE contextualisation' \
-d $TRQ_UHOME -g $TRQ_GNAME -m \
-u $TRQ_UID -s /bin/bash $TRQ_UNAME

## add SSH_KEY to user's home directory
if [ $? == 0 ] && [ -d $TRQ_UHOME ]; then
    echo 'adding ssh key to user ...' >> /tmp/context.log
    mkdir ${TRQ_UHOME}/.ssh
    echo $SSH_PUBLIC_KEY > ${TRQ_UHOME}/.ssh/authorized_keys
    chmod 700 ${TRQ_UHOME}/.ssh/authorized_keys
    chown -R $TRQ_UNAME:$TRQ_GNAME ${TRQ_UHOME}/.ssh
fi
