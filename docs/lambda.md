# Using in an AWS Lambda function

## Create the Lambda ZIP

There are two ways to create the Lambda:

```sh
# 1. Run the creation script directly
./tasks/create_lambda.sh

# 2. Build the Lambda in Docker
docker compose up -d create-lambda
```

Both methods should result in a `lambda/bulk_downloads_processor.zip` file being created.

## Running the Lambda

### Environment variables

See the [README.md](https://github.com/nationalarchives/ds-bulk-download/blob/main/README.md#environment-variables) for more details.

- `S3_EXPORT_BUCKET`

Per-batch environment variables:

- Merlin
  - `S3_SOURCE_BUCKET_MERLIN`
  - `S3_SOURCE_PREFIX_MERLIN` (optional)
  - `S3_EXPORT_PREFIX_MERLIN` (optional)

### Event payload

- `Batch` - the preset name of the project to package, e.g. `merlin`
- `Packager` - the type of packager you want to run, e.g. `all`, `chunked`, `last_month`...

Run `poetry run python tasks/process.py help` or check [process a batch using command line tasks](./command-line-tasks.md#process-a-batch) for more details on the `Batch` and `Packager` options available.
