"""
Pure-Python MP4 faststart: move the `moov` atom before `mdat`.

Fixes browser playback where <video> shows 0:00 because moov is at EOF.
No external dependencies required.
"""
import struct
import os
import shutil


def faststart_mp4(input_path: str) -> bool:
    """
    Move the moov atom to the beginning of an MP4 file (in-place).
    Returns True if modified, False if already faststarted or not applicable.
    """
    try:
        with open(input_path, 'rb') as f:
            # Parse top-level boxes
            boxes = []
            while True:
                pos = f.tell()
                data = f.read(8)
                if len(data) < 8:
                    break
                box_size, box_type = struct.unpack('>I4s', data)
                box_type = box_type.decode('latin-1')
                if box_size == 1:
                    ext = f.read(8)
                    if len(ext) < 8:
                        break
                    box_size = struct.unpack('>Q', ext)[0]
                elif box_size == 0:
                    cur = f.tell()
                    f.seek(0, 2)
                    box_size = f.tell() - pos
                    f.seek(cur)
                if box_size < 8:
                    break
                boxes.append((box_type, pos, box_size))
                f.seek(pos + box_size)

        # Find moov and mdat positions
        moov_box = None
        mdat_box = None
        for box_type, pos, size in boxes:
            if box_type == 'moov':
                moov_box = (pos, size)
            elif box_type == 'mdat':
                mdat_box = (pos, size)

        if moov_box is None or mdat_box is None:
            return False

        moov_pos, moov_size = moov_box
        mdat_pos, mdat_size = mdat_box

        # Already faststarted (moov before mdat)?
        if moov_pos < mdat_pos:
            return False

        # Read moov data
        with open(input_path, 'rb') as f:
            f.seek(moov_pos)
            moov_data = bytearray(f.read(moov_size))

        # The offset delta: moov is being moved from after mdat to before mdat.
        # All chunk offsets inside moov that point into mdat need to increase
        # by moov_size (because mdat shifts right by moov_size bytes).
        offset_delta = moov_size
        _patch_stco_co64(moov_data, 0, len(moov_data), offset_delta)

        # Rewrite the file: [ftyp...][moov][mdat...]
        tmp_path = input_path + '.faststart.tmp'
        with open(input_path, 'rb') as fin, open(tmp_path, 'wb') as fout:
            # Copy everything before mdat (ftyp, etc.)
            fin.seek(0)
            fout.write(fin.read(mdat_pos))

            # Insert patched moov
            fout.write(bytes(moov_data))

            # Copy mdat
            fin.seek(mdat_pos)
            fout.write(fin.read(moov_pos - mdat_pos))

            # Copy anything after moov (unlikely but safe)
            fin.seek(moov_pos + moov_size)
            tail = fin.read()
            if tail:
                fout.write(tail)

        shutil.move(tmp_path, input_path)
        print(f"[faststart] Moved moov atom to front: {input_path}")
        return True

    except Exception as e:
        print(f"[faststart] Warning: {e}")
        tmp_path = input_path + '.faststart.tmp'
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return False


def _patch_stco_co64(data, start, end, delta):
    """
    Walk the box tree inside `data[start:end]` and adjust all
    stco (32-bit) and co64 (64-bit) chunk-offset entries by `delta`.
    """
    pos = start
    while pos < end - 8:
        # Read box header
        box_size = struct.unpack_from('>I', data, pos)[0]
        box_type = data[pos+4:pos+8].decode('latin-1')

        if box_size < 8 or pos + box_size > end:
            break

        content_start = pos + 8

        if box_type == 'stco':
            # version(1) + flags(3) + entry_count(4) + entries(4 each)
            if box_size >= 16:
                entry_count = struct.unpack_from('>I', data, content_start + 4)[0]
                for i in range(entry_count):
                    off = content_start + 8 + i * 4
                    if off + 4 <= pos + box_size:
                        old = struct.unpack_from('>I', data, off)[0]
                        struct.pack_into('>I', data, off, old + delta)

        elif box_type == 'co64':
            if box_size >= 16:
                entry_count = struct.unpack_from('>I', data, content_start + 4)[0]
                for i in range(entry_count):
                    off = content_start + 8 + i * 8
                    if off + 8 <= pos + box_size:
                        old = struct.unpack_from('>Q', data, off)[0]
                        struct.pack_into('>Q', data, off, old + delta)

        elif box_type in ('moov', 'trak', 'mdia', 'minf', 'stbl', 'edts',
                          'udta', 'mvex', 'dinf', 'sinf', 'schi', 'tref'):
            # Container box — recurse into children
            _patch_stco_co64(data, content_start, pos + box_size, delta)

        pos += box_size


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        result = faststart_mp4(sys.argv[1])
        print(f"Result: {'modified' if result else 'no change'}")
