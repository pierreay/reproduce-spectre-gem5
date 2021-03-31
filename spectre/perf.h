/**
 * \brief  Performance counters.
 * \author Pierre AYOUB -- IRISA, CNRS
 * \date   2020
 *
 * \details Contain all perf_event related stuff. perf_event usage is simple
 * here: init, read, close. Counters could be enabled with ioctl(), grouped,
 * sampled, multiplexed... we do not use all of this.
 */

#ifndef _PERF_H_
#define _PERF_H_

#include <stdint.h>

/**
 * \brief Initialize the PMU's counters with the perf_event interface.
 * \details Counters are initialized to zero and started as soon as they can.
 */
void perf_init();

/**
 * \brief Stop the PMU's counters.
 */
void perf_close();

/**
 * \brief Get the number of cache miss since the initialization.
 *
 * \return uint64_t (long unsigned int) Value of the cache miss counter.
 */
uint64_t perf_read_cache_miss();

/**
 * \brief Get the number of mispredicted branches since the initialization.
 *
 * \return uint64_t (long unsigned int) Value of the mispredicted branches counter.
 */
uint64_t perf_read_branch_miss();

#endif /* _PERF_H_ */
