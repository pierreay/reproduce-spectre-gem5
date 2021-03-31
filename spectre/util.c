/**
 * \brief  Utilities.
 * \author Pierre AYOUB -- IRISA, CNRS
 * \date   2020
 *
 * \details Contain useful stuff: managing arguments, statistics, output and
 * formatting.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <argp.h>
#include <assert.h>

/* Used to compute cache threshold. */
#include "asm.h"

#include "util.h"

/* * Public variables: */

/* The assignation to 0 is just initialization. The value will be computed at
   runtime by \sa {flush_reload_threshold()} function, or specified on the
   command-line. */
int CACHE_HIT_THRESHOLD = 0;

/* * Variables: */

/** Maintainers' address. Used in the output of "-?" and "--help". */
const char *argp_program_bug_address = "<pierre.ayoub@irisa.fr>";
/** Program's version. Used in the output of "-V" and "--version". */
const char *argp_program_version = "Spectre v0.1";
/** Program's documentation. Used in the output of "-?" and "--help". Can be
 * long if needed. */
static char doc[] = "Spectre -- A Spectre implementation useful for research";

/* * Functions: */

/* ** Strings: */

int char_is_printable(char c)
{
    return c > 31 && c < 127 ? 1 : 0;
}

int string_hamming_dist(char * str1, char * str2, size_t size)
{
    int sum = 0;
    for (int i = 0; i < size; i++)
        sum += str1[i] != str2[i] ? 1 : 0;
    return sum;
}

/* ** Arrays: */

int int_sum(int * array, size_t size)
{
    int sum = 0;
    for (int i = 0; i < size; i++)
        sum += array[i];
    return sum;
}

/* ** Arguments: */

/**
 * \brief Parse a single option.
 *
 * \param key An integer specifying which option this is (taken from the KEY
 *            field in each struct argp_option), or a special key specifying
 *            something else. The only special keys we use here are
 *            ARGP_KEY_ARG, meaning a non-option argument, and ARGP_KEY_END,
 *            meaning that all arguments have been parsed.
 * \param arg For an option KEY, the string value of its argument, or NULL if
 *            it has none.
 * \param state A pointer to a struct argp_state, containing various useful
 *              information about the parsing state. Used here are the INPUT
 *              field, which reflects the INPUT argument to argp_parse, and the
 *              ARG_NUM field, which is the number of the current non-option
 *              argument being parsed.
 * \return error_t It should return either 0, meaning success,
 *                 ARGP_ERR_UNKNOWN, meaning the given KEY wasn’t recognized,
 *                 or an errno value indicating some other error.
 */
static error_t arg_parse_opt (int key, char *arg, struct argp_state *state)
{
    /* Get the input argument from argp_parse, which we
       know is a pointer to our arguments structure. */
    struct arguments *arguments = state->input;

    /* Test the passed option or argument. */
    switch (key)
        {
        /* Options. */
        case 'q': case 's':
            arguments->quiet = 1;
            break;
        case 'v':
            arguments->verbose = 1;
            break;
        case 'm':
            arguments->meta = atoi(arg);
            if (arguments->meta <= 0) {
                fprintf(stderr, "<meta> must be superior to 0.\n");
                argp_usage(state);
            }
            break;
        case 't':
            arguments->tries = atoi(arg);
            if (arguments->tries <= 0) {
                fprintf(stderr, "<tries> must be superior to 0.\n");
                argp_usage(state);
            }
            break;
        case 'l':
            arguments->loops = atoi(arg);
            if (arguments->loops <= 0) {
                fprintf(stderr, "<loops> must be superior to 0.\n");
                argp_usage(state);
            }
            break;
        case 'c':
            arguments->cache_threshold = atoi(arg);
            if (arguments->cache_threshold <= 0) {
                fprintf(stderr, "<cache_threshold> must be superior to 0.\n");
                argp_usage(state);
            }
            break;

        /* End of parsing. */
        case ARGP_KEY_END:
            break;
        default:
            return ARGP_ERR_UNKNOWN;
        }
    return 0;
}

void arg_init(struct arguments *args)
{
    args->quiet           = 0;
    args->verbose         = 0;
    args->meta            = 1;
    args->tries           = 999;
    args->loops           = 30;
    args->cache_threshold = 0;
}

void arg_parse(int argc, char **argv, struct arguments *arguments)
{
    /**
     * Options of the program. Here is the description of the fields:
     * NAME   – The name of this option's long option (may be zero).
     * KEY    – The KEY to pass to the PARSER function when parsing this
     *          option, and the name of this option’s short option, if it is a
     *          printable ASCII character.
     * ARG    – The name of this option’s argument, if any.
     * FLAGS  – Flags describing this option, some of them are:
     * - OPTION_ARG_OPTIONAL The argument to this option is optional,
     * - OPTION_ALIAS        This option is an alias for the previous option,
     * - OPTION_HIDDEN       Don’t show this option in "-–help" output.
     * DOC    – A documentation string for this option, shown in "–-help"
     *          output.
     */
    static struct argp_option options[] =
        {
         {"verbose",         'v', 0,        0,  "Produce verbose output" },
         {"quiet",           'q', 0,        0,  "Don't produce the header for csv" },
         {"silent",          's', 0,        OPTION_ALIAS },
         {"meta",            'm', "NUMBER", 0, "Number of meta-repetition of Spectre (default: 1)" },
         {"tries",           't', "NUMBER", 0, "Number of attempts to guess a secret byte (default: 999)" },
         {"loops",           'l', "NUMBER", 0, "Number of loops (training and attack) per attempts (default: 30)" },
         {"cache_threshold", 'c', "NUMBER", 0, "Cache threshold separating hit and miss (default: automatically computed)" },
         { 0 }
        };

    /** Our argument parser. */
    static struct argp argp = {options, arg_parse_opt, 0, doc};
    /* Use it to parse the command-line. */
    argp_parse(&argp, argc, argv, 0, 0, arguments);
}

/* ** Flush+Reload: */

size_t flush_reload_threshold() {
    /* Number of cycle taken by reload and flush+reload operations. */
    size_t reload_time = 0, flush_reload_time = 0;
    /* Number of operation to have a good estimation (arbitrary). If we are on
       gem5, use a very low iteration count (or even 1) : gem5 is
       deterministic. */
    size_t count = gem5_is_sim() ? 10 : 100000;
    /* Create dummy data to access. */
    size_t dummy[16] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15};
    size_t *ptr = dummy + 8;

    /* Access to the data one time, and reload it. */
    mem_access(ptr);
    for (int i = 0; i < count; i++)
        reload_time += reload_t(ptr);
    /* Flush the data and reload it. */
    for (int i = 0; i < count; i++)
        flush_reload_time += flush_reload_t(ptr);
    /* Compute the mean of the two measures above. */
    reload_time /= count;
    flush_reload_time /= count;
    /* Compute an approximation of the middle of the two mean. */
    return (flush_reload_time + reload_time * 2) / 3;
}

/* ** gem5: */

int gem5_is_sim() {
    char *gem5_sim = getenv("GEM5_SIM");
    return gem5_sim ? strcmp(gem5_sim, "false") : 0;
}
