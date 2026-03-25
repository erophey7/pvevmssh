// filename: agent_linux.x86_64.c
// os: linux
// arch: x86_64
// compile: gcc -static -nostdlib -ffreestanding -Os -s -o agent agent/agent_linux.x86_64.c


typedef unsigned long size_t;
typedef long ssize_t;

#define SYS_write 1
#define SYS_read  0
#define SYS_open  2
#define SYS_close 3
#define SYS_ioctl 16
#define SYS_exit  60

#define O_RDWR 2
#define TIOCSWINSZ 0x5414

struct winsize {
    unsigned short ws_row;
    unsigned short ws_col;
    unsigned short ws_xpixel;
    unsigned short ws_ypixel;
};

static long syscall0(long n) {
    long ret;
    __asm__ volatile ("syscall" : "=a"(ret) : "a"(n) : "rcx", "r11", "memory");
    return ret;
}
static long syscall1(long n, long arg1) {
    long ret;
    __asm__ volatile ("syscall" : "=a"(ret) : "a"(n), "D"(arg1) : "rcx", "r11", "memory");
    return ret;
}
static long syscall2(long n, long arg1, long arg2) {
    long ret;
    __asm__ volatile ("syscall" : "=a"(ret) : "a"(n), "D"(arg1), "S"(arg2) : "rcx", "r11", "memory");
    return ret;
}
static long syscall3(long n, long arg1, long arg2, long arg3) {
    long ret;
    __asm__ volatile ("syscall" : "=a"(ret) : "a"(n), "D"(arg1), "S"(arg2), "d"(arg3) : "rcx", "r11", "memory");
    return ret;
}

static ssize_t sys_write(int fd, const void *buf, size_t count) {
    return syscall3(SYS_write, fd, (long)buf, count);
}
static ssize_t sys_read(int fd, void *buf, size_t count) {
    return syscall3(SYS_read, fd, (long)buf, count);
}
static int sys_open(const char *path, int flags) {
    return syscall2(SYS_open, (long)path, flags);
}
static int sys_close(int fd) {
    return syscall1(SYS_close, fd);
}
static int sys_ioctl(int fd, unsigned long cmd, void *arg) {
    return syscall3(SYS_ioctl, fd, cmd, (long)arg);
}
static void my_exit(int code) {
    syscall1(SYS_exit, code);
}

static int parse_number(const char **s) {
    int num = 0;
    while (**s >= '0' && **s <= '9') {
        num = num * 10 + (**s - '0');
        (*s)++;
    }
    return num;
}

void _start(void) {
    char buf[256];
    long n = sys_read(0, buf, sizeof(buf) - 1);
    if (n <= 0) my_exit(1);
    buf[n] = '\0';

    const char *p = buf;
    while (*p == ' ') p++;

    const char *target_start = p;
    while (*p && *p != ':') p++;
    if (*p != ':') my_exit(1);
    char target[64];
    int len = p - target_start;
    if (len >= sizeof(target)) my_exit(1);
    for (int i = 0; i < len; i++) target[i] = target_start[i];
    target[len] = '\0';
    p++;

    int rows = parse_number(&p);
    if (*p != ':') my_exit(1);
    p++;
    int cols = parse_number(&p);

    if (rows <= 0 || cols <= 0) my_exit(1);

    int fd = sys_open(target, O_RDWR);
    if (fd < 0) my_exit(1);

    struct winsize ws;
    ws.ws_row = rows;
    ws.ws_col = cols;
    ws.ws_xpixel = 0;
    ws.ws_ypixel = 0;

    long ret = sys_ioctl(fd, TIOCSWINSZ, &ws);
    sys_close(fd);
    my_exit(ret ? 1 : 0);
}