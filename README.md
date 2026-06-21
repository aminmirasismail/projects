# projects

This repo holds all of my personal projects. See below for setup and basic usage instructions.
## Setup

### 1. Install uv

uv manages the Python version and virtual environment for this project.

- Windows (winget): `winget install --id astral-sh.uv -e`
- Or follow the install instructions at https://docs.astral.sh/uv/getting-started/installation/

### 2. Clone the repo

```sh
git clone https://github.com/aminmirasismail/projects.git
cd projects
```

### 3. Create the virtual environment

This project targets Python 3.12. uv will download it automatically if it isn't already installed.

```sh
uv venv --python 3.12
```

### 4. Install the project

```sh
uv pip install -e .
```

### 5. Activate the venv (optional)

```sh
# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

Or just prefix commands with `uv run`, e.g. `uv run python -c "import projects"`.
