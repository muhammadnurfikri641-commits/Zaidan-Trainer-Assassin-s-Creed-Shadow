.intel_syntax noprefix
.text
.org 0
.org 0x0
godmode: .long 0
.org 0x4
health: .long 0
.org 0x8
max_health_f: .long 0
.org 0xC
bonus_health: .long 0x461C4000
.org 0x10
dmg: .long 0
.org 0x14
dmgmul_f: .long 0
.org 0x18
defmul_f: .long 0
.org 0x1C
armordmg: .long 0
.org 0x20
armordmgmul_f: .long 0
.org 0x24
max_value: .long 0x497423F0
.org 0x28
selected_item: .long 0
.org 0x2C
exp: .long 0
.org 0x30
expmul_f: .long 0
.org 0x34
mastery_points: .long 0
.org 0x38
ration_wont_decrease: .long 0
.org 0x3C
ration_consumption_f: .long 0
.org 0x40
ration_consumption_check: .long 0
.org 0x44
throwables_wont_decrease: .long 0
.org 0x48
throwables_consumption_f: .long 0
.org 0x4C
throwables_consumption_check: .long 0
.org 0x50
infinite_oxygen: .long 0
.org 0x54
oxygen_drain_f: .long 0
.org 0x58
freeze_daytime: .long 0
.org 0x5C
daytime_add: .long 0
.org 0x60
one_hour: .long 0x3F800000
.org 0x64
gamespeed_f: .long 0xFFFFFFFF
.org 0x80
player: .quad 0
.org 0x88
player_check: .quad 0
.org 0x90
is_player_damaged: .quad 0
.org 0x98
selected_item_ptr: .quad 0
.org 0xA0
location: .quad 0
.org 0xC0
waypoint_location: .fill 32,1,0
.org 0x100
ret_player: .quad 0
.org 0x108
ret_godmode: .quad 0
.org 0x110
ret_focus_add: .quad 0
.org 0x118
ret_focus_sub: .quad 0
.org 0x120
ret_skillcd: .quad 0
.org 0x128
ret_armordmg: .quad 0
.org 0x130
ret_dmg_a: .quad 0
.org 0x138
ret_dmg_b: .quad 0
.org 0x140
ret_dmg_c: .quad 0
.org 0x148
ret_selptr_1: .quad 0
.org 0x150
ret_selptr_2: .quad 0
.org 0x158
ret_edititem: .quad 0
.org 0x160
ret_exp: .quad 0
.org 0x168
ret_skillpts: .quad 0
.org 0x170
ret_ploc: .quad 0
.org 0x178
ret_waypoint: .quad 0
.org 0x180
ret_potions: .quad 0
.org 0x188
ret_throwables: .quad 0
.org 0x190
ret_oxygen: .quad 0
.org 0x198
ret_daytime: .quad 0
.org 0x1A0
ret_gamespeed_1: .quad 0
.org 0x1A8
ret_gamespeed_2: .quad 0
.org 0x1000
cave_player:
 test rcx,rcx
 je 3f
 push rbx
 mov rbx,qword ptr [rcx+0x7E7E7E7E]
patch_player_sr1:
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
 jmp qword ptr [rip+ret_player]
.org 0x2000
cave_godmode:
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
 jmp qword ptr [rip+ret_godmode]
.org 0x3000
cave_focus_add:
 mov dword ptr [rcx+0xC],0x497423F0
 vaddss xmm1,xmm0,dword ptr [rcx+0xC]
 jmp qword ptr [rip+ret_focus_add]
.org 0x4000
cave_focus_sub:
 xorps xmm1,xmm1
 jmp qword ptr [rip+ret_focus_sub]
.org 0x5000
cave_skillcd:
 cmove rcx,rax
 mov qword ptr [rdi+0x68],0
 cmp qword ptr [rdi+0x68],rcx
 jmp qword ptr [rip+ret_skillcd]
.org 0x6000
cave_armordmg:
 vcvtsi2ss xmm1,xmm1,r8
 cmp dword ptr [rip+armordmgmul_f],0
 jle 1f
 mulss xmm1,dword ptr [rip+armordmgmul_f]
1:
 cmp dword ptr [rip+armordmg],1
 jne 2f
 movss xmm1,dword ptr [rip+max_value]
2:
 jmp qword ptr [rip+ret_armordmg]
.org 0x7000
cave_dmg_a:
 push rdx
 cmp dword ptr [rax+0x20],0x3F800000
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
 mov dword ptr [rax+0x20],0x497423F0
9:
 vmovss xmm1,dword ptr [rax+0x20]
 pop rdx
 jmp qword ptr [rip+ret_dmg_a]
.org 0x8000
cave_dmg_b:
 push rdx
 cmp dword ptr [rax+0x20],0x3F800000
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
 mov dword ptr [rax+0x20],0x497423F0
9:
 vmovss xmm1,dword ptr [rax+0x20]
 pop rdx
 jmp qword ptr [rip+ret_dmg_b]
.org 0x9000
cave_dmg_c:
 cmp dword ptr [rcx+0x20],0x3F800000
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
 mov dword ptr [rcx+0x20],0x497423F0
9:
 pop rax
8:
 vmovss xmm1,dword ptr [rcx+0x20]
 jmp qword ptr [rip+ret_dmg_c]
.org 0xA000
cave_selptr_1:
 mov qword ptr [rip+selected_item_ptr],rax
 mov rsi,qword ptr [rax]
 test rsi,rsi
 jmp qword ptr [rip+ret_selptr_1]
.org 0xB000
cave_selptr_2:
 mov qword ptr [rip+selected_item_ptr],rax
 mov rsi,qword ptr [rax]
 test rsi,rsi
 jmp qword ptr [rip+ret_selptr_2]
.org 0xC000
cave_edititem:
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
 jmp qword ptr [rip+ret_edititem]
.org 0xD000
cave_exp:
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
 jmp qword ptr [rip+ret_exp]
.org 0xE000
cave_skillpts:
 mov ebx,dword ptr [rip+mastery_points]
 cmp ebx,0
 jle 1f
 mov dword ptr [rax+8],ebx
1:
 mov ebx,dword ptr [rax+8]
 xor ecx,ecx
 jmp qword ptr [rip+ret_skillpts]
.org 0xF000
cave_ploc:
 push rbx
 lea rbx,[rax+0x50]
 mov qword ptr [rip+location],rbx
 vmovss xmm0,dword ptr [rbx]
 pop rbx
 jmp qword ptr [rip+ret_ploc]
.org 0x10000
cave_waypoint:
 .byte 0xC5,0xFC,0x5A,0x44,0x24,0x20
 vmovaps ymmword ptr [rip+waypoint_location],ymm0
 jmp qword ptr [rip+ret_waypoint]
.org 0x11000
cave_potions:
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
 jmp qword ptr [rip+ret_potions]
.org 0x12000
cave_throwables:
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
 jmp qword ptr [rip+ret_throwables]
.org 0x13000
cave_oxygen:
 vmovss xmm0,dword ptr [rsi+0x7E7E7E7E]
patch_oxygen_s1:
 cmp dword ptr [rip+oxygen_drain_f],0
 jle 1f
 mulss xmm0,dword ptr [rip+oxygen_drain_f]
1:
 cmp dword ptr [rip+infinite_oxygen],1
 jne 9f
 xorps xmm0,xmm0
9:
 jmp qword ptr [rip+ret_oxygen]
.org 0x14000
cave_daytime:
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
 jmp qword ptr [rip+ret_daytime]
.org 0x15000
cave_gamespeed_1:
 push rbx
 lea rbx,[r14+0x7E7E7E7E]
patch_gamespeed_1_s1:
 cmp dword ptr [rip+gamespeed_f],0
 js 9f
 jne 5f
 mov dword ptr [rbx-0x20],0x3F800000
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
 jmp qword ptr [rip+ret_gamespeed_1]
.org 0x16000
cave_gamespeed_2:
 push rbx
 lea rbx,[rdi+0x7E7E7E7E]
patch_gamespeed_2_s1:
 cmp dword ptr [rip+gamespeed_f],0
 js 9f
 jne 5f
 mov dword ptr [rbx-0x20],0x3F800000
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
 jmp qword ptr [rip+ret_gamespeed_2]
