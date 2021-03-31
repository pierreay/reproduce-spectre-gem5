"""ARMv8-A Cortex A72 - DerivO3CPU

Cluster and cores classes based on the real CPU. It is shipped with a Raspberry
Pi system emulation script. The intended use is security research.

"""
# * Terminology:

# Processors = CPUs = Cores : gather all components needed to execute one
# stream of instruction, often with a private and banked level-1 memory system.

# Processor = CPU = Cluster = Package : 1 or more processors, i.e. 1 or more
# cores that allow parallelism, often with a shared and unified memory system.

# Detailed mode = Timing mode : simulation mode in which the processor and the
# memory subsystem are the most accurate, but the simulation is very slow.

# Fast mode = Atomic mode : simulation mode in which the processor and the
# memory subsystem are pretty simple and therefore not accurate, but the
# simulation is very fast.

# * Importations:

# ** Gem5:

# M5/gem5 library (created when gem5 is compiled).
import m5
# Python SimObjects list.
from m5.objects import *

# * Classes:

# ** Core:

class ARM_A72_CacheWalker(Cache):
    """Page Table Walker Cache.

    This cache is used by the MMU when a TLB miss occurs. The specification is
    not given by ARM, therefore we can refer to the HPI.py parameters and the
    Schaik et al. 'Reverse Engineering Hardware Page Table Caches Using
    Side-Channel Attacks on the MMU' paper.

    """
    # Find into the mentioned paper above.
    assoc = 4
    # Taken from the HPI.py. Correspond to the O3_ARM_v7a.py too. 
    size = '1kB' # The size have to correspond to 64 entries. Since we don't
                 # know the size of an entry, we don't know what to set for the
                 # size.
    data_latency = 4
    tag_latency = 4
    response_latency = 4
    mshrs = 6
    tgts_per_mshr = 8
    write_buffers = 16
    # Taken from the the O3_ARM_v7a.py.
    is_read_only = True

class ARM_A72_TLB_L1D(ArmDTB):
    """L1 Data TLB.

    This private TLB is used by one core to store VA-PA translations address
    for data. Specification are given in the architecture manual.

    """
    # 48 entries.
    size = 48

class ARM_A72_TLB_L1I(ArmITB):
    """L1 Instruction TLB.

    This private TLB is used by one core to store VA-PA translations address
    for instructions. Specification are given in the architecture manual.

    """
    # 32 entries.
    size = 32

class ARM_A72_CacheL1I(Cache):
    """L1 Instruction cache.
    
    This private cache is used by one core to store
    instructions. Specifications are given in the architecture manual.

    """
    size = '48kB'
    # 3-way set associative.
    assoc = 3
    # Latencies are not precised into the manual. These one are take from
    # HPI.py, and seems reasonable.
    data_latency = 1
    tag_latency = 1
    response_latency = 1
    # Taken from HPI.py. No information on them in architecture manual.
    mshrs = 2
    tgts_per_mshr = 8
    # Taken from the the O3_ARM_v7a.py.
    is_read_only = True
    # Cache line size is child of the system object.
    # TODO No prefetcher, this is handled by the core?

class ARM_A72_CacheL1D(Cache):
    """L1 Data cache.
    
    This private cache is used by one core to store data. Specifications are
    given in the architecture manual.

    """
    size = '32kB'
    # 2-way set associative.
    assoc = 2
    # Latencies are not precised into the manual. These one are take from
    # HPI.py, and seems reasonable.
    data_latency = 1
    tag_latency = 1
    response_latency = 1
    # Taken from HPI.py. No information on them in architecture manual.
    mshrs = 4
    tgts_per_mshr = 8
    write_buffers = 4
    # Cache line size is child of the system object.
    # TODO This prefetcher is taken from HPI.py. We have to configure it.
    prefetcher = StridePrefetcher(queue_size=4, degree=4)

class ARM_A72_BP(BiModeBP):
    """Branch Predictor. TODO"""
    BTBEntries = 2048
    
    # No simple two-level global-based predictor on gem5. Only TournamentBP and
    # Bi-Mode predictors are global-based predictors, but the first one is also
    # local and the second one separate mostly-taken and mostly-not-taken
    # branches into two PHTs. Since our Spectre attacked branches is trained to
    # be mostly-taken, the BiMode seems to be the closer one.

    # No static predictor on gem5. IndirectPredictor is already set and used by
    # default. RAS is set and used by default.

def ARM_A72_CoreCreate(self, BaseCPU, idx):
    """Create an ARM_A72_Core.

    Specialize the ARM_A72_Core regarding the mode of the simulation.

    :param BaseCPU: Either "AtomicSimpleCPU" if system.mem_mode == "atomic",
                    DerivO3CPU otherwise.
    :returns: Return the configured core.

    """
    class ARM_A72_Core(BaseCPU):
        """ARMv8-A Cortex-A72 core. This is considered by gem5 as one CPU, inherited
        from the O3CPU if we are in detailed mode.

        """
        # Declare the branch predictor of the core.
        branchPred_type = ARM_A72_BP

        # Instantiate the banked TLBs for the core.
        itb = ARM_A72_TLB_L1I()
        dtb = ARM_A72_TLB_L1D()

        def branchPredAdd(self):
            """Instantiate the predifined branch predictor to this core."""
            self.branchPred = self.branchPred_type()

    core = ARM_A72_Core(cpu_id=idx)

    # Configuration based on CPU type.
    if isinstance(core, AtomicSimpleCPU):
        pass
    elif isinstance(core, DerivO3CPU):
        # Pipeline width (in instructions).
        core.fetchWidth = 4 # 128 bits width for 32-bit instructions.
        core.decodeWidth = 3
        core.commitWidth = 3
        core.dispatchWidth = 5
        core.issueWidth = 8
        
    return core

# ** Cluster:

class ARM_A72_CacheL2Bus(L2XBar):
    """Unification bus.

    This bus connect the L1 private caches to the shared L2 cache. It is
    considered as the PoU (Point of Unification). No mention of it in the
    architecture manual.

    """
    # Set the width of the crossbar to the cache line size.
    width = 64

class ARM_A72_CacheL2(Cache):
    """L2 unified cache.

    This shared cache is used by all cores to store data and
    instructions. Specifications are given in the architecture manual.

    """
    size = '1024kB'
    # 16-way set associative.
    assoc = 16
    # Latencies are not precised into the manual. These one are take from
    # HPI.py, and seems reasonable.
    data_latency = 13
    tag_latency = 13
    response_latency = 5
    # Taken from HPI.py. No information on them in architecture manual.
    mshrs = 4
    tgts_per_mshr = 8
    write_buffers = 16
    # Cache line size is child of the system object.
    # TODO This prefetcher is taken from HPI.py. We have to configure it.
    prefetcher = StridePrefetcher(queue_size=4, degree=4)
    # Create a bus used as the unification point for all L1 caches.
    bus = ARM_A72_CacheL2Bus()
    
class ARM_A72_Cluster(SubSystem):
    """ARMv8-A Cortex A72 cluster. 

    This processor contains one or more CPUs (cores) with a shared L2 cache.

    """
    # Processor clock and voltage.
    _cpu_clock   = "1.5GHz"
    _cpu_voltage = "1.2V"

    # Declare the classes (or builder functions) used to build the
    # processor. They will be instantiated later.
    cpu_type    = ARM_A72_CoreCreate
    l1i_type    = ARM_A72_CacheL1I
    l1d_type    = ARM_A72_CacheL1D
    l2_type     = ARM_A72_CacheL2
    wcache_type = ARM_A72_CacheWalker

    # Constructor.
    def __init__(self, system, num_cpus):
        """Return a CPU cluster with the number of cores specified.

        The clock/voltage domain and the cores are configured. The memory
        hierarchy (caches) have to be connected to a memory bus later.

        """
        super().__init__()
        assert num_cpus > 0

        # Create a voltage and clock domain for cluster components.
        self.voltage_domain = VoltageDomain(voltage=self._cpu_voltage)
        self.clk_domain     = SrcClockDomain(clock=self._cpu_clock,
                                             voltage_domain=self.voltage_domain,
                                             domain_id=1)

        # Instantiate the core(s) of the CPU regarding the system memory mode.
        cpu_base = AtomicSimpleCPU if system.getMemoryMode() == "atomic" else DerivO3CPU
        self.cpus = [self.cpu_type(cpu_base, idx) for idx in range(num_cpus)]

        # Configure each core of the CPU:
        for cpu in self.cpus:
            # Create an ISA instance for each HW threads (one per core without
            # SMT).
            cpu.createThreads()
            # Create an ARM interrupt controller for each HW threads (one per
            # core without SMT).
            cpu.createInterruptController()
            # Only in detailed mode:
            if system.getMemoryMode() == "timing":
                # Add the branch predictor.
                cpu.branchPredAdd()

        # Configure the cluster:
        if system.getMemoryMode() == "timing":
            # Configure the memory hierarchy of the cores and of the cluster.
            self.cacheAddL1()
            self.cacheAddL2()

    def cacheAddL1(self):
        """Configure L1 caches.

        For each cores of the CPU, instantiate the L1 caches, register them
        into the appropriate variables, and connect each core to his L1 and
        walk cache.

        """
        assert self.l1i_type    is not None
        assert self.l1d_type    is not None
        assert self.wcache_type is not None
        for cpu in self.cpus:
            cpu.addPrivateSplitL1Caches(self.l1i_type(),    self.l1d_type(),
                                        self.wcache_type(), self.wcache_type())

    def cacheAddL2(self):
        """Configure L2 caches.

        Instantiate the L2 bus and the L2 cache. For each L1 caches for each
        cores of the CPU, connect it to the L2 bus and connect the bus to the
        L2 cache.

        """
        assert self.l2_type is not None
        self.l2 = self.l2_type()
        for cpu in self.cpus:
            cpu.connectAllPorts(self.l2.bus)
        self.l2.bus.master = self.l2.cpu_side

    def connectCacheL2(self, bus):
        """Connect the L2 cache.

        Connect the L2 cache to a memory bus.

        """
        self.l2.mem_side = bus.slave

    def connectDirect(self, bus):
        """Connect the CPU directly to the rest of the system.

        This function connect the 4 CPU's ports (caches & TLBs) to the main
        memory bus, which has to be used when using "atomic" mode.

        :param bus: The memory bus of the system.

        """
        for cpu in self.cpus:
            cpu.dtb.walker.port = bus.slave
            cpu.itb.walker.port = bus.slave
            cpu.dcache_port = bus.slave
            cpu.icache_port = bus.slave

# * Public interface:

__all__ = [
    "ARM_A72_Cluster"
]
