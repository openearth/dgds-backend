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

  config.vm.define "dgds" do |dgds|

    # Create a forwarded port mapping which allows access to a specific port
    # within the machine from a port on the host machine. In the example below,
    # accessing "localhost:8080" will access port 80 on the guest machine.
    # dgds.vm.network "forwarded_port", guest: 80, host: 8888
    # dgds.vm.network "forwarded_port", guest: 8000, host: 8000

    # Create a private network, which allows host-only access to the machine
    # using a specific IP.
    dgds.vm.network "private_network", ip: "10.0.1.5"

    # Share an additional folder to the guest VM. The first argument is
    # the path on the host to the actual folder. The second argument is
    # the path on the guest to mount the folder. And the optional third
    # argument is a set of non-required options.
    dgds.vm.synced_folder "app", "/opt/dgds", type: "nfs", create: true
    dgds.vm.synced_folder "../dgds-front-end/dist", "/opt/dgds/static", type: "nfs", create: true

    config.vm.provision "ansible" do |ansible|
        ansible.playbook = "ansible/site.yml"
        ansible.verbose = "vvv"
        ansible.limit = "all"
        ansible.inventory_path = "ansible/host_vagrant"
        ansible.extra_vars = {vagrant: true}
    end
  end
end
