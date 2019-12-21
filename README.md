# chip9

## What is CHIP9?

CHIP9 is a fictional CPU architecture invented by the folks at [X-MAS CTF]().

It was featured in two challenges in the "Emulation" category.
The first being to write an emulator for it, and the second to create a demo that runs on said emulator.

## The Emulator

[chip9.py](https://github.com/rynorris/chip9/blob/master/chip9.py)

```
pypy3 chip9.py ./bootrom ./rom
```

Note: This emulator is painfully slow in CPython.  PyPy strongly recommended.

I wrote my emulator in python for speed purposes (coding speed, not execution speed!).
It's pretty simple and just generates a bit map from opcodes to methods to run, and runs them one-by-one.

There aren't too many gotchas with the CHIP9 unlike most real CPUs, which I'm thankful to the challenge creators for.

The only "gotcha" I can remember is the side-note about CMP being implemented using SUB, 
which means it sets the H and C flags despite that not being directly specified in the documentation.

I actually didn't notice that at first, so for the first flag I hacked the emulator to jump around a particular 
JMPNH instruction in the bootloader so I could execute the provided ROM and get the flag.

## The Demo

As soon as I saw the demo challenge, I knew I wanted to write a CHIP8 emulator for the CHIP9.

This basically consumed all my time for the last 2 days of the CTF, but it was great fun, 
and this was my first time writing a large amount of assembly code by hand, so I learned a lot.

### Assembler

[assemble.py](https://github.com/rynorris/chip9/blob/master/assemble.py)

```
python3 assemble.py chip8.ch9 chip8.rom
```

It was pretty clear that in order to make anything substantial I would need an assembler.

However I didn't want to waste too much time here, so I hacked together something fairly rudimentary which would just allow me to:

  1. Reference opcodes by name
  2. Set labels and reference their addresses by name
  3. Create named variables and reference their addresses by name
  
I didn't put all the opcodes in it, just adding them as and when I needed them for my demo.

This turned out to be enough to unblock development.

### CHIP8

[chip8.ch9](https://github.com/rynorris/chip9/blob/master/chip8.ch9)

[Demo video](https://www.youtube.com/watch?v=u0YOBKMGVZs)

Note:  You must pass to stdin firstly two bytes representing the chip8 ROM size in bytes, followed by the ROM itself.

```
pypy3 chip9.py ./bootrom ./chip8.rom < <(echo -en "\x00\xF6"; cat games/PONG)
```

#### Architecture

I knew this was going to be possible, since the CHIP8 only uses memory up to 0xFFF, we're using a much more powerful machine.

It makes things much easier to have the CHIP8 ROM situated where it wants to be in memory (0x200) so that all the addresses
in it are correct without needing to be shifted.

To that end, the first part of the ROM is a loader which 
first re-situates the entire CHIP8 emulator out of the way over at 0xA000.
Then we read the CHIP8 ROM in from stdin into memory starting at 0x200, and finally jump to the emulator itself at 0xA000.

The emulator itself is fairly simple.  The main loop loads the next instruction into BC and then switches on it to jump
to the correct subroutine to execute that instruction.

#### Graphics

Drawing the screen was by far the hardest part.

Both the CHIP8 and CHIP9 use a draw call like `draw(x, y, byte)`, the CHIP9 does direct drawing (1=white, 0=black), 
while the CHIP8 XORs the bits with the current screen state.

This means that I have to keep an entire copy of the screen state in memory, and XOR against it before sending the bytes to
the screen.

But this led to a new problem.  I want to store the screen bit-packed, so it fits in a 0x1000 wide space. 
Which means if the x coordinate for a draw is not byte-aligned, I can't just XOR with the in-memory screen.

On top of all that, we also need to set the VF flag if any bits flip from 1 to 0.  This is how collision-detection works on CHIP8.

So the full draw routine ends up going something like this:

  1. Set VF = 0
  2. Load the pixel byte from I into BC.
  3. Left-shift the pixel data in BC, incrementing the x coordinate until it's byte-aligned.  Now B and C contain two halves of the pixel data which should be drawn at x-8 and x respectively.
  4. Calculate the address of x, y in the in-memory screen.
  5. AND C with the current screen byte at x.  If non-zero, set VF = 1.  (non-zero => bits overlap => they will go from 1 to 0 in the XOR)
  6. XOR C with the current screen byte, store it in memory.
  7. Finally call the CHIP9 DRAW instruction with x, y, screen byte.
  8. Subtract 8 from X, 1 from in-memory screen address and repeat with the other pixel byte.
  9. Increment y and repeat again starting from #2, until we've drawn enough lines.
  
This is by far the most complicated part of the emulator, and I wouldn't be surprised if this is where my remaining bugs lie.
But it does seem to work in general, which I'm pretty happy with!

One improvement I would like to make is to scale the screen 2X so it takes up the entire CHIP9 display.
  
#### Input

CHIP9 only has 8 buttons, so we can't emulate all 16 keys on the CHIP8 keyboard.

For now the ROM has a key mapping hard-coded in, so not all games are playable.  
Perhaps I could come up with a way to read in a keymapping from stdin at runtime as an improvement on this.

## Conclusion

Overall this was a really fun challenge which I learned a lot from.

And thanks to those who voted for my demo.  I got the flag, so it was all worth it in the end haha!
