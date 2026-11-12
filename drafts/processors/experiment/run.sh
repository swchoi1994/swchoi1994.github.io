#!/bin/bash
# Compile dot.c for x86-64, 64-bit Arm and 64-bit RISC-V, run all three, and list what the compiler produced.
# Needs (Ubuntu/Debian): gcc gcc-aarch64-linux-gnu gcc-riscv64-linux-gnu qemu-user
set -e
cd "$(dirname "$0")"
work=$(mktemp -d)

echo "## Tools"
gcc --version | head -1
aarch64-linux-gnu-gcc --version | head -1
riscv64-linux-gnu-gcc --version | head -1
qemu-aarch64 --version | head -1

gcc -O2 -static -o "$work/dot-x86" dot.c
aarch64-linux-gnu-gcc -O2 -static -o "$work/dot-arm" dot.c
riscv64-linux-gnu-gcc -O2 -static -o "$work/dot-riscv" dot.c

echo; echo "## The same answer from three processors"
echo "x86-64:  $("$work/dot-x86")"
echo "Arm:     $(qemu-aarch64 "$work/dot-arm")"
echo "RISC-V:  $(qemu-riscv64 "$work/dot-riscv")"

listing() {  # listing <name> <tool prefix>
  echo; echo "## dot() on $1: $((16#$(${2}nm -S "$work/dot-$3" | awk '$4=="dot"{print $2}'))) bytes"
  ${2}objdump -d "$work/dot-$3" | awk '/<dot>:/{f=1;next} f&&/^$/{exit} f' |
    awk -F'\t' 'NF>=3{h=$2; gsub(/ /,"",h); text=$3; for(i=4;i<=NF;i++) text=text " " $i; printf "%d bytes  %s\n", length(h)/2, text}' | sed 's/ *\/\/.*//; s/ *<dot+0x[0-9a-f]*>//; s/ *$//'
}
listing "x86-64" "" x86
listing "Arm (AArch64)" aarch64-linux-gnu- arm
listing "RISC-V (RV64GC)" riscv64-linux-gnu- riscv

echo; echo "## With vector instructions switched on (-O3 -ffast-math)"
gcc -O3 -ffast-math -mavx2 -mfma -static -o "$work/v-x86" dot.c
aarch64-linux-gnu-gcc -O3 -ffast-math -static -o "$work/v-neon" dot.c
aarch64-linux-gnu-gcc -O3 -ffast-math -march=armv8.2-a+sve -static -o "$work/v-sve" dot.c
riscv64-linux-gnu-gcc -O3 -ffast-math -march=rv64gcv -static -o "$work/v-riscv" dot.c
echo "x86-64 AVX2:  $("$work/v-x86")"
echo "Arm NEON:     $(qemu-aarch64 "$work/v-neon")"
echo "Arm SVE:      $(qemu-aarch64 -cpu max "$work/v-sve")"
echo "RISC-V V:     $(qemu-riscv64 -cpu max "$work/v-riscv")"
vectors() {  # vectors <label> <tool prefix> <file> <pattern>
  echo; echo "### $1: the instructions that do the arithmetic"
  found=$(${2}objdump -d --no-show-raw-insn "$work/$3" | awk '/<dot>:/{f=1;next} f&&/^$/{exit} f' | sed 's/^ *[0-9a-f]*:\s*//; s/ *\/\/.*//' | grep -E "$4" | head -6 || true)
  if [ -n "$found" ]; then echo "$found"; else echo "(none: this compiler produced no vector instructions for this target)"; fi
}
vectors "x86-64 with AVX2 (256-bit, 8 numbers at a time)" "" v-x86 'ymm'
vectors "Arm with NEON (128-bit, 4 numbers at a time)" aarch64-linux-gnu- v-neon 'fmla|v[0-9]+\.4s'
vectors "Arm with SVE (the processor decides the width)" aarch64-linux-gnu- v-sve 'whilelo|ld1w|fmla'
vectors "RISC-V with the V extension" riscv64-linux-gnu- v-riscv 'vset|vf[a-z]+\.v|vle|vse'
rm -rf "$work"
