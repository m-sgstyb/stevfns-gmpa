# Installation
---

This project uses `uv` with `pyproject.toml` as the source of truth for dependencies. 

There are two main setup paths depending on type of user:
- Model users only need the runtime environment to run the model
- Collaborators/ developers also need the development tools used for linting, formatting and checks.

## Pre-requisites
Before installing the project, make sure you have:
- Python installed 
- `uv` installed. For detailed documentation on `uv`, see [Astral's uv documentation](https://docs.astral.sh/uv/) 
- Git installed. For detailed documentation on git, see [git's installation page](https://git-scm.com/install/)


If you are cloning the repository for development, also make sure you have access to the repository and can run commands from a terminal.

## Clone the repository
Through your terminal, navigate to the directory you want the repository to be saved and run
```
git clone https://github.com/m-sgstyb/stevfns-gmpa
```

Navigate to the repository root through
```
cd stevfns-gmpa
```

### For model users
From the repository root, model users can run
```
uv sync --no-dev
```
This will create or update the local virtual environment and install project dependencies defined in `pyproject.toml`.

- `uv sync` installs dependencies and keeps the environment aligned with the lockfile  
- `uv run` ensures the environment is up to date before executing commands  
- `--no-dev` excludes development dependencies

### For collaborators / developers
Collaborators should install the full development environment, including linting and formatting tools.

The project includes a development dependency group for tools such as Ruff and pre-commit. Once that is defined, run:
```
uv sync
```

The development tools will be available in the same environment, so you can run:
```
uv run ruff check .
uv run ruff format .
uv run pre-commit run --all-files
```

### Enable pre-commit hooks

To automatically run checks before each commit, install the pre-commit hook:
```
uv run pre-commit install
```

# Recommended workflow

## After installing:

Activate the environment implicitly through `uv run`, or explicitly if you prefer working inside the virtual environment.
Run the example model or main entry point.
For development work, run Ruff and pre-commit before committing changes.

!!! info 
	The full collaboration set up will be tied with a pre-commit hook, more detailed instructions on this workflow will be developed as the migration advances

## Notes
`pyproject.toml` is the main dependency file for this project.
The virtual environment is created locally in the repository as `.venv`.
If the environment ever gets out of sync, rerun `uv sync`.

### Troubleshooting

If a command cannot find installed packages, make sure you are running it through `uv run` or inside the project environment.

For example, to run a python script with the installed python through pyproject.toml the CLI command is `uv run python script.py`

If you have an old environment from a previous setup, you may need to delete .venv and run `uv sync` again.

### Development tools

This project uses:
- Ruff for linting and formatting (for more details, [https://docs.astral.sh/ruff/](https://docs.astral.sh/ruff/))
- pre-commit for automated checks (for more details, [https://pre-commit.com/](https://pre-commit.com/))



