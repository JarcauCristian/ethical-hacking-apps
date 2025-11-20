#include <array>
#include <cstdint>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <functional>
#include <random>
#include <string>
#include <vector>

namespace Inspect {

// --- Utilities copied from main.cpp to ensure behaviour parity ---

static inline uint8_t rotl8(uint8_t x, unsigned r) {
    return static_cast<uint8_t>((x << (r & 7)) | (x >> ((8 - r) & 7)));
}
static inline uint8_t rotr8(uint8_t x, unsigned r) {
    return static_cast<uint8_t>((x >> (r & 7)) | (x << ((8 - r) & 7)));
}
static const std::array<uint8_t, 256> SBOX = [] {
    std::array<uint8_t, 256> t{};
    uint8_t a = 0x63;
    for (size_t i = 0; i < 256; i++) {
        t[i] = a;
        a = static_cast<uint8_t>(a * 29u + 17u);
    }
    for (size_t i = 0; i < 256; i++) {
        t[i] = rotl8(static_cast<uint8_t>(t[i] ^ 0xA5u), i % 7);
    }
    return t;
}();

static inline uint8_t gmul(uint8_t a, uint8_t b) {
    uint8_t p = 0;
    for (int i = 0; i < 8; i++) {
        if (b & 1) p ^= a;
        uint8_t hi = static_cast<uint8_t>(a & 0x80);
        a <<= 1;
        if (hi) a ^= 0x1B;
        b >>= 1;
    }
    return p;
}

static std::mt19937_64 R0(0);
inline void reset_rng() { R0.seed(0); }
inline uint8_t r8() { return static_cast<uint8_t>(R0() & 0xFF); }
inline uint32_t r32() { return static_cast<uint32_t>(R0()); }

struct RngScope {
    std::mt19937_64 backup;
    explicit RngScope(const std::mt19937_64& next_state) : backup(R0) { R0 = next_state; }
    ~RngScope() { R0 = backup; }
};

void sx(uint8_t *b, size_t n, uint8_t k) {
    for (size_t i = 0; i < n; i++) {
        b[i] ^= static_cast<uint8_t>(k ^ r8() ^ (i & 0xFF));
    }
}

size_t b64d(const char *in, uint8_t *out, size_t on) {
    auto v = [](char c) -> int {
        if (c >= 'A' && c <= 'Z') return c - 'A';
        if (c >= 'a' && c <= 'z') return c - 'a' + 26;
        if (c >= '0' && c <= '9') return c - '0' + 52;
        if (c == '+') return 62;
        if (c == '/') return 63;
        return -1;
    };
    int buf = 0, bits = 0;
    size_t o = 0;
    for (size_t i = 0; in[i] && o < on; ++i) {
        int val = v(in[i]);
        if (val < 0) continue;
        buf = (buf << 6) | val;
        bits += 6;
        if (bits >= 8) {
            bits -= 8;
            out[o++] = static_cast<uint8_t>((buf >> bits) & 0xFF);
        }
    }
    return o;
}

std::string b64_plain(const char *blob) {
    uint8_t tmp[256];
    std::memset(tmp, 0, sizeof(tmp));
    size_t n = b64d(blob, tmp, sizeof(tmp));
    return std::string(reinterpret_cast<char *>(tmp), n);
}

std::string dt(const char *blob, uint8_t salt) {
    uint8_t tmp[128];
    std::memset(tmp, 0, sizeof(tmp));
    size_t n = b64d(blob, tmp, sizeof(tmp));
    sx(tmp, n, salt);
    std::string s(reinterpret_cast<char *>(tmp), n);
    while (!s.empty() && static_cast<unsigned char>(s.back()) < 0x20) {
        s.pop_back();
    }
    return s;
}

std::vector<uint8_t> k_verify(const uint8_t *in, size_t n) {
    std::vector<uint8_t> v(in, in + n);

    uint32_t l = 0xC0FFEE01u;
    for (size_t i = 0; i < n; ++i) {
        l = l * 1664525u + 1013904223u;
        uint8_t m = static_cast<uint8_t>((l >> ((i * 3) & 31)) ^ (l >> 24));
        v[i] ^= static_cast<uint8_t>(m + static_cast<uint8_t>(i));
    }

    uint8_t carry = 0x5A;
    for (size_t i = 0; i < n; ++i) {
        uint8_t x = static_cast<uint8_t>(v[i] ^ carry);
        if (i & 1) {
            x = rotl8(x, static_cast<unsigned>((i ^ carry) & 7));
        } else {
            x = rotr8(x, static_cast<unsigned>((i + carry) & 7));
        }
        carry = static_cast<uint8_t>(carry + x * 0x3D);
        v[i] = static_cast<uint8_t>(x ^ static_cast<uint8_t>((i * 0x77u) ^ (carry >> 1)));
    }

    for (size_t i = 0; i + 3 < n; i += 5) {
        std::swap(v[i], v[i + 3]);
        if (i + 5 < n) std::swap(v[i + 1], v[i + 2]);
    }

    for (size_t i = 0; i + 1 < n; i += 2) {
        uint8_t k1 = static_cast<uint8_t>(0xA3 ^ ((i * 0x1F) + v[i]));
        uint8_t k2 = static_cast<uint8_t>(0x7D ^ ((i * 0x2B) + v[i + 1]));
        uint8_t L = v[i];
        uint8_t R = v[i + 1];

        uint8_t F = SBOX[static_cast<uint8_t>(L ^ k1)];
        R ^= rotl8(static_cast<uint8_t>(gmul(F, 0xB1) ^ k1), (k1 & 7));
        std::swap(L, R);
        F = SBOX[static_cast<uint8_t>(L ^ k2)];
        R ^= rotr8(static_cast<uint8_t>(gmul(F, 0x5D) ^ k2), (k2 & 7));
        std::swap(L, R);

        v[i] = L;
        v[i + 1] = R;
    }

    for (size_t i = 0; i + 3 < n; i += 4) {
        uint8_t a = v[i], b = v[i + 1], c = v[i + 2], d = v[i + 3];
        uint8_t a2 = static_cast<uint8_t>(gmul(a, 2) ^ gmul(b, 3) ^ c ^ d);
        uint8_t b2 = static_cast<uint8_t>(a ^ gmul(b, 2) ^ gmul(c, 3) ^ d);
        uint8_t c2 = static_cast<uint8_t>(a ^ b ^ gmul(c, 2) ^ gmul(d, 3));
        uint8_t d2 = static_cast<uint8_t>(gmul(a, 3) ^ b ^ c ^ gmul(d, 2));
        v[i] = a2;
        v[i + 1] = b2;
        v[i + 2] = c2;
        v[i + 3] = d2;
    }

    for (size_t i = 0; i < n; ++i) {
        v[i] = static_cast<uint8_t>(SBOX[v[i]] ^ static_cast<uint8_t>((0x55 + i * 13) & 0xFF));
    }
    return v;
}

// --- Introspection Helpers ---

constexpr std::array<const char *, 5> KEYWORD_IDS = {"U1", "U2", "U3", "U4", "U5"};
constexpr std::array<const char *, 5> KEYWORD_DATA = {"U1RBS0s=", "SEVBUA==", "UkVU", "UVVJVA==", "QVNN"};
constexpr std::array<const char *, 6> RESPONSE_IDS = {"A1", "A2", "A3", "A4", "A5", "A6"};
constexpr std::array<const char *, 6> RESPONSE_DATA = {
    "UkVBRFk6U1RBQ0sK", "UkVBRFk6SEVBUEoK", "UkVBRFk6UkVUCg==",
    "QllFCg==",         "VU5LTk9XTgo=",     "UkVBRFk6QVNNCg=="};

struct Context {
    std::array<std::string, 5> keywords{};
    std::array<std::string, 6> responses{};
    std::mt19937_64 post_setup_rng{};
};

Context build_context() {
    reset_rng();
    Context ctx;
    for (size_t i = 0; i < ctx.keywords.size(); ++i) {
        ctx.keywords[i] = dt(KEYWORD_DATA[i], 0x5A);
    }
    for (size_t i = 0; i < ctx.responses.size(); ++i) {
        ctx.responses[i] = dt(RESPONSE_DATA[i], 0xA5);
    }
    ctx.post_setup_rng = R0;
    return ctx;
}

std::string printable(const std::string& s) {
    std::string out = s;
    for (char &c : out) {
        unsigned char uc = static_cast<unsigned char>(c);
        if (uc < 0x20 || uc > 0x7E) c = '.';
    }
    return out;
}

void dump_bytes(const std::string& label, const std::string& s) {
    std::cout << label << " (hex): ";
    for (unsigned char c : s) {
        std::cout << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(c) << ' ';
    }
    std::cout << std::dec << "\n" << label << " (printable): \"" << printable(s) << "\"\n";
}

void print_decoded_strings(const Context& ctx) {
    std::cout << "[+] Keyword routing strings (plain Base64 vs dt() output)\n";
    for (size_t i = 0; i < KEYWORD_IDS.size(); ++i) {
        std::string plain = b64_plain(KEYWORD_DATA[i]);
        while (!plain.empty() && plain.back() <= 0x20) plain.pop_back();
        std::cout << "  " << KEYWORD_IDS[i] << " -> plain:\""
                  << plain << "\" | dt():\"" << printable(ctx.keywords[i]) << "\"\n";
    }
    std::cout << "\n[+] Response banners (plain vs dt())\n";
    for (size_t i = 0; i < RESPONSE_IDS.size(); ++i) {
        std::string plain = b64_plain(RESPONSE_DATA[i]);
        while (!plain.empty() && plain.back() <= 0x20) plain.pop_back();
        std::cout << "  " << RESPONSE_IDS[i] << " -> plain:\""
                  << plain << "\" | dt():\"" << printable(ctx.responses[i]) << "\"\n";
    }
    std::cout << '\n';
}

void print_handler_summary() {
    std::cout << "[+] Handler overview & guaranteed bugs\n";
    std::cout << "  F_a (keyword STACK): copies up to 511 bytes into 48-byte stack buffer via strcpy -> certain stack overflow.\n";
    std::cout << "  F_b (keyword HEAP): memcpy into 24-byte heap buffer -> heap overflow + UAF primitives.\n";
    std::cout << "  F_c (keyword RET): strcpy into 32-byte stack buffer -> stack overflow.\n";
    std::cout << "  F_d (keyword ASM): rep movsb into 40-byte stack buffer -> controllable overwrite.\n";
    std::cout << "  maintenance(): calls /bin/sh through system() with zero auth -> built-in RCE backdoor.\n\n";
}

void print_api_blob() {
    std::cout << "[+] Embedded \"pi / pika\" blob (human readable):\n";
    const unsigned char k[] = {
        0x70,0x69,0x20,0x70,0x69,0x20,0x70,0x69,0x20,0x70,0x69,0x20,0x70,0x69,0x20,
        0x70,0x69,0x20,0x70,0x69,0x20,0x70,0x69,0x20,0x70,0x69,0x20,0x70,0x69,0x20,
        0x70,0x69,0x6B,0x61,0x20,0x70,0x69,0x70,0x69,0x20,0x70,0x69,0x20,0x70,0x69,
        0x70,0x69,0x20,0x70,0x69,0x20,0x70,0x69,0x20,0x70,0x69,0x20,0x70,0x69,0x20,
        0x70,0x69,0x70,0x69,0x20,0x70,0x69,0x20,0x70,0x69,0x20,0x70,0x69,0x20,0x70,
        0x69,0x20,0x70,0x69,0x20,0x70,0x69,0x20,0x70,0x69,0x20,0x70,0x69,0x20,0x70,
        0x69,0x63,0x68,0x75,0x20,0x70,0x69,0x63,0x68,0x75,0x20,0x70,0x69,0x63,0x68,
        0x75,0x20,0x70,0x69,0x63,0x68,0x75,0x20,0x6B,0x61,0x20,0x63,0x68,0x75,0x20,
        0x70,0x69,0x70,0x69,0x20,0x70,0x69,0x70,0x69,0x20,0x6B,0x61,0x20,0x6B,0x61,
        0x20,0x6B,0x61,0x20,0x6B,0x61,0x20,0x6B,0x61,0x20,0x70,0x69,0x6B,0x61,0x63,
        0x68,0x75,0x20,0x70,0x69,0x70,0x69,0x20,0x70,0x69,0x20,0x70,0x69,0x20,0x70,
        0x69,0x20,0x70,0x69,0x20,0x70,0x69,0x20,0x70,0x69,0x20,0x70,0x69,0x20,0x70,
        0x69,0x20,0x70,0x69,0x20,0x70,0x69,0x6B,0x61,0x63,0x68,0x75,0x20,0x6B,0x61,
        0x20,0x6B,0x61,0x20,0x6B,0x61,0x20,0x6B,0x61,0x20,0x6B,0x61,0x20,0x6B,
        0x61,0x20,0x6B,0x61,0x20,0x6B,0x61,0x20,0x6B,0x61,0x20,0x6B,0x61,0x20,0x6B,
        0x61,0x20,0x70,0x69,0x6B,0x61,0x63,0x68,0x75,0x20,0x70,0x69,0x20,0x70,0x69,
        0x20,0x70,0x69,0x20,0x70,0x69,0x20,0x70,0x69,0x6B,0x61,0x63,0x68,0x75,0x20,
        0x70,0x69,0x63,0x68,0x75,0x20,0x70,0x69,0x63,0x68,0x75,0x20,0x70,0x69,0x6B,
        0x61,0x63,0x68,0x75,0x20,0x70,0x69,0x70,0x69,0x20,0x70,0x69,0x70,0x69,0x20,
        0x6B,0x61,0x20,0x6B,0x61,0x20,0x6B,0x61,0x20,0x6B,0x61,0x20,0x6B,0x61,0x20,
        0x6B,0x61,0x20,0x6B,0x61,0x20,0x6B,0x61,0x20,0x6B,0x61,0x20,0x6B,0x61,0x20,
        0x6B,0x61,0x20,0x70,0x69,0x6B,0x61,0x63,0x68,0x75,0x20,0x70,0x69,0x20,0x70,
        0x69,0x20,0x70,0x69,0x20,0x70,0x69,0x20,0x70,0x69,0x20,0x70,0x69,0x20,0x70,
        0x69,0x20,0x70,0x69,0x20,0x70,0x69,0x6B,0x61,0x63,0x68,0x75,0x20,0x70,0x69,
        0x20,0x70,0x69,0x20,0x70,0x69,0x20,0x70,0x69,0x20,0x70,0x69,0x6B,0x61,0x63,
        0x68,0x75,0x20,0x70,0x69,0x63,0x68,0x75,0x20,0x70,0x69,0x63,0x68,0x75,0x20,
        0x70,0x69,0x6B,0x61,0x63,0x68,0x75,0x20,0x70,0x69,0x70,0x69,0x20,0x70,0x69,
        0x70,0x69,0x20,0x6B,0x61,0x20,0x6B,0x61,0x20,0x6B,0x61,0x20,0x6B,0x61,0x20,
        0x6B,0x61,0x20,0x6B,0x61,0x20,0x6B,0x61,0x20,0x6B,0x61,0x20,0x6B,0x61,0x20,
        0x6B,0x61,0x20,0x6B,0x61,0x20,0x70,0x69,0x6B,0x61,0x63,0x68,0x75,0x20,0x70,
        0x69,0x63,0x68,0x75,0x20,0x70,0x69,0x63,0x68,0x75,0x20,0x70,0x69,0x6B,0x61,
        0x63,0x68,0x75,0x00};

    std::cout.write(reinterpret_cast<const char *>(k), sizeof(k) - 1);
    std::cout << "\n\n[+] Same blob after k_verify() (hex dump):\n";
    auto transformed = k_verify(k, sizeof(k) - 1);
    for (size_t i = 0; i < transformed.size(); ++i) {
        std::cout << std::hex << std::setw(2) << std::setfill('0')
                  << static_cast<int>(transformed[i]) << ((i + 1) % 16 ? ' ' : '\n');
    }
    if (transformed.size() % 16) std::cout << '\n';
    std::cout << std::dec << '\n';
}

void print_protocol_notes() {
    std::cout << "[+] Protocol flow summary\n";
    std::cout << "  * Service listens on TCP 4444 and expects one keyword line.\n";
    std::cout << "  * Keywords above unlock handlers F_a–F_d or BYE/UNKNOWN branches.\n";
    std::cout << "  * Equality check mixes both strings with the same mt19937 output, so plain keywords always match.\n";
    std::cout << "  * After handling a client, the program keeps the /bin/sh pointer alive (maintenance) for easy exploitation.\n\n";
}

void print_slurp_details() {
    std::cout << "[+] slurp() XOR dance\n";
    std::cout << "  The function reads byte-by-byte, then XORs the buffer twice with streams derived from (0x5A ^ r8()).\n";
    std::cout << "  Each pass consumes new PRNG output, so the net effect is input ^ mask1 ^ mask2. Knowing both masks is required to recover the original bytes.\n\n";
}

struct SlurpTrace {
    std::string transformed;
    std::vector<uint8_t> mask_first;
    std::vector<uint8_t> mask_second;
    std::mt19937_64 post_rng;
};

SlurpTrace run_slurp_trace(const Context& ctx, const std::string& user_input) {
    RngScope scope(ctx.post_setup_rng);
    std::string buf = user_input;
    if (buf.empty() || buf.back() != '\n') buf.push_back('\n');
    size_t i = buf.size();
    std::vector<uint8_t> first(i);
    std::vector<uint8_t> second(i);
    for (size_t j = 0; j < i; ++j) {
        first[j] = static_cast<uint8_t>(0x5A ^ r8());
        buf[j] ^= static_cast<char>(first[j]);
    }
    for (size_t j = 0; j < i; ++j) {
        second[j] = static_cast<uint8_t>(0x5A ^ r8());
        buf[j] ^= static_cast<char>(second[j]);
    }
    size_t m = i;
    while (m > 0 && (buf[m - 1] == '\n' || buf[m - 1] == '\r')) {
        buf[--m] = 0;
    }
    SlurpTrace trace;
    trace.transformed.assign(buf.data(), buf.data() + m);
    trace.mask_first = std::move(first);
    trace.mask_second = std::move(second);
    trace.post_rng = R0;
    return trace;
}

uint32_t poly_hash(const std::string& s) {
    uint32_t h = 0;
    for (unsigned char c : s) {
        h = h * 31u + c;
    }
    return h;
}

struct EqTrace {
    std::string branch;
    uint32_t key_hash{};
    uint32_t input_hash{};
    uint32_t rand_a{};
    uint32_t rand_b{};
    bool match{};
};

std::vector<EqTrace> run_eq_trace(const Context& ctx, const std::string& mutated,
                                  const std::mt19937_64& start_rng) {
    RngScope scope(start_rng);
    static const std::array<size_t, 5> order = {0, 1, 2, 4, 3};  // K1,K2,K3,K5,K4
    static const std::array<const char *, 5> branch_names = {"STACK/F_a", "HEAP/F_b", "RET/F_c",
                                                            "ASM/F_d", "QUIT"};
    uint32_t input_hash = poly_hash(mutated);
    std::vector<EqTrace> traces;
    for (size_t idx = 0; idx < order.size(); ++idx) {
        size_t key_index = order[idx];
        EqTrace t;
        t.branch = branch_names[idx];
        t.key_hash = poly_hash(ctx.keywords[key_index]);
        t.input_hash = input_hash;
        t.rand_a = r32();
        t.rand_b = r32();
        uint32_t left = t.key_hash ^ t.rand_a;
        uint32_t right = t.input_hash ^ t.rand_b;
        t.match = (left == right);
        traces.push_back(t);
        if (t.match) break;
    }
    return traces;
}

void print_slurp_demo(const Context& ctx, const std::string& user_input) {
    std::cout << "[+] Simulating client input \"" << user_input << "\" (newline terminated)\n";
    auto slurp = run_slurp_trace(ctx, user_input + "\n");
    dump_bytes("  transformed buffer", slurp.transformed);
    std::cout << "  keystream pass #1: ";
    for (size_t i = 0; i < slurp.transformed.size(); ++i) {
        std::cout << std::hex << std::setw(2) << std::setfill('0')
                  << static_cast<int>(slurp.mask_first[i]) << ' ';
    }
    std::cout << "\n  keystream pass #2: ";
    for (size_t i = 0; i < slurp.transformed.size(); ++i) {
        std::cout << std::hex << std::setw(2) << std::setfill('0')
                  << static_cast<int>(slurp.mask_second[i]) << ' ';
    }
    std::cout << "\n  combined mask     : ";
    for (size_t i = 0; i < slurp.transformed.size(); ++i) {
        uint8_t combo = slurp.mask_first[i] ^ slurp.mask_second[i];
        std::cout << std::hex << std::setw(2) << std::setfill('0')
                  << static_cast<int>(combo) << ' ';
    }
    std::cout << std::dec << "\n\n";

    auto eq_traces = run_eq_trace(ctx, slurp.transformed, slurp.post_rng);
    std::cout << "  eq() trace (key_hash ↔ input_hash):\n";
    for (const auto& t : eq_traces) {
        std::cout << "    [" << t.branch << "] key_hash=0x" << std::hex << t.key_hash
                  << " input_hash=0x" << t.input_hash << " randA=0x" << t.rand_a
                  << " randB=0x" << t.rand_b << " => match=" << std::boolalpha << t.match
                  << std::noboolalpha << std::dec << '\n';
    }
    std::cout << '\n';
}

}  // namespace Inspect

int main() {
    using namespace Inspect;
    std::cout << "=== debug_inspector :: full verbosity walkthrough ===\n\n";
    Context ctx = build_context();
    print_decoded_strings(ctx);
    print_protocol_notes();
    print_handler_summary();
    print_slurp_details();
    print_slurp_demo(ctx, "STAKK");
    print_api_blob();
    std::cout << "[+] Done. Use this output as a reference while auditing main.cpp.\n";
    return 0;
}
