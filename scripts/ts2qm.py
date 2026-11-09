# -*- coding: utf-8 -*-
"""
Compila un file di traduzione Qt (.ts) nel formato binario .qm, senza lrelease.

Uso:
    python scripts/ts2qm.py i18n/it.ts [i18n/altro.ts ...]

Produce i18n/it.qm accanto al .ts. Vengono incluse solo le traduzioni non vuote
e non marcate come "unfinished" o "obsolete"/"vanished", come fa lrelease.
Il formato è quello letto da QTranslator (Qt 5/6): sezione degli hash + sezione dei messaggi.
"""
import struct
import sys
import xml.etree.ElementTree as ET

QM_MAGIC = bytes([0x3C, 0xB8, 0x64, 0x18, 0xCA, 0xEF, 0x9C, 0x95,
                  0xCD, 0x21, 0x1C, 0xBF, 0x60, 0xA1, 0xBD, 0xDD])

# Tag delle sezioni e dei campi dei messaggi (qtbase/src/corelib/kernel/qtranslator.cpp)
SECTION_HASHES = 0x42
SECTION_MESSAGES = 0x69
TAG_END = 1
TAG_TRANSLATION = 3
TAG_SOURCE_TEXT = 6
TAG_CONTEXT = 7
TAG_COMMENT = 8


def elf_hash(data):
    h = 0
    for byte in data:
        h = ((h << 4) + byte) & 0xFFFFFFFF
        g = h & 0xF0000000
        if g:
            h ^= g >> 24
        h &= ~g & 0xFFFFFFFF
    return h or 1


def _bytes_field(tag, data):
    return struct.pack('>BI', tag, len(data)) + data


def compile_ts(ts_path, qm_path):
    root = ET.parse(ts_path).getroot()
    entries = []
    for context in root.iter('context'):
        context_name = context.findtext('name') or ''
        for message in context.iter('message'):
            translation = message.find('translation')
            if translation is None or translation.get('type') in ('unfinished', 'obsolete', 'vanished'):
                continue
            text = translation.text or ''
            if not text:
                continue
            source = message.findtext('source') or ''
            comment = message.findtext('comment') or ''
            entries.append((context_name, source, comment, text))

    messages = bytearray()
    hashes = []
    for context_name, source, comment, text in entries:
        source_b = source.encode('utf-8')
        comment_b = comment.encode('utf-8')
        hashes.append((elf_hash(source_b + comment_b), len(messages)))
        messages += _bytes_field(TAG_TRANSLATION, text.encode('utf-16-be'))
        messages += _bytes_field(TAG_SOURCE_TEXT, source_b)
        messages += _bytes_field(TAG_COMMENT, comment_b)
        messages += _bytes_field(TAG_CONTEXT, context_name.encode('utf-8'))
        messages += struct.pack('>B', TAG_END)

    hashes.sort()
    hash_table = b''.join(struct.pack('>II', h, offset) for h, offset in hashes)

    with open(qm_path, 'wb') as f:
        f.write(QM_MAGIC)
        f.write(struct.pack('>BI', SECTION_HASHES, len(hash_table)) + hash_table)
        f.write(struct.pack('>BI', SECTION_MESSAGES, len(messages)) + bytes(messages))
    return len(entries)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for path in sys.argv[1:]:
        out = path[:-3] + '.qm' if path.endswith('.ts') else path + '.qm'
        count = compile_ts(path, out)
        print(f"{path} -> {out}: {count} messages")
