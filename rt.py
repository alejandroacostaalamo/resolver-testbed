#!/usr/bin/env python3
'''
Testbed for DNS resolvers
See https://github.com/icann/resolver-testbed for more information
Must be run in the same directory as the config files
'''

import os, subprocess, sys, time, logging, configparser
import fabric

# Some program-wide constants
PROG_DIR = os.path.abspath(os.getcwd())
LOG_FILE = "{}/log_resolver_testbed.txt".format(PROG_DIR)
LOCAL_CONFIG = "{}/local_config.txt".format(PROG_DIR)
BUILD_CONFIG = "{}/build_config.json".format(PROG_DIR)
CLONE_BASENAME = "debian960-base"

VM_INFO = {
    "gateway-vm": {
        "control_addr": "192.168.56.2"
    },
    "servers-vm": {
        "control_addr": "192.168.56.3"
    },
    "resolvers-vm": {
        "control_addr": "192.168.56.4"
    }
}

CLI_COMMANDS = [
"help",
"check_vms"
]

HELP_TEXT = '''
Available commands for rt.py are:
help                 Show this text
check_vms            Run simple checks on the VMs
'''.strip()

# Do very early check for contents of the directory that we're running in
LOG_FORMAT = logging.Formatter("%(message)s")
LOG_HANDLER = logging.FileHandler(LOG_FILE)
LOG_HANDLER.setFormatter(LOG_FORMAT)
LOG = logging.getLogger()
LOG.setLevel(logging.INFO)
LOG.addHandler(LOG_HANDLER)

def log(in_str):
	''' Prints a message and logs it, but only if the message is non-null; returns nothing '''
	if not in_str:
		return
	out = "{}: {}".format(time.strftime("%H-%M-%S"), in_str)
	LOG.info(out)
	print(out)

def die(in_str):
    ''' log then exit  '''
    err_str = in_str + " Exiting."
    log(err_str)
    exit()

def show_help():
    print(HELP_TEXT)

def cmd_to_vm(cmd_to_run, vm_name):
    ''' Runs a list of commands on a named VM. Returns list of [ success_boolean, output_text ] '''
    if not vm_name in VM_INFO:
        die("Attempt to run on {}, which is not a valid VM".format(vm_name))
    is_vm_running(vm_name)
    this_control_address = (rt_config["vm_info"][vm_name]).get("control_addr")
    if not this_control_address:
        die("There was no address for {}".format(vm_name))
    fabconn = fabric.Connection(host=this_control_address, user="root")
    try:
        fabconn.open()
    except:
        die("Could not open an SSH connection to {}.".format(vm_name))
    # Is this the right VM?
    ret_hostname = fabconn.run("hostname", hide=True)
    if ret_hostname.failed:
        die("Could not run hostname on {}".format(vm_name))
    ret_text = ret_hostname.stdout
    if ret_text.rstrip() != vm_name:
        die("The host at {} is not {}: '{}'".format(this_control_address, vm_name, ret_text))
    # Run the command
    ret_main_cmd = fabconn.run(cmd_to_run, hide=True, warn=True)
    if ret_main_cmd.failed:
        return "Error: {}".format(ret_main_cmd.stderr.strip())
    else:
        return ret_main_cmd.stdout.strip()

def is_vm_running(vm_name):
    ''' Check if the VM is running; die if not '''
    p = subprocess.Popen("VBoxManage list runningvms", stdout=subprocess.PIPE, shell=True)  
    ret_val = p.wait()
    if ret_val > 0:
        die("VBoxManage runningvms failed to run.")
    running_vms_lines = (p.stdout.read()).decode("latin-1").strip().split("\n")
    running_vms = []
    for this_line in running_vms_lines:
        running_vms.append(this_line[1:this_line.find('"', 2)])
    if not vm_name in running_vms:
        die("{} is not in the list of running VMs: '{}'.".format(vm_name, " ".join(running_vms)))

def startup_and_config_general():
    ''' Make sure everything on the control host is set up correctly, and die if it is not; returns local configuration '''
    # Be sure we are running from the directory the program is in
    if sys.argv[0] != "./rt.py":
        die("This program must be run as ./rt.py so that all the additional files are found.")
    # Make sure that vboxmanage is available
    p = subprocess.Popen("VBoxManage --version >/dev/null 2>/dev/null", shell=True)
    ret_val = p.wait()
    if ret_val > 0:
        die("Could not run VBoxManage during sanity check.")
    # Make sure the three VMs at least exist
    for this_vm_name in VM_INFO:
        p = subprocess.Popen("VBoxManage showvminfo {} >/dev/null 2>/dev/null".format(this_vm_name), shell=True)
        ret_val = p.wait()
        if ret_val > 0:
            die("Could not find '{}' in the VirtualBox inventory.".format(this_vm_name))
    # Keep the configuration info here; this could expand in the future
    this_local_config = {}
    # Add VM_INFO to the local configuration
    this_local_config["vm_info"] = {}
    for this_key in VM_INFO:
        this_local_config["vm_info"][this_key] = VM_INFO[this_key]
    # Finish up initialization
    return this_local_config

def sanity_check_vms():
    ''' See if the VMs are running and have the expected things on them; fix silently if that's easy '''
    for this_vm in rt_config["vm_info"]:
        log("Starting sanity check on {}".format(this_vm))
        is_vm_running(this_vm)
        # Make a Target directory if it not already there
        this_ret = cmd_to_vm("ls ~/Target", this_vm)
        if "No such file or directory" in this_ret:
            inner_ret = cmd_to_vm("mkdir ~/Target", this_vm)
            log("Created ~/Target on {}".format(this_vm))
        # Make a Source directory if it not already there
        this_ret = cmd_to_vm("ls ~/Source", this_vm)
        if "No such file or directory" in this_ret:
            inner_ret = cmd_to_vm("mkdir ~/Source", this_vm)
            log("Created ~/Source on {}".format(this_vm))
    ################ MORE GOES HERE ###################
    return True

# Run the main program
if __name__ == "__main__":
    log("## Starting run on date {}".format(time.strftime("%Y-%m-%d")))
    # Parse the input
    if len(sys.argv) < 2:
        show_help()
        die("There were no arguments on the command line.")
    rt_config = startup_and_config_general()  # Get the config, and make sure everything is set up correctly
    # Get the command
    cmd = sys.argv[1]
    cmd_args = sys.argv[2:]
    log("Command was {} {}".format(cmd, " ".join(cmd_args)))
    if not cmd in CLI_COMMANDS:
        show_help()
        die("{} is not valid command.".format(cmd))
    # Figure out which command it was
    if cmd == "help":
        show_help()
    elif cmd == "check_vms":
        if sanity_check_vms():
            log("VMs are running as expected")
    # We're done, so exit
    log("## Finished run")
    exit()
