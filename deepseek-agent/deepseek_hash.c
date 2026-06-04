#include <stdint.h>
#include <string.h>
#include <stddef.h>
#include <stdio.h>

#define PLEN 136
#define OLEN 32

void deepseek_hash_v1(const unsigned char *input, size_t input_len,
                       unsigned char output[OLEN]);

static const uint64_t RC[24] = {
    0x0000000000000001ULL, 0x0000000000008082ULL,
    0x800000000000808aULL, 0x8000000080008000ULL,
    0x000000000000808bULL, 0x0000000080000001ULL,
    0x8000000080008081ULL, 0x8000000000008009ULL,
    0x000000000000008aULL, 0x0000000000000088ULL,
    0x0000000080008009ULL, 0x000000008000000aULL,
    0x000000008000808bULL, 0x800000000000008bULL,
    0x8000000000008089ULL, 0x8000000000008003ULL,
    0x8000000000008002ULL, 0x8000000000000080ULL,
    0x000000000000800aULL, 0x800000008000000aULL,
    0x8000000080008081ULL, 0x8000000000008080ULL,
    0x0000000080000001ULL, 0x8000000080008008ULL
};

static inline uint64_t rotl64(uint64_t x, int n) {
    return (x << n) | (x >> (64 - n));
}

static void keccak_f1600_skip_round0(uint64_t s[25]) {
    uint64_t a0, a1, a2, a3, a4, a5, a6, a7, a8, a9;
    uint64_t a10, a11, a12, a13, a14, a15, a16, a17, a18, a19;
    uint64_t a20, a21, a22, a23, a24;

    a0 = s[0];  a1 = s[1];  a2 = s[2];  a3 = s[3];  a4 = s[4];
    a5 = s[5];  a6 = s[6];  a7 = s[7];  a8 = s[8];  a9 = s[9];
    a10 = s[10]; a11 = s[11]; a12 = s[12]; a13 = s[13]; a14 = s[14];
    a15 = s[15]; a16 = s[16]; a17 = s[17]; a18 = s[18]; a19 = s[19];
    a20 = s[20]; a21 = s[21]; a22 = s[22]; a23 = s[23]; a24 = s[24];

    for (int r = 1; r < 24; r++) {
        uint64_t c0 = a0 ^ a5 ^ a10 ^ a15 ^ a20;
        uint64_t c1 = a1 ^ a6 ^ a11 ^ a16 ^ a21;
        uint64_t c2 = a2 ^ a7 ^ a12 ^ a17 ^ a22;
        uint64_t c3 = a3 ^ a8 ^ a13 ^ a18 ^ a23;
        uint64_t c4 = a4 ^ a9 ^ a14 ^ a19 ^ a24;

        uint64_t d0 = c4 ^ rotl64(c1, 1);
        uint64_t d1 = c0 ^ rotl64(c2, 1);
        uint64_t d2 = c1 ^ rotl64(c3, 1);
        uint64_t d3 = c2 ^ rotl64(c4, 1);
        uint64_t d4 = c3 ^ rotl64(c0, 1);

        a0 ^= d0;  a5 ^= d0;  a10 ^= d0;  a15 ^= d0;  a20 ^= d0;
        a1 ^= d1;  a6 ^= d1;  a11 ^= d1;  a16 ^= d1;  a21 ^= d1;
        a2 ^= d2;  a7 ^= d2;  a12 ^= d2;  a17 ^= d2;  a22 ^= d2;
        a3 ^= d3;  a8 ^= d3;  a13 ^= d3;  a18 ^= d3;  a23 ^= d3;
        a4 ^= d4;  a9 ^= d4;  a14 ^= d4;  a19 ^= d4;  a24 ^= d4;

        uint64_t b0  = a0;
        uint64_t b10 = rotl64(a1, 1);
        uint64_t b20 = rotl64(a2, 62);
        uint64_t b5  = rotl64(a3, 28);
        uint64_t b15 = rotl64(a4, 27);
        uint64_t b16 = rotl64(a5, 36);
        uint64_t b1  = rotl64(a6, 44);
        uint64_t b11 = rotl64(a7, 6);
        uint64_t b21 = rotl64(a8, 55);
        uint64_t b6  = rotl64(a9, 20);
        uint64_t b7  = rotl64(a10, 3);
        uint64_t b17 = rotl64(a11, 10);
        uint64_t b2  = rotl64(a12, 43);
        uint64_t b12 = rotl64(a13, 25);
        uint64_t b22 = rotl64(a14, 39);
        uint64_t b23 = rotl64(a15, 41);
        uint64_t b8  = rotl64(a16, 45);
        uint64_t b18 = rotl64(a17, 15);
        uint64_t b3  = rotl64(a18, 21);
        uint64_t b13 = rotl64(a19, 8);
        uint64_t b14 = rotl64(a20, 18);
        uint64_t b24 = rotl64(a21, 2);
        uint64_t b9  = rotl64(a22, 61);
        uint64_t b19 = rotl64(a23, 56);
        uint64_t b4  = rotl64(a24, 14);

        a0 = b0 ^ (~b1 & b2);
        a1 = b1 ^ (~b2 & b3);
        a2 = b2 ^ (~b3 & b4);
        a3 = b3 ^ (~b4 & b0);
        a4 = b4 ^ (~b0 & b1);
        a5 = b5 ^ (~b6 & b7);
        a6 = b6 ^ (~b7 & b8);
        a7 = b7 ^ (~b8 & b9);
        a8 = b8 ^ (~b9 & b5);
        a9 = b9 ^ (~b5 & b6);
        a10 = b10 ^ (~b11 & b12);
        a11 = b11 ^ (~b12 & b13);
        a12 = b12 ^ (~b13 & b14);
        a13 = b13 ^ (~b14 & b10);
        a14 = b14 ^ (~b10 & b11);
        a15 = b15 ^ (~b16 & b17);
        a16 = b16 ^ (~b17 & b18);
        a17 = b17 ^ (~b18 & b19);
        a18 = b18 ^ (~b19 & b15);
        a19 = b19 ^ (~b15 & b16);
        a20 = b20 ^ (~b21 & b22);
        a21 = b21 ^ (~b22 & b23);
        a22 = b22 ^ (~b23 & b24);
        a23 = b23 ^ (~b24 & b20);
        a24 = b24 ^ (~b20 & b21);

        a0 ^= RC[r];
    }

    s[0]=a0;  s[1]=a1;  s[2]=a2;  s[3]=a3;  s[4]=a4;
    s[5]=a5;  s[6]=a6;  s[7]=a7;  s[8]=a8;  s[9]=a9;
    s[10]=a10; s[11]=a11; s[12]=a12; s[13]=a13; s[14]=a14;
    s[15]=a15; s[16]=a16; s[17]=a17; s[18]=a18; s[19]=a19;
    s[20]=a20; s[21]=a21; s[22]=a22; s[23]=a23; s[24]=a24;
}

void deepseek_hash_v1(const unsigned char *input, size_t input_len,
                       unsigned char output[OLEN]) {
    uint64_t state[25] = {0};
    int i;

    size_t off = 0;
    while (off + PLEN <= input_len) {
        for (i = 0; i < PLEN / 8; i++) {
            uint64_t v = 0;
            for (int j = 0; j < 8; j++)
                v |= (uint64_t)input[off + i*8 + j] << (8 * j);
            state[i] ^= v;
        }
        keccak_f1600_skip_round0(state);
        off += PLEN;
    }

    unsigned char final[PLEN] = {0};
    size_t rem = input_len - off;
    memcpy(final, input + off, rem);
    final[rem] = 0x06;
    final[PLEN - 1] |= 0x80;

    for (i = 0; i < PLEN / 8; i++) {
        uint64_t v = 0;
        for (int j = 0; j < 8; j++)
            v |= (uint64_t)final[i*8 + j] << (8 * j);
        state[i] ^= v;
    }
    keccak_f1600_skip_round0(state);

    for (i = 0; i < OLEN / 8; i++) {
        uint64_t v = state[i];
        for (int j = 0; j < 8; j++)
            output[i*8 + j] = (v >> (8 * j)) & 0xFF;
    }
}

int solve_pow(const char *challenge_hex, const char *prefix,
               double difficulty, double *answer) {
    unsigned char chal_bytes[OLEN];
    unsigned char hash[OLEN];

    for (int i = 0; i < OLEN; i++) {
        int hi = challenge_hex[2*i];
        int lo = challenge_hex[2*i+1];
        chal_bytes[i] = ((hi >= 'a' ? hi - 'a' + 10 : hi - '0') << 4)
                      | (lo >= 'a' ? lo - 'a' + 10 : lo - '0');
    }

    int diff = (int)difficulty;
    char input[512];
    size_t plen = strlen(prefix);
    memcpy(input, prefix, plen);

    for (int nonce = 0; nonce < diff; nonce++) {
        int nlen = sprintf(input + plen, "%d", nonce);
        deepseek_hash_v1((unsigned char*)input, plen + nlen, hash);
        if (memcmp(hash, chal_bytes, OLEN) == 0) {
            *answer = (double)nonce;
            return 1;
        }
    }
    return 0;
}

