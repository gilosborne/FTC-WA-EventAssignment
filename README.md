# FIRST Washington Team Sorter

This tool sorts FIRST teams into events so teams drive as little as possible. You give it a list of teams and a list of events, and it places each team at a nearby event with room. It saves the results as a spreadsheet and marks the placements a person should double-check.

It works for FLL, FTC and FRC.

## What's in this folder

| Folder or file | What it's for |
|---|---|
| **Input Files** | Put your teams, events and pre-assignments files here. |
| **Code** | The sorter itself. You don't need to open or change anything in here. |
| `team_assignments_...csv` and `event_summary_...csv` | Your results. A new pair appears each time you run the sorter. |

Your team files and results stay on your computer. They're never uploaded to GitHub.

---

## One-time setup

### 1. Install Python

Download the latest version from [python.org/downloads](https://www.python.org/downloads/) and run the installer.
- **Windows:** on the first screen of the installer, check **Add python.exe to PATH**.
- **Mac:** your Mac already has an older Python built in, but it's too old for the sorter, so install the new one anyway.

### 2. Get the sorter folder

On this page, click the green **Code** button and choose **Download ZIP**. Double-click the ZIP to unzip it, rename the folder to **FTC-WA-EventAssignment**, and move it somewhere easy to find, like your Desktop.

---

## Sorting teams

### Step 1. Put your files in the Input Files folder

Save each file from Excel or Google Sheets with **Save as CSV**, and put it in the **Input Files** folder. You can name the files anything you like.

| File | One line per | Columns, in this order | Example |
|---|---|---|---|
| Teams | team | team number, team name, zip code | `75355,Jing Mei Storm,98005` |
| Events | event | event code, venue zip code, number of seats | `BEA-SAT,98029,32` |
| Pre-assignments (optional) | team you're placing by hand | event code, team number, host flag, reason | `BEL-SUN1,11429,is_host_team,Host team - BEL-SUN1` |

**Every file must follow these rules, or the sort will stop:**
- **No header row.** The first line is the first team or event, not column names.
- **No blank rows** at the bottom.

**Filling in the pre-assignments file:**
- **Host team:** write `is_host_team` in the third column.
- **Any other hand placement** (a coach request, for example): leave the third column blank, like `SMS-SAT,75429,,Richland requested Pasco`.
- **Reason:** always fill it in. It shows up in your results so you remember why you placed the team.
- The event codes and team numbers must match your events and teams files exactly.

To change how many teams an event holds, change its number of seats in the events file.

### Step 2. Open a terminal in the FTC-WA-EventAssignment folder

A terminal is a window where you type commands.

- **Mac:** open the **Terminal** app (press **Command + Space**, type `Terminal`, and press **Enter**). Type `cd` followed by a space, drag the **FTC-WA-EventAssignment** folder from Finder into the Terminal window, and press **Enter**.
- **Windows:** open the **FTC-WA-EventAssignment** folder in File Explorer. Click the address bar at the top, type `cmd`, and press **Enter**. A terminal opens already in the folder.

The folder name **FTC-WA-EventAssignment** now shows in the terminal, just before where you type.

### Step 3. Run the sorter

Once you're in the **FTC-WA-EventAssignment** folder, type this and press **Enter**:

- **Mac:**
  ```
  python3 Code/sort_teams.py
  ```
- **Windows:**
  ```
  python Code\sort_teams.py
  ```

### Step 4. Answer the three questions

The sorter lists the files in your **Input Files** folder and asks you to pick:
1. Your **teams** file
2. Your **events** file
3. Whether you have a **pre-assignments** file. If you pick **Yes**, it asks you to pick that file too.

On a Mac, use the **up and down arrow keys** to highlight a file and press **Enter**. On Windows, type the file's **number** and press **Enter**.

The first time you run it, it spends about a minute downloading a public list of zip codes, so you need an internet connection. After that, it sorts in a few seconds.

### Step 5. Open your results

When it says **Done!**, two new files are in the **FTC-WA-EventAssignment** folder, with the date and time in their names:

| File | What's in it |
|---|---|
| `team_assignments_<date>_<time>.csv` | One row per team, with its event. This is the file for the Maps team. |
| `event_summary_<date>_<time>.csv` | One row per event, with how full it is. Empty and under-filled events are flagged. |

Open them in Excel. Earlier results are never overwritten, so you can compare runs.

### Step 6. Review the flagged teams

In the team assignments file, filter the **flagged_for_manual_review** column to `true`. The **flagged_reason** column tells you what to check for each team, like a long drive or a zip code with only a few teams.

If a team has no event, its reason starts with **unassigned**:

| The reason says | What to do |
|---|---|
| `zip code not found` | Check the team's zip code for a typo, or place the team in your pre-assignments file. |
| `no event with room` | Add seats in your events file, or place the team in your pre-assignments file. |
| `zip is in ID` (or another state) | The team is outside Washington and Oregon. Place it in your pre-assignments file. |

**To fix a placement,** add the team to your pre-assignments file, save it, and run the sorter again (Step 3).

---

## Sorting FTC or FRC instead of FLL

The sorter is set to FLL. To change it, open **Code/sorter.toml** in TextEdit (Mac) or Notepad (Windows). Near the top, change `program = "FLL"` to `"FTC"` or `"FRC"`, and save. Leave the rest of the file as it is.

## If something goes wrong

| You see | What to do |
|---|---|
| `This sorter needs Python 3.11 or newer` | Install the latest Python from python.org (one-time setup, step 1), then close and reopen the terminal. |
| `can't open file` or `No such file or directory` | The terminal isn't in the FTC-WA-EventAssignment folder. Redo Step 2. |
| `'python' is not recognized` (Windows) | Run the Python installer again, choose **Modify**, and check **Add Python to environment variables**. |
| `The Input Files folder needs at least two .csv files` | Put your teams and events files in Input Files, saved as CSV. |
| `invalid literal for int()` or `is_host_team is '...'` | One of your files has a header row. Delete the first line, save, and run it again. |
| `does not match this season's files` | Your pre-assignments file has a team number or event code that isn't in your teams or events file. Fix the ones it lists. |
| `Couldn't build the zip code table` | Check your internet connection and run it again. |

To stop the sorter at any point, press **q** (Mac) or **Ctrl + C**.

## Technical details

Drive times, review limits, the review map and how teams are placed are covered in [Code/TECHNICAL.md](Code/TECHNICAL.md).
