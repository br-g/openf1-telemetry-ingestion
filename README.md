# openf1 telemetry ingestor

docker build --no-cache -t my-app .
docker run -it \
 -e MONGO_CONNECTION_STRING \
 -e PUSHOVER_USER_KEY \
 -e PUSHOVER_API_TOKEN \
 -e OPENF1_DB_NAME \
 -e OPENF1_CLIENT_ID \
 -e OPENF1_CLIENT_SECRET \
 my-app bash
python main.py

## Ingestion schedule

The Scaleway Serverless Job runs at the start of every hour (UTC). Each run
fetches the schedule using `openf1.util.openf1_client.get` and reingests every
non-cancelled session for which `date_end <= now <= date_end + 6 hours`.
Outside these inclusive windows it exits without ingesting or sending a success
notification. Sessions whose data is not available yet are retried on the next
hourly run while their window remains open.

Only `pit` is reingested. Edit the `REINGEST_COLLECTIONS` list in `main.py`
(for example `["pit", "car_data"]`) to change this.

## Scaleway deployment

The workflow `.github/workflows/deploy-job-scaleway.yml` replaces Cloud Run
and follows the `openf1-ingestor` deployment: region `fr-par`, registry
`rg.fr-par.scw.cloud/namespace-funny-visvesvaraya`, immutable commit image tags.
Pushes to `main` update the job image and set its schedule to `0 * * * *` in UTC.

Before the first deployment:

1. Configure GitHub Actions secrets `SCW_ACCESS_KEY`, `SCW_SECRET_KEY`,
   `SCW_DEFAULT_PROJECT_ID`, and `SCW_DEFAULT_ORGANIZATION_ID` as in `openf1-ingestor`.
2. Create a Scaleway Serverless Job named `telemetry-ingestion` in `fr-par`,
   using the image `rg.fr-par.scw.cloud/namespace-funny-visvesvaraya/telemetry_ingestion:latest`
   after the workflow's first image push. Configure suitable resources and timeout.
   The workflow deliberately fails if the job is missing, so it can be rerun once
   the job is configured.
3. Configure the job's runtime environment: `MONGO_CONNECTION_STRING`,
   `OPENF1_DB_NAME`, `OPENF1_CLIENT_ID`, `OPENF1_CLIENT_SECRET`,
   `PUSHOVER_USER_KEY`, and `PUSHOVER_API_TOKEN`. The workflow preserves these.
4. Disable the old Cloud Scheduler trigger and Cloud Run job when switching to
   Scaleway to avoid duplicate executions. Removing the workflow does not remove
   those existing Google Cloud resources.

Run the isolated scheduling tests with `python3 -m unittest discover -s tests`.

The job loads `F1_TOKEN` from MongoDB immediately before ingestion, using the
`_f1_tokens` collection and `_key: "current_token"` record maintained by
`openf1-ingestor`. Use the same `MONGO_CONNECTION_STRING` and `OPENF1_DB_NAME`
as that project, with read access to `_f1_tokens`. No static `F1_TOKEN` deployment
variable is needed. Missing or invalid tokens fail the run; this job does not
refresh tokens. Runs outside the ingestion window do not read the token.
