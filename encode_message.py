import json
import sys
import os

C1 = [1, 0, -1, 0]
C2 = [1, -1, 0]
trit_to_val = {"+": 1, "=": 0, "-": -1}
val_to_trit = {1: "+", 0: "=", -1: "-"}

# 3-trit nibble map for hex escape sequences
HEX_NIBBLE_ENCODE = {
    0x0: "+++", 0x1: "++=", 0x2: "++-", 0x3: "+=+",
    0x4: "+==", 0x5: "+=-", 0x6: "+-+", 0x7: "+-=",
    0x8: "+--", 0x9: "=++", 0xA: "=+=", 0xB: "=+-",
    0xC: "==+", 0xD: "===", 0xE: "==-", 0xF: "=-+",
}
HEX_END = "=-="

def normalize_trit(val):
    while val > 1: val -= 3
    while val < -1: val += 3
    return val

def modulate(stream):
    modulated = ""
    for i, char in enumerate(stream):
        s = trit_to_val.get(char)
        if s is None: continue
        val = s + C1[i % len(C1)] + C2[i % len(C2)]
        val = normalize_trit(val)
        modulated += val_to_trit[val]
    return modulated

def load_maps():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(script_dir, 'arch-identity/map.json'), 'r') as f:
        tier1_data = json.load(f)
    tier1 = tier1_data['mapping']

    tier2_path = os.path.join(script_dir, 'arch-identity/tier2_map.json')
    tier2 = {}
    if os.path.exists(tier2_path):
        with open(tier2_path, 'r') as f:
            tier2 = json.load(f)['mapping']

    return tier1, tier2

def encode_hex_codepoint(codepoint):
    """Encode a Unicode codepoint as 3-trit hex nibbles + terminator."""
    hex_str = f"{codepoint:X}"
    nibbles = ""
    for h in hex_str:
        nibbles += HEX_NIBBLE_ENCODE[int(h, 16)]
    nibbles += HEX_END
    return nibbles

def encode_text(text, tier1, tier2):
    """Encode text with mode-shift state machine and hex escape fallback."""
    # Build reverse lookups
    t1_reverse = {v: k for k, v in tier1.items()}
    t2_reverse = {v: k for k, v in tier2.items()}

    # Get shift/escape codes
    shift_8 = t1_reverse.get("SHIFT_8", "+-+=+=")
    shift_6 = t1_reverse.get("SHIFT_6", "+-++-=")
    hex_escape = t1_reverse.get("HEX_ESCAPE", "++++++")

    trit_stream = ""
    mode = 6  # current encoding mode

    for char in text:
        if char == " ":
            seq = t1_reverse.get(" ", "----==")
            if mode != 6:
                trit_stream += shift_6
                mode = 6
            trit_stream += seq
            continue

        # Try tier 1 first
        seq = t1_reverse.get(char)
        if seq is not None:
            if mode != 6:
                trit_stream += shift_6
                mode = 6
            trit_stream += seq
            continue

        # Try tier 2
        seq = t2_reverse.get(char)
        if seq is not None:
            if mode != 8:
                trit_stream += shift_8
                mode = 8
            trit_stream += seq
            continue

        # Fallback: hex escape (works in any mode — shift back to 6 first)
        if mode != 6:
            trit_stream += shift_6
            mode = 6
        trit_stream += hex_escape + encode_hex_codepoint(ord(char))

    # If we ended in non-6 mode, shift back for clean termination
    if mode != 6:
        trit_stream += shift_6

    return trit_stream

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 encode_message.py <text> [--raw] [--save <filename>]")
        print("  text:   plain text to encode (supports Cyrillic, Arabic, Hebrew, Devanagari via mode-shift)")
        print("         Any unmapped Unicode falls back to hex escape")
        print("  --raw:  output raw trits (no modulation)")
        print("  --save: save to encoded_messages/<filename>.txt")
        sys.exit(1)

    tier1, tier2 = load_maps()

    raw_mode = "--raw" in sys.argv
    save_name = None
    args = [a for a in sys.argv[1:] if a not in ("--raw",)]
    if "--save" in args:
        idx = args.index("--save")
        save_name = args[idx + 1]
        args = args[:idx] + args[idx+2:]

    text = " ".join(args)
    raw_trits = encode_text(text, tier1, tier2)

    if raw_mode:
        output = raw_trits
    else:
        output = modulate(raw_trits)

    if save_name:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        outpath = os.path.join(script_dir, f"encoded_messages/{save_name}.txt")
        with open(outpath, 'w') as f:
            f.write(output + "\n")
        print(f"Saved to {outpath}", file=sys.stderr)

    print(output)
