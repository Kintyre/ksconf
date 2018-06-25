# -*- mode: ruby -*-
# vi: set ft=ruby :

# All Vagrant configuration is done below. The "2" in Vagrant.configure
# configures the configuration version (we support older styles for
# backwards compatibility). Please don't change it unless you know what
# you're doing.
Vagrant.configure("2") do |config|
  # The most common configuration options are documented and commented below.
  # For a complete reference, please see the online documentation at
  # https://docs.vagrantup.com.

  # Every Vagrant development environment requires a box. You can search for
  # boxes at https://vagrantcloud.com/search.
  config.vm.box = "centos/7"

  # Disable automatic box update checking. If you disable this, then
  # boxes will only be checked for updates when the user runs
  # `vagrant box outdated`. This is not recommended.
  # config.vm.box_check_update = false

  # Create a forwarded port mapping which allows access to a specific port
  # within the machine from a port on the host machine. In the example below,
  # accessing "localhost:8080" will access port 80 on the guest machine.
  # NOTE: This will enable public access to the opened port
  # config.vm.network "forwarded_port", guest: 80, host: 8080

  # Create a forwarded port mapping which allows access to a specific port
  # within the machine from a port on the host machine and only allow access
  # via 127.0.0.1 to disable public access
  # config.vm.network "forwarded_port", guest: 80, host: 8080, host_ip: "127.0.0.1"

  # Create a private network, which allows host-only access to the machine
  # using a specific IP.
  # config.vm.network "private_network", ip: "192.168.33.10"

  # Create a public network, which generally matched to bridged network.
  # Bridged networks make the machine appear as another physical device on
  # your network.
  # config.vm.network "public_network"

  # Share an additional folder to the guest VM. The first argument is
  # the path on the host to the actual folder. The second argument is
  # the path on the guest to mount the folder. And the optional third
  # argument is a set of non-required options.
  config.vm.synced_folder ".", "/vagrant_ksconf"

  # Provider-specific configuration so you can fine-tune various
  # backing providers for Vagrant. These expose provider-specific options.
  # Example for VirtualBox:
  #
  # config.vm.provider "virtualbox" do |vb|
  #   # Display the VirtualBox GUI when booting the machine
  #   vb.gui = true
  #
  #   # Customize the amount of memory on the VM:
  #   vb.memory = "1024"
  # end
  #
  # View the documentation for the provider you are using for more
  # information on available options.


  # https://gist.github.com/clozed2u/b0421d8af60e26d97372
  config.vm.provision "shell", privileged: false, inline: <<-SHELL
    sudo yum install -y gcc gcc-c++ make git patch openssl-devel zlib-devel readline-devel sqlite-devel bzip2-devel
    git clone git://github.com/yyuu/pyenv.git ~/.pyenv --depth=20
    echo 'export PATH="$HOME/.pyenv/bin:$PATH"' >> ~/.bashrc
    echo 'eval "$(pyenv init -)"' >> ~/.bashrc

    # Enable git bash prompt
    git clone https://github.com/magicmonty/bash-git-prompt.git .bash-git-prompt --depth=20
    echo 'GIT_PROMPT_ONLY_IN_REPO=1' >> ~/.bashrc
    echo 'source ~/.bash-git-prompt/gitprompt.sh' >> ~/.bashrc

    # Reload shell
    source ~/.bashrc

    pyenv install 2.7.15
    pyenv install 3.6.5
    pyenv install 3.5.5
    pyenv install 3.4.8

    pyenv global 2.7.15 3.6.5 3.5.5 3.4.8
    pyenv rehash

    # Intall tox
    python -m pip install tox
    pyenv rehash


    # Checkout the 'ksconf' project locally
    git clone https://github.com/Kintyre/ksconf.git

    echo
    echo "Install complete."
    echo
    echo "To run tests, run"
    echo "    vagrant ssh"
    echo "    cd ksconf"
    echo "    tox"
  SHELL
end
