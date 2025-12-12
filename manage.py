#!/usr/bin/env python3
import argparse
from management import commands

def main():
    parser = argparse.ArgumentParser(description="Decade Journey Management Tool")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command Definitions
    # Format: (command_name, help_text, function_to_call)
    COMMANDS = {
        "migrate": ("Run database schema migrations", commands.run_migrations),
        "backfill-gps": ("Extract and update GPS data from images", commands.backfill_gps),
        "backfill-hashes": ("Generate SHA256 hashes for files", commands.backfill_hashes),
        "backfill-tags": ("Run AI analysis to tag images", commands.backfill_tags),
        "backfill-faces": ("Detect and cluster faces in photos (Additive)", commands.backfill_faces),
        "reset-faces": ("WARNING: Delete all faces/persons and re-scan", commands.reset_faces),
        "backfill-captions": ("Generate AI captions for photos", lambda: commands.backfill_captions(force=True)),
        "backfill-phash": ("Generate perceptual hashes for fuzzy duplicate detection", commands.backfill_phash),
        "backfill-rag": ("Re-index all memories into ChromaDB for Search", commands.backfill_rag),
        "retry-analysis": ("Retry failed AI analysis for incomplete events", commands.retry_failures),
        "backup": ("Create a zip backup of DB and Uploads", commands.create_backup),
        "reset": ("DANGER: Delete all data and files", commands.cleanup_all),
        "all": ("Run all maintenance tasks in sequence", lambda: commands.process_all_media(force=False)),
    }

    # Register Commands
    for cmd, (help_text, _) in COMMANDS.items():
        subparsers.add_parser(cmd, help=help_text)

    args = parser.parse_args()

    if args.command in COMMANDS:
        # Execute the corresponding function
        print(f"🔧 Running command: {args.command}")
        func = COMMANDS[args.command][1]
        func()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
