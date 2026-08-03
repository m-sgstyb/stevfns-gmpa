# Quick Start

Once the repository has been installed locally with [Installation](installation.md), and running `uv sync` to set up the virtual environment, create your own local branch for testing. For example, with branch name "my-test"

```
git checkout -b my-test
```

After that, you can run the model for a basic example that includes data using:
```
uv run python run_cases.py --name test-collab
```

