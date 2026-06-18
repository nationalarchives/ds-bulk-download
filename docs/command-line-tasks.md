# Command line tasks

## Process a batch

The process script can be found in `tasks/process.py`.

```sh
poetry run python tasks/process.py <batch> <packager> <options>
```

### Batches

- `merlin` - all files in the series `ES 38`

### Packagers

- `last_year` - create a ZIP of all files from the previous year and remove any monthly ZIPs from that year
- `last_month` - create a ZIP of all files from the previous month and remove any weekly ZIPs from that month
- `this_week` - create a ZIP of all files from this week, replacing any existing bundles for this week
- `all` - create a ZIP of all files
- `chunked` - create multiple ZIPs, chunked into a set size which can be set by passing a number into the `<options>` parameter of the command

## Merlin

- Run `last_year` at 01:00 on the first day of the year (cron `0 1 1 1 *`)
- Run `last_month` at 02:00 on the first day of the month (cron `0 2 1 * *`)
- Run `this_week` at 03:00 every day (cron `0 3 * * *`)
