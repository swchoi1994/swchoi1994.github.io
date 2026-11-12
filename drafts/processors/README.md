# Processor series: material for the writer

This folder is working material for a series on processors: x86, Arm, RISC-V and Qualcomm's chips. It is not published; the site build ignores `drafts/`.

Whoever writes the posts: everything below marked **Verified** was read in the named source on 12 November 2026. Everything marked **Lead** is a pointer to check, not a fact to copy. Read the sources yourself before you write, and list the ones you read in the post's `sources`. The format and the checks a post must pass are in `tools/writing-guide.md`.

## Suggested parts

| Part | Subject | State of the material |
| --- | --- | --- |
| 1 | The same code on three processors: x86, Arm and RISC-V | Experiment run, output saved in `experiment/` |
| 2 | Intel v. AMD: how x86 came to have two makers | Court opinion read; key facts below |
| 3 | Qualcomm's new chips and where the company is heading | Release titles found; contents and plans still to read |
| 4 | Arm in detail | Sources named only |
| 5 | RISC-V in detail | Sources named only |

Parts in a series must be numbered 1, 2, 3 with no gaps, so publish them in order or renumber as they arrive. When part 1 is ready, add the series to `content/series.json`:

```json
"processors": {
  "title": "Processors, explained by looking inside",
  "description": "x86, Arm and RISC-V compared by compiling the same code, then the companies behind them."
}
```

## Part 1: the same code on three processors

`experiment/dot.c` is a dot product: multiply two lists of numbers pair by pair and add up the results. It is the loop at the centre of most AI arithmetic. `experiment/run.sh` compiles it for x86-64, 64-bit Arm and 64-bit RISC-V, runs all three, and lists the instructions each compiler produced. `experiment/output.txt` is the output of that script, unedited.

**Verified, from `output.txt`:**

- All three programs print the same answer, `120.0`.
- The function is 64 bytes on x86-64, 52 on Arm and 38 on RISC-V.
- Instruction length: x86 instructions here are 1 to 5 bytes long. Every Arm instruction is 4 bytes. RISC-V instructions are 2 or 4 bytes.
- The inner loop is six instructions on all three. x86 multiplies and adds in two steps (`mulss`, then `addss`). Arm and RISC-V do both in one fused instruction (`fmadd`, `fmadd.s`).
- With vector instructions switched on: x86 with AVX2 handles 8 numbers per instruction, Arm with NEON handles 4, and Arm with SVE leaves the width to the processor (the `whilelo` instruction sets up how many elements each pass takes).
- For RISC-V, GCC 13.3 with `-march=rv64gcv` produced **no** vector instructions. Report that as what this compiler did. Do not write that newer compilers do better unless you run one.

**Limits to state in the post:**

- The Arm and RISC-V programs ran under QEMU's user-mode emulation on an x86 machine. That proves they are correct, not how fast they are. The experiment contains no timings and the post must not imply any.
- One small function says nothing general about which design produces smaller or faster programs.
- x86-64's baseline has no fused multiply-add; it appears only when the compiler is told the processor has it (`-mfma`). That is why the plain x86 build uses two instructions.

To repeat it on Ubuntu or Debian: `sudo apt install gcc gcc-aarch64-linux-gnu gcc-riscv64-linux-gnu qemu-user`, then `./run.sh`.

## Part 2: Intel v. AMD

Source read: *Advanced Micro Devices, Inc. v. Intel Corp.*, 9 Cal.4th 362 (Supreme Court of California, 30 December 1994), at <https://scocal.stanford.edu/opinion/advanced-micro-devices-inc-v-intel-corp-31610>. The first 100,000 characters of the page were read; the end of the dissent was not.

**Verified, from the opinion:**

- In February 1982 the two companies signed a ten-year agreement "to establish a mechanism for exchanging technical information". Either could become a second source for the other's products: it would receive the technical information and a licence to make and sell the part, and pay a royalty.
- A 1984 amendment had AMD second-source the 80186 and 80286.
- From mid-1984 Intel decided to take no more products from AMD, and kept that decision from AMD.
- AMD went to court to compel arbitration in April 1987. The arbitration lasted four and a half years, with 355 days of hearings.
- The arbitrator found that Intel had "extensively breached" its duty to act in good faith.
- The arbitrator also faulted AMD: it should have sought arbitration by mid-1985, or begun reverse engineering the 80386 when the chip became available in July 1986. In his words, "Intel's plan succeeded ... because of AMD's inertia." He did not award the lost 80386 profits AMD asked for.
- AMD did not produce its own 80386, the Am386, until March 1991.
- The remedy in dispute: "a permanent, nonexclusive and royalty-free license to any Intel intellectual property embodied in the Am386", and a two-year extension of certain patent and copyright licences as they related to the Am386.
- The superior court confirmed the award. The Court of Appeal struck those two remedies. The Supreme Court of California restored them, 4 to 3, holding that an arbitrator's remedy stands if it "bears a rational relationship to the underlying contract".

**How to tell it accurately.** The common short version is "AMD reverse engineered the 386 and won in court". The record is more interesting. The case was about a broken contract, not about whether reverse engineering is allowed, and it was decided by an arbitrator; the courts only ruled on whether he had gone beyond his powers. On reverse engineering, the arbitrator's criticism was that AMD started too late.

**Leads, not verified here. Find a primary source for each before using it:**

- The separate lawsuits over Intel's microcode, and the settlement of the companies' disputes in the mid-1990s. Look in each company's annual report filed with the SEC for those years.
- AMD's 64-bit extension to x86, and Intel's adoption of it. Look in AMD's and Intel's own announcements and manuals.
- The 2009 settlement between the two companies. Both published it; find the press release or the SEC filing and take the figures from there.
- The antitrust cases in the United States, the European Union, Japan and Korea. Each authority published its decision.

## Part 3: Qualcomm

Qualcomm's news index is built by script and could not be read here. A search limited to qualcomm.com returned these release titles. **Only the titles and addresses are verified. Read each one before using it.**

- September 2026: "Snapdragon Leads the Agentic AI Age with Two of the World's Fastest Mobile SoCs Powering the Next Generation of Smartphones" (Snapdragon 8 Elite Extreme Gen 6 and Snapdragon 8 Elite Gen 6). <https://www.qualcomm.com/news/releases/2026/09/snapdragon-leads-the-agentic-ai-age-with-two-of-the-world-s-fast>
- May 2026: "Qualcomm Unveils Two New Snapdragon Mobile Platforms, Delivering Faster, Smoother Mobile Experiences to More Users Globally". <https://www.qualcomm.com/news/releases/2026/05/qualcomm-unveils-two-new-snapdragon-mobile-platforms--delivering>
- February 2026: "Qualcomm Unveils the Snapdragon 8 Elite Gen 5 for Galaxy". <https://www.qualcomm.com/news/releases/2026/02/qualcomm-unveils-the-snapdragon-8-elite-gen-5-for-galaxy--drivin>
- January 2026: Snapdragon X2 Plus, for PCs. <https://www.qualcomm.com/news/releases/2026/01/empowering-professionals-and-aspiring-creators--snapdragon-x2-pl>
- October 2026, developer blog: same-day upstream Linux support for the two Gen 6 platforms. <https://www.qualcomm.com/developer/blog/2026/10/same-day-snapdragon-8-elite-gen-6-upstream-linux-support>

**Not found, and needed for the "business plans" half:** the latest quarterly results and any stated targets for revenue outside phones. Take them only from Qualcomm's investor site (<https://investor.qualcomm.com>): the earnings release, the prepared remarks and the most recent investor-day presentation. A plan the company has not stated in its own words is a rumour; leave it out. A company's performance figures for its own chips are its claims; say so.

## Parts 4 and 5: Arm and RISC-V

Nothing has been read yet. Start from the organisations' own documents:

- Arm: the architecture documentation at <https://developer.arm.com>, and the annual report on <https://investors.arm.com> for how licensing and royalties work.
- RISC-V: the ratified specifications and the profiles at <https://riscv.org>.

Part 1's output gives both parts a concrete example to point back to: fixed 4-byte instructions on Arm, 2- and 4-byte instructions on RISC-V, and the two approaches to vectors.
