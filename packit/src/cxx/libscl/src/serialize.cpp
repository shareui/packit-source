#include "serialize.h"
#include "value.h"

#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <sstream>
#include <string>
#include <cmath>

//  helpers 

static char *heapStr(const std::string &s) {
    char *p = static_cast<char *>(malloc(s.size() + 1));
    memcpy(p, s.data(), s.size() + 1);
    return p;
}

static scl_str_t makeStr(const std::string &s) {
    scl_str_t r;
    r.data = heapStr(s);
    r.len  = s.size();
    return r;
}

// escape a string for SCL output  only escapes that SCL requires
static std::string sclEscapeString(const char *p, size_t len) {
    std::string out;
    out.reserve(len + 2);
    out += '"';
    for (size_t i = 0; i < len; i++) {
        unsigned char c = static_cast<unsigned char>(p[i]);
        if (c == '\\')      { out += "\\\\"; }
        else if (c == '"')  { out += "\\\""; }
        else if (c == '\t') { out += "\\t"; }
        else if (c == '\n') { out += "\\n"; }
        else                { out += static_cast<char>(c); }
    }
    out += '"';
    return out;
}

// escape a string for JSON
static std::string jsonEscapeString(const char *p, size_t len) {
    std::string out;
    out.reserve(len + 2);
    out += '"';
    for (size_t i = 0; i < len; i++) {
        unsigned char c = static_cast<unsigned char>(p[i]);
        if (c == '\\')      { out += "\\\\"; }
        else if (c == '"')  { out += "\\\""; }
        else if (c == '\n') { out += "\\n"; }
        else if (c == '\r') { out += "\\r"; }
        else if (c == '\t') { out += "\\t"; }
        else if (c < 0x20) {
            char buf[8];
            snprintf(buf, sizeof(buf), "\\u%04x", c);
            out += buf;
        } else {
            out += static_cast<char>(c);
        }
    }
    out += '"';
    return out;
}

static std::string base64Encode(const uint8_t *data, size_t len) {
    static const char tab[] =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string out;
    out.reserve(((len + 2) / 3) * 4);
    for (size_t i = 0; i < len; i += 3) {
        uint32_t v = static_cast<uint32_t>(data[i]) << 16;
        if (i + 1 < len) v |= static_cast<uint32_t>(data[i + 1]) << 8;
        if (i + 2 < len) v |= static_cast<uint32_t>(data[i + 2]);
        out += tab[(v >> 18) & 0x3f];
        out += tab[(v >> 12) & 0x3f];
        out += (i + 1 < len) ? tab[(v >> 6) & 0x3f] : '=';
        out += (i + 2 < len) ? tab[v & 0x3f] : '=';
    }
    return out;
}

// format double without trailing zeros but keep it valid
static std::string formatFloat(double v) {
    if (std::isinf(v) || std::isnan(v)) return "0.0";  // not valid SCLJSON
    char buf[64];
    snprintf(buf, sizeof(buf), "%.17g", v);
    // ensure a dot is present so it doesnt look like int
    bool hasDot = false;
    for (char *p = buf; *p; p++) {
        if (*p == '.' || *p == 'e' || *p == 'E') { hasDot = true; break; }
    }
    if (!hasDot) strcat(buf, ".0");
    return buf;
}

static void sclSerializeValue(std::ostringstream &out, scl_value_t *val,
                               int depth);

static void sclIndent(std::ostringstream &out, int depth) {
    for (int i = 0; i < depth; i++) out << "    ";
}

static void sclSerializeKV(std::ostringstream &out, scl_value_t *val,
                            int depth) {
    // structmap: emit as  key  value ...
    out << "{\n";
    for (SclKV *kv = val->as.kv.head; kv; kv = kv->next) {
        sclIndent(out, depth + 1);
        out << kv->key << " = ";
        sclSerializeValue(out, kv->val, depth + 1);
        out << ",\n";
    }
    sclIndent(out, depth);
    out << "}";
}

static void sclSerializeValue(std::ostringstream &out, scl_value_t *val,
                               int depth) {
    switch (val->type) {
        case SCL_TYPE_NULL:
            out << "null";
            break;
        case SCL_TYPE_BOOL:
            out << (val->as.b ? "true" : "false");
            break;
        case SCL_TYPE_INT:
            out << val->as.i;
            break;
        case SCL_TYPE_UINT:
            out << val->as.u << "u";
            break;
        case SCL_TYPE_FLOAT:
            out << formatFloat(val->as.f);
            break;
        case SCL_TYPE_STRING:
        case SCL_TYPE_DATE:
        case SCL_TYPE_DATETIME:
        case SCL_TYPE_DURATION:
            out << sclEscapeString(val->as.str.ptr, val->as.str.len);
            break;
        case SCL_TYPE_BYTES: {
            std::string b64 = base64Encode(val->as.bytes.ptr, val->as.bytes.len);
            out << "b64\"" << b64 << "\"";
            break;
        }
        case SCL_TYPE_LIST: {
            out << "[\n";
            for (size_t i = 0; i < val->as.list.count; i++) {
                sclIndent(out, depth + 1);
                sclSerializeValue(out, val->as.list.items[i], depth + 1);
                out << ",\n";
            }
            sclIndent(out, depth);
            out << "]";
            break;
        }
        case SCL_TYPE_STRUCT:
        case SCL_TYPE_MAP:
            sclSerializeKV(out, val, depth);
            break;
        case SCL_TYPE_UNION:
            // union values are stored as their actual concrete value
            out << "null";
            break;
    }
}

scl_str_t sclSerialize(scl_doc_t *doc) {
    std::ostringstream out;
    out << "@scl 1\n\n";

    for (SclKV *kv = doc->root->as.kv.head; kv; kv = kv->next) {
        // we dont have type info at doc level  emit as inferred
        scl_value_t *v = kv->val;

        // determine inline type annotation
        const char *typeName = nullptr;
        switch (v->type) {
            case SCL_TYPE_STRING:   typeName = "string";   break;
            case SCL_TYPE_INT:      typeName = "int";      break;
            case SCL_TYPE_UINT:     typeName = "uint";     break;
            case SCL_TYPE_FLOAT:    typeName = "float";    break;
            case SCL_TYPE_BOOL:     typeName = "bool";     break;
            case SCL_TYPE_BYTES:    typeName = "bytes";    break;
            case SCL_TYPE_DATE:     typeName = "date";     break;
            case SCL_TYPE_DATETIME: typeName = "datetime"; break;
            case SCL_TYPE_DURATION: typeName = "duration"; break;
            case SCL_TYPE_NULL:     typeName = "null";     break;
            case SCL_TYPE_LIST:     typeName = nullptr;    break;
            case SCL_TYPE_STRUCT:   typeName = nullptr;    break;
            case SCL_TYPE_MAP:      typeName = nullptr;    break;
            case SCL_TYPE_UNION:    typeName = nullptr;    break;
        }

        out << kv->key << ": ";
        if (typeName) {
            out << typeName;
        } else if (v->type == SCL_TYPE_LIST) {
            // infer element type from first element
            if (v->as.list.count > 0) {
                scl_value_t *first = v->as.list.items[0];
                const char *et = "string";
                if (first->type == SCL_TYPE_INT)         et = "int";
                else if (first->type == SCL_TYPE_UINT)   et = "uint";
                else if (first->type == SCL_TYPE_FLOAT)  et = "float";
                else if (first->type == SCL_TYPE_BOOL)   et = "bool";
                else if (first->type == SCL_TYPE_STRUCT) et = "struct open {}";
                else if (first->type == SCL_TYPE_MAP)    et = "struct open {}";
                out << "[" << et << "]";
            } else {
                out << "[string]";
            }
        } else {
            out << "struct";
        }
        out << " = ";
        sclSerializeValue(out, v, 0);
        out << "\n";
    }

    return makeStr(out.str());
}


static void jsonSerializeValue(std::ostringstream &out, scl_value_t *val,
                                int depth);

static void jsonIndent(std::ostringstream &out, int depth) {
    for (int i = 0; i < depth; i++) out << "    ";
}

static void jsonSerializeValue(std::ostringstream &out, scl_value_t *val,
                                int depth) {
    switch (val->type) {
        case SCL_TYPE_NULL:
            out << "null";
            break;
        case SCL_TYPE_BOOL:
            out << (val->as.b ? "true" : "false");
            break;
        case SCL_TYPE_INT:
            out << val->as.i;
            break;
        case SCL_TYPE_UINT:
            out << val->as.u;
            break;
        case SCL_TYPE_FLOAT:
            out << formatFloat(val->as.f);
            break;
        case SCL_TYPE_STRING:
            out << jsonEscapeString(val->as.str.ptr, val->as.str.len);
            break;
        case SCL_TYPE_DATE:
        case SCL_TYPE_DATETIME:
        case SCL_TYPE_DURATION:
            out << jsonEscapeString(val->as.str.ptr, val->as.str.len);
            break;
        case SCL_TYPE_BYTES: {
            std::string b64 = base64Encode(val->as.bytes.ptr, val->as.bytes.len);
            out << '"' << b64 << '"';
            break;
        }
        case SCL_TYPE_LIST: {
            out << "[\n";
            for (size_t i = 0; i < val->as.list.count; i++) {
                jsonIndent(out, depth + 1);
                jsonSerializeValue(out, val->as.list.items[i], depth + 1);
                if (i + 1 < val->as.list.count) out << ",";
                out << "\n";
            }
            jsonIndent(out, depth);
            out << "]";
            break;
        }
        case SCL_TYPE_STRUCT:
        case SCL_TYPE_MAP: {
            out << "{\n";
            for (SclKV *kv = val->as.kv.head; kv; kv = kv->next) {
                jsonIndent(out, depth + 1);
                out << '"' << kv->key << "\": ";
                jsonSerializeValue(out, kv->val, depth + 1);
                if (kv->next) out << ",";
                out << "\n";
            }
            jsonIndent(out, depth);
            out << "}";
            break;
        }
        case SCL_TYPE_UNION:
            // union: emit as null  no type info at value level
            out << "null";
            break;
    }
}

scl_str_t sclToJson(scl_doc_t *doc) {
    std::ostringstream out;
    out << "{\n";
    for (SclKV *kv = doc->root->as.kv.head; kv; kv = kv->next) {
        jsonIndent(out, 1);
        out << '"' << kv->key << "\": ";
        jsonSerializeValue(out, kv->val, 1);
        if (kv->next) out << ",";
        out << "\n";
    }
    out << "}\n";
    return makeStr(out.str());
}

static std::string tomlCheckType(scl_value_t *val) {
    if (val->type == SCL_TYPE_UNION)
        return "union type cannot be serialized to TOML";
    if (val->type == SCL_TYPE_BYTES)
        return "bytes type cannot be serialized to TOML";
    return "";
}

static std::string tomlSerializeScalar(std::ostringstream &out,
                                        scl_value_t *val) {
    std::string err = tomlCheckType(val);
    if (!err.empty()) return err;

    switch (val->type) {
        case SCL_TYPE_NULL:
            // TOML has no null  emit empty string as closest approximation
            out << "\"\"";
            break;
        case SCL_TYPE_BOOL:
            out << (val->as.b ? "true" : "false");
            break;
        case SCL_TYPE_INT:
            out << val->as.i;
            break;
        case SCL_TYPE_UINT:
            out << val->as.u;
            break;
        case SCL_TYPE_FLOAT:
            out << formatFloat(val->as.f);
            break;
        case SCL_TYPE_STRING:
            out << jsonEscapeString(val->as.str.ptr, val->as.str.len);
            break;
        case SCL_TYPE_DATE:
        case SCL_TYPE_DATETIME:
            // TOML supports ISO 8601 natively without quotes
            out.write(val->as.str.ptr, static_cast<std::streamsize>(val->as.str.len));
            break;
        case SCL_TYPE_DURATION:
            // no TOML native type  emit as string
            out << jsonEscapeString(val->as.str.ptr, val->as.str.len);
            break;
        case SCL_TYPE_BYTES:
        case SCL_TYPE_UNION:
            return tomlCheckType(val);
        default:
            break;
    }
    return "";
}

static bool tomlIsScalar(scl_value_t *val) {
    switch (val->type) {
        case SCL_TYPE_STRING:
        case SCL_TYPE_INT:
        case SCL_TYPE_UINT:
        case SCL_TYPE_FLOAT:
        case SCL_TYPE_BOOL:
        case SCL_TYPE_DATE:
        case SCL_TYPE_DATETIME:
        case SCL_TYPE_DURATION:
        case SCL_TYPE_NULL:
            return true;
        default:
            return false;
    }
}

static std::string tomlSerializeArray(std::ostringstream &out,
                                       scl_value_t *val) {
    out << "[";
    for (size_t i = 0; i < val->as.list.count; i++) {
        if (i > 0) out << ", ";
        scl_value_t *elem = val->as.list.items[i];
        std::string err = tomlSerializeScalar(out, elem);
        if (!err.empty()) return err;
    }
    out << "]";
    return "";
}

static std::string tomlSerializeTable(std::ostringstream &out,
                                       scl_value_t *val,
                                       const std::string &keyPath,
                                       std::ostringstream &tables) {
    // scalar fields first then nested tables
    for (SclKV *kv = val->as.kv.head; kv; kv = kv->next) {
        std::string err = tomlCheckType(kv->val);
        if (!err.empty()) return err;

        if (tomlIsScalar(kv->val)) {
            out << kv->key << " = ";
            err = tomlSerializeScalar(out, kv->val);
            if (!err.empty()) return err;
            out << "\n";
        } else if (kv->val->type == SCL_TYPE_LIST) {
            // check all elements are scalar
            bool allScalar = true;
            for (size_t i = 0; i < kv->val->as.list.count; i++) {
                if (!tomlIsScalar(kv->val->as.list.items[i])) {
                    allScalar = false;
                    break;
                }
            }
            if (!allScalar) {
                return std::string("nested array of tables not supported: ") + kv->key;
            }
            out << kv->key << " = ";
            err = tomlSerializeArray(out, kv->val);
            if (!err.empty()) return err;
            out << "\n";
        }
        // nested structmap deferred to tables
    }

    // nested structs as section
    for (SclKV *kv = val->as.kv.head; kv; kv = kv->next) {
        if (kv->val->type == SCL_TYPE_STRUCT || kv->val->type == SCL_TYPE_MAP) {
            std::string subPath = keyPath.empty()
                ? kv->key
                : keyPath + "." + kv->key;
            tables << "\n[" << subPath << "]\n";
            std::string err = tomlSerializeTable(tables, kv->val, subPath, tables);
            if (!err.empty()) return err;
        }
    }
    return "";
}

sclTomlResult sclToToml(scl_doc_t *doc) {
    std::ostringstream scalars;
    std::ostringstream tables;

    std::string err = tomlSerializeTable(scalars, doc->root, "", tables);
    if (!err.empty()) {
        sclTomlResult r;
        r.ok    = false;
        r.str   = {nullptr, 0};
        r.error = heapStr(err);
        return r;
    }

    std::string result = scalars.str() + tables.str();
    sclTomlResult r;
    r.ok    = true;
    r.str   = makeStr(result);
    r.error = nullptr;
    return r;
}
