"""Guided runner: pick the input files from "Input Files", then run the team sorter.

Run from the FTC-WA-EventAssignment folder:

    python3 Code/sort_teams.py

It asks for the teams file, the events file and, optionally, a pre-assignments file, then runs
sorter.cli on them unchanged. Results land in the FTC-WA-EventAssignment folder with the date
and time in their names, so earlier runs are never overwritten.

Keep this file runnable on old Pythons (no 3.10+ syntax) so it can explain a version problem
instead of crashing on it.
"""
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent
ROOT_DIR = CODE_DIR.parent
INPUT_DIR = ROOT_DIR / "Input Files"
ZIP_TABLE = CODE_DIR / ".data" / "zips.csv"

try:
    import termios
    import tty
except ImportError:  # Windows: fall back to typed numbers
    termios = tty = None


class Cancelled(Exception):
    pass


def arrows_available():
    return termios is not None and sys.stdin.isatty() and sys.stdout.isatty()


def read_key():
    """One keypress from the terminal: 'up', 'down', 'enter', 'quit', a digit, or ''."""
    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = os.read(fd, 1)
        if ch == b"\x1b":
            seq = os.read(fd, 2)
            return {b"[A": "up", b"[B": "down"}.get(seq, "")
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)
    if ch in (b"\r", b"\n"):
        return "enter"
    if ch in (b"\x03", b"q", b"Q"):
        return "quit"
    if ch in (b"k",):
        return "up"
    if ch in (b"j",):
        return "down"
    return ch.decode(errors="ignore") if ch.isdigit() else ""


def choose_with_arrows(options):
    selected = 0
    print("  (Use the up and down arrow keys, then press Enter. Press q to quit.)")

    def draw(first=False):
        if not first:
            sys.stdout.write(f"\x1b[{len(options)}F")  # back to the first option line
        for i, option in enumerate(options):
            pointer = "\x1b[1;36m> " if i == selected else "  "
            sys.stdout.write(f"\x1b[2K  {pointer}{i + 1}. {option}\x1b[0m\n")
        sys.stdout.flush()

    draw(first=True)
    while True:
        key = read_key()
        if key == "up":
            selected = (selected - 1) % len(options)
        elif key == "down":
            selected = (selected + 1) % len(options)
        elif key.isdigit() and 1 <= int(key) <= len(options):
            selected = int(key) - 1
        elif key == "enter":
            return selected
        elif key == "quit":
            raise Cancelled
        draw()


def choose_with_numbers(options):
    for i, option in enumerate(options, start=1):
        print(f"    {i}. {option}")
    while True:
        try:
            answer = input(f"  Type a number from 1 to {len(options)} and press Enter: ").strip()
        except (EOFError, KeyboardInterrupt):
            raise Cancelled
        if answer.lower() in ("q", "quit"):
            raise Cancelled
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return int(answer) - 1
        print("  That isn't one of the numbers above. Try again.")


def choose(question, options):
    print(f"\n{question}")
    if arrows_available():
        index = choose_with_arrows(options)
    else:
        index = choose_with_numbers(options)
    print(f"  You picked: {options[index]}")
    return index


def input_files():
    if not INPUT_DIR.is_dir():
        return []
    return sorted((p for p in INPUT_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".csv"),
                  key=lambda p: p.name.lower())


def pick_file(question, files):
    return files[choose(question, [p.name for p in files])]


def ensure_zip_table():
    """Build the zip code table the first time; it needs internet once."""
    if ZIP_TABLE.exists():
        return True
    print("\nFirst run: building the zip code table. This needs internet and takes a minute...")
    result = subprocess.run([sys.executable, "tools/build_zip_table.py"], cwd=CODE_DIR)
    if result.returncode != 0:
        print("\nCouldn't build the zip code table. Check your internet connection and try again.")
        return False
    return True


def main():
    sys.stdout.reconfigure(line_buffering=True)  # keep our lines in order with the sorter's output
    if sys.version_info < (3, 11):
        print(f"This sorter needs Python 3.11 or newer, and this is Python {sys.version.split()[0]}.")
        print("Install the latest Python from https://www.python.org/downloads/, then close and")
        print("reopen the terminal and run the command again.")
        return 2

    print("=" * 60)
    print("  FIRST Washington Team Sorter: setup")
    print("=" * 60)
    print(f"Looking for files in: {INPUT_DIR}")

    files = input_files()
    if len(files) < 2:
        print("\nThe Input Files folder needs at least two .csv files: your teams file and")
        print("your events file. Add them to the Input Files folder and run this again.")
        return 2

    try:
        teams = pick_file("Step 1 of 3: Which file is your TEAMS file?", files)
        events = pick_file("Step 2 of 3: Which file is your EVENTS file?", files)
        if events == teams:
            print("\nYou picked the same file for teams and events. Run this again and pick two different files.")
            return 2
        has_pre = choose("Step 3 of 3: Do you have a pre-assignments file?", ["No", "Yes"]) == 1
        pre = pick_file("Which file is your PRE-ASSIGNMENTS file?", files) if has_pre else None
    except Cancelled:
        print("\nStopped. Nothing was sorted.")
        return 1

    if not ensure_zip_table():
        return 2

    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out = ROOT_DIR / f"team_assignments_{stamp}.csv"
    summary = ROOT_DIR / f"event_summary_{stamp}.csv"

    print("\nSorting with:")
    print(f"  Teams:           {teams.name}")
    print(f"  Events:          {events.name}")
    print(f"  Pre-assignments: {pre.name if pre else 'none'}")
    print("-" * 60)

    result = subprocess.run([
        sys.executable, "-m", "sorter.cli",
        "--teams", str(teams),
        "--events", str(events),
        "--pre-assignments", str(pre) if pre else "",
        "--out", str(out),
        "--event-summary", str(summary),
    ], cwd=CODE_DIR)

    print("-" * 60)
    if out.exists() and summary.exists():
        print("Done! Your results are in the FTC-WA-EventAssignment folder:")
        print(f"  {out.name}")
        print(f"  {summary.name}")
        if result.returncode == 1:
            print("Some teams couldn't be placed. Look for 'unassigned' in the flagged_reason column.")
    else:
        print("The sort stopped before it finished, so no results were saved.")
        print("Read the Error line above to see what to fix in your files.")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
