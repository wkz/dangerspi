#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

import argcomplete, argparse
import collections
import sys

import pyftdi.i2c

EepromModel = collections.namedtuple("EepromModel", (
    "size",
    "page"
))

class Eeprom(object):
    MODELS =  {
        "24c02": EepromModel(256, 16),
    }

    def __init__(self, dev, model):
        self.dev = dev

        if model not in Eeprom.MODELS:
            raise ValueError("Unsupported EEPROM model: \"%s\"" % model)

        self.model = Eeprom.MODELS[model]

    def read(self, to, offset, count):
        data = self.dev.read_from(offset, count)
        to.write(data)

    def write(self, frm, offset, count):
        align = offset % self.model.page
        if align:
            data = frm.read(align)
            self.dev.write_to(offset, data)
            count -= align
            offset += align

        while count > self.model.page:
            data = frm.read(self.model.page)
            self.dev.write_to(offset, data)
            count -= self.model.page
            offset += self.model.page

        if count:
            data = frm.read(count)
            self.dev.write_to(offset, data)

parser = argparse.ArgumentParser(prog="dangeri2c")
parser.add_argument("-B", "--bus", type=str,
                    default="ftdi://ftdi:2232h/2",
                    metavar="I2C-URL")
parser.add_argument("-M", "--model", default="24c02", choices=Eeprom.MODELS.keys())

subparsers = parser.add_subparsers(dest="cmd")

def int0(s):
    return int(s, 0)

locargs = argparse.ArgumentParser(add_help=False)
locargs.add_argument("address", type=int0)
locargs.add_argument("offset", type=int0)
locargs.add_argument("count",  type=int0)

rparser = subparsers.add_parser("read", parents=[locargs])
rparser.add_argument("dst", nargs="?", default=sys.stdout.buffer,
                     type=argparse.FileType(mode="bw"))

wparser = subparsers.add_parser("write", parents=[locargs])
wparser.add_argument("src", nargs="?", default=sys.stdin.buffer,
                     type=argparse.FileType(mode="b"))

argcomplete.autocomplete(parser)
args = parser.parse_args()

bus = pyftdi.i2c.I2cController()
bus.configure(args.bus)

dev = bus.get_port(args.address)
eeprom = Eeprom(dev, args.model)

if   args.cmd == "read":
    eeprom.read(args.dst, args.offset, args.count)
elif args.cmd == "write":
    eeprom.write(args.src, args.offset, args.count)
