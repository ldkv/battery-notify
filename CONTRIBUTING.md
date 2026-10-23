# Contributing Guidelines

## Table of Contents

- [Development environment](#development-environment)

## Development environment

### Environment variables

Take a look at [.env.default](./.env.default) and generate your own `.env` file with your secrets or customized values.

### Taskfile

A [Taskfile](./Taskfile.yml) is provided to simplify working in development environment.

More details can be found inside the file, or with the command:

```bash
task --help
```

### Dependencies management with `uv`

The project uses [uv](https://docs.astral.sh/uv/) for dependencies management.

A task command is provided to execute `uv` with custom `.env` variables:

```bash
task uv -- <uv_command>
# example
task uv -- tree --outdated
```

For more information about dependencies management with `uv`, please refer to the [official documentation](https://docs.astral.sh/uv/concepts/dependencies/).

### Initial setup

- Run the following command **ONCE** to install `uv` and initialize the virtual environment:

```bash
task dev-install
```

By default, the virtual environment is created in the `.venv` directory. It is possible to change the directory by setting the `UV_PROJECT_ENVIRONMENT` variable in your own [`.env` file](#environment-variables).

```
UV_PROJECT_ENVIRONMENT=/absolute/path/to/your/venv
```

### Testing

A convinent command is provided to run the tests locally:

```bash
task test
```

### Code style

The codebase is formatted and linted using `ruff`.

To verify the code style:

```bash
task lint
```

To automatically fix the code style and formatting:

```bash
task lint-fix
```
