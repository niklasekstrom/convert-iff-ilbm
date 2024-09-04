from collections import namedtuple
from PIL import Image
from struct import unpack
from sys import argv

class ByteBuffer:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def remaining(self):
        return len(self.data) - self.pos

    def get_pos(self):
        return self.pos

    def set_pos(self, pos: int):
        self.pos = pos

    def skip(self, n: int):
        self.pos += n

    def get_bytes(self, n: int):
        self.pos += n
        return self.data[self.pos - n:self.pos]

    def get_byte(self) -> int:
        return unpack('>B', self.get_bytes(1))[0]

    def get_word(self) -> int:
        return unpack('>H', self.get_bytes(2))[0]

    def get_long(self) -> int:
        return unpack('>L', self.get_bytes(4))[0]

BitmapHeader = namedtuple('BitmapHeader', 'w, h, x, y, planes, masking, compression, pad1, transparent_color, x_aspect, y_aspect, page_width, page_height')

def convert_ilbm(filename: str, y_scaling: int):
    with open(filename, 'rb') as f:
        bb = ByteBuffer(f.read())

    hdr = bb.get_bytes(4)
    length = bb.get_long()
    if hdr != b'FORM':
        raise RuntimeError('Expected FORM header')

    if length + 8 != len(bb.data):
        raise RuntimeError('Expected matching file length in header')

    if bb.get_bytes(4) != b'ILBM':
        raise RuntimeError('Expected ILBM type')

    chunks = {}

    while bb.remaining() >= 8:
        hdr = bb.get_bytes(4)
        chunks[hdr] = bb.get_pos()
        length = bb.get_long()
        bb.skip(length)

    bb.set_pos(chunks[b'BMHD'])
    length = bb.get_long()
    if length != 20:
        raise RuntimeError('Expected length of BMHD chunk to be 20 bytes')

    bmhd = BitmapHeader(*unpack('>HHHHBBBBHBBHH', bb.get_bytes(20)))

    bb.set_pos(chunks[b'CMAP'])
    length = bb.get_long()
    cmap = []
    for i in range(length // 3):
        cmap.append(tuple(bb.get_bytes(3)))

    bb.set_pos(chunks[b'BODY'])
    length = bb.get_long()

    W, H, B = bmhd.w, bmhd.h, bmhd.planes
    BPR = W // 8

    bpls = [[] for _ in range(B)]

    if bmhd.compression == 0:
        for y in range(H):
            for i in range(B):
                bpls[i] += bb.get_bytes(BPR)
    elif bmhd.compression == 1:
        for y in range(H):
            for i in range(B):
                row = []
                while len(row) < BPR:
                    n = bb.get_byte()
                    if n >= 0 and n <= 127:
                        for _ in range(n + 1):
                            row.append(bb.get_byte())
                    elif n != 128:
                        v = bb.get_byte()
                        for _ in range(256 - n + 1):
                            row.append(v)
                bpls[i] += row
    else:
        raise RuntimeError('Expected compression to be 0 or 1')

    im = Image.new('RGB', (W, H * y_scaling))

    for y in range(H * y_scaling):
        for x in range(W):
            off = x // 8
            bit = 7 - (x % 8)
            ind = 0
            for i in range(B):
                ind |= ((bpls[i][(y // y_scaling) * BPR + off] >> bit) & 1) << i
            im.putpixel((x, y), cmap[ind])

    filename = filename[:-4] if filename.lower().endswith('.iff') else filename
    im.save(filename + '.png')

if __name__ == '__main__':
    convert_ilbm(argv[1], 2)
