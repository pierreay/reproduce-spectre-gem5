"""Raspberry Pi 4 Model B Rev. 1.1 - Syscall emulation & Full-system simulation

Script based on a real Raspberry Pi system. It is shipped with a "reproduced"
ARM Cortex-A72 CPU. The intended use is security research. It can be used both
in system-call emulation or full-system simulation. For the full-system
simulation mode only, first boot your system and create a checkpoint where the
used CPU will be the atomic one. Only then, restore you system from your
checkpoint, where the CPU used will be the detailed one. When passing filenames
in arguments of the script, please be sure that your M5_PATH environment
variable is set accordingly.

"""

# * Importations:

# ** Python:

# System.
import os
import sys
# Logging.
import time
# Parsing.
import argparse
import shlex

# ** Gem5:

# M5/gem5 library (created when gem5 is compiled).
import m5
# Python SimObjects list.
from m5.objects import *
# Memory configuration helper.
from common import MemConfig
# System-path (M5_PATH) search helper.
from common import SysPaths

# ** Custom:

# Classes to built an ARM Cortex-A72.
from ARMv8A_Cortex_A72 import *

# * Variables:

# Hold user-supplied arguments to the script.
args = None
# Keep trace of elapsed time.
t_start = None

# * Classes:

class RPIMem:
    """Raspberry Pi main memory.

    The main memory of the RPI consist of 4GB LPDDR4 SDRAM. No information
    about channels, controllers, banks... Main memory configuration is unified
    into one class because it is used by the MemConfig helper function.

    """
    # We want LPDDR4. We have choice between LPDDR3 and DDR4 for default
    # configuration.
    mem_type = "DDR4_2400_16x4"
    # Determine the number of memory controllers for the MemConfig helper
    mem_channels = 1
    # Size of the main memory.
    mem_size = '4096MB'

    def getMemRanges(args):
        """Get the RPISystem DRAM memory ranges.

        Return a list of ranges of DRAM memory. It should start from 0 for the
        SE mode, but from 2GB for FS mode since the first 2GB are already
        mapped by the RealView platform.

        """
        if args.se is True:
            return [AddrRange(start=0, size=RPIMem.mem_size)]
        else:
            return [AddrRange(start=0x80000000, size=RPIMem.mem_size)]

def RPISystemCreate(BaseSystem, args, mode):
    """Create an RPISystem which inherit dynamically from the class "BaseSystem".

    :param BaseSystem: Should be "System" when using SE mode, or "ArmSystem"
                       when using FS mode.
    :param args: Arguments of the script.
    :param mode: Either "atomic" or "timing", depending on simulation mode and
                 restore point.
    :returns: RPISystem with a fully-configured architecture.

    """
    class RPISystem(BaseSystem):

        """Raspberry Pi system.

        Return an RPI system fully-configured, ready to be loaded with a workload.

        """
        # Cache line size are 64 bytes.
        cache_line_size = 64

        # System clock and voltage.
        _system_clock = "1GHz"
        _system_voltage = "3.3V"

        def __init__(self, args, mode, **kwargs):
            super().__init__(**kwargs)

            # Create a voltage and clock domain for system components.
            self.voltage_domain = VoltageDomain(voltage=self._system_voltage)
            self.clk_domain     = SrcClockDomain(clock=self._system_clock,
                                                 voltage_domain=self.voltage_domain)
            
            # Tell gem5 about the memory mode used by the CPU we are simulating.
            self.mem_mode = mode

            # Add the CPU cluster to the system, possibly with multiples cores.
            self.cpu_cluster = ARM_A72_Cluster(self, args.num_cores)

            # Configure the memory for the added cluster and the system.
            self.configMem(args)

        def configMem(self, args):
            """Configure all the memory of the system.

            Create a memory bus, a memory controller, and wire-up all needed port
            to connect the caches and the main memory.

            """
            # Create the off-chip coherent crossbar memory bus, tying CPU clusters,
            # DRAM controllers and I/O coherent masters if any.
            self.membus = SystemXBar()

            # The Bad Address Responder is only used in full-system mode.
            if args.fs:
                # Attach to the memory bus a Bad Address Responder, used to respond
                # with default data to the devices if they made a request outside a
                # valid memory range and inform the user by printing a
                # message. This component is optional.
                self.membus.badaddr_responder = BadAddr(warn_access="warn badaddr_responder")
                self.membus.default = self.membus.badaddr_responder.pio

            # Wire up the system port to the previously created memory bus (gem5
            # uses it to load the kernel and to perform debug accesses).
            self.system_port = self.membus.slave

            # Connect the cache hierarchy of the CPU cluster to the shared memory
            # bus, if there is one.
            if self.getMemoryMode() == "timing":
                self.cpu_cluster.connectCacheL2(self.membus)
            else:
                self.cpu_cluster.connectDirect(self.membus)

            # Tell components about the expected physical memory ranges. This is, for
            # example, used by the MemConfig helper to determine where to map DRAMs in
            # the physical address space.
            self.mem_ranges = RPIMem.getMemRanges(args)

            # Configure the off-chip main memory system (DRAM memory &
            # controller).
            MemConfig.config_mem(RPIMem, self)

        def getMemoryMode(self):
            """Get the current memory mode of the system.

            This function is important, because you have to convert the
            mem_mode attribute which is of "MemoryMode" type for any comparison
            with a string. Otherwise, the comparison will always silently
            failed.
            
            :returns: The memory mode as a string.

            """
            return str(self.mem_mode)

    return RPISystem(args, mode)
                
# * Functions:

def getTimeStr():
    """Return a string header with the time since the beginning of simulation."""
    return "[{:.3f}] ".format(time.time() - t_start)
    

def printVerbose(str):
    global args
    """Print str if args.verbose is True"""
    if args.verbose is True:
        print(getTimeStr() + str)
    

def argsCheck(args):
    """Check arguments.

    Check the correctness of passed arguments. Return 1 in case of error, 0
    otherwise.

    """
    # Common arguments.
    if args.num_cores <= 0:
        print("Error: num_cores must be superior or equal to 1.")
        return 1
    if (args.fs is False and args.se is False) or (args.fs is True and args.se is True):
        print("Error: select either --fs or --se mode.")
        return 1
    if args.fs is True:
        # Required arguments.
        if args.fs_kernel is None or args.fs_disk_image is None:
            print("Error: you must supply --fs-kernel and --fs-disk-image option.")
            return 1
        # False mode arguments.
        if args.se_commands_to_run:
            print("Error: fs-mode is selected but se-mode arguments are provided.")
            return 1
    if args.se is True:
        # Required arguments.
        if args.se_commands_to_run is None:
            print("Error: you must supply command positional argument.")
            return 1
        # False mode arguments.
        if args.fs_kernel is not None or args.fs_disk_image is not None or args.fs_restore is not None or args.fs_workload_image is not None:
            print("Error: se-mode is selected but fs-mode arguments are provided.")
            return 1
        
def seGetProcesses(cmd):
    """Get gem5 processes from arguments.

    Interprets commands to run and returns a list of gem5 processes. Only used
    in system-call emulation mode.

    """
    cwd = os.getcwd()
    multiprocesses = []
    # Parse each string in the 'cmd' list.
    for idx, c in enumerate(cmd):
        # Split the string using shell-like syntax.
        argv = shlex.split(c)
        # Create a gem5 process. The minimal requirement is to set the 'cmd'
        # variable, which is a list containing the executable in [0]. Set the
        # environment variable "GEM5_SIM" to "true" to indicate to our PoCs
        # that we are simulating them in gem5.
        process = Process(pid=100 + idx, cwd=cwd, cmd=argv, executable=argv[0], env=["GEM5_SIM=true"])

        printVerbose("[PID %d] %s" % (process.pid, process.cmd))
        multiprocesses.append(process)

    return multiprocesses

def fsImageCOWCreate(name):
    """Helper function to create a Copy-on-Write disk image.

    Create a disk image using gem5's Copy-on-Write functionality to avoid
    writing changes to the stored copy of the disk image.

    """
    image = CowDiskImage()
    image.child.image_file = SysPaths.disk(name)
    return image;

def systemCreate(args):
    """Create a system ready to be simulated.

    Create and configure an RPISystem. The returned system object will be ready
    to be instantiated.

    """
    # Configure the SE-mode.
    if args.se:
        # Use a Raspberry Pi system.
        system = RPISystemCreate(System, args, "timing")
        # Configure the workload. Parse the end of the command line and get a
        # list of "Processes" instances that we can pass to gem5. The number of
        # processes must match the number of cores.
        processes = seGetProcesses(args.se_commands_to_run)
        if len(processes) != args.num_cores:
            print("Error: Cannot map %d command(s) onto %d CPU(s)." %
                  (len(processes), args.num_cores))
            sys.exit(1)
        # Assign one process to a workload for each CPU.
        for cpu, process in zip(system.cpu_cluster.cpus, processes):
            cpu.workload = process
    # Configure the FS-mode.
    # TODO This section needs a refactoring. All gem5 related configuration
    # goes here (e.g. workload), where all system architecture configuration
    # goes into the System class.
    else:
        # Choose the mode (and indirectly, the CPU and the cache hierarchy)
        # depending on if we restore an already-booted system or not.
        mode = "timing" if args.fs_restore else "atomic"
        # Use a Raspberry Pi system.
        system = RPISystemCreate(ArmSystem, args, mode)
        # Add a DVFS handler to the system, in order to communicate with the
        # Energy controller and suppress a warning. If we really want to use
        # it, we can de-comment the line which assign to it a domain to handle.
        system.dvfs_handler = DVFSHandler(enable=True)
        # system.dvfs_handler.domains = [system.cpu_cluster.clk_domain]
        # Model a RealView ARM Platform, default platform for ARM simulation on
        # gem5. This platform define memory map, interrupts, GIC, and a lot of
        # other low-level things.
        system.realview = VExpress_GEM5_V1()
        # Set the address of the 'Flags' register, used for SMP booting. The
        # primary CPU writes the secondary start address here before sends it a
        # soft interrupt. The secondary CPU reads this register and if it's
        # non-zero it jumps to the address. When using a bootloader, even if
        # the system is non-SMP, the register must be set properly (default is
        # 0). We set it to the address of the RealView controller + 0x30, which
        # is an hard-coded offset to the 'Flags' register found in the
        # 'rv_ctrl.hh' file.
        system.flags_addr = system.realview.realview_io.pio_addr + 0x30
        # Set the address of the GIC CPU interface. Default value to 0, require
        # to be set when using a bootloader. The ARM GIC handle interrupts
        # between the CPU and the RealView devices.
        system.gic_cpu_addr = system.realview.gic.cpu_addr
        # Set to true because the register width of the highest implemented
        # exception level is 64 bits (ARMv8).
        system.highest_el_is_64 = True
        # interconnect, we have on-chip I/O non-coherent crossbars.
        system.iobus = IOXBar()
        # Create two bridges which will link the IO bus for off-chip devices
        # and the system memory bus in both sense. These bridge holds requests
        # with a buffer (request and response queue) and serves them.
        system.iobridge = SubSystem()                                                # Contain the two bridge.
        system.iobridge.iobus = Bridge(delay='50ns')                                 # Serve requests from CPU to off-chip IO devices.
        system.iobridge.membus = Bridge(delay='50ns', ranges=[system.mem_ranges[0]]) # Serve requests from off-chip IO devices to CPU.
        # We need a generic interrupts controller, serves as an abstraction of
        # the ARM GIC.
        system.intrctrl = IntrControl()
        # List of all PCI devices of the system.
        system._pci_devices = []
        # Create a PCI VirtIO block device for the system's boot disk. VirtIO
        # is a standardized interface which allows virtual machines access to
        # simplified "virtual" devices, such as block devices, network adapters
        # and consoles. At its core, the VirtIO API is a set of functions that
        # are provided by the hypervisor driver to be used by the guest to
        # communicate between each others. This VirtIO block device will be
        # accessible under the "/dev/vdx" hierarchy.
        system.pci_vio_system = PciVirtIO(vio=VirtIOBlock(image=fsImageCOWCreate(args.fs_disk_image)))
        system._pci_devices.append(system.pci_vio_system)
        # If a workload image is passed by argument, then create another VirtIO
        # block device with the workload image attached. Previously, we have
        # used an IDE controller and controller, but reading the disk causing a
        # segfault.
        if args.fs_workload_image is not None:
            system.pci_vio_workload = PciVirtIO(vio=VirtIOBlock(image=fsImageCOWCreate(args.fs_workload_image)))
            system._pci_devices.append(system.pci_vio_workload)
        # Attach the PCI devices to the system. The helper method of the
        # RealView component in the system assigns a unique PCI bus ID to each
        # of the devices and connects them to the IO bus.
        for pci_dev in system._pci_devices:
            system.realview.attachPciDevice(pci_dev, system.iobus)
        # Connect the two IO bridges to the IO bus and the system bus.
        system.iobridge.iobus.master  = system.iobus.slave
        system.iobridge.iobus.slave   = system.membus.master
        system.iobridge.membus.master = system.membus.slave
        system.iobridge.membus.slave  = system.iobus.master
        # Link the on-chip memories and IO devices (HDLcd, GIC, GenericTimer,
        # Trusted_Watchdog, Trusted_SRAM, Flash0, Bootmem) to the system memory
        # bus. Configure the memory ranges of the IO bridge which serve from
        # CPU to IO devices requests.
        system.realview.attachOnChipIO(system.membus, system.iobridge.iobus)
        # Link the off-chip memories and IO devices (Flash1, VIO,
        # {Power,Energy}_Ctrl, PCI_Host, RTC, Watchdog, KMI, UART, RealView_IO,
        # PCI_Devices) to the system IO bus.
        system.realview.attachIO(system.iobus)

        # To see how it works:
        # https://www.mail-archive.com/gem5-users@gem5.org/msg18401.html
        # https://stackoverflow.com/questions/63988672/using-perf-event-with-the-arm-pmu-inside-gem5
        # https://community.arm.com/developer/ip-products/system/b/embedded-blog/posts/using-the-arm-performance-monitor-unit-pmu-linux-driver
        # 
        # At the time of writing, in order to have a functional PMU, gem5 needs
        # to be patched manually (see the first links above).
        # 
        # For each ISA of each CPU, add to it a PMU with a unique interrupt
        # number and the already implemented architectural event. An example of
        # this function could be found in "devices.py".
        for cpu in system.cpu_cluster.cpus:
            for isa in cpu.isa:
                # To choose an interrupt number, pick a free PPI interrupt in
                # the platform interrupt mapping. Here, we choose PPI n°20,
                # according to the RealView interrupt map (RealView.py). Since
                # PPIs interrupts are local per PE (cores), they can be the
                # same for all PE.
                isa.pmu = ArmPMU(interrupt=ArmPPI(num=20))
                # Add the implemented architectural events of gem5. We can
                # discover which events is implemented by looking at the file
                # "ArmPMU.py".
                isa.pmu.addArchEvents(
                    cpu=cpu, dtb=cpu.dtb, itb=cpu.itb,
                    icache=getattr(cpu, "dcache", None),
                    dcache=getattr(cpu, "icache", None),
                    l2cache=getattr(system.cpu_cluster, "l2", None))
                # Add custom events.
                # 0x33 corresponds to the "0x0033, LL_CACHE_MISS" common microarchitectural event.
                isa.pmu.addEvent(ProbeEvent(isa.pmu, 0x33, getattr(system.cpu_cluster, "l2", None), "Miss"))
        
        # Attach a gem5 terminal (SerialDevice) listening on port 3456 to
        # connect the system later.
        system.terminal = Terminal()
        # Attach a VNC server to the system. It's required by the
        # VExpress_GEM5_V1 platform, even if you don't use it, for the HDLcd
        # controller (simulation of an LCD display with a frame buffer).
        system.vncserver = VncServer()
        # Configure the workload for our system with the predefined class for
        # Linux kernel on ARM. Note that, in the SE mode, the workload is
        # directly passed to the CPU, unlike here.
        system.workload = ArmFsLinux(object_file=SysPaths.binary(args.fs_kernel))
        # Setup gem5's minimal Linux boot loader ('boot.arm' in the 'M5_PATH/binaries').
        system.realview.setupBootLoader(system, SysPaths.binary)
        # Since the system is configured from gem5, it has to be declared to
        # the Linux kernel, so that it can use the appropriate driver, know the
        # interrupt and memory mapping, and so on. The Device Tree Binary (DTB)
        # we will be automatically generated by gem5 (function declared in
        # ArmSystem.py).
        system.workload.dtb_filename = os.path.join(m5.options.outdir, 'system.dtb')
        system.generateDtb(system.workload.dtb_filename)
        # Linux kernel boot command flags.
        kernel_cmd = [
            # Tell Linux to use the simulated serial port as a console.
            "console=ttyAMA0",
            # Hard-code timi.
            "lpj=19988480",
            # Disable address space randomisation to get a consistent memory
            # layout.
            "norandmaps",
            # Tell Linux where to find the root disk image (could be "vda" or "vda1").
            "root=/dev/vda1",
            # Mount the root disk read-write by default.
            "rw",
            # Tell Linux about the amount of memory it should use and its base
            # offset. Beware that it can't be superior to 8GB, otherwise the
            # kernel will not boot with no message at all: gem5 will run and
            # nothing happen. We make the kernel memory start at 2GB, as
            # specified by the RealView platform.
            "mem=2G@0x80000000",
        ]
        system.workload.command_line = " ".join(kernel_cmd)

    return system

def simRun(args):
    """Run the actual simulation.

    This function run the simulation and handle some runtime gem5's service
    passed by special events, like taking a checkpoint.

    :param args: Arguments of the script.
    :returns: gem5's exit event.

    """
    # Infinite loop to handle events passed by exit_msg, until a real exit
    # happened.
    while True:
        # Launch the simulation and get the exit reason.
        event = m5.simulate()
        exit_msg = event.getCause()
        # If the exist reason is to take a checkpoint, then take it and restart
        # the simulation.
        if exit_msg == "checkpoint":
            printVerbose("Dropping checkpoint at tick %d" % m5.curTick())
            cpt_dir = os.path.join(m5.options.outdir, "cpt.%d" % m5.curTick())
            m5.checkpoint(os.path.join(cpt_dir))
            printVerbose("Checkpoint done.")
        # If this is not a special exit reason, exit the simulation.
        else:
            return event
        
# * Entry:

def main():
    global args
    global t_start
    # Initialize time elapsed.
    t_start = time.time()
    
    # Handle the command-line arguments specification and parsing.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Print detailed information of what is done")
    parser.add_argument("--num-cores", type=int, default=1,
                        help="Number of CPU cores (default = 1)")
    parser.add_argument("--se", action="store_true",
                        help="Enable system-call emulation (must provide 'command' positional arguments)")
    parser.add_argument("se_commands_to_run", metavar="se-command", nargs='*',
                        help="Command(s) to run (multiples commands are assigned to a dedicated core)")
    parser.add_argument("--fs", action="store_true",
                        help="Enable full-system emulation (must provide '--fs-kernel' and '--fs-disk-image' options)")
    parser.add_argument("--fs-kernel", type=str,
                        help="Filename of the Linux kernel to use in full-system emulation (searched under '$M5_PATH/binaries' directory)")
    parser.add_argument("--fs-disk-image", type=str,
                        help="Filename of the disk image containing the system to instantiate in full-system emulation")
    parser.add_argument("--fs-workload-image", type=str,
                        help="Filename of the disk image containing the workload to mount in full-system emulation")
    parser.add_argument("--fs-restore", type=str,
                        help="Path to a folder created by \"m5 checkpoint\" command to use for restoration")

    args = parser.parse_args()
    if argsCheck(args):
        sys.exit(1)

    # Create a single root node for gem5's object hierarchy.
    root = Root(full_system=args.fs)

    # Populate the root hierarchy with a system. A system corresponds to a
    # single node with shared memory.
    root.system = systemCreate(args)

    # Instantiate the C++ object hierarchy. After this point, SimObjects can't
    # be instantiated anymore. The system can optionally by restored from a
    # previous checkpoint.
    printVerbose("Instantiate the system.")
    if args.fs is True and args.fs_restore is not None:
        m5.instantiate(args.fs_restore)
    else:
        m5.instantiate()

    # Start the simulator. This gives control to the C++ world and starts
    # executing instructions. The returned event tells the simulation script
    # why the simulator exited.
    printVerbose("Start the simulation.")
    event = simRun(args)

    # Print the reason for the simulation exit and quit.
    printVerbose("%s @ %d" % (event.getCause(), m5.curTick()))
    sys.exit(event.getCode())

if __name__ == "__m5_main__":
    main()
