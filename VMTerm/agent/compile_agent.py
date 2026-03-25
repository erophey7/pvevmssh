#!/usr/bin/env python3
import subprocess
import sys
import os
import tempfile

def compile_agent():
    source = os.path.join(os.path.dirname(__file__), 'agent.c')
    if not os.path.exists(source):
        print(f"Файл {source} не найден", file=sys.stderr)
        return None

    tmp_bin = tempfile.mktemp(dir=os.path.dirname(__file__), prefix='agent_tmp_')
    
    for cc in ['gcc', 'tcc']:
        if subprocess.call(['which', cc], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
            continue
        cmd = [cc, '-static', '-nostdlib', '-ffreestanding', '-Os', '-s', '-o', tmp_bin, source]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
            with open(tmp_bin, 'rb') as f:
                binary = f.read()
            # Преобразуем в hex-строку вида \x7f\x45...
            hex_str = ''.join(f'\\x{b:02x}' for b in binary)
            return hex_str
        except subprocess.CalledProcessError as e:
            sys.stderr.write(f"Ошибка компиляции с {cc}:\n{e.stderr.decode()}\n")
        finally:
            if os.path.exists(tmp_bin):
                os.unlink(tmp_bin)
    
    print("Не найден подходящий компилятор (gcc или tcc) или компиляция не удалась", file=sys.stderr)
    return None

def main():
    hex_str = compile_agent()
    if hex_str:
        print(hex_str)
    else:
        sys.exit(1)

if __name__ == '__main__':
    main()