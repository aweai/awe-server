# Awe Agent Platform


## Getting Started

### Create the config file and adjust the config items

```bash
(venv) $ mv ./persisted_data/.env.example ./persisted_data/.env
```

### Create or upgrade the database

```bash
(venv) $ alembic upgrade head
```

More info on how to use the migration tool, [please read this doc](./migrations/README.md).

### Start the server

```bash
(venv) $ python run.py
```

### Start the workers

```bash
(venv) $ celery -A awe.awe_agent.worker worker --loglevel=INFO --queues=llm --pool=solo
(venv) $ celery -A awe.awe_agent.worker worker --loglevel=INFO --queues=sd --pool=solo
```

### Build and deploy the SOL contracts

```bash
$ cd contracts-sol
$ anchor build
$ anchor deploy
```

### Start the WebUI

```bash
$ cd webui

# Copy the newest IDL file from the contracts project
$ cp ../contracts-sol/target/ild/awe.json ./src/sol-client/

# Create the config file and adjust the config if needed
$ cp ./src/config.example.json ./src/config.json

$ yarn install
$ yarn dev
```
