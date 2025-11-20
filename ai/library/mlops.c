#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdint.h>
#include <limits.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/utsname.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Helper: safe multiply check */
static int mul_size_safe(size_t a, size_t b, size_t *out) {
    if (b != 0 && a > SIZE_MAX / b) return 0;
    *out = a * b;
    return 1;
}

/* Helper: validate basepath (no absolute, no "..", no backslashes, reasonable length) */
static int validate_basepath(const char *basepath) {
    if (!basepath) return 0;
    size_t len = strnlen(basepath, PATH_MAX);
    if (len == 0 || len >= PATH_MAX) return 0;
    if (basepath[0] == '/' || basepath[0] == '\\') return 0; /* disallow absolute paths */
    if (strstr(basepath, "..") != NULL) return 0; /* disallow traversal */
    if (strchr(basepath, '\n') || strchr(basepath, '\r')) return 0;
    if (strchr(basepath, '\\')) return 0;
    return 1;
}

void matmul(const double *A, const double *B, double *C,
                 size_t m, size_t k, size_t n) {
    if (!A || !B || !C) return;
    if (m == 0 || k == 0 || n == 0) return;
    for (size_t i = 0; i < m; ++i) {
        for (size_t j = 0; j < n; ++j) {
            double acc = 0.0;
            for (size_t p = 0; p < k; ++p) {
                acc += A[i * k + p] * B[p * n + j];
            }
            C[i * n + j] = acc;
        }
    }
}

void relu_inplace(double *x, size_t n) {
    if (!x) return;
    for (size_t i = 0; i < n; ++i) {
        double v = x[i];
        x[i] = (v > 0.0) ? v : 0.0;
    }
}

/* softmax -> out buffer with capacity to avoid fixed-buffer overflow */
void softmax_to_fixedbuf(const double *x, size_t n, char *out, size_t out_cap) {
    if (!x || !out || out_cap == 0) return;
    double maxv = x[0];
    for (size_t i = 1; i < n; ++i) if (x[i] > maxv) maxv = x[i];
    double sum = 0.0;
    double *tmp = (double*) malloc(n * sizeof(double));
    if (!tmp) {
        out[0] = '\0';
        return;
    }
    for (size_t i = 0; i < n; ++i) {
        tmp[i] = exp(x[i] - maxv);
        sum += tmp[i];
    }
    if (sum == 0.0) sum = 1.0;
    for (size_t i = 0; i < n; ++i) {
        tmp[i] /= sum;
    }
    /* Safely write into out using snprintf and tracking remaining capacity */
    size_t used = 0;
    if (out_cap > 0) out[0] = '\0';
    for (size_t i = 0; i < n; ++i) {
        int r = snprintf(out + used, (used < out_cap) ? (out_cap - used) : 0, "p[%zu]=%.6g ", i, tmp[i]);
        if (r < 0) break;
        /* r does not include trailing NUL; but snprintf returns required/printed length */
        size_t to_add = (size_t) r;
        if (used + to_add >= out_cap) {
            /* truncated, ensure NUL termination */
            if (out_cap > 0) out[out_cap - 1] = '\0';
            break;
        }
        used += to_add;
    }
    free(tmp);
}

/* Atomic save with validations and overflow checks */
int save_model_raw(const char *basepath, const double *weights, int count) {
    if (!validate_basepath(basepath) || !weights || count <= 0) return -1;

    /* ensure multiplication safe */
    size_t need_bytes;
    if (!mul_size_safe((size_t)count, sizeof(double), &need_bytes)) return -2;

    char fname[PATH_MAX];
    char tmpname[PATH_MAX];
    if (snprintf(fname, sizeof(fname), "%s/model.weights.bin", basepath) >= (int)sizeof(fname)) return -3;
    if (snprintf(tmpname, sizeof(tmpname), "%s/.model.weights.bin.tmp", basepath) >= (int)sizeof(tmpname)) return -3;

    /* open temp file atomically; disallow following symlinks */
#ifdef O_NOFOLLOW
    int fd = open(tmpname, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, S_IRUSR | S_IWUSR);
#else
    int fd = open(tmpname, O_WRONLY | O_CREAT | O_EXCL, S_IRUSR | S_IWUSR);
#endif
    if (fd < 0) return -4;

    /* write count (int) first */
    ssize_t written;
    const char *ptr = (const char*)&count;
    ssize_t to_write = (ssize_t)sizeof(int);
    while (to_write > 0) {
        written = write(fd, ptr, (size_t)to_write);
        if (written <= 0) {
            close(fd);
            unlink(tmpname);
            return -5;
        }
        to_write -= written;
        ptr += written;
    }

    /* write weights */
    const char *wptr = (const char*)weights;
    ssize_t remaining = (ssize_t)need_bytes;
    while (remaining > 0) {
        written = write(fd, wptr, (size_t)remaining);
        if (written <= 0) {
            close(fd);
            unlink(tmpname);
            return -6;
        }
        remaining -= written;
        wptr += written;
    }

    /* flush to disk */
    fsync(fd);
    close(fd);

    /* atomically rename */
    if (rename(tmpname, fname) != 0) {
        unlink(tmpname);
        return -7;
    }
    return 0;
}

/* Safe load with validations, overflow checks, O_NOFOLLOW and proper reads */
double* load_model_raw(const char *basepath, int *out_count) {
    if (out_count) *out_count = 0;
    if (!validate_basepath(basepath) || !out_count) return NULL;

    char fname[PATH_MAX];
    if (snprintf(fname, sizeof(fname), "%s/model.weights.bin", basepath) >= (int)sizeof(fname)) return NULL;

#ifdef O_NOFOLLOW
    int fd = open(fname, O_RDONLY | O_NOFOLLOW);
#else
    int fd = open(fname, O_RDONLY);
#endif
    if (fd < 0) return NULL;

    struct stat st;
    if (fstat(fd, &st) != 0) { close(fd); return NULL; }
    if (!S_ISREG(st.st_mode)) { close(fd); return NULL; }

    /* read count */
    int count = 0;
    ssize_t r;
    char *bufp = (char*)&count;
    ssize_t to_read = (ssize_t)sizeof(int);
    while (to_read > 0) {
        r = read(fd, bufp, (size_t)to_read);
        if (r <= 0) { close(fd); return NULL; }
        to_read -= r;
        bufp += r;
    }
    if (count <= 0) { close(fd); return NULL; }

    size_t need_bytes;
    if (!mul_size_safe((size_t)count, sizeof(double), &need_bytes)) { close(fd); return NULL; }

    double *buf = (double*) malloc(need_bytes);
    if (!buf) { close(fd); return NULL; }

    char *w = (char*)buf;
    ssize_t remaining = (ssize_t)need_bytes;
    while (remaining > 0) {
        r = read(fd, w, (size_t)remaining);
        if (r <= 0) {
            /* partial read: set out_count to number of doubles read (if any) */
            ssize_t read_bytes = (ssize_t)need_bytes - remaining;
            close(fd);
            if (read_bytes <= 0) { free(buf); return NULL; }
            int got = (int)(read_bytes / sizeof(double));
            *out_count = got;
            return buf;
        }
        remaining -= r;
        w += r;
    }

    close(fd);
    *out_count = count;
    return buf;
}

void c_free_model(void *p) {
    if (!p) return;
    free(p);
}

void copy_weights(int count, const double *src, double *dst) {
    if (!src || !dst) return;
    if (count <= 0) return;
    size_t n = (size_t) count;
    /* check overflow for memcpy size */
    size_t bytes;
    if (!mul_size_safe(n, sizeof(double), &bytes)) return;
    memcpy(dst, src, bytes);
}

double* alloc_weights(int count) {
    if (count <= 0) return NULL;
    size_t bytes;
    if (!mul_size_safe((size_t)count, sizeof(double), &bytes)) return NULL;
    double *p = (double*) malloc(bytes);
    return p;
}

/* Remove popen() usage. Provide safe system info using uname(). Caller must free return value via c_free_model(). */
char* get_system_info() {
    struct utsname u;
    if (uname(&u) != 0) {
        char *s = (char*)malloc(32);
        if (s) snprintf(s, 32, "uname failed: %d", errno);
        return s;
    }
    /* construct a small string */
    size_t need = strlen(u.sysname) + strlen(u.nodename) + strlen(u.release) + strlen(u.version) + strlen(u.machine) + 32;
    char *out = (char*) malloc(need);
    if (!out) return NULL;
    snprintf(out, need, "%s %s %s %s %s", u.sysname, u.nodename, u.release, u.version, u.machine);
    return out;
}

/* Avoid running external untrusted binaries. Try to read NVIDIA driver version file if available, otherwise return informative string. */
char* get_gpu_info() {
    const char *pfile = "/proc/driver/nvidia/version";
    FILE *f = fopen(pfile, "r");
    if (!f) {
        char *out = (char*) malloc(64);
        if (!out) return NULL;
        snprintf(out, 64, "nvidia info unavailable");
        return out;
    }
    char line[256];
    if (!fgets(line, sizeof(line), f)) {
        fclose(f);
        char *out = (char*) malloc(64);
        if (!out) return NULL;
        snprintf(out, 64, "nvidia info empty");
        return out;
    }
    fclose(f);
    size_t len = strnlen(line, sizeof(line));
    char *out = (char*) malloc(len + 1);
    if (!out) return NULL;
    memcpy(out, line, len);
    out[len] = '\0';
    return out;
}

#ifdef __cplusplus
} // extern "C"
#endif
