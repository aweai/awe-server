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

### Start the AI task workers

```bash
(venv) $ celery -A awe.awe_agent.worker worker --loglevel=INFO --queues=llm --pool=solo
(venv) $ celery -A awe.awe_agent.worker worker --loglevel=INFO --queues=sd --pool=solo
```

### Start the remote signing machine

```bash
(venv) $ celery -A awe.blockchain.worker worker --loglevel=INFO --queues=tx_token_in,tx_token_out
```
