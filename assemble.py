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
