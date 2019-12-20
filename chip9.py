#!/usr/bin/env python3
import os
import time
import sys

import pygame
from pygame.locals import *


def wrap8(x):
    return x & 0xFF

def wrap16(x):
    return x & 0xFFFF

def split16(x):
    return ((x >> 8) & 0xFF, x & 0xFF)

def comb16(a, b):
    return (a << 8) + b

def to_signed(x):
    if x > 0b10000000:
        return x - 0xFF - 1
    else:
        return x

def negate(x):
    return 0xFF - x + 1

def has_carry(x, y, s, bit):
    return (x ^ y ^ s) & (1 << bit) != 0

def print_grid_dict(grid, charmap=None, default=0):
    if len(grid) == 0:
        print()
        return
    # Expects a grid of (x, y) -> val
    # Charmap maps vals to tokens for printing.  Otherwise prints str(val).
    min_x = 0
    max_x = max([x for x, y in grid.keys()])
    min_y = min([y for x, y in grid.keys()])
    max_y = max([y for x, y in grid.keys()])
    for y in range(min_y, max_y+1):
        for x in range(min_x, max_x+1):
            v = grid.get((x, y), default)
            if charmap:
                v = charmap[v]
            sys.stdout.write(str(v))
        sys.stdout.write("\n")


class TerminalScreen():
    def __init__(self):
        pass

    def print_screen(self, screen):
        os.system("clear")
        print_grid_dict(screen, charmap={0:" ", 1:"#"})


class PygameScreen():
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode(size=(512, 512))
        self.surface = pygame.surface.Surface((128, 128))
        self.white = pygame.Color(255, 255, 255)
        self.black = pygame.Color(0, 0, 0)
        self.last_draw = 0

    def clear_screen(self):
        pygame.transform.scale(self.surface, (512, 512), self.screen)
        pygame.display.flip()
        self.surface.fill(self.white)
        self._maybe_draw()

    def fill_pixel(self, x, y):
        self.surface.set_at((x, y), self.black)
        self._maybe_draw()

    def clear_pixel(self, x, y):
        self.surface.set_at((x, y), self.white)
        self._maybe_draw()

    def _maybe_draw(self):
        t = time.time() * 1000
        if t - self.last_draw > 60:
            pygame.transform.scale(self.surface, (512, 512), self.screen)
            pygame.display.flip()
            self.last_draw = t


class Chip9():
    def __init__(self):
        self.memory = [0] * 0x10000
        self.A = 0
        self.B = 0
        self.C = 0
        self.D = 0
        self.E = 0
        self.H = 0
        self.L = 0
        self.SP = 0
        self.PC = 0
        self.FLAG = 0
        self.trace = None
        self.tracebuf = [""] * 10000
        self.traceix = 0
        self.screen = {}
        self.screen_out = None
        self.printix = 0
        self.booting = True
        self.key_byte = 0x00

        self.operations = {
            # LDI
            0x20: self.ldi("B"), 0x30: self.ldi("C"), 0x40: self.ldi("D"), 0x50: self.ldi("E"),
            0x60: self.ldi("H"), 0x70: self.ldi("L"), 0x80: self.ldi("(HL)"), 0x90: self.ldi("A"),

            # LDX
            0x21: self.ldx("BC"), 0x31: self.ldx("DE"), 0x41: self.ldx("HL"), 0x22: self.ldx("SP"),

            # PUSH R
            0x81: self.push("B"), 0x91: self.push("C"), 0xA1: self.push("D"), 0xB1: self.push("E"),
            0xC1: self.push("H"), 0xD1: self.push("L"), 0xC0: self.push("(HL)"), 0xD0: self.push("A"),

            # PUSH RR
            0x51: self.push2("BC"), 0x61: self.push2("DE"), 0x71: self.push2("HL"),

            # POP R
            0x82: self.pop("B"), 0x92: self.pop("C"), 0xA2: self.pop("D"), 0xB2: self.pop("E"),
            0xC2: self.pop("H"), 0xD2: self.pop("L"), 0xC3: self.pop("(HL)"), 0xD3: self.pop("A"),

            # POP RR
            0x52: self.pop2("BC"), 0x62: self.pop2("DE"), 0x72: self.pop2("HL"),

            # MOV R1 R2
            # Generated below.

            # MOV RR1 RR2
            0xED: self.mov("HL", "BC"), 0xFD: self.mov("HL", "DE"),

            # CLRFLAG
            0x08: self.clrflag,

            # SETFLAG
            0x18: self.setflag("Z", 1), 0x28: self.setflag("Z", 0), 0x38: self.setflag("N", 1), 0x48: self.setflag("N", 0),
            0x58: self.setflag("H", 1), 0x68: self.setflag("H", 0), 0x78: self.setflag("C", 1), 0x88: self.setflag("C", 0),

            # ADD
            0x04: self.add("B"), 0x14: self.add("C"), 0x24: self.add("D"), 0x34: self.add("E"),
            0x44: self.add("H"), 0x54: self.add("L"), 0x64: self.add("(HL)"), 0x74: self.add("A"),

            # ADDI
            0xA7: self.addi,

            # ADDX
            0x83: self.addx("BC"),
            0x93: self.addx("DE"),
            0xA3: self.addx("HL"),

            # SUB
            0x84: self.sub("B"), 0x94: self.sub("C"), 0xA4: self.sub("D"), 0xB4: self.sub("E"),
            0xC4: self.sub("H"), 0xD4: self.sub("L"), 0xE4: self.sub("(HL)"), 0xF4: self.sub("A"),

            # SUBI
            0xB7: self.subi,

            # INC
            0x03: self.inc("B"), 0x13: self.inc("C"), 0x23: self.inc("D"), 0x33: self.inc("E"),
            0x43: self.inc("H"), 0x53: self.inc("L"), 0x63: self.inc("(HL)"), 0x73: self.inc("A"),

            # INX
            0xA8: self.incx("BC"), 0xB8: self.incx("DE"), 0xC8: self.incx("HL"),

            # DEC
            0x07: self.dec("B"), 0x17: self.dec("C"), 0x27: self.dec("D"), 0x37: self.dec("E"),
            0x47: self.dec("H"), 0x57: self.dec("L"), 0x67: self.dec("(HL)"), 0x77: self.dec("A"),

            # AND
            0x05: self.andr("B"), 0x15: self.andr("C"), 0x25: self.andr("D"), 0x35: self.andr("E"),
            0x45: self.andr("H"), 0x55: self.andr("L"), 0x65: self.andr("(HL)"), 0x75: self.andr("A"),

            # ANDI
            0xC7: self.andi,

            # ORR
            0x85: self.orr("B"), 0x95: self.orr("C"), 0xA5: self.orr("D"), 0xB5: self.orr("E"),
            0xC5: self.orr("H"), 0xD5: self.orr("L"), 0xE5: self.orr("(HL)"), 0xF5: self.orr("A"),

            # ORI
            0xD7: self.ori,

            # XORR
            0x06: self.xorr("B"), 0x16: self.xorr("C"), 0x26: self.xorr("D"), 0x36: self.xorr("E"),
            0x46: self.xorr("H"), 0x56: self.xorr("L"), 0x66: self.xorr("(HL)"), 0x76: self.xorr("A"),

            # XORI
            0xE7: self.xori,

            # CMP
            0x86: self.cmpr("B"), 0x96: self.cmpr("C"), 0xA6: self.cmpr("D"), 0xB6: self.cmpr("E"),
            0xC6: self.cmpr("H"), 0xD6: self.cmpr("L"), 0xE6: self.cmpr("(HL)"), 0xF6: self.cmpr("A"),

            # CMPI
            0xF7: self.cmpi,

            # CMPS
            0x0D: self.cmps("B"), 0x1D: self.cmps("C"), 0x2D: self.cmps("D"), 0x3D: self.cmps("E"),
            0x4D: self.cmps("H"), 0x5D: self.cmps("L"), 0x6D: self.cmps("(HL)"), 0x7D: self.cmps("A"),

            # Serial IO
            0xE0: self.sin, 0xE1: self.sout,

            # Graphical IO
            0xF0: self.clrscr, 0xF1: self.draw,

            # JUMP
            0x0F: self.jump,

            # JUMP CC
            0x1F: self.jump_cond("Z"), 0x2F: self.jump_cond("NZ"), 0x3F: self.jump_cond("N"), 0x4F: self.jump_cond("NN"),
            0x5F: self.jump_cond("H"), 0x6F: self.jump_cond("NH"), 0x7F: self.jump_cond("C"), 0x8F: self.jump_cond("NC"),

            # NJUMP
            0x9F: self.njump,

            # NJUMP CC
            0xAF: self.njump_cond("Z"), 0xBF: self.njump_cond("NZ"), 0xCF: self.njump_cond("N"), 0xDF: self.njump_cond("NN"),
            0xEF: self.njump_cond("H"), 0xFF: self.njump_cond("NH"), 0xEE: self.njump_cond("C"), 0xFE: self.njump_cond("NC"),

            # CALL, RET
            0x1E: self.call,
            0x0E: self.ret,

            # NOP
            0x00: self.nop,

            # HCF
            0x6C: self.hcf,
        }

        # Generate MOV instructions.
        regnames = ["B", "C", "D", "E", "H", "L", "(HL)", "A"]
        for r1 in regnames:
            for r2 in regnames:
                op_low = (regnames.index(r1) // 2) + 0x9
                op_high = regnames.index(r2) + (regnames.index(r1) % 2) * 0x8
                opcode = (op_high << 4) + op_low
                if opcode == 0x6C:
                    continue
                self.operations[opcode] = self.mov(r1, r2)


    def step(self):
        if self.PC > 0xA000:
            self.booting = False
        opcode = self.memget(self.PC)
        if self.trace and not self.booting:
            s = ""
            s += (f"0x{self.PC:04X}: 0x{opcode:02X} [")
            s += (f"A=0x{self.A:02X} ")
            s += (f"B=0x{self.B:02X} ")
            s += (f"C=0x{self.C:02X} ")
            s += (f"D=0x{self.D:02X} ")
            s += (f"E=0x{self.E:02X} ")
            s += (f"H=0x{self.H:02X} ")
            s += (f"L=0x{self.L:02X} ")
            s += (f"FL=0b{self.FLAG:08b} ")
            s += ("]\n")
            self.tracebuf[self.traceix] = s
            self.traceix = (self.traceix + 1) % len(self.tracebuf)

        try:
            op = self.operations[opcode]
            op()
        except:
            print(f"Exception at 0x{self.PC:02X}")
            raise


    # Op Generators.
    def ldi(self, reg):
        def _op():
            xx = self.arg(1)
            self.regset(reg, xx)
            self.inc_pc(2)
        return _op

    def ldx(self, reg):
        def _op():
            yy = self.arg(1)
            xx = self.arg(2)
            self.regset(reg, comb16(xx, yy))
            self.inc_pc(3)
        return _op

    def push(self, reg):
        def _op():
            self._push(self.regget(reg))
            self.inc_pc(1)
        return _op

    def push2(self, reg):
        def _op():
            xx, yy = split16(self.regget(reg))
            self._push(xx, yy)
            self.inc_pc(1)
        return _op

    def pop(self, reg):
        def _op():
            xx, yy = self._pop()
            self.regset(reg, xx)
            self.inc_pc(1)
        return _op

    def pop2(self, reg):
        def _op():
            xx, yy = self._pop()
            self.regset(reg, comb16(xx, yy))
            self.inc_pc(1)
        return _op

    def mov(self, r1, r2):
        def _op():
            self.regset(r1, self.regget(r2))
            self.inc_pc(1)
        return _op

    def clrflag(self):
        self.FLAG = 0
        self.inc_pc(1)

    def setflag(self, flag, on):
        def _op():
            self.flagset(flag, on == 1)
            self.inc_pc(1)
        return _op

    def add(self, reg):
        def _op():
            cur = self.regget(reg)
            a = self.regget("A")
            s, z, n, h, c = self.do_add8(cur, a)
            self.regset(reg, s)
            self.flagset("Z", z)
            self.flagset("N", n)
            self.flagset("H", h)
            self.flagset("C", c)
            self.inc_pc(1)
        return _op

    def addi(self):
        xx = self.arg(1)
        a = self.regget("A")
        s, z, n, h, c = self.do_add8(xx, a)
        self.regset("A", s)
        self.flagset("Z", z)
        self.flagset("N", n)
        self.flagset("H", h)
        self.flagset("C", c)
        self.inc_pc(2)

    def addx(self, reg):
        def _op():
            cur = self.regget(reg)
            a = self.regget("A")
            new = wrap16(cur + a)
            self.flagset("Z", new == 0)
            self.flagset("N", new & 0x8000 != 0)
            self.flagset("H", has_carry(cur, a, new, 5))
            self.flagset("C", new < cur)
            self.regset(reg, new)
            self.inc_pc(1)
        return _op

    def sub(self, reg):
        def _op():
            cur = self.regget(reg)
            a = self.regget("A")
            s, z, n, h, c = self.do_add8(cur, negate(a))
            self.regset(reg, s)
            self.flagset("Z", z)
            self.flagset("N", n)
            self.flagset("H", h)
            self.flagset("C", c)
            self.inc_pc(1)
        return _op

    def subi(self):
        xx = self.arg(1)
        a = self.regget("A")
        s, z, n, h, c = self.do_add8(a, negate(xx))
        self.regset("A", s)
        self.flagset("Z", z)
        self.flagset("N", n)
        self.flagset("H", h)
        self.flagset("C", c)
        self.inc_pc(2)

    def inc(self, reg):
        def _op():
            cur = self.regget(reg)
            s, z, n, h, c = self.do_add8(cur, 1)
            self.regset(reg, s)
            self.flagset("Z", z)
            self.flagset("N", n)
            self.flagset("H", h)
            self.flagset("C", c)
            self.inc_pc(1)
        return _op

    def incx(self, reg):
        def _op():
            cur = self.regget(reg)
            new = wrap16(cur + 1)
            self.regset(reg, new)
            self.inc_pc(1)
        return _op

    def dec(self, reg):
        def _op():
            cur = self.regget(reg)
            s, z, n, h, c = self.do_add8(cur, negate(1))
            self.regset(reg, s)
            self.flagset("Z", z)
            self.flagset("N", n)
            self.flagset("H", h)
            self.flagset("C", c)
            self.inc_pc(1)
        return _op

    def andr(self, reg):
        def _op():
            cur = self.regget(reg)
            new = cur & self.regget("A")
            self.flagset("Z", new == 0)
            self.flagset("N", new & 0x80 != 0)
            self.flagset("H", False)
            self.flagset("C", False)
            self.regset(reg, new)
            self.inc_pc(1)
        return _op

    def andi(self):
        xx = self.arg(1)
        new = self.regget("A") & xx
        self.flagset("Z", new == 0)
        self.flagset("N", new & 0x80 != 0)
        self.flagset("H", False)
        self.flagset("C", False)
        self.regset("A", new)
        self.inc_pc(2)

    def orr(self, reg):
        def _op():
            cur = self.regget(reg)
            new = cur | self.regget("A")
            self.flagset("Z", new == 0)
            self.flagset("N", new & 0x80 != 0)
            self.flagset("H", False)
            self.flagset("C", False)
            self.regset(reg, new)
            self.inc_pc(1)
        return _op

    def ori(self):
        xx = self.arg(1)
        new = self.regget("A") | xx
        self.flagset("Z", new == 0)
        self.flagset("N", new & 0x80 != 0)
        self.flagset("H", False)
        self.flagset("C", False)
        self.regset("A", new)
        self.inc_pc(2)

    def xorr(self, reg):
        def _op():
            cur = self.regget(reg)
            new = cur ^ self.regget("A")
            self.flagset("Z", new == 0)
            self.flagset("N", new & 0x80 != 0)
            self.flagset("H", False)
            self.flagset("C", False)
            self.regset(reg, new)
            self.inc_pc(1)
        return _op

    def xori(self):
        xx = self.arg(1)
        new = self.regget("A") ^ xx
        self.flagset("Z", new == 0)
        self.flagset("N", new & 0x80 != 0)
        self.flagset("H", False)
        self.flagset("C", False)
        self.regset("A", new)
        self.inc_pc(2)

    def cmpr(self, reg):
        def _op():
            r = self.regget(reg)
            a = self.regget("A")
            s, z, n, h, c = self.do_add8(r, negate(a))
            self.flagset("Z", z)
            self.flagset("N", n)
            self.flagset("H", h)
            self.flagset("C", c)
            self.inc_pc(1)
        return _op

    def cmpi(self):
        xx = self.arg(1)
        a = self.regget("A")
        s, z, n, h, c = self.do_add8(a, negate(xx))
        self.flagset("Z", z)
        self.flagset("N", n)
        self.flagset("H", h)
        self.flagset("C", c)
        self.inc_pc(2)

    def cmps(self, reg):
        def _op():
            r = self.regget(reg)
            a = self.regget("A")
            r = to_signed(r)
            a = to_signed(a)
            self.flagset("Z", r == a)
            self.flagset("N", r < a)
            self.inc_pc(1)
        return _op

    def sin(self):
        b = sys.stdin.buffer.read(1)
        self.regset("A", ord(b))
        self.inc_pc(1)

    def sout(self):
        sys.stdout.write(chr(self.regget("A")))
        self.inc_pc(1)

    def clrscr(self):
        self.screen = {}
        self.inc_pc(1)
        self.screen_out.clear_screen()

    def draw(self):
        self.inc_pc(1)
        y = to_signed(self.regget("B"))
        if y < 0:
            return

        x = to_signed(self.regget("C"))
        a = self.regget("A")
        mask = f"{a:08b}"
        for ix, b in enumerate(mask):
            xx = x + ix
            if xx < 0:
                continue
            if b == '1':
                self.screen_out.fill_pixel(xx, y)
            else:
                self.screen_out.clear_pixel(xx, y)

    def jump(self):
        yy = self.arg(1)
        xx = self.arg(2)
        self.regset("PC", comb16(xx, yy))

    def jump_cond(self, cond):
        def _op():
            yy = self.arg(1)
            xx = self.arg(2)
            tgt = True
            if len(cond) > 1:
                tgt = False
                flg = cond[1:]
            else:
                flg = cond

            if self.flagget(flg) == tgt:
                self.regset("PC", comb16(xx, yy))
            else:
                self.inc_pc(3)
        return _op

    def njump(self):
        xx = self.arg(1)
        offset = to_signed(xx)
        self.inc_pc(2)
        self.regset("PC", self.regget("PC") + offset)

    def njump_cond(self, cond):
        def _op():
            xx = self.arg(1)
            offset = to_signed(xx)
            self.inc_pc(2)
            tgt = True
            if len(cond) > 1:
                tgt = False
                flg = cond[1:]
            else:
                flg = cond

            if self.flagget(flg) == tgt:
                self.regset("PC", self.regget("PC") + offset)
        return _op

    def call(self):
        yy = self.arg(1)
        xx = self.arg(2)
        self.inc_pc(3)
        pc = self.regget("PC")
        pcx, pcy = split16(pc)
        self._push(pcy, pcx)
        self.regset("PC", comb16(xx, yy))

    def ret(self):
        yy, xx = self._pop()
        self.regset("PC", comb16(xx, yy))

    def nop(self):
        self.inc_pc(1)

    def hcf(self):
        raise Exception("IT BURNS!")

    # Utils
    def arg(self, ix):
        return self.memget(self.PC + ix)

    def _push(self, val, val2=None):
        self.memset(self.SP, val)
        if val2 is not None:
            self.memset(self.SP+1, val2)
        self.SP -= 2

    def _pop(self):
        self.SP += 2
        return (self.memget(self.SP), self.memget(self.SP+1))

    def memset(self, addr, val):
        if addr == 0x200:
            print(f"{self.PC:04X}: {addr:04X} = {val:02X}")
        self.memory[addr] = wrap8(val)

    def memget(self, addr):
        if addr == 0xF000:
            return self.key_byte
        return self.memory[addr]

    def regset(self, name, val):
        if name == "A":
            self.A = wrap8(val)
        elif name == "B":
            self.B = wrap8(val)
        elif name == "C":
            self.C = wrap8(val)
        elif name == "D":
            self.D = wrap8(val)
        elif name == "E":
            self.E = wrap8(val)
        elif name == "H":
            self.H = wrap8(val)
        elif name == "L":
            self.L = wrap8(val)
        elif name == "BC":
            self.B, self.C = split16(val)
        elif name == "DE":
            self.D, self.E = split16(val)
        elif name == "HL":
            self.H, self.L = split16(val)
        elif name == "SP":
            self.SP = wrap16(val)
        elif name == "PC":
            self.PC = wrap16(val)
        elif name == "(HL)":
            addr = self.regget("HL")
            self.memset(addr, wrap8(val))
        else:
            raise Exception(f"Unknown register: {name}")

    def regget(self, name):
        if name == "A":
            return self.A
        elif name == "B":
            return self.B
        elif name == "C":
            return self.C
        elif name == "D":
            return self.D
        elif name == "E":
            return self.E
        elif name == "H":
            return self.H
        elif name == "L":
            return self.L
        elif name == "BC":
            return comb16(self.B, self.C)
        elif name == "DE":
            return comb16(self.D, self.E)
        elif name == "HL":
            return comb16(self.H, self.L)
        elif name == "SP":
            return self.SP
        elif name == "PC":
            return self.PC
        elif name == "(HL)":
            addr = self.regget("HL")
            return self.memget(addr)
        else:
            raise Exception(f"Unknown register: {name}")

    def inc_pc(self, n):
        self.regset("PC", self.PC + n)

    def flagget(self, name):
        mask = self.flagmask(name)
        return self.FLAG & mask != 0

    def flagset(self, name, on):
        mask = self.flagmask(name)
        if on:
            self.FLAG |= mask
        else:
            self.FLAG &= ~mask

    def flagmask(self, name):
        if name == "Z":
            return 0b10000000
        elif name == "N":
            return 0b01000000
        elif name == "H":
            return 0b00100000
        elif name == "C":
            return 0b00010000
        else:
            raise Exception(f"Unknown flag: {name}")

    def do_add8(self, a, b):
        s = wrap8(a + b)
        c = s < a
        h = has_carry(a, b, s, 4)
        z = s == 0
        n = s & 0x80 != 0
        return (s, z, n, h, c)

    def load_bootrom(self, data):
        base = 0x0
        for ix, c in enumerate(data):
            self.memset(base + ix, c)

    def load_rom(self, data):
        base = 0x597
        for ix, c in enumerate(data):
            self.memset(base + ix, c)

    def dump_trace(self):
        if self.trace is None:
            return
        with open(self.trace, "w") as f:
            for ix in range(len(self.tracebuf)):
                f.write(self.tracebuf[(self.traceix + ix) % len(self.tracebuf)])

def load_binary_file(path):
    with open(path, "rb") as f:
        bs = f.read()
    return bs


if __name__ == '__main__':
    emu = Chip9()
    print(f"Currently implemented {len(emu.operations)} opcodes.")

    bootrom_path = sys.argv[1]
    rom_path = sys.argv[2]

    bootrom = load_binary_file(bootrom_path)
    rom = load_binary_file(rom_path)

    emu.load_bootrom(bootrom)
    emu.load_rom(rom)

    emu.screen_out = PygameScreen()

    emu.trace = "trace.log"
    ix = 0
    try:
        while True:
            try:
                emu.step()

                # Handle input every few instructions.
                ix = (ix + 1) % 10000
                if ix == 0:
                    for event in pygame.event.get():
                        if event.type == pygame.KEYDOWN:
                            if event.key == pygame.K_UP:
                                emu.key_byte |= 0x80
                            elif event.key == pygame.K_LEFT:
                                emu.key_byte |= 0x40
                            elif event.key == pygame.K_DOWN:
                                emu.key_byte |= 0x20
                            elif event.key == pygame.K_RIGHT:
                                emu.key_byte |= 0x10
                            elif event.key == pygame.K_z:
                                # A
                                emu.key_byte |= 0x08
                            elif event.key == pygame.K_x:
                                # B
                                emu.key_byte |= 0x04
                            elif event.key == pygame.K_a:
                                # Start
                                emu.key_byte |= 0x02
                            elif event.key == pygame.K_s:
                                # Select
                                emu.key_byte |= 0x01
                        elif event.type == pygame.KEYUP:
                            if event.key == pygame.K_UP:
                                emu.key_byte &= ~0x80
                            elif event.key == pygame.K_LEFT:
                                emu.key_byte &= ~0x40
                            elif event.key == pygame.K_DOWN:
                                emu.key_byte &= ~0x20
                            elif event.key == pygame.K_RIGHT:
                                emu.key_byte &= ~0x10
                            elif event.key == pygame.K_z:
                                # A
                                emu.key_byte &= ~0x08
                            elif event.key == pygame.K_x:
                                # B
                                emu.key_byte &= ~0x04
                            elif event.key == pygame.K_a:
                                # Start
                                emu.key_byte &= ~0x02
                            elif event.key == pygame.K_s:
                                # Select
                                emu.key_byte &= ~0x01

            except:
                emu.dump_trace()
                time.sleep(2)
                raise
    except KeyboardInterrupt:
        print("Closing!")
        emu.dump_trace()
