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

  # Should work with either.  Take your pick.
  config.vm.box = "centos/7"
  config.vm.box = "ubuntu/trusty64"

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
  # config.vm.synced_folder ".", "/vagrant_ksconf"

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
  if [[ -x $(command -v yum ) ]]; then
        echo "Using RedHat/CentOS  package names..."
        sudo yum install -y vim
        sudo yum install -y gcc gcc-c++ make git patch openssl-devel zlib-devel readline-devel sqlite-devel bzip2-devel xz-devel libffi-devel
    else
        echo "Assuming debian base distro.  Using 'apt'"
        sudo apt install -y vim
        sudo apt install -y build-essential git
        sudo apt install -y libssl-dev zlib1g-dev libncurses5-dev libncursesw5-dev libreadline-dev libsqlite3-dev libgdbm-dev libdb5.3-dev libbz2-dev libexpat1-dev liblzma-dev libffi-dev

    fi

    git clone git://github.com/yyuu/pyenv.git ~/.pyenv --depth=20
    echo 'export PATH="$HOME/.pyenv/bin:$PATH"' >> ~/.bashrc
    echo 'eval "$(pyenv init -)"' >> ~/.bashrc

    # Enable git bash prompt
    git clone https://github.com/magicmonty/bash-git-prompt.git .bash-git-prompt --depth=20
    echo 'GIT_PROMPT_ONLY_IN_REPO=1' >> ~/.bashrc
    echo 'source ~/.bash-git-prompt/gitprompt.sh' >> ~/.bashrc

    # Prep shell
    export PATH="$HOME/.pyenv/bin:$PATH"
    eval "$(pyenv init -)"

    # Keep python versions in just one list to reduce number of edits and typos ;-)
    PYVERS="2.7.15 3.7.1 3.6.7 3.5.6 3.4.9 pypy2.7-6.0.0"

    for ver in $PYVERS
    do
        pyenv install $ver && echo $ver >> ~/.pyver-installed-okay
    done

    # Fallback to the first version (in case any compiles fail) :   pyver global ${PYVERS%% *}
    pyenv global $(cat ~/.pyver-installed-okay)

    # Another option: (down side, priority list is different, but 2.7 is still the first.  Probably be good enough)
    # pyenv global $(pyenv versions --bare)
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
