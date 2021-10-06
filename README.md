dangerspi
=========

Program serial FLASH chips using an FTDIx232H based debug probe.

Use-case
--------

You have just upgraded the bootloader on your board to enable that one
missing feature that you needed. Great. But you messed up the build
and now your board is a brick. Not as great.

Fortunately, you have a [Bus Blaster v4][1] from [Dangerous
Prototypes][2] that you can use with dangerspi to reprogram the board
with a working version. Typically you would do something like this:

```
$ ./dangerspi.py erase 0 0x100000
$ ./dangerspi.py write 0 0x100000 </path/to/shiny/loader.bin
```

[1]: https://www.seeedstudio.com/Bus-Blaster-v4-p-1416.html
[2]: http://dangerousprototypes.com
