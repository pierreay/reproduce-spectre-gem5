/**
 * \brief  ARM Assembly.
 * \author Pierre AYOUB -- IRISA, CNRS
 * \date   2020
 *
 * \details Contain all ARM assembly related stuff. It can be constants or
 *          (macro-)function. The ARM ISA targeted here is only the ARMv8-A
 *          one.
 */

#include "asm.h"

int reload_t(void *ptr) {
    /* Measured times. */
    uint64_t start = 0, end = 0;
    /* Measure the time, load the byte, re-measure the time. */
    start = rdtsc();
    mem_access(ptr);
    end = rdtsc();
    mfence();
    /* Compute the elapsed time. */
    return (int)(end - start);
}

int flush_reload_t(void *ptr) {
    /* Measured times. */
    uint64_t start = 0, end = 0;
    /* Measure the time, load the byte, re-measure the time. */
    start = rdtsc();
    mem_access(ptr);
    end = rdtsc();
    mfence();
    /* Flush the pointed byte. */
    flush(ptr);
    /* Compute the elapsed time. */
    return (int)(end - start);
}
