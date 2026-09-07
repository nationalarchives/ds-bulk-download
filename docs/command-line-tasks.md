# Command line tasks

## Process a batch

The process script can be found in `tasks/process.py`.

```sh
poetry run python tasks/process.py <batch> <packager> <options>
```

### Batches

A batch is the group of records you want to package up. These are preset values.

- `merlin` - all files in the series `ES 38`

### Packagers

A packager defines how the records are grouped.

#### Date-based

##### First-time

- `all_year_month_week` - create all the year, month and week ZIPs from `all_previous_years`, `all_months_this_year` and `all_weeks_this_month`

##### Regular

- `this_week` - create a ZIP of all files from this week, replacing any existing bundles for this week
  Run at 03:00 every day (cron `0 3 * * *`)
- `last_month` - create a ZIP of all files from the previous month and remove any weekly ZIPs from that month
  Run at 02:00 on the first day of the month (cron `0 2 1 * *`)
- `last_year` - create a ZIP of all files from the previous year and remove any monthly ZIPs from that year
  Run at 01:00 on the first day of the year (cron `0 1 1 1 *`)

##### One-off for fixes and updates

- `all_weeks_this_month` - create multiple ZIPs, for every week this month
- `this_month` - create a ZIP of all files from this month, replacing all weekly files for the month
- `month` - create a ZIP of all files from a specific month, passed into the `<options>` parameter of the command in `YYYY-MM` format (e.g. `2026-03`), replacing any existing ZIP for that month and removing any weekly ZIPs within that month
- `all_months_this_year` - create multiple ZIPs, for every month this year excluding the current month
- `this_year` - create a ZIP of all files from this year, replacing all weekly and monthly files for the year
- `year` - create a ZIP of all files from a specific year, passed into the `<options>` parameter of the command in `YYYY` format (e.g. `2025`), replacing any existing ZIP for that year and removing any monthly ZIPs within that year
- `all_months_in_year` - create multiple ZIPs, one for each month with files in a specific year, passed into the `<options>` parameter of the command in `YYYY` format (e.g. `2025`)
- `all_previous_years` - create multiple ZIPs, for every year prior to the current year

#### Other packagers

- `all` - create a ZIP of all files
- `chunked` - create multiple ZIPs, chunked into a set size which can be set by passing a number into the `<options>` parameter of the command
- `sized` - create multiple ZIPs, chunked into a target file size which can be set by passing a number into the `<options>` parameter of the command (the file size of the chunk in bytes before writing to a ZIP file)
