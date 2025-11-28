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
