#!/usr/bin/env python3
import os
import sys
import pty
import termios
import signal
import select
import socket
import struct
import fcntl
import argparse
import time
import errno

def parse_args():
    parser = argparse.ArgumentParser(description='Полноценный терминал для serial-сокета QEMU')
    parser.add_argument('vmid', nargs='?', default='105', help='VMID виртуальной машины')
    return parser.parse_args()

args = parse_args()
VMID = args.vmid
SERIAL_PATH = f"/var/run/qemu-server/{VMID}.serial0"

def wait_for_socket(path, timeout=5):
    for _ in range(timeout * 10):
        if os.path.exists(path):
            return True
        time.sleep(0.1)
    return False

if not wait_for_socket(SERIAL_PATH):
    sys.stderr.write(f"[!] {SERIAL_PATH} не найден\n")
    sys.exit(1)

# Создаём PTY
master_fd, slave_fd = pty.openpty()
slave_name = os.ttyname(slave_fd)
print(f"[+] PTY slave: {slave_name}")

pid = os.fork()
if pid == 0:
    # Дочерний процесс: мост между сокетом и PTY slave
    os.close(master_fd)
    signal.signal(signal.SIGINT, signal.SIG_IGN)      # не реагируем на Ctrl+C
    os.setsid()                                       # новая сессия
    fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)       # slave как управляющий терминал
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(SERIAL_PATH)
    while True:
        rlist, _, _ = select.select([slave_fd, sock.fileno()], [], [])
        for fd in rlist:
            try:
                if fd == slave_fd:
                    data = os.read(slave_fd, 65536)
                    if not data:
                        sys.exit(0)
                    sock.sendall(data)
                else:
                    data = sock.recv(65536)
                    if not data:
                        sys.exit(0)
                    os.write(slave_fd, data)
            except (OSError, socket.error):
                sys.exit(0)
else:
    # Родительский процесс: работаем с PTY master
    os.close(slave_fd)

    # Сохраняем старые настройки терминала для master и stdin
    old_stdin_attr = termios.tcgetattr(sys.stdin.fileno())
    old_master_attr = termios.tcgetattr(master_fd)

    # Настраиваем master и stdin в raw-режим, отключаем ISIG (чтобы Ctrl+C не прерывал)
    for fd in (sys.stdin.fileno(), master_fd):
        attr = termios.tcgetattr(fd)
        attr[3] &= ~(termios.ISIG | termios.ICANON | termios.ECHO)   # c_lflag
        attr[6][termios.VMIN] = 1
        attr[6][termios.VTIME] = 0
        termios.tcsetattr(fd, termios.TCSANOW, attr)

    def sigwinch_handler(signum=None, frame=None):
        rows, cols = os.get_terminal_size()
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        try:
            fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
        except Exception:
            pass

    signal.signal(signal.SIGWINCH, sigwinch_handler)
    sigwinch_handler()

    print("[+] Подключено. Для выхода нажмите Ctrl+O")
    sys.stdout.flush()

    try:
        while True:
            rlist, _, _ = select.select([sys.stdin.fileno(), master_fd], [], [])
            for fd in rlist:
                if fd == sys.stdin.fileno():
                    data = os.read(sys.stdin.fileno(), 65536)
                    if not data:
                        break
                    if b'\x0f' in data:   # Ctrl+O
                        print("\n[+] Ctrl+O обнаружен, выход...")
                        raise SystemExit
                    os.write(master_fd, data)
                elif fd == master_fd:
                    data = os.read(master_fd, 65536)
                    if not data:
                        break
                    os.write(sys.stdout.fileno(), data)
    except (SystemExit, KeyboardInterrupt):
        pass
    finally:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_stdin_attr)
        termios.tcsetattr(master_fd, termios.TCSADRAIN, old_master_attr)
        os.close(master_fd)
        try:
            os.kill(pid, signal.SIGTERM)
            os.waitpid(pid, 0)
        except:
            pass
        print("\n[+] Соединение закрыто")