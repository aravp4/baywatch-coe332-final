NAME ?= baywatch

all: build run

build:
	docker compose build
run:
	docker compose up
down:
	docker compose down
test:
	docker compose exec baywatch-api uv run -- pytest
ps-me:
	docker ps -a | grep ${NAME}
im-me:
	docker images | grep ${NAME}