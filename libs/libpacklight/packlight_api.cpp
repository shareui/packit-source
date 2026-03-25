#include "packlight.h"
#include "pl_utf.h"
#include <stdlib.h>
#include <string.h>

// forward declarations from language modules
uint32_t pl_tokenize_json(const char* src, uint32_t src_len, Token* out, uint32_t out_cap);
uint32_t pl_tokenize_python(const char* src, uint32_t src_len, Token* out, uint32_t out_cap);

extern "C" {

PL_API uint32_t packlight_json(
    const char* src, uint32_t src_len,
    Token* out_tokens, uint32_t out_cap
) {
    return pl_tokenize_json(src, src_len, out_tokens, out_cap);
}

PL_API uint32_t packlight_python(
    const char* src, uint32_t src_len,
    Token* out_tokens, uint32_t out_cap
) {
    return pl_tokenize_python(src, src_len, out_tokens, out_cap);
}

// convert token byte offsets to char index ranges in a single utf-8 walk
// tokens must be sorted by start (tokenizers always produce them in order)
PL_API uint32_t packlight_tokens_to_chars(
    const char* src, uint32_t src_len,
    const Token* tokens, uint32_t token_count,
    CharRange* out_ranges, uint32_t out_cap
) {
    if (token_count == 0 || out_cap == 0) return 0;

    uint32_t count = token_count < out_cap ? token_count : out_cap;

    // collect unique byte offsets (start and end of each token) sorted
    uint32_t* offsets = (uint32_t*)malloc(count * 2 * sizeof(uint32_t));
    if (!offsets) return 0;

    for (uint32_t k = 0; k < count; k++) {
        offsets[k * 2]     = tokens[k].start;
        offsets[k * 2 + 1] = tokens[k].start + tokens[k].length;
    }

    // offsets array is already in ascending order because tokens are sorted,
    // and end[k] <= start[k+1] is guaranteed by the tokenizer structure.
    // we need a fully sorted unique list for utf8MapOffsets.
    // build merged sorted array of 2*count offsets:
    // since tokens don't overlap and are sorted, we can merge pairs inline.
    // simplest: just sort the flat array (2*count entries, usually small per chunk)
    // use insertion sort count is bounded by _MAX_TOKENS which is chunked in python
    uint32_t n = count * 2;
    for (uint32_t i = 1; i < n; i++) {
        uint32_t key = offsets[i];
        int32_t j = (int32_t)i - 1;
        while (j >= 0 && offsets[j] > key) {
            offsets[j + 1] = offsets[j];
            j--;
        }
        offsets[j + 1] = key;
    }

    uint32_t* charMap = (uint32_t*)malloc(n * sizeof(uint32_t));
    if (!charMap) { free(offsets); return 0; }

    utf8MapOffsets(src, src_len, offsets, n, charMap);

    // map results back to CharRange per token
    // for each token, find its start/end in offsets[] and look up charMap
    for (uint32_t k = 0; k < count; k++) {
        uint32_t bs = tokens[k].start;
        uint32_t be = tokens[k].start + tokens[k].length;

        // binary search in sorted offsets for bs
        uint32_t lo = 0, hi = n;
        while (lo < hi) { uint32_t mid = (lo + hi) / 2; if (offsets[mid] < bs) lo = mid + 1; else hi = mid; }
        uint32_t cs = (lo < n && offsets[lo] == bs) ? charMap[lo] : UINT32_MAX;

        lo = 0; hi = n;
        while (lo < hi) { uint32_t mid = (lo + hi) / 2; if (offsets[mid] < be) lo = mid + 1; else hi = mid; }
        uint32_t ce = (lo < n && offsets[lo] == be) ? charMap[lo] : UINT32_MAX;

        out_ranges[k] = {bs, be, cs, ce};
    }

    free(offsets);
    free(charMap);
    return count;
}

}
