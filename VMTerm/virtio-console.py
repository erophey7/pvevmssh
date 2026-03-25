#!/usr/bin/env python3
import os
import sys
import argparse
import select
import termios
import tty
import signal
import fcntl
import struct
import socket
import subprocess
import time

# ------------------------------------------------------------
# Пути и утилиты
# ------------------------------------------------------------
BASE_DIR = "/var/run/qemu-server/virtio-console"

def device_path(vmid, port):
    return os.path.join(BASE_DIR, str(vmid), f"{port}.virtio")

def open_chardev(path):
    if not os.path.exists(path):
        return None
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(path)
        return sock
    except (socket.error, FileNotFoundError):
        pass
    try:
        fd = os.open(path, os.O_RDWR)
        return fd
    except OSError:
        return None

def write_chardev(dev, data):
    if isinstance(dev, socket.socket):
        dev.sendall(data)
    else:
        os.write(dev, data)

def read_chardev(dev, size):
    if isinstance(dev, socket.socket):
        return dev.recv(size)
    else:
        return os.read(dev, size)

def close_chardev(dev):
    if isinstance(dev, socket.socket):
        dev.close()
    else:
        os.close(dev)

# ------------------------------------------------------------
# Отправка команды изменения размера на управляющий порт
# ------------------------------------------------------------
def send_resize(vmid, target_tty, rows, cols, debug=False):
    path = device_path(vmid, "hvc0_control")
    if not os.path.exists(path):
        if debug:
            sys.stderr.write(f"[DEBUG] Управляющий порт {path} не найден\n")
        return
    dev = open_chardev(path)
    if dev is None:
        if debug:
            sys.stderr.write(f"[DEBUG] Не удалось открыть {path}\n")
        return
    try:
        cmd = f"{target_tty}:{cols}:{rows}\n".encode()
        if debug:
            sys.stderr.write(f"[DEBUG] Отправка команды: {cmd.decode().strip()}\n")
        write_chardev(dev, cmd)
    finally:
        close_chardev(dev)

# ------------------------------------------------------------
# Отправка агента в гостевую систему через основной порт
# ------------------------------------------------------------
def send_agent(vmid, main_port, target_tty, main_dev, debug=False):
    compile_script = os.path.join(os.path.dirname(__file__), "compile_agent.py")
    if not os.path.exists(compile_script):
        sys.stderr.write("compile_agent.py не найден\n")
        return

    try:
        result = subprocess.run([compile_script], capture_output=True, text=True, check=True)
        hex_bytes = result.stdout.strip()
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"Ошибка компиляции агента:\n{e.stderr}\n")
        return

    cmd = (
        f"if command -v printf >/dev/null 2>&1; then "
        f"printf '%b' '{hex_bytes}' > /tmp/vterm_agent; "
        f"else echo -n -e '{hex_bytes}' > /tmp/vterm_agent; fi "
        f"&& chmod +x /tmp/vterm_agent "
        f"&& nohup sh -c 'while read line; do echo \"$line\" | /tmp/vterm_agent; done < /dev/hvc0' &\n"
    )

    if debug:
        sys.stderr.write(f"[DEBUG] Отправка агента: {cmd[:100]}...\n")

    try:
        write_chardev(main_dev, cmd.encode())
    except Exception as e:
        sys.stderr.write(f"Ошибка отправки агента: {e}\n")
    else:
        print("\r\n[+] Агент скомпилирован и передан.\r\n")
        print("    Проверьте в гостевой системе: ls -l /tmp/vterm_agent\n")

# ------------------------------------------------------------
# Основная функция клиента
# ------------------------------------------------------------
def run_console(vmid, main_port, use_agent, target_tty, debug):
    main_path = device_path(vmid, main_port)
    if not os.path.exists(main_path):
        print(f"[-] Устройство {main_path} не найдено")
        return

    main = open_chardev(main_path)
    if main is None:
        print(f"[-] Не удалось открыть {main_path}")
        return

    old_settings = termios.tcgetattr(sys.stdin.fileno())
    tty.setraw(sys.stdin.fileno())
    fl = fcntl.fcntl(sys.stdin, fcntl.F_GETFL)
    fcntl.fcntl(sys.stdin, fcntl.F_SETFL, fl | os.O_NONBLOCK)

    def sigwinch_handler(signum=None, frame=None):
        if not use_agent:
            return
        size = fcntl.ioctl(sys.stdin.fileno(), termios.TIOCGWINSZ, '1234')
        cols, rows = struct.unpack('HH', size)
        if debug:
            sys.stderr.write(f"[DEBUG] SIGWINCH: cols={cols}, rows={rows}\n")
        send_resize(vmid, target_tty, rows, cols, debug)

    signal.signal(signal.SIGWINCH, sigwinch_handler)
    sigwinch_handler()   # отправить начальный размер

    print(f"\r\n[+] Подключено к {vmid}:{main_port}. Выход: Ctrl+O.\r\n")
    if use_agent:
        print("    Изменение размера окна передаётся через управляющий порт hvc0_control.")
        print("    Нажмите Ctrl+A для установки агента.\r\n")
    else:
        print("    Изменение размера окна не передаётся. Используйте --use-agent для авторесайза.\r\n")
    if debug:
        print("    Режим отладки включён, сообщения выводятся в stderr.\r\n")

    try:
        while True:
            rlist = [main, sys.stdin.fileno()]
            r, _, _ = select.select(rlist, [], [])

            if main in r:
                data = read_chardev(main, 4096)
                if not data:
                    break
                os.write(sys.stdout.fileno(), data)

            if sys.stdin.fileno() in r:
                while True:
                    try:
                        ch = os.read(sys.stdin.fileno(), 1)
                        if not ch:
                            break
                        if ch == b'\x01':  # Ctrl+A
                            send_agent(vmid, main_port, target_tty, main, debug)
                        elif ch == b'\x0f':  # Ctrl+O
                            break
                        else:
                            write_chardev(main, ch)
                    except BlockingIOError:
                        break
                if ch == b'\x0f':
                    break
    finally:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
        close_chardev(main)

def main():
    parser = argparse.ArgumentParser(description="Клиент virtio-консоли QEMU")
    parser.add_argument("vmid", help="ID виртуальной машины")
    parser.add_argument("--port", default="hvc0", help="Имя основного порта (по умолчанию hvc0)")
    parser.add_argument("--use-agent", action="store_true", help="Включить отправку resize через управляющий порт hvc.control")
    parser.add_argument("--target", default="/dev/hvc1", help="Целевой терминал для агента (по умолчанию /dev/hvc1)")
    parser.add_argument("--debug", action="store_true", help="Вывод отладочной информации")
    args = parser.parse_args()
    run_console(args.vmid, args.port, args.use_agent, args.target, args.debug)

if __name__ == "__main__":
    main()