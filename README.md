#BayWatch Final Project Directory
- This folder containerizes the BayWatch api w/ Docker Compose, Redis, uv, and a worker. The Docker image has the code and dependencies needed to run the api and the worker, and the Redis container stores the NOAA water level data, the queued job ids, the saved job data, and the saved results outside of the api container. The api downloads the JSON data directly from the NOAA JSON links when a POST request w/ /data is ran. All water level readings can be accessed w/ the api routes, and jobs can also be created and updated, and results can be returned w/ the new jobs and results routes.
- This is important because we're combining what we learned about containerization, FastAPI, Redis, workers, queues, logging, testing, JSON data, matplotlib, and Kubernetes, and we're applying it to real-world coastal water level data.

#Build and Run the Containers
From inside the "finalProject/" directory:
docker compose up --build

##Data loading
- All the JSON data is loaded directly from the NOAA Tides and Currents site w/ a POST request is made to /data
- Key West data link:
https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=hourly_height&application=TideTrack&begin_date=20250101&end_date=20250107&datum=MLLW&station=8724580&time_zone=gmt&units=metric&format=json
- Lake Michigan / Holland data link:
https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?product=hourly_height&application=TideTrack&begin_date=20250101&end_date=20250107&datum=IGLD&station=9087031&time_zone=gmt&units=metric&format=json
- The data links are hardcoded into the api.py file, but these are the links I got them from.
- The data is stored in Redis using the reading_id as keys.
- The NOAA data is a coastal water level dataset. Each object is a water level reading and includes fields such as reading_id, station_id, station_name, timestamp, water_level, sigma, flags, datum, and units. For this project, the most important fields for the worker analysis are station_id, timestamp, and water_level, because the worker compares water level variation between Key West and Lake Michigan over the requested date range.
- The two stations used are Key West, Florida w/ station id 8724580 and Holland, Michigan w/ station id 9087031.

##FastAPI Routes
#After starting the containers, can open a second terminal and run the following curl commands to test

curl "localhost:8000/help"
curl -X POST "localhost:8000/data"
curl "localhost:8000/data"
curl -X DELETE "localhost:8000/data"
curl "localhost:8000/stations"
curl "localhost:8000/stations/8724580"
curl "localhost:8000/stations/9087031"
curl "localhost:8000/readings/8724580_2025-01-01_0000"
curl "localhost:8000/readings/9087031_2025-01-01_0000"
curl -X POST "localhost:8000/jobs" -H "Content-Type: application/json" -d '{"start_date":"2025-01-01", "end_date":"2025-01-07"}'
curl "localhost:8000/jobs"
curl "localhost:8000/jobs/<job_id>"
curl "localhost:8000/results/<job_id>"

##Can replace example station_id, 8724580 or 9087031, with any specific station id that was loaded
##Can replace example reading_id, 8724580_2025-01-01_0000, with any specific reading_id from the data
##Replace <job_id> with any actual job_id from curl "localhost:8000/jobs"

##Instructions for posting a job to /jobs
- The /jobs route takes JSON data w/ a start_date and end_date which is the range to check
Example:
curl -X POST "localhost:8000/jobs" -H "Content-Type: application/json" -d '{"start_date":"2025-01-01", "end_date":"2025-01-07"}'
- This creates a job to analyze all water level readings whose dates are between 2025-01-01 and 2025-01-07 inclusive, and we will compare water level variation between Key West and Lake Michigan.
- The dates must be in YYYY-MM-DD format.
- The start_date must be less than or equal to the end_date.

##Instructions for getting and interpreting results from /results/<job_id>
- After creating a job, we use the returned job_id to check the result
Example:
curl "localhost:8000/results/<job_id>"
- If complete, the route returns a result object with:
- job_id
- start_date
- end_date
- total number of water level readings found in that date range
- average water level for Key West
- average water level for Lake Michigan
- max water level for Key West
- max water level for Lake Michigan
- min water level for Key West
- min water level for Lake Michigan
- plot_file for the saved matplotlib plot

##Important note about the plot
- The plot compares water level change from each station's average instead of raw water level.
- This is because Key West and Lake Michigan use different datum references, so the raw water levels are on very different vertical scales.
- Plotting change from average makes it easier to compare the variability between the two stations.
- The worker saves the plot as a png file in the plots folder.

#Example jobs commands and expected outputs
#Creating
curl -X POST "localhost:8000/jobs" -H "Content-Type: application/json" -d '{"start_date":"2025-01-01", "end_date":"2025-01-07"}'
#Output
{"job_id":"37fe59ab-bba1-408f-9abd-1855e3c0d627","status":"queued","start_date":"2025-01-01","end_date":"2025-01-07"}

#Checking job status
curl "localhost:8000/jobs/37fe59ab-bba1-408f-9abd-1855e3c0d627"
#Output
{"job_id":"37fe59ab-bba1-408f-9abd-1855e3c0d627","status":"complete","start_date":"2025-01-01","end_date":"2025-01-07"}

#Getting result
curl "localhost:8000/results/37fe59ab-bba1-408f-9abd-1855e3c0d627" | python -m json.tool
#Output
{
    "job_id": "37fe59ab-bba1-408f-9abd-1855e3c0d627",
    "start_date": "2025-01-01",
    "end_date": "2025-01-07",
    "total_readings_found": 336,
    "key_west_average": 0.319,
    "lake_michigan_average": 176.238,
    "key_west_max": 0.769,
    "lake_michigan_max": 176.354,
    "key_west_min": -0.023,
    "lake_michigan_min": 176.118,
    "plot_file": "/plots/baywatch_plot_37fe59ab-bba1-408f-9abd-1855e3c0d627.png"
}

#invalid job example
curl -X POST "localhost:8000/jobs" -H "Content-Type: application/json" -d '{"start_date":"2025-01-07", "end_date":"2025-01-01"}'
Output: {"detail":"start_date must be less than or equal to end_date"}

#invalid date format example
curl -X POST "localhost:8000/jobs" -H "Content-Type: application/json" -d '{"start_date":"01-01-2025", "end_date":"2025-01-07"}'
Output: {"detail":"Dates must be in YYYY-MM-DD format"}

#Checking plot file
ls -lh plots/
#Output
baywatch_plot_<job_id>.png

#Testing
#After starting the containers, can open a second terminal and run the tests
#Searached ip how to run the uv inside the baywatch api, will run all 3 tests here
docker compose exec baywatch-api uv run -- pytest test_api.py test_jobs.py test_worker.py

#The tests include:
- Integration tests for the FastAPI routes using requests
- Unit tests for the jobs helper logic
- Unit tests for the worker helper functions
- Tests for valid and invalid job creation
- Tests for water level summary calculations

##Files in This Directory
- src/api.py
This is the main python script w/ the routes and helper functions to load, store, delete, and find specific NOAA water level data from Redis. It also has the /help route, /stations routes, /readings route, /jobs routes, and /results route.

- docker-compose.yaml
This file defines the api container, Redis container, and worker container so they can run together and communicate through Docker Compose. It also includes the environment variables for REDIS_IP and LOG_LEVEL. For local testing, the api and worker use host networking so that the containers can reach NOAA from the VM.

- src/worker.py
This file is the worker script to watch for new job ids in the queue. When a job is found, it updates it to in_progress, pulls the water level data for the requested date range, calculates summary values for both stations, creates a matplotlib plot, saves the result, and then updates the job status to complete.

- src/jobs.py
This file has the shared jobs logic to set up the redis, queue, job statuses, result model, and helper functions to find and update jobs.

- test/test_api.py
This file has some integration tests for the FastAPI routes using requests.

- test/test_jobs.py
This file has some unit tests for the jobs helper logic.

- test/test_worker.py
This file has some unit tests for the worker helper functions.

- Dockerfile
Builds the Python image, installs uv and dependencies, and copies the api.py, jobs.py, worker.py, and test scripts.

- Project_Pitch_AravPatel_COE332.pdf
This is the final project pitch with the updates to the baseModel and the second station

- data/.gitcanary
This keeps the data folder in Git. The Redis dump.rdb file can appear here after running the containers, but it should not be committed.

- plots/.gitcanary
This keeps the plots folder in Git. The worker saves matplotlib png plots in this folder when jobs complete.

- baywatch_diagram.png
This is the software diagram image for the BayWatch final project.

- kubernetes/test
This folder has the Kubernetes yaml files for the test deployment.

- kubernetes/prod
This folder has the Kubernetes yaml files for the prod deployment.

- requirements.txt
Has the list of Python packages needed for this repo.

- Makefile
Has the basic and necessary dev commands.

##Kubernetes Deployment
- The final version of this project is also deployed on the class Kubernetes cluster.
- The kubernetes/test folder is used for the test version of the app.
- The kubernetes/prod folder is used for the prod version of the app.
- The Kubernetes deployment includes a Redis deployment, FastAPI deployment, worker deployment, Redis service, FastAPI service, NodePort service, Ingress, and PVC for Redis persistence.
- The Redis PVC is used so Redis can save data across pod restarts.
- The worker deployment runs separately from the FastAPI deployment, so jobs can be handled asynchronously.

#Example Kubernetes commands
kubectl apply -f kubernetes/test/
kubectl get pods
kubectl get services
kubectl get pvc
kubectl get ingress

##API endpoints
- The test deployment can be found at:
http://aravp06-baywatch-prod.coe332.tacc.cloud
- The prod deployment can be found at:
http://aravp06-baywatch-test.coe332.tacc.cloud

Example:
curl "http://aravp06-baywatch-prod.coe332.tacc.cloud/help"
curl -X POST "http://aravp06-baywatch-prod.coe332.tacc.cloud/data"
curl "http://aravp06-baywatch-prod.coe332.tacc.cloud/stations"

#After testing, prod can be applied w/
kubectl apply -f kubernetes/prod/

##Redis Persistent Storage
- Redis uses PVC to store data even when pods restart.
- To test this, I loaded the data with POST /data, deleted the Redis pod, waited for Kubernetes to recreate it, and then checked /stations again, which did work after the Kubernetes fix.

Example:
kubectl get pods
kubectl delete pod <redis-pod-name>
kubectl get pods
curl "http://aravp06-baywatch-prod.coe332.tacc.cloud/stations"

#Note
- pyproject.toml and uv.lock are stored in my main branch
- The Dockerfile copies pyproject.toml and uv.lock from the main repo root
- The data is pulled from NOAA when /data is posted, so the full dataset is not stored directly in this repo
- The current default date range is 2025-01-01 to 2025-01-07
- The local Docker Compose setup uses network_mode: host because the NOAA API timed out from the normal Docker bridge network on the VM