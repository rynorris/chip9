import sys


"""
Example:

var foo

label:

# Comment
a6 b7

76 $foo

98 $label
"""

OPCODES = {
    "LDX.BC": "21", "LDX.DE": "31", "LDX.HL": "41", "LDX.SP": "22",

    "MOV.B.B": "09", "MOV.B.C": "19", "MOV.B.D": "29", "MOV.B.E": "39",
    "MOV.B.H": "49", "MOV.B.L": "59", "MOV.B.(HL)": "69", "MOV.B.A": "79",
    "MOV.C.B": "89", "MOV.C.C": "99", "MOV.C.D": "A9", "MOV.C.E": "B9",
    "MOV.C.H": "C9", "MOV.C.L": "D9", "MOV.C.(HL)": "E9", "MOV.C.A": "F9",

    "MOV.D.B": "0A", "MOV.D.C": "1A", "MOV.D.D": "2A", "MOV.D.E": "3A",
    "MOV.D.H": "4A", "MOV.D.L": "5A", "MOV.D.(HL)": "6A", "MOV.D.A": "7A",
    "MOV.E.B": "8A", "MOV.E.C": "9A", "MOV.E.D": "AA", "MOV.E.E": "BA",
    "MOV.E.H": "CA", "MOV.E.L": "DA", "MOV.E.(HL)": "EA", "MOV.E.A": "FA",

    "MOV.H.B": "0B", "MOV.H.C": "1B", "MOV.H.D": "2B", "MOV.H.E": "3B",
    "MOV.H.H": "4B", "MOV.H.L": "5B", "MOV.H.(HL)": "6B", "MOV.H.A": "7B",
    "MOV.L.B": "8B", "MOV.L.C": "9B", "MOV.L.D": "AB", "MOV.L.E": "BB",
    "MOV.L.H": "CB", "MOV.L.L": "DB", "MOV.L.(HL)": "EB", "MOV.L.A": "FB",

    "MOV.(HL).B": "0C", "MOV.(HL).C": "1C", "MOV.(HL).D": "2C", "MOV.(HL).E": "3C",
    "MOV.(HL).H": "4C", "MOV.(HL).L": "5C", "MOV.(HL).A": "7C",
    "MOV.A.B": "8C", "MOV.A.C": "9C", "MOV.A.D": "AC", "MOV.A.E": "BC",
    "MOV.A.H": "CC", "MOV.A.L": "DC", "MOV.A.(HL)": "EC", "MOV.A.A": "FC",

    "MOV.HL.BC": "ED", "MOV.HL.DE": "FD",

    "INX.BC": "A8", "INX.DE": "B8", "INX.HL": "C8",

    "DEC.B": "07", "DEC.C": "17", "DEC.D": "27", "DEC.E": "37",
    "DEC.H": "47", "DEC.L": "57", "DEC.(HL)": "67", "DEC.A": "77",

    "ANDI": "C7",

    "CMPI": "F7",

    "JMP": "0F",

    "JMPZ": "1F", "JMPNZ": "2F", "JMPN": "3F", "JMPNN": "4F",
    "JMPH": "5F", "JMPNH": "6F", "JMPC": "7F", "JMPNC": "8F",

    "CALL": "1E", "RET": "0E",

    "CLRSCR": "F0",

    "FIRE": "6C",
}


class Token():
    def __init__(self, typ, val):
        if typ not in ["def", "var", "label", "word", "byte"]:
            raise Exception(f"Invalid token type: {typ}")

        self.typ = typ
        self.val = val

    def __str__(self):
        return f"{self.typ}({self.val})"


class Assembler():
    def __init__(self):
        self.variables = {}
        self.labels = {}
        self.base_addr = 0xA000 - 0x15
        self.var_base = 0xE000
        self.cur_byte = 0
        self.prog = []
        self.tokens = []

    def log(self, msg):
        sys.stderr.write(f"{msg}\n")

    def assemble(self, asm):
        self.parse(asm)

        while self.tokens:
            tok = self.next_token()
            self.log(tok)

            if tok.typ == "def":
                if tok.val in self.variables:
                    raise Exception(f"There is already a variable named: {tok.val}.")
                if tok.val in self.labels:
                    raise Exception(f"There is already a label named: {tok.val}.")
                var_addr = self.var_base + len(self.variables)
                self.log(f"Defining variable: {tok.val}")
                self.variables[tok.val] = var_addr

            elif tok.typ == "label":
                if tok.val in self.variables:
                    raise Exception(f"There is already a variable named: {tok.val}.")
                if tok.val in self.labels:
                    raise Exception(f"There is already a label named: {tok.val}.")
                self.labels[tok.val] = self.cur_byte + self.base_addr + 1

            elif tok.typ == "var":
                self.write_placeholder(tok.val)

            elif tok.typ == "word":
                val = int(tok.val, 16)
                self.write_word(val)

            elif tok.typ == "byte":
                self.write_byte(int(tok.val, 16))

            else:
                raise Exception(f"Unknown token type: {tok.typ}")

        # Fix placeholders.
        for ix, val in enumerate(self.prog):
            if isinstance(val, str):
                if val in self.variables:
                    w = self.variables[val]
                elif val in self.labels:
                    w = self.labels[val]
                else:
                    raise Exception(f"'{tok.val}' is not a variable or label")
                low = w & 0xFF
                high = (w >> 8) & 0xFF
                # Little endian.
                self.prog[ix] = low
                self.prog[ix+1] = high


        return bytes(self.prog)

    def write_byte(self, b):
        self.prog.append(b)
        self.cur_byte += 1

    def write_word(self, w):
        low = w & 0xFF
        high = (w >> 8) & 0xFF
        self.write_byte(low)
        self.write_byte(high)

    def write_placeholder(self, name):
        self.prog.append(name)
        self.prog.append(None)
        self.cur_byte += 2

    def next_token(self):
        tok = self.tokens[0]
        self.tokens = self.tokens[1:]
        return tok

    def parse(self, asm):
        lines = asm.split("\n")

        # Filter comments.
        lines = [l for l in lines if not l.startswith("#")]

        # Split
        tok_lines = [l.strip().split() for l in lines]

        # Parse
        self.tokens = [self.parse_token(s) for l in tok_lines for s in l]

    def parse_token(self, s):
        if s.startswith("@"):
            return Token("def", s[1:])
        elif s.startswith("$"):
            return Token("var", s[1:])
        elif s.endswith(":"):
            return Token("label", s[:-1])
        elif s in OPCODES:
            return Token("byte", OPCODES[s])
        elif len(s) == 2:
            return Token("byte", s)
        elif len(s) == 4:
            return Token("word", s)
        else:
            raise Exception(f"Cannot parse token: {s}")


if __name__ == "__main__":
    path = sys.argv[1]
    out = sys.argv[2]
    with open(path) as f:
        asm = f.read()

    assembler = Assembler()
    prog = assembler.assemble(asm)
    with open(out, "wb") as f:
        f.write(prog)
