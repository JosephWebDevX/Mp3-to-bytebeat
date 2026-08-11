#!/usr/bin/env python3
"""
mp3_to_bytebeat.py

Converte um arquivo MP3 para um "bytebeat" representado por um array de bytes
(0-255) e gera uma saída JavaScript simples que indexa esse array com t % N.

Requisitos:
- ffmpeg instalado e disponível no PATH
- Python 3.8+

Uso:
    python tools/mp3_to_bytebeat.py input.mp3 out.js --samplerate 8000 --max-len 65536

O script decodifica o MP3 para PCM 8-bit unsigned (u8), mono, com a taxa de amostragem
(especificada) usando ffmpeg, lê os bytes, faz downsampling simples se necessário para
caber no comprimento máximo de array e grava um arquivo JavaScript com a declaração
`const data = [ ... ];` e uma função `bytebeat(t)` que retorna `data[t % N]`.

Isso não gera uma fórmula matemática compacta — em vez disso gera uma tabela de
valores (lookup) que pode ser usada em players bytebeat (por exemplo, no browser).

"""

import argparse
import math
import subprocess
import sys
from shutil import which


def check_ffmpeg():
    if which("ffmpeg") is None:
        print("Erro: ffmpeg não encontrado no PATH. Instale ffmpeg para prosseguir.")
        sys.exit(1)


def decode_to_u8(input_path, samplerate):
    # Usa ffmpeg para produzir PCM unsigned 8-bit mono em stdout
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        input_path,
        "-f",
        "u8",
        "-ac",
        "1",
        "-ar",
        str(samplerate),
        "-",
    ]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if p.returncode != 0:
        print("ffmpeg falhou:", err.decode("utf-8", errors="replace"))
        sys.exit(1)
    return out  # bytes in range 0..255


def downsample_bytes(data_bytes: bytes, factor: int) -> bytes:
    if factor <= 1:
        return data_bytes
    # Simple decimation: take every factor-th sample
    return data_bytes[::factor]


def shrink_to_maxlength(data_bytes: bytes, max_len: int) -> bytes:
    length = len(data_bytes)
    if length <= max_len:
        return data_bytes
    factor = math.ceil(length / max_len)
    print(f"Reduzindo comprimento: {length} -> usando fator de decimação {factor}")
    ds = downsample_bytes(data_bytes, factor)
    if len(ds) > max_len:
        ds = ds[:max_len]
    return ds


def format_js_array(data_bytes: bytes, per_line=20):
    parts = []
    for i, b in enumerate(data_bytes):
        parts.append(str(b))
    lines = []
    for i in range(0, len(parts), per_line):
        lines.append("  " + ", ".join(parts[i : i + per_line]))
    return "[\n" + ",\n".join(lines) + "\n]"


def generate_js_out(js_path: str, data_bytes: bytes, samplerate: int, original_file: str):
    arr_text = format_js_array(data_bytes)
    n = len(data_bytes)
    content = f"// Gerado por mp3_to_bytebeat.py a partir de: {original_file}\n"
    content += f"// samplerate: {samplerate}, length: {n}\n\n"
    content += f"const SAMPLE_RATE = {samplerate};\n"
    content += "const data = " + arr_text + ";\n\n"
    content += "function bytebeat(t) {\n"
    content += "  // Retorna 0..255\n"
    content += "  return data[t % data.length];\n"
    content += "}\n\n"
    content += "// Exemplo de uso no browser (WebAudio)\n"
    content += "// Crie um AudioContext e alimente um ScriptProcessor/AudioWorklet que chame bytebeat(t)\n"
    content += "// para cada amostra e escreva o valor como 8-bit unsigned convertido para -1..1 float.\n"
    with open(js_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Arquivo JS gerado: {js_path} (tamanho array = {n})")


def main():
    parser = argparse.ArgumentParser(description="Converter MP3 para bytebeat (array de bytes)")
    parser.add_argument("input", help="Arquivo MP3 de entrada")
    parser.add_argument("output", help="Arquivo JS de saída (por exemplo out.js)")
    parser.add_argument("--samplerate", type=int, default=8000, help="Taxa de amostragem para conversão (default 8000)")
    parser.add_argument("--max-len", type=int, default=65536, help="Comprimento máximo do array de saída")
    args = parser.parse_args()

    check_ffmpeg()
    print(f"Decodificando {args.input} para PCM u8 (sr={args.samplerate})...")
    raw = decode_to_u8(args.input, args.samplerate)
    print(f"Bytes decodificados: {len(raw)}")
    shrunk = shrink_to_maxlength(raw, args.max_len)
    print(f"Tamanho final do array: {len(shrunk)}")
    generate_js_out(args.output, shrunk, args.samplerate, args.input)


if __name__ == "__main__":
    main()
