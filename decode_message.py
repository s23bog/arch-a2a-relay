import json
import sys
import os

SHIFT_CODES = {"SHIFT_6": 6, "SHIFT_8": 8, "SHIFT_9": 9, "SHIFT_12": 12}

# 3-trit nibble map for hex escape sequences
# 16 hex digits + 1 terminator = 17 of 27 possible 3-trit values
HEX_NIBBLE_DECODE = {
    "+++": 0x0, "++=": 0x1, "++-": 0x2, "+=+": 0x3,
    "+==": 0x4, "+=-": 0x5, "+-+": 0x6, "+-=": 0x7,
    "+--": 0x8, "=++": 0x9, "=+=": 0xA, "=+-": 0xB,
    "==+": 0xC, "===": 0xD, "==-": 0xE, "=-+": 0xF,
}
HEX_END = "=-="  # terminator nibble

def load_maps():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(script_dir, 'arch-identity/map.json'), 'r') as f:
        tier1 = json.load(f)['mapping']

    tier2_path = os.path.join(script_dir, 'arch-identity/tier2_map.json')
    tier2 = {}
    if os.path.exists(tier2_path):
        with open(tier2_path, 'r') as f:
            tier2 = json.load(f)['mapping']

    # Build shift-code lookup: raw trit sequence -> target width
    shift_lookup = {}
    for code, width in SHIFT_CODES.items():
        for seq, val in tier1.items():
            if val == code:
                shift_lookup[seq] = width
                break

    # Find HEX_ESCAPE sequence
    hex_escape_seq = None
    for seq, val in tier1.items():
        if val == "HEX_ESCAPE":
            hex_escape_seq = seq
            break

    return tier1, tier2, shift_lookup, hex_escape_seq

def demodulate_nested(stream):
    C1 = [1, 0, -1, 0]
    C2 = [1, -1, 0]
    trit_to_val = {"+": 1, "=": 0, "-": -1}
    val_to_trit = {1: "+", 0: "=", -1: "-"}

    demodulated = ""
    for i, char in enumerate(stream):
        m = trit_to_val.get(char)
        if m is None:
            continue
        val = m - C1[i % len(C1)] - C2[i % len(C2)]
        while val > 1:
            val -= 3
        while val < -1:
            val += 3
        demodulated += val_to_trit[val]
    return demodulated

CONTROL_CHARS = {
    "LF": "\n",
    "HT": "\t",
    "CR": "\r",
    " ": " ",
    "0": " "
}

def decode_hex_escape(content, pos):
    """Read 3-trit hex nibbles until HEX_END terminator. Returns (char, new_pos)."""
    codepoint = 0
    nibble_count = 0
    while pos + 3 <= len(content):
        nibble = content[pos:pos + 3]
        if nibble == HEX_END:
            pos += 3
            if nibble_count == 0:
                return "", pos  # empty escape, skip
            try:
                return chr(codepoint), pos
            except (ValueError, OverflowError):
                return f"[U+{codepoint:04X}?]", pos
        hex_val = HEX_NIBBLE_DECODE.get(nibble)
        if hex_val is not None:
            codepoint = (codepoint << 4) | hex_val
            nibble_count += 1
            pos += 3
        else:
            # Unknown nibble, bail out
            return f"[HEX_ERR]", pos
    return f"[HEX_TRUNC]", pos

def decode_trits(content, tier1, tier2, shift_lookup, hex_escape_seq):
    """Decode a demodulated trit stream using mode-shift state machine."""
    decoded = []
    mode = 6  # current trit width
    pos = 0

    while pos < len(content):
        # In non-6 modes, check for 6-trit shift codes only
        # (HEX_ESCAPE requires mode 6 — shift back first if needed)
        if mode != 6 and pos + 6 <= len(content):
            maybe_shift = content[pos:pos + 6]
            shift_width = shift_lookup.get(maybe_shift)
            if shift_width is not None:
                mode = shift_width
                pos += 6
                continue

        # Not enough trits for current mode
        if pos + mode > len(content):
            break

        chunk = content[pos:pos + mode]

        if mode == 6:
            val = tier1.get(chunk)
            if val is None:
                decoded.append(f"[{chunk}]")
                pos += mode
                continue

            # Check if this is a shift code
            if val in SHIFT_CODES:
                mode = SHIFT_CODES[val]
                pos += 6
                continue

            # Check for HEX_ESCAPE
            if val == "HEX_ESCAPE":
                pos += 6
                char, pos = decode_hex_escape(content, pos)
                decoded.append(char)
                continue

            if val in CONTROL_CHARS:
                decoded.append(CONTROL_CHARS[val])
            else:
                decoded.append(val)
            pos += 6

        elif mode == 8:
            val = tier2.get(chunk)
            if val is None:
                decoded.append(f"[{chunk}]")
            elif val in CONTROL_CHARS:
                decoded.append(CONTROL_CHARS[val])
            else:
                decoded.append(val)
            pos += 8

        elif mode in (9, 12):
            # No tier9/tier12 maps yet, output raw
            decoded.append(f"[T{mode}:{chunk}]")
            pos += mode

    # Handle leftover trits
    if pos < len(content):
        leftover = content[pos:]
        if leftover.strip('=+-'):
            pass  # non-trit chars, ignore
        elif len(leftover) > 0:
            decoded.append(f"[{leftover}]")

    return "".join(decoded)

def decode_stream(content, demodulate=True):
    """Decode a trit stream (string) with full mode-shift support."""
    tier1, tier2, shift_lookup, hex_escape_seq = load_maps()
    content = "".join(content.split())

    if demodulate:
        content = demodulate_nested(content)

    return decode_trits(content, tier1, tier2, shift_lookup, hex_escape_seq)

def decode_file(file_path, demodulate=True):
    with open(file_path, 'r') as f:
        content = f.read().strip()
    return decode_stream(content, demodulate)

def decode_string(trit_string, demodulate=True):
    return decode_stream(trit_string, demodulate)

if __name__ == "__main__":
    import glob as globmod

    if len(sys.argv) < 2 and sys.stdin.isatty():
        print("Usage: python3 decode_message.py <file_or_glob_or_trits> [--no-demod]")
        print("  file_or_glob: path to .txt file or glob pattern (e.g. encoded_messages/G_*.txt)")
        print("  trits:        raw trit string (+=-)")
        print("  stdin:        pipe or redirect encoded data (e.g. cat msg.txt | python3 decode_message.py)")
        sys.exit(1)

    demod = "--no-demod" not in sys.argv
    args = [a for a in sys.argv[1:] if a != "--no-demod"]

    # No args — read from stdin
    if not args:
        content = sys.stdin.read().strip()
        if content:
            print(decode_string(content, demod))
        sys.exit(0)

    # Collect all files: expand globs and accept shell-expanded args
    files = []
    for arg in args:
        if all(c in '+=- \t\n\r' for c in arg):
            # Raw trit string, decode directly and exit
            print(decode_string(arg, demod))
            sys.exit(0)
        expanded = sorted(globmod.glob(arg))
        if expanded:
            files.extend(expanded)
        else:
            files.append(arg)

    for f in files:
        if len(files) > 1:
            print(f"=== {os.path.basename(f)} ===")
        print(decode_file(f, demod))
        if len(files) > 1:
            print()
