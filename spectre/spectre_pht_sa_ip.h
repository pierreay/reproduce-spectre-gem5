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

#ifndef _SPECTRE_PHT_SA_IP_H_
#define _SPECTRE_PHT_SA_IP_H_

/* Used for \sa {struct arguments}. */
#include "util.h"

/* * Constants: */

/** Page size. Can be obtain at runtime by 'pagesize =
    sysconf(_SC_PAGESIZE);'. */
#define PAGESIZE (256) // TODO Test 256, 512, 4096. It's called PAGESIZE, which
                       // I though initially. Currently, I don't thought that
                       // anymore. What this number really is?

/** Cache line size. Can be obtain with the architecture manual. */
#define CACHELINE (64)

/* * Variables: */

/* Offset array used to read an arbitrary memory location. It has to be shared
   by the victim and the attack. */
extern uint8_t array1[160];

/* Probing array used to recover the read memory location by a
   covert-channel. */
extern uint8_t array2[256 * PAGESIZE];

/* This string has to be read without accessing to it. */
extern char *secret;

/* * Prototypes: */

/**
 * \brief Try to read a memory byte with Spectre.
 * \details Given an offset to array1, train the branch predictor and try to
 *          read the data pointed by this offset with a Spectre attack. To do
 *          this, we perform a lot of try and compute basics statistics about
 *          them, in order to decide which guess is the better.
 *
 * \param malicious_x The offset to array1 which is the target of Spectre.
 * \param args Parameters for the experiment. Must contain "tries" field.
 * \param value Pointer to a char where to store the best guess.
 * \param score Pointer to a int where to store the score of the best guess.
 */
void spectre_pht_sa_ip_read(size_t malicious_x, struct arguments * args, uint8_t * value, int * score);

#endif /* _SPECTRE_PHT_SA_IP_H_ */
