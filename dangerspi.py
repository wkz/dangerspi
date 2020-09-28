#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

import argcomplete, argparse
import collections
import sys
import time

import pyftdi.spi


SpiFlashModel = collections.namedtuple("SpiFlashModel", (
    "name",
    "size",
    "sect"
))

def KB(n):
    return n << 10

def MB(n):
    return n << 20

class SpiFlash(object):
    MODELS = {
        0xc2201b: SpiFlashModel("mx66l1g45g", MB(128), KB(64)),
    }

    def __init__(self, dev):
        self.dev = dev
        self.reset()

        id = self.jedec_id()
        if id in SpiFlash.MODELS:
            self.model = SpiFlash.MODELS[id]
        else:
            raise ValueError("JEDEC ID {:06x} is not supported".format(id))

        if self.model.size > MB(16):
            # Enter 4B addressing mode
            self.dev.write([0xb7])

    def addr(self, offset):
        buf = []

        if self.model.size > MB(16):
            buf.append((offset >> 24) & 0xff)

        buf.append((offset >> 16) & 0xff)
        buf.append((offset >>  8) & 0xff)
        buf.append((offset >>  0) & 0xff)
        return buf

    def reset(self):
        self.dev.write([0x66])
        self.dev.write([0x99])

    def jedec_id(self):
        buf = self.dev.exchange([0x9f], 3)
        return (buf[0] << 16) | (buf[1] << 8) | buf[2]

    def status(self):
        buf = self.dev.exchange([0x05], 1)
        return buf[0]

    def wip(self):
        return self.status() & 1 == 1

    def wait_write(self):
        while self.wip():
            time.sleep(0.001)

    def read(self, to, offset, count):
        self.dev.write([0x03] + self.addr(offset), stop=False)

        while (count > 4096):
            page = self.dev.read(4096, start=False, stop=False)
            to.write(page)
            count -= 4096

        frag = self.dev.read(count, start=False, stop=True)
        to.write(frag)

    def program_page(self, frm, offset, count):
        buf = frm.read(count)
        if not buf:
            return

        self.dev.write([0x06])
        self.dev.write([0x02] + self.addr(offset), stop=False)
        self.dev.write(buf, start=False)
        self.wait_write()

    def program(self, frm, offset, count):
        # Initial non-page-aligned data.
        if offset & 0xff:
            self.program_page(frm, offset, offset & 0xff)
            count -= offset & 0xff
            offset = (offset + 0x100) & ~0xff

        # Aligned full pages
        while count > 0x100:
            self.program_page(frm, offset, 0x100)
            count -= 0x100
            offset += 0x100

        # Final page
        if count > 0:
            self.program_page(frm, offset, count)

    def erase_sect(self, offset):
        self.dev.write([0x06])
        self.dev.write([0xd8] + self.addr(offset))
        self.wait_write()

    def erase(self, offset, count):
        if offset & (self.model.sect - 1):
            raise ValueError("Offset is not on a sector boundary")

        if count & (self.model.sect - 1):
            raise ValueError("Count is not an even number of sectors")

        while count > 0:
            self.erase_sect(offset)
            offset += self.model.sect
            count  -= self.model.sect

    def write(self, frm, offset, count):
        self.program(frm, offset, count)

class BusBlaster(object):
    def __init__(self, url):
        self.bus = pyftdi.spi.SpiController()
        self.bus.configure(url)

        self.gpio = self.bus.get_gpio()
        # Enable CPLD output buffers on ADBUS4/GPIOL0
        self.gpio.set_direction(0x10, 0x10)
        self.gpio.write(0x0)

    def get_port(self, cs, freq, mode):
        return self.bus.get_port(cs, freq, mode)

HARDWARE = {
    "busblaster": BusBlaster,
}

parser = argparse.ArgumentParser(prog="dangerspi")
parser.add_argument("-B", "--bus", type=str,
                    default="ftdi://ftdi:2232h/1",
                    metavar="SPI-URL")
parser.add_argument("-H", "--hardware", default="busblaster", choices=HARDWARE.keys())
parser.add_argument("-F", "--frequency", default=10E6)
parser.add_argument("-M", "--mode", default=0, choices=(0, 1, 2, 3))
parser.add_argument("-C", "--chip-select", default=0, choices=(0, 1))

subparsers = parser.add_subparsers(dest="cmd")

def int0(s):
    return int(s, 0)

locargs = argparse.ArgumentParser(add_help=False)
locargs.add_argument("offset", type=int0)
locargs.add_argument("count",  type=int0)

rparser = subparsers.add_parser("read", parents=[locargs])
rparser.add_argument("dst", nargs="?", default=sys.stdout.buffer,
                     type=argparse.FileType(mode="bw"))

wparser = subparsers.add_parser("write", parents=[locargs])
wparser.add_argument("src", nargs="?", default=sys.stdin.buffer,
                     type=argparse.FileType(mode="b"))

eparser = subparsers.add_parser("erase", parents=[locargs])

argcomplete.autocomplete(parser)
args = parser.parse_args()

hw  = HARDWARE[args.hardware](args.bus)
dev = hw.get_port(args.chip_select, args.frequency, args.mode)
sf  = SpiFlash(dev)

if   args.cmd == "read":
    sf.read(args.dst, args.offset, args.count)
elif args.cmd == "write":
    sf.write(args.src, args.offset, args.count)
elif args.cmd == "erase":
    sf.erase(args.offset, args.count)
