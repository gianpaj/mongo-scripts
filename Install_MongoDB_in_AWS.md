Install MongoDB in Amazon Web Services (AWS)
======

Step by step tutorial based on this article on [docs.mongodb.org](http://docs.mongodb.org/manual/tutorial/install-mongodb-on-redhat-centos-or-fedora-linux/)

This has no RAID setup at the moment. Though consider this [guide](http://www.mongodb.org/display/DOCS/Amazon+EC2+Quickstart#AmazonEC2Quickstart-ConfigureStorage) to create and attach a RAID-10 ebs setup.

Requirements
-------

* Amazon Linux AMI 2012.09 - 64bit

Tutorial
-------

Add yum repostory

    sudo nano /etc/yum.repos.d/10gen.repo
    echo -e "[10gen]\nname=10gen Repository\nbaseurl=http://downloads-distro.mongodb.org/repo/redhat/os/x86_64\ngpgcheck=0\nenabled=1" | sudo tee /etc/yum.repos.d/10gen.repo

Install mongo and mongod

    sudo yum install mongo-10gen mongo-10gen-server

Set mongod to start at startup

    sudo chkconfig mongod on

Attach EBS volume to the EC2 instance
Format build a Linux file system

    sudo mkfs -t ext4 /dev/xvdf

Set readahead

    sudo blockdev --setra 128 /dev/xvdf

See readahead value

    sudo blockdev --report

    sudo mkdir /data
    echo "/dev/xvdf   /data   auto    defaults,auto,noatime,noexec    0   0" | sudo tee -a /etc/fstab

Mount the database path and set permissions for the group mongod process

    sudo mount /data
    sudo chown mongod:mongod /data


Start mongod

    sudo service mongod start