#include "includes.h"
#include "parser.h"
#include "types.h"
#include "error.h"
#include "arena.h"

#include <string>
#include <vector>
#include <unordered_set>
#include <cstring>
#include <cstdlib>
#include <cstdio>

#ifdef _WIN32
#include <windows.h>
#define PATH_SEP '\\'
#define PATH_SEP_STR "\\"
#else
#include <unistd.h>
#define PATH_SEP '/'
#define PATH_SEP_STR "/"
#endif

// read entire file into heap-allocated buffer. caller must free. returns nullptr on error.
static char *readFile(const char *path, size_t *outLen) {
    FILE *f = fopen(path, "rb");
    if (!f) return nullptr;

    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return nullptr; }
    long size = ftell(f);
    if (size < 0) { fclose(f); return nullptr; }
    rewind(f);

    char *buf = (char *)malloc((size_t)size + 1);
    if (!buf) { fclose(f); return nullptr; }

    size_t n = fread(buf, 1, (size_t)size, f);
    fclose(f);

    buf[n] = '\0';
    if (outLen) *outLen = n;
    return buf;
}

// resolve includeRel relative to baseDir normalising separators cross-platform.
static std::string resolvePath(const std::string &baseDir,
                                const std::string &includeRel) {
    // if includeRel is absolute use it directly
#ifdef _WIN32
    bool isAbs = (includeRel.size() >= 3 &&
                  ((includeRel[1] == ':') || (includeRel[0] == '\\' && includeRel[1] == '\\')));
#else
    bool isAbs = (!includeRel.empty() && includeRel[0] == '/');
#endif
    if (isAbs) return includeRel;

    std::string path = baseDir;
    if (!path.empty() && path.back() != PATH_SEP && path.back() != '/') {
        path += PATH_SEP;
    }
    path += includeRel;

    // normalise all forward slashes to platform separator
#ifdef _WIN32
    for (char &c : path) {
        if (c == '/') c = '\\';
    }
#endif
    return path;
}

// extract directory from path. returns . if no separator found.
static std::string dirOf(const std::string &path) {
    size_t pos = path.find_last_of("/\\");
    if (pos == std::string::npos) return ".";
    return path.substr(0, pos);
}

// forward declaration for recursion
static bool resolveDoc(AstNode *doc, const std::string &baseDir,
                       Arena *arena, int maxDepth,
                       std::unordered_set<std::string> &stack,
                       std::vector<std::string> &warnings,
                       char **errOut);

/*
 * process one @include node.
 * merges the included declarations into parentDecls / parentCount.
 * asName is non-null when "as name" was specified keys are prefixed.
 */
static bool processInclude(AstNode *includeNode,
                            const std::string &baseDir,
                            Arena *arena, int maxDepth,
                            std::unordered_set<std::string> &stack,
                            std::vector<std::string> &warnings,
                            AstNode ***parentDecls, size_t *parentCount,
                            char **errOut) {
    const char *rel    = includeNode->as.include.path;
    const char *asName = includeNode->as.include.asName;

    std::string absPath = resolvePath(baseDir, rel);

    if (stack.count(absPath)) {
        char buf[512];
        snprintf(buf, sizeof(buf), "cyclic include detected: \"%s\"", absPath.c_str());
        *errOut = strdup(buf);
        return false;
    }

    size_t srcLen = 0;
    char *src = readFile(absPath.c_str(), &srcLen);
    if (!src) {
        char buf[512];
        snprintf(buf, sizeof(buf), "cannot open include file \"%s\"", absPath.c_str());
        *errOut = strdup(buf);
        return false;
    }

    ParseResult pr = sclParse(src, srcLen, arena, maxDepth);
    if (!pr.ok) {
        *errOut = pr.error;  // already heap-allocated
        free(src);
        return false;
    }

    TypeResult tr = sclTypeCheck(pr.node, src, arena);
    for (size_t i = 0; i < tr.warningCount; i++) {
        warnings.emplace_back(tr.warnings[i]);
        free(tr.warnings[i]);
    }
    free(tr.warnings);

    if (!tr.ok) {
        *errOut = tr.error;
        free(src);
        return false;
    }

    // recurse into the included docs own includes
    stack.insert(absPath);
    std::string subDir = dirOf(absPath);
    bool ok = resolveDoc(pr.node, subDir, arena, maxDepth, stack, warnings, errOut);
    stack.erase(absPath);

    free(src);
    if (!ok) return false;

    AstNode *childDoc = pr.node;
    size_t childCount = childDoc->as.document.count;
    AstNode **childDecls = childDoc->as.document.decls;

    // merge declarations into parent
    for (size_t i = 0; i < childCount; i++) {
        AstNode *decl = childDecls[i];

        if (decl->type == NODE_DIRECTIVE_INCLUDE) continue;  // already resolved
        if (decl->type == NODE_DIRECTIVE_SCL)     continue;  // skip version directive

        if (asName && decl->type == NODE_FIELD) {
            // prefix field name: asName.originalName
            std::string prefixed = std::string(asName) + "." + decl->as.field.name;
            decl->as.field.name = arenaStrdup(arena, prefixed.c_str());
        }

        size_t newCount = *parentCount + 1;
        AstNode **newDecls = (AstNode **)arenaAlloc(arena, newCount * sizeof(AstNode *));
        memcpy(newDecls, *parentDecls, *parentCount * sizeof(AstNode *));
        newDecls[newCount - 1] = decl;

        *parentDecls = newDecls;
        *parentCount = newCount;
    }

    return true;
}

static bool resolveDoc(AstNode *doc, const std::string &baseDir,
                       Arena *arena, int maxDepth,
                       std::unordered_set<std::string> &stack,
                       std::vector<std::string> &warnings,
                       char **errOut) {
    // collect includes first then expand them
    std::vector<size_t> includeIndices;
    for (size_t i = 0; i < doc->as.document.count; i++) {
        if (doc->as.document.decls[i]->type == NODE_DIRECTIVE_INCLUDE) {
            includeIndices.push_back(i);
        }
    }

    for (size_t idx : includeIndices) {
        AstNode *incNode = doc->as.document.decls[idx];

        bool ok = processInclude(incNode, baseDir, arena, maxDepth,
                                 stack, warnings,
                                 &doc->as.document.decls, &doc->as.document.count,
                                 errOut);
        if (!ok) return false;

        /* mark the @include slot as resolved by nulling it;
           callers skip null entries, so no reshuffle needed here.
           we do a compaction pass below. */
        doc->as.document.decls[idx] = nullptr;
    }

    // compact: remove null slots
    if (!includeIndices.empty()) {
        size_t dst = 0;
        for (size_t i = 0; i < doc->as.document.count; i++) {
            if (doc->as.document.decls[i]) {
                doc->as.document.decls[dst++] = doc->as.document.decls[i];
            }
        }
        doc->as.document.count = dst;
    }

    return true;
}

IncludeResult sclResolveIncludes(AstNode *doc, const char *basePath,
                                 Arena *arena, int maxDepth) {
    IncludeResult result = {};

    std::string baseDir = basePath ? std::string(basePath) : std::string(".");

    std::unordered_set<std::string> stack;
    std::vector<std::string> warnings;
    char *err = nullptr;

    bool ok = resolveDoc(doc, baseDir, arena, maxDepth, stack, warnings, &err);

    result.ok    = ok;
    result.error = ok ? nullptr : err;

    if (!warnings.empty()) {
        result.warningCount = warnings.size();
        result.warnings = (char **)malloc(result.warningCount * sizeof(char *));
        for (size_t i = 0; i < result.warningCount; i++) {
            result.warnings[i] = strdup(warnings[i].c_str());
        }
    }

    return result;
}

void includeResultFree(IncludeResult *r) {
    if (!r) return;
    free(r->error);
    for (size_t i = 0; i < r->warningCount; i++) free(r->warnings[i]);
    free(r->warnings);
    r->error        = nullptr;
    r->warnings     = nullptr;
    r->warningCount = 0;
}
