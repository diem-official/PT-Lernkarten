#!/usr/bin/env python3
"""Migrate clean image filenames to include subject prefix.

Usage:
  python migrate_images.py               # dry-run (shows planned changes)
  python migrate_images.py --apply       # apply changes
"""
import argparse
import json
import shutil
from pathlib import Path

DEFAULT_WEB = Path(__file__).parent.parent / 'web'


def _derive_clean_name(og_filename: str) -> str:
    return Path(og_filename).stem + '-clean.jpg'


def migrate(web_dir: Path, apply: bool) -> None:
    data_json = web_dir / 'data' / 'data.json'
    images_dir = web_dir / 'data' / 'images'

    entries = json.loads(data_json.read_text(encoding='utf-8'))

    if apply:
        backup = data_json.with_name('data.json.bak')
        shutil.copy2(data_json, backup)
        print(f'Backup: {backup}')

    any_change = False
    for entry in entries:
        old_name = entry['filename']
        new_name = _derive_clean_name(entry['og_filename'])

        if old_name == new_name:
            continue

        any_change = True
        old_path = images_dir / old_name
        new_path = images_dir / new_name

        if new_path.exists():
            print(f'  SKIP_RENAME (target exists): {old_name} → {new_name}')
            if apply:
                entry['filename'] = new_name
        elif old_path.exists():
            print(f'  RENAME: {old_name} → {new_name}')
            if apply:
                old_path.rename(new_path)
                entry['filename'] = new_name
        else:
            print(f'  WARN (source missing): {old_name} → {new_name}')
            if apply:
                entry['filename'] = new_name

    if not any_change:
        print('No changes needed.')
        return

    if apply:
        data_json.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding='utf-8')
        print('data.json updated.')
    else:
        print('\nDry-run: no changes applied. Use --apply to apply.')


def main():
    parser = argparse.ArgumentParser(
        description='Migrate clean image filenames to include subject prefix'
    )
    parser.add_argument('--apply', action='store_true',
                        help='Apply changes (default: dry-run)')
    parser.add_argument('--web', type=Path, default=DEFAULT_WEB,
                        help=f'Path to web/ directory (default: {DEFAULT_WEB})')
    args = parser.parse_args()
    migrate(args.web, apply=args.apply)


if __name__ == '__main__':
    main()
