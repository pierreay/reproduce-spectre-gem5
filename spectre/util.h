/**
 * \brief  Utilities.
 * \author Pierre AYOUB -- IRISA, CNRS
 * \date   2020
 *
 * \details Contain useful stuff: managing arguments, statistics, output and
 * formatting.
 */

#ifndef _UTIL_H_
#define _UTIL_H_

/* * Structures: */

/**
 * \brief Program's arguments.
 *
 * \details Instantiate and initialized at the beginning of the program, used
 * to hold and dispatch program's options and arguments across the program.
 * 
 * \note Description of fields can be found in the function that parse
 * arguments \sa {arg_parse()}. They are initialized into the \sa {arg_init()}
 * function.
 */
struct arguments
{
    int quiet;
    int verbose;
    int meta;
    int tries;
    int loops;
    int cache_threshold;
};

/* * Variables: */

/** Assume a cache hit if (time <= threshold). We can use a define for speed,
    or a variable to compute it at runtime. */
extern int CACHE_HIT_THRESHOLD;

/* * Prototypes: */

/**
 * \brief Test if a character is printable or not.
 *
 * \param c The character to test.
 * \return 1 if it is printable, 0 otherwise.
 */
int char_is_printable(char c);

/**
 * \brief Compute the hamming distance between two strings.
 * \details Hamming distance is computed by comparing each byte of the two
 *          strings and sum the number of differences.
 *
 * \param str1 First string to compare.
 * \param str2 Second string to compare.
 * \param size Size of the strings.
 * \return int The hamming distance \in [0, size] (in theory, it should be \in
 *             [0, max(|str1|, |str2|)]).
 *
 * \warning size <= max(strlen(str1), strlen(str2))
 */
int string_hamming_dist(char * str1, char * str2, size_t size);

/**
 * \brief Compute the sum of an array (a vector) of integer.
 *
 * \param array Array of int to sum.
 * \param size Size of the integer array.
 * \return int The sum of array's elements.
 */
int int_sum(int * array, size_t size);

/**
 * \brief Initialize the command-line arguments with default values.
 *
 * \param args Structure that will hold user's supplied options and arguments.
 */
void arg_init(struct arguments *args);

/**
 * \brief Parse the given command-line arguments.
 *
 * \param argc Number of arguments.
 * \param argv Array of arguments.
 * \param arguments Structure holding initialized arguments that will reflect
 *                  command-line arguments.
 */
void arg_parse(int argc, char **argv, struct arguments *arguments);

/**
 * \brief Detect the threshold to use for Flush+Reload attack.
 * \details Perform multiple reload and flush+reload operation, compute the
 *          mean of them and estimate a good threshold allowing to distinguish
 *          a cache hit from a cache miss.
 *
 * \return size_t The computed threshold, typically between 50 and 300.
 */
size_t flush_reload_threshold();

/**
 * \brief Test if the program is under a gem5 simulation.
 * \details Use a user-defined environment variable (GEM5_SIM) to test for
 *          gem5. If we are on gem5, set this variable to "true". Otherwise,
 *          set it to "false" or let it undefined.
 *
 * \return int 1 if we are under gem5, 0 otherwise.
 */
int gem5_is_sim();

#endif
