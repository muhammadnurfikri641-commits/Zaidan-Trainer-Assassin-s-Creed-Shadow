#!/usr/bin/env python3
"""Generator cave Zaidan Trainer (dijalankan di Linux, hasilnya sudah dibundel di caves.py).
Merakit semua code cave dengan GNU as (sintaks Intel) lalu menulis:
  - caves.asm : source assembly yang bisa diaudit
  - caves.py  : blob biner + tabel simbol + tabel hook (dipakai engine.py)
"""
import struct, subprocess, os, re, textwrap, sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "."
F = lambda v: "0x%08X" % struct.unpack("<I", struct.pack("<f", v))[0]
F_999999, F_1 = F(999999.0), F(1.0)

# ---------- layout data bersama (page 0) ----------
DATA_DWORDS = [  # (nama, offset, nilai awal)
    ("godmode", 0x000, "0"), ("health", 0x004, "0"), ("max_health_f", 0x008, "0"),
    ("bonus_health", 0x00C, F(10000.0)), ("dmg", 0x010, "0"), ("dmgmul_f", 0x014, "0"),
    ("defmul_f", 0x018, "0"), ("armordmg", 0x01C, "0"), ("armordmgmul_f", 0x020, "0"),
    ("max_value", 0x024, F_999999), ("selected_item", 0x028, "0"), ("exp", 0x02C, "0"),
    ("expmul_f", 0x030, "0"), ("mastery_points", 0x034, "0"),
    ("ration_wont_decrease", 0x038, "0"), ("ration_consumption_f", 0x03C, "0"),
    ("ration_consumption_check", 0x040, "0"), ("throwables_wont_decrease", 0x044, "0"),
    ("throwables_consumption_f", 0x048, "0"), ("throwables_consumption_check", 0x04C, "0"),
    ("infinite_oxygen", 0x050, "0"), ("oxygen_drain_f", 0x054, "0"),
    ("freeze_daytime", 0x058, "0"), ("daytime_add", 0x05C, "0"), ("one_hour", 0x060, F_1),
    ("gamespeed_f", 0x064, "0xFFFFFFFF"),
]
DATA_QWORDS = [("player", 0x080), ("player_check", 0x088), ("is_player_damaged", 0x090),
               ("selected_item_ptr", 0x098), ("location", 0x0A0)]
WAYPOINT_OFF = 0x0C0  # 32 byte, rata 32 (vmovaps ymm)
RET_BASE = 0x100      # slot alamat kembali, 8 byte per cave


def dmg_rax():  # varian A/B: pakai rax (rdx di-push)
    return f"""
 push rdx
 cmp dword ptr [rax+0x20],{F_1}
 jle 9f
 lea rdx,[rip+is_player_damaged]
 cmp dword ptr [rdx],1
 jne 5f
 cmp dword ptr [rip+defmul_f],0
 jle 1f
 fld dword ptr [rax+0x20]
 fdiv dword ptr [rip+defmul_f]
 fstp dword ptr [rax+0x20]
1:
 lea rdx,[rip+health]
 cmp dword ptr [rdx],1
 jne 2f
 mov dword ptr [rax+0x20],0
2:
 jmp 9f
5:
 cmp dword ptr [rip+dmgmul_f],0
 jle 6f
 fld dword ptr [rax+0x20]
 fmul dword ptr [rip+dmgmul_f]
 fstp dword ptr [rax+0x20]
6:
 cmp dword ptr [rip+dmg],1
 jne 9f
 mov dword ptr [rax+0x20],{F_999999}
9:
 vmovss xmm1,dword ptr [rax+0x20]
 pop rdx
"""


DMG_RCX = f"""
 cmp dword ptr [rcx+0x20],{F_1}
 jle 8f
 push rax
 mov eax,dword ptr [rip+is_player_damaged]
 cmp eax,1
 jne 5f
 cmp dword ptr [rip+defmul_f],0
 jle 1f
 fld dword ptr [rcx+0x20]
 fdiv dword ptr [rip+defmul_f]
 fstp dword ptr [rcx+0x20]
1:
 mov eax,dword ptr [rip+health]
 cmp eax,1
 jne 2f
 mov dword ptr [rcx+0x20],0
2:
 jmp 9f
5:
 cmp dword ptr [rip+dmgmul_f],0
 jle 6f
 fld dword ptr [rcx+0x20]
 fmul dword ptr [rip+dmgmul_f]
 fstp dword ptr [rcx+0x20]
6:
 cmp dword ptr [rip+dmg],1
 jne 9f
 mov dword ptr [rcx+0x20],{F_999999}
9:
 pop rax
8:
 vmovss xmm1,dword ptr [rcx+0x20]
"""


def gamespeed(reg):
    return f"""
 push rbx
 lea rbx,[{reg}+0x7E7E7E7E]
PATCH_s1:
 cmp dword ptr [rip+gamespeed_f],0
 js 9f
 jne 5f
 mov dword ptr [rbx-0x20],{F_1}
 mov byte ptr [rbx],0
 mov dword ptr [rip+gamespeed_f],-1
 jmp 9f
5:
 fld dword ptr [rip+gamespeed_f]
 fstp dword ptr [rbx-0x20]
 mov byte ptr [rbx],1
9:
 cmp byte ptr [rbx],0
 pop rbx
"""


SELPTR = """
 mov qword ptr [rip+selected_item_ptr],rax
 mov rsi,qword ptr [rax]
 test rsi,rsi
"""

# ---------- definisi hook ----------
# name, group, pola AOB, offset hook (hex), panjang patch, body asm, (opsional) pre-capture
HOOKS = [
 dict(name="player", group="player", pat="48 85 C9 48 0F 44 D7 C5 FA 10 32 A8 01 0F 85", off=0x0, plen=7,
      pre=("48 39 * sr1.2 00 00 75 * * * * * 8B * * * 89 * B0 01 EB", "sr1"),
      body="""
 test rcx,rcx
 je 3f
 push rbx
 mov rbx,qword ptr [rcx+0x7E7E7E7E]
PATCH_sr1:
 mov qword ptr [rip+player_check],rbx
 mov qword ptr [rip+player],rcx
 mov ebx,dword ptr [rip+max_health_f]
 cmp ebx,0
 jle 1f
 mov dword ptr [rdx+4],ebx
1:
 cmp dword ptr [rip+godmode],1
 je 2f
 cmp dword ptr [rip+health],1
 jne 4f
2:
 fld dword ptr [rdx+4]
 fadd dword ptr [rip+bonus_health]
 fstp dword ptr [rdx]
4:
 pop rbx
3:
 test rcx,rcx
 cmove rdx,rdi
"""),
 dict(name="godmode", group="godmode",
      pat="48 8B 41 20 F6 40 0B 80 74 * * 8B * * 85 * 74 * 8A * * * 00 00 F6 * A8 03 74 * * 8B * 24 * * 00 00 * * * E8 * * * * C5 F8 28",
      off=0x0, plen=8, body="""
 mov rax,qword ptr [rip+player_check]
 cmp rax,qword ptr [rcx+0x20]
 lea rax,[rip+is_player_damaged]
 sete byte ptr [rax]
 jne 1f
 mov eax,dword ptr [rip+godmode]
 cmp eax,1
 je 2f
1:
 mov rax,qword ptr [rcx+0x20]
 test byte ptr [rax+0xB],0x80
2:
 mov rax,qword ptr [rcx+0x20]
"""),
 dict(name="focus_add", group="focus_add", pat="C5 FA 58 49 0C 48 8B * 45 * * FF * * * 00 00", off=0x0, plen=5,
      body=f"""
 mov dword ptr [rcx+0xC],{F_999999}
 vaddss xmm1,xmm0,dword ptr [rcx+0xC]
"""),
 dict(name="focus_sub", group="focus_sub", pat="C5 FA 10 4B 10 C5 F0 57 * * 8D", off=0x0, plen=5,
      body=" xorps xmm1,xmm1\n"),
 dict(name="skillcd", group="skillcd", pat="48 0F 44 C8 48 39 4F 68 0F 86 * * 00 00", off=0x0, plen=8, body="""
 cmove rcx,rax
 mov qword ptr [rdi+0x68],0
 cmp qword ptr [rdi+0x68],rcx
"""),
 dict(name="armordmg", group="armordmg", pat="C4 C1 F2 2A C8 * 8B * * 45", off=0x0, plen=5, body="""
 vcvtsi2ss xmm1,xmm1,r8
 cmp dword ptr [rip+armordmgmul_f],0
 jle 1f
 mulss xmm1,dword ptr [rip+armordmgmul_f]
1:
 cmp dword ptr [rip+armordmg],1
 jne 2f
 movss xmm1,dword ptr [rip+max_value]
2:
"""),
 dict(name="dmg_a", group="dmg", pat="C5 FA 10 48 20 * 88 * 24 * * 89 * 24 * * 89", off=0x0, plen=5, body=dmg_rax()),
 dict(name="dmg_b", group="dmg", pat="C5 FA 10 48 20 88 * 24 * * 00 00 88", off=0x0, plen=5, body=dmg_rax()),
 dict(name="dmg_c", group="dmg", pat="C5 FA 10 49 20 88 * 24 * * 00 00 88", off=0x0, plen=5, body=DMG_RCX),
 dict(name="selptr_1", group="selptr", pat="48 89 * 24 * 48 8B * 68 F6 * 0B 80 0F 84 * * 00 00 48 8B 30 48 85 F6 0F 84 * * 00 00",
      off=0x13, plen=6, body=SELPTR),
 dict(name="selptr_2", group="selptr", pat="48 8B 30 48 85 F6 0F 84 * * 00 00 * 8B * * * * * * 8B * * * 00 00 * 8D",
      off=0x0, plen=6, body=SELPTR),
 dict(name="edititem", group="edititem",
      pat="49 8B 07 F6 40 0B 80 74 * * 8B * * 85 * 74 * * 8B * * * * FF * * * 80 * 08 00 0F 95 * * * 74 * EB * 48 * * 48 83",
      off=0x0, plen=7, body="""
 push rdx
 mov edx,dword ptr [rip+selected_item]
 cmp edx,0
 jle 1f
 mov rax,qword ptr [rip+selected_item_ptr]
 cmp rax,qword ptr [r15]
 jne 1f
 cmp dword ptr [r15+0x10],1
 jle 1f
 mov dword ptr [rip+selected_item],0
 mov dword ptr [r15+0x10],edx
1:
 pop rdx
 mov rax,qword ptr [r15]
 test byte ptr [rax+0xB],0x80
"""),
 dict(name="exp", group="exp", pat="48 83 C6 38 44 01 C2 * 89 * 24 * * 89", off=0x0, plen=7, body="""
 add rsi,0x38
 add edx,r8d
 cmp dword ptr [rip+expmul_f],0
 jle 1f
 push rdx
 fild dword ptr [rsp]
 fmul dword ptr [rip+expmul_f]
 fistp dword ptr [rsp]
 pop rdx
1:
 cmp dword ptr [rip+exp],1
 jne 9f
 mov dword ptr [rip+exp],0
 mov edx,999999
9:
"""),
 dict(name="skillpts", group="skillpts", pat="8B 58 08 31 C9 2B * 14 0F 42 * * 8B * * E8", off=0x0, plen=5, body="""
 mov ebx,dword ptr [rip+mastery_points]
 cmp ebx,0
 jle 1f
 mov dword ptr [rax+8],ebx
1:
 mov ebx,dword ptr [rax+8]
 xor ecx,ecx
"""),
 dict(name="ploc", group="ploc", pat="C5 FA 10 40 50 C5 FA 10 * * EB * C5 F0 57", off=0x0, plen=5, body="""
 push rbx
 lea rbx,[rax+0x50]
 mov qword ptr [rip+location],rbx
 vmovss xmm0,dword ptr [rbx]
 pop rbx
"""),
 dict(name="waypoint", group="waypoint", pat="C5 FC 5A 44 24 20 C5 FC 29 06 * 8B * 24 * * * * * * * E8", off=0x0, plen=6, body="""
 .byte 0xC5,0xFC,0x5A,0x44,0x24,0x20
 vmovaps ymmword ptr [rip+waypoint_location],ymm0
"""),
 dict(name="potions", group="potions", pat="BA 01 00 00 00 * * * 45 * C9 E8 * * * * * * 01 * 8B * 24", off=0x0, plen=5, body="""
 mov edx,1
 cmp dword ptr [rip+ration_consumption_f],0
 jle 1f
 cmp dword ptr [rip+ration_consumption_check],1
 je 1f
 xor edx,edx
1:
 cmp dword ptr [rip+ration_wont_decrease],1
 jne 9f
 xor edx,edx
9:
"""),
 dict(name="throwables", group="throwables", pat="88 44 24 * C6 44 24 * 01 89 F2 41 B1 01 E8", off=0x9, plen=5, body="""
 mov edx,esi
 cmp dword ptr [rip+throwables_consumption_f],0
 jle 1f
 cmp dword ptr [rip+throwables_consumption_check],1
 je 1f
 xor edx,edx
1:
 cmp dword ptr [rip+throwables_wont_decrease],1
 jne 9f
 xor edx,edx
9:
 mov r9b,1
"""),
 dict(name="oxygen", group="oxygen", pat="C5 FA 10 86 s1.2 00 00 * * * * * * * * * C5 F8 57 * * 8D * * C4", off=0x0, plen=8, body="""
 vmovss xmm0,dword ptr [rsi+0x7E7E7E7E]
PATCH_s1:
 cmp dword ptr [rip+oxygen_drain_f],0
 jle 1f
 mulss xmm0,dword ptr [rip+oxygen_drain_f]
1:
 cmp dword ptr [rip+infinite_oxygen],1
 jne 9f
 xorps xmm0,xmm0
9:
"""),
 dict(name="daytime", group="daytime", pat="C5 FA 58 00 C5 FA 11 00 C5 FA 11 05 * * * * C5 FA 10 * C5 FA 10", off=0x0, plen=8, body="""
 cmp dword ptr [rip+freeze_daytime],0
 jle 1f
 xorps xmm0,xmm0
1:
 cmp dword ptr [rip+daytime_add],1
 jne 9f
 mov dword ptr [rip+daytime_add],0
 movss xmm0,dword ptr [rip+one_hour]
9:
 vaddss xmm0,xmm0,dword ptr [rax]
 vmovss dword ptr [rax],xmm0
"""),
 dict(name="gamespeed_1", group="gamespeed", pat="41 80 BE s1.2 00 00 00 74 * F6 * * * 00 00 * 75", off=0x0, plen=8,
      body=gamespeed("r14")),
 dict(name="gamespeed_2", group="gamespeed", pat="80 BF s1.2 00 00 00 74 * F6 * * * 00 00 * 0F 84 * * 00 00 C5 FA 10", off=0x0, plen=7,
      body=gamespeed("rdi")),
]


def build():
    asm = [".intel_syntax noprefix", ".text", ".org 0"]
    for n, o, v in DATA_DWORDS:
        asm += [f".org 0x{o:X}", f"{n}: .long {v}"]
    for n, o in DATA_QWORDS:
        asm += [f".org 0x{o:X}", f"{n}: .quad 0"]
    asm += [f".org 0x{WAYPOINT_OFF:X}", "waypoint_location: .fill 32,1,0"]
    for i, h in enumerate(HOOKS):
        asm += [f".org 0x{RET_BASE + 8 * i:X}", f"ret_{h['name']}: .quad 0"]
    for i, h in enumerate(HOOKS):
        asm += [f".org 0x{0x1000 * (i + 1):X}", f"cave_{h['name']}:"]
        body = h["body"].strip("\n")
        for ln in body.split("\n"):
            m = re.match(r"PATCH_(\w+):", ln)
            asm.append(f"patch_{h['name']}_{m.group(1)}:" if m else ln)
        asm.append(f" jmp qword ptr [rip+ret_{h['name']}]")
    src = "\n".join(asm) + "\n"
    open(os.path.join(OUT, "caves.asm"), "w").write(src)
    subprocess.check_call(["as", "--64", "-o", "/tmp/caves.o", os.path.join(OUT, "caves.asm")])
    subprocess.check_call(["objcopy", "-O", "binary", "-j", ".text", "/tmp/caves.o", "/tmp/caves.bin"])
    blob = open("/tmp/caves.bin", "rb").read()
    syms = {}
    for ln in subprocess.check_output(["nm", "/tmp/caves.o"], text=True).splitlines():
        a, _, n = ln.split()
        syms[n] = int(a, 16)
    table = {}
    for i, h in enumerate(HOOKS):
        n = h["name"]
        patches = []
        for k, v in syms.items():
            m = re.fullmatch(rf"patch_{n}_(\w+)", k)
            if m:
                patches.append((v - 4 - syms[f"cave_{n}"], m.group(1)))  # disp32 = 4 byte terakhir instruksi
        table[n] = dict(group=h["group"], pat=h["pat"], off=h["off"], plen=h["plen"], pre=h.get("pre"),
                        cave=syms[f"cave_{n}"], ret=syms[f"ret_{n}"], patches=patches)
    data = {n: syms[n] for n, _, _ in DATA_DWORDS}
    data.update({n: syms[n] for n, _ in DATA_QWORDS})
    data["waypoint_location"] = syms["waypoint_location"]
    with open(os.path.join(OUT, "caves.py"), "w") as f:
        f.write('"""Dibuat otomatis oleh gen_caves.py - jangan diedit manual. Source: caves.asm"""\n')
        f.write(f"BLOB = bytes.fromhex(\n{textwrap.fill(blob.hex(), 96, initial_indent='    ', subsequent_indent='    ').replace(chr(10), chr(10))!r}\n)\n"
                if False else "")
        hexs = blob.rstrip(b"\0").hex()
        f.write("BLOB_HEX = (\n" + "\n".join(f'    "{hexs[i:i+100]}"' for i in range(0, len(hexs), 100)) + "\n)\n")
        f.write("BLOB = bytes.fromhex(BLOB_HEX)\n")
        f.write(f"BLOB_SIZE = 0x{0x1000 * (len(HOOKS) + 1):X}\n")
        f.write(f"DATA = {data!r}\n")
        f.write(f"HOOKS = {table!r}\n")
    print("blob", len(blob), "hooks", len(HOOKS))


if __name__ == "__main__":
    build()
