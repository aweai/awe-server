# Database migrations

# Upgrade

```shell
$ alembic upgrade head
```

# Update the models

1. Update the model object files

If new models are created inside `awe/models`, it must be imported in `awe/models/__init__.py` to be recognized by Alembic.

2. Generate the migration files automatically using
```shell
$ alembic revision --autogenerate -m "description"
```
Alembic will compare the model files with current database to generate the incremental parts and write them to versions folder.
Current database will not be changed.

1. Run the migration on the target env

```shell
$ alembic upgrade head
```
Alembic will execute the migration scripts to upgrade current database.
