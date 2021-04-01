/**
 * \brief  Performance counters.
 * \author Pierre AYOUB -- IRISA, CNRS
 * \date   2020
 *
 * \details Contain all perf_event related stuff. perf_event usage is simple
 * here: init, read, close. Counters could be enabled with ioctl(), grouped,
 * sampled, multiplexed... we do not use all of this.
 * 
 * \TODO Refactor the choice between PERF_TYPE_HARDWARE for real ARM hardware
 * and PERF_TYPE_RAW to use with gem5. Currently, the choice is done by
 * commenting out a code portion. Very bad, but I don't have time for doing
 * better now.
 */

#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <stdint.h>
#include <assert.h>

#include <unistd.h>
#include <sys/syscall.h>
#include <linux/perf_event.h>

#include "perf.h"

/** File descriptor used to read cache miss counter. */
static int perf_fd_cache_miss;
/** File descriptor used to read mispredicted branches counter. */
static int perf_fd_branch_miss;

/**
 * \brief Initialize a "perf_event_attr", ready to be passed to "perf_event_open()".
 *
 * \param attr Pointer to the "perf_event_attr" to configure.
 * \param config Value of the "config" field for this "perf_event_attr".
 */
static void perf_attr_init(struct perf_event_attr * attr, uint64_t config)
{
    /* To use with real ARM hardware: */
    attr->type = PERF_TYPE_HARDWARE;
    /* To use with gem5 full-system ARM: */
    // attr->type = PERF_TYPE_RAW;
    attr->config = config;
    attr->size = sizeof(*attr);
    attr->exclude_kernel = 1;
    attr->exclude_hv = 1;
    attr->exclude_callchain_kernel = 1;
}

void perf_init() {
    /* Initialize our perf_event_attr, representing one counter to be read. */
    static struct perf_event_attr attr_cache_miss;
    /* To use with real ARM hardware: */
    perf_attr_init(&attr_cache_miss, PERF_COUNT_HW_CACHE_MISSES);
    /* To use with gem5 full-system ARM: */
    // perf_attr_init(&attr_cache_miss, 0x33);
    /* Open the file descriptor corresponding to this counter. The counter
       should start at this moment. */
    if ((perf_fd_cache_miss = syscall(__NR_perf_event_open, &attr_cache_miss, 0, -1, -1, 0)) == -1)
        fprintf(stderr, "perf_event_open fail %d %d: %s\n", perf_fd_cache_miss, errno, strerror(errno));
        
    /* Same here. */
    static struct perf_event_attr attr_branch_miss;
    /* To use with real ARM hardware: */
    perf_attr_init(&attr_branch_miss,PERF_COUNT_HW_BRANCH_MISSES);
    /* To use with gem5 full-system ARM: */
    // perf_attr_init(&attr_branch_miss, 0x10);
    if ((perf_fd_branch_miss = syscall(__NR_perf_event_open, &attr_branch_miss, 0, -1, -1, 0)) == -1)
        fprintf(stderr, "perf_event_open fail %d %d: %s\n", perf_fd_branch_miss, errno, strerror(errno));
}

void perf_close() {
    close(perf_fd_cache_miss);
    close(perf_fd_branch_miss);
}

uint64_t perf_read_cache_miss() {
    uint64_t result;
    read(perf_fd_cache_miss, &result, sizeof(result));
    return result;
}

uint64_t perf_read_branch_miss() {
    uint64_t result;
    read(perf_fd_branch_miss, &result, sizeof(result));
    return result;
}
