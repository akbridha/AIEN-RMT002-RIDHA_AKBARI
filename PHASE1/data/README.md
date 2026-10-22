# Data lake handoff

The raw snapshot is distributed through Google Drive rather than committed to
GitHub. Download the complete folder from:

```text
GOOGLE_DRIVE_DATA_FOLDER_URL
```

Place the downloaded source files under `data/raw/`. The local pipeline reads
JSON and CSV files in the `operational/`, `events/`, `inventory/`, and
`reference/` directories described in the project README. A `manifest.json`,
if present, is ignored; completeness is checked by validating and counting the
source files directly.

Raw data is ignored by Git so that a local download cannot be committed by
accident.
